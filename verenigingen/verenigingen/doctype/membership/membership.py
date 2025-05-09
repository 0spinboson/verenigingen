import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today, date_diff, add_to_date, nowdate, flt

class Membership(Document):
    def validate(self):
        self.validate_dates()
        self.validate_membership_type()
        self.set_membership_details()
        self.set_status()
        
    def validate_dates(self):
        # Ensure start date is before renewal date
        if self.renewal_date and getdate(self.start_date) > getdate(self.renewal_date):
            frappe.throw(_("Start Date cannot be after Renewal Date"))
            
        # If no renewal date is set, calculate it based on membership type
        if not self.renewal_date and self.membership_type:
            membership_type = frappe.get_doc("Membership Type", self.membership_type)
            
            if membership_type.subscription_period != "Lifetime":
                # Set renewal date based on subscription period
                months = self.get_months_from_period(membership_type.subscription_period, 
                                                    membership_type.subscription_period_in_months)
                
                if months:
                    self.renewal_date = add_to_date(self.start_date, months=months)
    
    def get_months_from_period(self, period, custom_months=None):
        period_months = {
            "Monthly": 1,
            "Quarterly": 3,
            "Biannual": 6,
            "Annual": 12,
            "Lifetime": 0,
            "Custom": custom_months or 0
        }
        
        return period_months.get(period, 0)
                
    def validate_membership_type(self):
        # Check if membership type exists and is active
        if self.membership_type:
            membership_type = frappe.get_doc("Membership Type", self.membership_type)
            
            if not membership_type.is_active:
                frappe.throw(_("Membership Type {0} is inactive").format(self.membership_type))
    
    def set_membership_details(self):
        """Set membership details from membership type"""
        if self.membership_type:
            membership_type = frappe.get_doc("Membership Type", self.membership_type)
            
            # Set payment details
            self.payment_amount = membership_type.amount
            self.currency = membership_type.currency
            self.membership_period = membership_type.subscription_period
            self.payment_frequency = membership_type.subscription_period
            
            # Set subscription plan if linked
            if membership_type.subscription_plan:
                self.subscription_plan = membership_type.subscription_plan
            
            # Set auto_renew based on membership type settings
            if membership_type.allow_auto_renewal:
                self.auto_renew = membership_type.allow_auto_renewal
                
    def set_status(self):
        """Set the status based on dates, payment status, and cancellation"""
        if self.docstatus == 0:
            self.status = "Draft"
        elif self.docstatus == 2:
            self.status = "Cancelled"
        elif self.cancellation_date and getdate(self.cancellation_date) <= getdate(today()):
            # Membership is cancelled
            self.status = "Cancelled"
        elif self.payment_status == "Overdue":
            # Payment is overdue - membership inactive
            self.status = "Inactive"
        elif self.renewal_date and getdate(self.renewal_date) < getdate(today()):
            # Past renewal date - membership expired
            self.status = "Expired"
        elif self.payment_status == "Unpaid" and getdate(self.start_date) <= getdate(today()):
            # Started but unpaid - pending
            self.status = "Pending"
        else:
            # All good - active membership
            self.status = "Active"
                
    def on_submit(self):
        # Update member's current membership
        self.update_member_status()
        
        # Ensure proper dates and status at submission
        if not self.payment_status:
            self.payment_status = "Unpaid"
            
        # Make sure next_payment_date is set
        if not self.next_payment_date:
            self.next_payment_date = self.start_date
            
        # Set cancellation date to null if not set
        self.cancellation_date = None
        self.cancellation_reason = None
        self.cancellation_type = None

        # Update status properly
        self.set_status()
        
        # Force update to database
        self.db_set('status', self.status)
        self.db_set('payment_status', self.payment_status)
        self.db_set('next_payment_date', self.next_payment_date)
        self.db_set('cancellation_date', None)
        self.db_set('cancellation_reason', None)
        self.db_set('cancellation_type', None)
    
        # Update member's current membership
        self.update_member_status()

        # Link to subscription if configured
        if not self.subscription and self.subscription_plan:
            self.create_subscription_from_membership()
            
            # Sync next payment date from subscription
            self.sync_payment_details_from_subscription()
    
    def on_cancel(self):
        """Handle when membership is cancelled directly (not the same as member cancellation)"""
        self.status = "Cancelled"
        self.cancellation_date = self.cancellation_date or nowdate()
        
        # Update member status
        self.update_member_status()
        
        # Cancel linked subscription
        if self.subscription:
            try:
                subscription = frappe.get_doc("Subscription", self.subscription)
                if subscription.status != "Cancelled":
                    # Set cancelation date
                    subscription.db_set('cancelation_date', getdate(self.cancellation_date))
                
                    # Use db_set to directly update database and bypass validation
                    subscription.flags.ignore_permissions = True
                
                    # Now cancel the subscription
                    try:
                        subscription.cancel_subscription()
                    except Exception as e:
                        # Directly set status to cancelled as a fallback
                        subscription.db_set('status', 'Cancelled')
                        frappe.db.commit()
                        frappe.msgprint(_("Subscription {0} has been cancelled").format(subscription.name))
            except Exception as e:
                error_msg = str(e)
                frappe.log_error(f"Error cancelling subscription {self.subscription}: {error_msg}", 
                            "Membership Cancellation Error")
                frappe.msgprint(_("Error cancelling subscription: {0}").format(error_msg))
    
    def update_member_status(self):
        """Update the membership status in the Member document"""
        if self.member:
            member = frappe.get_doc("Member", self.member)
            member.save()  # This will trigger the update_membership_status method
    
    def sync_payment_details_from_subscription(self):
        """Sync payment details from linked subscription"""
        if not self.subscription:
            return
            
        subscription = frappe.get_doc("Subscription", self.subscription)
        
        # Update next payment date
        if subscription.next_billing_date:
            self.next_payment_date = subscription.next_billing_date
            self.db_set('next_payment_date', subscription.next_billing_date)
        
        # Get invoices linked to this subscription
        invoices = frappe.get_all(
            "Subscription Invoice",
            filters={"subscription": subscription.name},
            fields=["invoice", "status", "creation"],
            order_by="creation desc"
        )
        
        if invoices:
            # Get the latest invoice
            latest_invoice = frappe.get_doc("Sales Invoice", invoices[0].invoice)
            
            # Update payment status
            if latest_invoice.status == "Paid":
                self.payment_status = "Paid"
                self.last_payment_date = latest_invoice.posting_date
                self.db_set('payment_status', "Paid")
                self.db_set('last_payment_date', latest_invoice.posting_date)
            elif latest_invoice.status == "Overdue":
                self.payment_status = "Overdue"
                self.db_set('payment_status', "Overdue")
            elif latest_invoice.status == "Return":
                self.payment_status = "Refunded"
                self.db_set('payment_status', "Refunded")
            else:
                self.payment_status = "Unpaid"
                self.db_set('payment_status', "Unpaid")
        
        # Update status based on changes
        self.set_status()
        self.db_set('status', self.status)

    def renew_membership(self):
        """Create a new membership as a renewal of the current one"""
        # Calculate new dates
        new_start_date = self.renewal_date or today()
        
        # Get duration from membership type
        membership_type = frappe.get_doc("Membership Type", self.membership_type)
        months = self.get_months_from_period(membership_type.subscription_period, 
                                          membership_type.subscription_period_in_months)
        
        new_renewal_date = None
        if months:
            new_renewal_date = add_to_date(new_start_date, months=months)
            
        # Create new membership
        new_membership = frappe.new_doc("Membership")
        new_membership.member = self.member
        new_membership.membership_type = self.membership_type
        new_membership.start_date = new_start_date
        new_membership.renewal_date = new_renewal_date
        new_membership.auto_renew = self.auto_renew
        new_membership.payment_amount = self.payment_amount
        new_membership.payment_frequency = self.payment_frequency
        new_membership.currency = self.currency
        new_membership.subscription_plan = self.subscription_plan
        new_membership.payment_method = self.payment_method
        
        # Save as draft
        new_membership.insert(ignore_permissions=True)
        
        frappe.msgprint(_("Renewal Membership {0} created").format(new_membership.name))
        return new_membership.name

    def create_subscription_from_membership(self, options=None):
        """Create an ERPNext subscription for this membership with additional options"""
        import frappe
        from frappe import _
        from frappe.utils import getdate, add_days, add_months
        import json
        
        # Initialize options with defaults if none provided
        if not options:
            options = {}
        
        # Check if member has a customer
        member = frappe.get_doc("Member", self.member)
        
        if not member.customer:
            # Create a customer for this member
            member.create_customer()
            member.reload()
        
        if not member.customer:
            frappe.throw(_("Please create a customer for this member first"))
        
        try:
            # Get subscription plan details
            if not self.subscription_plan:
                frappe.throw(_("Subscription Plan is required to create a subscription"))
            
            # Create subscription with minimal required fields
            subscription = frappe.new_doc("Subscription")
            
            # Set basic subscription properties
            subscription.party_type = "Customer"
            subscription.party = member.customer
            subscription.start_date = getdate(self.start_date)
            
            # Set the renewal date if defined in membership
            if self.renewal_date:
                subscription.end_date = getdate(self.renewal_date)
            
            # Determine billing interval based on membership period
            interval_map = {
                "Monthly": "Month",
                "Quarterly": "Quarter",
                "Biannual": "Half-Year",
                "Annual": "Year",
                "Lifetime": "Year",
                "Custom": "Month"
            }
            
            billing_interval = interval_map.get(self.membership_period, "Month")
            billing_interval_count = 1
            
            # Set billing details
            subscription.billing_interval = billing_interval
            subscription.billing_interval_count = billing_interval_count
            
            # Set next billing date
            subscription.next_billing_date = add_months(getdate(self.start_date), 1)
            
            # Explicitly add requested options
            subscription.follow_calendar_months = 1 if options.get('follow_calendar_months') else 0
            subscription.generate_invoice_at_period_start = 1 if options.get('generate_invoice_at_period_start') else 0
            subscription.generate_new_invoices_past_due_date = 1 if options.get('generate_new_invoices_past_due_date') else 0
            subscription.submit_invoice = 1 if options.get('submit_invoice') else 0
            
            if options.get('days_until_due'):
                subscription.days_until_due = options.get('days_until_due')
            
            # Add the subscription plan
            subscription.append("plans", {
                "subscription_plan": self.subscription_plan,
                "qty": 1
            })
            
            # Insert and submit
            subscription.flags.ignore_mandatory = True
            subscription.insert(ignore_permissions=True)
            subscription.submit()
            
            # Link subscription to membership
            self.subscription = subscription.name
            self.db_set('subscription', subscription.name)
            
            # Sync next payment date
            self.next_payment_date = subscription.next_billing_date
            self.db_set('next_payment_date', subscription.next_billing_date)
            
            frappe.msgprint(_("Subscription {0} created successfully").format(subscription.name))
            return subscription.name
            
        except Exception as e:
            error_details = f"Error details: Subscription Plan: {self.subscription_plan}"
            frappe.log_error(f"Error creating subscription: {str(e)}\n{error_details}", 
                          "Membership Subscription Error")
            raise

@frappe.whitelist()
def get_subscription_query(doctype, txt, searchfield, start, page_len, filters):
    """Filter subscriptions to only show ones related to the current member"""
    member = filters.get('member')
    
    if not member:
        # If called from the form, try to get member from doc
        if filters.get('doctype') == 'Membership' and filters.get('name'):
            member_doc = frappe.get_doc('Membership', filters.get('name'))
            member = member_doc.member
            
    if not member:
        return []
        
    # Get customer linked to this member
    customer = frappe.db.get_value('Member', member, 'customer')
    
    if not customer:
        return []
        
    return frappe.db.sql("""
        SELECT name, billing_status
        FROM `tabSubscription`
        WHERE party_type = 'Customer' 
        AND party = %s
        AND name LIKE %s
        ORDER BY creation DESC
    """, (customer, "%" + txt + "%"))

@frappe.whitelist()
def cancel_membership(membership_name, cancellation_date=None, cancellation_reason=None, cancellation_type="Immediate"):
    """
    Cancel a membership with the given details
    - cancellation_date: Date when the cancellation was requested
    - cancellation_reason: Reason for cancellation
    - cancellation_type: "Immediate" or "End of Period"
    """
    if not cancellation_date:
        cancellation_date = nowdate()
        
    membership = frappe.get_doc("Membership", membership_name)
    
    # Set cancellation details
    membership.cancellation_date = cancellation_date
    membership.cancellation_reason = cancellation_reason
    membership.cancellation_type = cancellation_type
    
    # Immediate cancellation updates status right away
    if cancellation_type == "Immediate":
        membership.status = "Cancelled"
    
    # For end of period, status remains active until renewal date
    membership.flags.ignore_validate_update_after_submit = True
    membership.save()
    
    # If immediate cancellation, also cancel the subscription
    if cancellation_type == "Immediate" and membership.subscription:
        subscription = frappe.get_doc("Subscription", membership.subscription)
        if subscription.status != "Cancelled":
            subscription.cancelation_date = cancellation_date
            try:
                subscription.cancel_subscription()
            except Exception as e:
                # Fallback to direct update
                subscription.db_set('status', 'Cancelled')
                frappe.db.commit()
    
    frappe.msgprint(_("Membership {0} has been cancelled").format(membership.name))
    return membership.name

@frappe.whitelist()
def sync_membership_payments(membership_name=None):
    """
    Sync payment details for a membership or all active memberships
    """
    if membership_name:
        # Sync a single membership
        membership = frappe.get_doc("Membership", membership_name)
        if membership.subscription:
            membership.sync_payment_details_from_subscription()
            return True
    else:
        # Sync all active memberships
        memberships = frappe.get_all(
            "Membership",
            filters={
                "status": ["in", ["Active", "Pending", "Inactive"]],
                "subscription": ["is", "set"]
            },
            fields=["name"]
        )
        
        count = 0
        for m in memberships:
            try:
                membership = frappe.get_doc("Membership", m.name)
                membership.sync_payment_details_from_subscription()
                count += 1
            except Exception as e:
                frappe.log_error(f"Error syncing membership {m.name}: {str(e)}", 
                              "Membership Payment Sync Error")
        
        return count

@frappe.whitelist()
def show_payment_history(membership_name):
    """
    Get payment history for a membership from linked subscription
    """
    membership = frappe.get_doc("Membership", membership_name)
    
    if not membership.subscription:
        return []
        
    # Get invoices from subscription
    invoices = frappe.get_all(
        "Subscription Invoice",
        filters={"subscription": membership.subscription},
        fields=["invoice", "status", "creation"],
        order_by="creation desc"
    )
    
    payment_history = []
    
    for invoice_info in invoices:
        invoice = frappe.get_doc("Sales Invoice", invoice_info.invoice)
        
        # Get linked payments
        payments = frappe.get_all(
            "Payment Entry Reference",
            filters={"reference_name": invoice.name},
            fields=["parent"]
        )
        
        payment_entries = []
        for payment in payments:
            payment_doc = frappe.get_doc("Payment Entry", payment.parent)
            payment_entries.append({
                "payment_entry": payment_doc.name,
                "amount": payment_doc.paid_amount,
                "date": payment_doc.posting_date,
                "mode": payment_doc.mode_of_payment,
                "status": payment_doc.status
            })
        
        payment_history.append({
            "invoice": invoice.name,
            "date": invoice.posting_date,
            "amount": invoice.grand_total,
            "status": invoice.status,
            "payments": payment_entries
        })
    
    return payment_history

@frappe.whitelist()
def renew_membership(membership_name):
    """Renew a membership and return the new membership doc"""
    membership = frappe.get_doc("Membership", membership_name)
    return membership.renew_membership()

@frappe.whitelist()
def create_subscription(membership_name, options=None):
    """Create a subscription for a membership with the specified options"""
    import frappe
    from frappe import _
    from frappe.utils import getdate
    
    try:
        # Parse options if provided as string
        if options and isinstance(options, str):
            import json
            options = json.loads(options)
        
        # Get default options if none provided
        if not options:
            options = {
                'follow_calendar_months': 1,
                'generate_invoice_at_period_start': 1,
                'generate_new_invoices_past_due_date': 1,
                'submit_invoice': 1,
                'days_until_due': 30
            }
            
        # Get the membership
        membership = frappe.get_doc("Membership", membership_name)
        
        # Create subscription
        subscription_name = membership.create_subscription_from_membership(options)
        
        # Sync payment details after creation
        membership.sync_payment_details_from_subscription()
        
        return subscription_name
        
    except Exception as e:
        frappe.log_error(f"Error creating subscription: {str(e)}", "Subscription Error")
        frappe.throw(_("Error creating subscription: {0}").format(str(e)))

def process_membership_statuses():
    """
    Scheduled job to update membership statuses based on dates and payments
    - Expire memberships past renewal date
    - Mark memberships as inactive if payment is overdue
    - Auto-renew memberships if configured
    """
    from frappe.utils import today, getdate
    
    # Get memberships that need status updates
    memberships = frappe.get_all(
        "Membership",
        filters={
            "docstatus": 1,
            "status": ["not in", ["Cancelled", "Expired"]]
        },
        fields=["name", "renewal_date", "status", "auto_renew"]
    )
    
    today_date = getdate(today())
    
    for membership_info in memberships:
        try:
            membership = frappe.get_doc("Membership", membership_info.name)
            
            # First sync payment details to get current payment status
            if membership.subscription:
                membership.sync_payment_details_from_subscription()
            
            # Check expiry - if past renewal date
            if membership.renewal_date and getdate(membership.renewal_date) < today_date:
                if membership.auto_renew:
                    # Auto-renew if configured
                    new_membership_name = membership.renew_membership()
                    
                    # Submit the new membership
                    new_membership = frappe.get_doc("Membership", new_membership_name)
                    new_membership.docstatus = 1
                    new_membership.save()
                    
                    frappe.logger().info(f"Auto-renewed membership {membership.name} to {new_membership_name}")
                else:
                    # Just mark as expired if not auto-renewing
                    membership.status = "Expired"
                    membership.flags.ignore_validate_update_after_submit = True
                    membership.save()
                    
                    frappe.logger().info(f"Marked membership {membership.name} as Expired")
            
            # Check if payment is overdue and update status
            elif membership.payment_status == "Overdue" and membership.status != "Inactive":
                membership.status = "Inactive"
                membership.flags.ignore_validate_update_after_submit = True
                membership.save()
                
                frappe.logger().info(f"Marked membership {membership.name} as Inactive due to overdue payment")
            
            # Check cancellations with end-of-period dates that have now been reached
            elif membership.cancellation_date and membership.cancellation_type == "End of Period":
                if getdate(membership.renewal_date) <= today_date:
                    membership.status = "Cancelled"
                    membership.flags.ignore_validate_update_after_submit = True
                    membership.save()
                    
                    frappe.logger().info(f"Processed end-of-period cancellation for membership {membership.name}")
        
        except Exception as e:
            frappe.log_error(f"Error processing membership status for {membership_info.name}: {str(e)}", 
                          "Membership Status Update Error")
    
    return True
