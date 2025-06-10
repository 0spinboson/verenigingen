import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today, date_diff, add_to_date, nowdate, flt, add_months

class Membership(Document):
    def validate(self):
        self.validate_dates()
        self.validate_membership_type()
        self.validate_existing_memberships()
        self.set_renewal_date()  # Calculate renewal date based on start date and membership type
        self.set_status()
        self.calculate_effective_amount()  # New: Calculate effective amount

    def validate_existing_memberships(self):
        """Check if there are any existing active memberships for this member"""
        if self.is_new() and self.member:
            existing_memberships = frappe.get_all(
                "Membership",
                filters={
                    "member": self.member,
                    "status": ["not in", ["Cancelled", "Expired"]],
                    "docstatus": 1,
                    "name": ["!=", self.name]
                },
                fields=["name", "membership_type", "start_date", "renewal_date", "status"]
            )
            
            if existing_memberships:
                membership = existing_memberships[0]
                msg = _("This member already has an active membership:")
                msg += f"<br><b>{membership.name}</b> ({membership.membership_type})"
                msg += f"<br>Status: {membership.status}"
                msg += f"<br>Start Date: {frappe.format(membership.start_date, {'fieldtype': 'Date'})}"
                msg += f"<br>Renewal Date: {frappe.format(membership.renewal_date, {'fieldtype': 'Date'})}"
                
                if len(existing_memberships) > 1:
                    msg += f"<br><br>{_('And')} {len(existing_memberships) - 1} {_('more active memberships.')}"
                    
                # Add view memberships link
                msg += f'<br><br><a href="/app/membership/list?member={self.member}">{_("View All Memberships")}</a>'
                
                # Add allow creation checkbox
                allow_creation = frappe.form_dict.get("allow_multiple_memberships")
                
                if not allow_creation:
                    msg += f'<br><br>{_("If you want to create multiple memberships for this member, check the Allow Multiple Memberships box.")}'
                    
                    frappe.msgprint(
                        msg=msg,
                        title=_("Existing Membership Found"),
                        indicator="orange",
                        primary_action={
                            "label": _("Create Anyway"),
                            "server_action": "verenigingen.verenigingen.doctype.membership.membership.allow_multiple_memberships",
                            "args": {
                                "member": self.member
                            }
                        }
                    )
                    
                    if not frappe.flags.get("allow_multiple_memberships"):
                        frappe.throw(_("Member already has an active membership. Cancel the existing membership before creating a new one."), 
                                   title=_("Duplicate Membership"))
    
    @frappe.whitelist()
    def allow_multiple_memberships(member):
        """Set a flag to allow creating multiple memberships for a member"""
        frappe.flags.allow_multiple_memberships = True
        return True
        
    def validate_dates(self):
        # If cancellation date is set, check if it's at least 1 year after start date
        # but allow exceptions for admins and unsubmitted memberships
        if self.cancellation_date and self.start_date and self.docstatus == 1:
            min_membership_period = add_months(getdate(self.start_date), 12)
            if getdate(self.cancellation_date) < min_membership_period:
                # Check if user is an admin
                is_admin = "System Manager" in frappe.get_roles(frappe.session.user)
            
                if is_admin:
                    # Show warning but allow cancellation
                    frappe.msgprint(_("Warning: Membership is being cancelled before the minimum 1-year period."), 
                                   indicator='yellow', alert=True)
                else:
                    frappe.throw(_("Cancellation is only allowed after a minimum membership period of 1 year"))

    def set_renewal_date(self):
        """Calculate renewal date based on membership type and start date"""
        if self.membership_type and self.start_date:
            membership_type = frappe.get_doc("Membership Type", self.membership_type)
            
            # Get duration from membership type
            if membership_type.subscription_period != "Lifetime":
                months = self.get_months_from_period(membership_type.subscription_period, 
                                                  membership_type.subscription_period_in_months)
                
                # Ensure minimum 1-year membership period
                if months and months < 12:
                    months = 12
                    frappe.msgprint(_("Note: Membership type has a period less than 1 year. Due to the mandatory minimum period, the renewal date is set to 1 year from start date."), 
                                  indicator='yellow')
                
                if months:
                    self.renewal_date = add_to_date(self.start_date, months=months)
            else:
                # For lifetime memberships, still set a minimum 1-year initial period
                # This allows the 1-year cancellation rule to be enforced
                self.renewal_date = add_to_date(self.start_date, months=12)
                frappe.msgprint(_("Note: Although this is a lifetime membership, a 1-year minimum commitment period still applies."), 
                              indicator='info')
    
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

    def set_status(self):
        """Set the status based on dates, payment amount, and cancellation"""
        if self.docstatus == 0:
            self.status = "Draft"
        elif self.docstatus == 2:
            self.status = "Cancelled"
        elif self.cancellation_date and getdate(self.cancellation_date) <= getdate(today()):
            # Membership is cancelled
            self.status = "Cancelled"
        elif self.unpaid_amount and flt(self.unpaid_amount) > 0:
            # Has unpaid invoices - membership inactive
            self.status = "Inactive"
        elif self.renewal_date and getdate(self.renewal_date) < getdate(today()):
            # Past renewal date - membership expired
            self.status = "Expired"
        else:
            # All good - active membership
            self.status = "Active"
    
    def calculate_effective_amount(self):
        """Calculate the effective amount and difference from standard"""
        if self.uses_custom_amount and self.custom_amount:
            self.effective_amount = self.custom_amount
        elif self.membership_type:
            membership_type = frappe.get_cached_doc("Membership Type", self.membership_type)
            self.effective_amount = membership_type.amount
        else:
            self.effective_amount = 0
        
        # Calculate difference
        if self.membership_type and self.effective_amount:
            membership_type = frappe.get_cached_doc("Membership Type", self.membership_type)
            self.amount_difference = flt(self.effective_amount) - flt(membership_type.amount)
        else:
            self.amount_difference = 0
        
        # Set membership fee field for display
        self.membership_fee = self.effective_amount
                
    def on_submit(self):
        import frappe
        from frappe import _
        from frappe.utils import getdate, add_days, add_months
        import json
        # Update member's current membership
        self.update_member_status()
        
        # Make sure unpaid_amount is set if not already
        if not self.unpaid_amount:
            self.unpaid_amount = 0
            
        # Initialize next_billing_date to start_date if not set
        if not self.next_billing_date:
            self.next_billing_date = self.start_date
            
        # Clear cancellation fields if not set
        if not self.cancellation_date:
            self.cancellation_date = None
            self.cancellation_reason = None
            self.cancellation_type = None

        # Update status properly
        self.set_status()
        
        # Force update to database
        self.db_set('status', self.status)
        self.db_set('unpaid_amount', self.unpaid_amount)
        self.db_set('next_billing_date', self.next_billing_date)
        self.db_set('cancellation_date', None)
        self.db_set('cancellation_reason', None)
        self.db_set('cancellation_type', None)
    
        # Update member's current membership
        self.update_member_status()

        # Link to subscription if configured
        if not self.subscription and self.subscription_plan:
            options = {
                'follow_calendar_months': 0,
                'generate_invoice_at_period_start': 1,  # Beginning of period
                'generate_new_invoices_past_due_date': 1,  # Generate even if past due
                'submit_invoice': 1,  # Submit invoices
                'days_until_due': 27
            }
            self.create_subscription_from_membership()
            
            # Sync payment details from subscription
            self.sync_payment_details_from_subscription()
    
    def on_cancel(self):
        """Handle when membership is cancelled directly (not the same as member cancellation)"""
        # Check if membership is submitted (docstatus == 1) before enforcing the 1-year rule
        if self.docstatus == 1 and getdate(self.start_date):
            min_membership_period = add_months(getdate(self.start_date), 12)
            current_date = getdate(today())
        
            if current_date < min_membership_period:
                # Check if user is an admin
                is_admin = "System Manager" in frappe.get_roles(frappe.session.user)
            
                if is_admin:
                    # Show warning but allow cancellation
                    frappe.msgprint(_("Warning: Membership is being cancelled before the minimum 1-year period. This is allowed for administrators only."), 
                                  indicator='yellow', alert=True)
                else:
                    frappe.throw(_("Membership cannot be cancelled before 1 year from start date"))
                
        self.status = "Cancelled"
        self.cancellation_date = self.cancellation_date or nowdate()
    
        # Update member status
        self.update_member_status()
    
        # Store subscription reference before unlinking 
        subscription_reference = self.subscription
        
        # Unlink subscription instead of cancelling it
        if subscription_reference:
            # Log the unlinking for tracking
            frappe.log_error(
                f"Membership {self.name} cancelled. Unlinked from subscription {subscription_reference}.",
                "Membership Subscription Unlinked"
            )
            
            # Unlink the subscription
            self.db_set('subscription', None)
            
            # Let the user know about the unlinked subscription
            frappe.msgprint(
                _("Subscription {0} has been unlinked from this membership.<br>You may need to manually cancel it if required.").format(
                    frappe.get_desk_link("Subscription", subscription_reference)
                ), 
                indicator='blue', 
                alert=True
            )
    
    def on_update_after_submit(self):
        """Handle updates after submission, including amount changes"""
        
        # Call existing code first
        super().on_update_after_submit() if hasattr(super(), 'on_update_after_submit') else None
        
        # Handle subscription amount updates when custom amount changes
        if self.has_value_changed('custom_amount') or self.has_value_changed('uses_custom_amount'):
            self.update_subscription_amount()

    def update_member_status(self):
        """Update the membership status in the Member document"""
        if self.member:
            member = frappe.get_doc("Member", self.member)
            member.save()  # This will trigger the update_membership_status method
    
    def sync_payment_details_from_subscription(self):
        """Sync payment details from linked subscription"""
        from frappe.utils import add_days, getdate, flt
        
        if not self.subscription:
            return
                
        subscription = frappe.get_doc("Subscription", self.subscription)
        
        # Update next billing date
        if subscription.current_invoice_end:
            # First define the variable
            next_billing_date = add_days(subscription.current_invoice_end, 1)
            # Then use it to update the object
            self.next_billing_date = next_billing_date
            # Then use it again for db_set
            self.db_set('next_billing_date', next_billing_date)
        
        # Get invoices from the subscription's child table
        if not hasattr(subscription, 'invoices') or not subscription.invoices:
            return
                
        # Calculate unpaid amount
        unpaid_amount = 0
        payment_date = None
        
        for invoice_ref in subscription.invoices:
            try:
                # Determine invoice type based on party type
                invoice_type = invoice_ref.document_type or ("Sales Invoice" if subscription.party_type == "Customer" else "Purchase Invoice")
                invoice = frappe.get_doc(invoice_type, invoice_ref.invoice)
                
                # Add to unpaid amount if unpaid or overdue
                if invoice.status in ["Unpaid", "Overdue"]:
                    unpaid_amount += flt(invoice.outstanding_amount)
                
                # Get latest payment date
                if invoice.status == "Paid" and (not payment_date or getdate(invoice.posting_date) > getdate(payment_date)):
                    payment_date = invoice.posting_date
            except Exception as e:
                frappe.log_error(f"Error processing invoice {invoice_ref.invoice}: {str(e)}", 
                              "Membership Payment Sync Error")
        
        # Update unpaid amount
        self.unpaid_amount = unpaid_amount
        self.db_set('unpaid_amount', unpaid_amount)
        
        # Update last payment date if found
        if payment_date:
            self.last_payment_date = payment_date
            self.db_set('last_payment_date', payment_date)
        
        # Update status based on changes
        self.set_status()
        self.db_set('status', self.status)

    def renew_membership(self):
        """Create a new membership as a renewal of the current one"""
        # Calculate new dates
        new_start_date = self.renewal_date or today()
        
        # Create new membership
        new_membership = frappe.new_doc("Membership")
        new_membership.member = self.member
        new_membership.membership_type = self.membership_type
        new_membership.start_date = new_start_date
        new_membership.auto_renew = self.auto_renew
        new_membership.payment_method = self.payment_method
        new_membership.subscription_plan = self.subscription_plan
        
        # Copy custom amount settings
        new_membership.uses_custom_amount = self.uses_custom_amount
        new_membership.custom_amount = self.custom_amount
        new_membership.amount_reason = self.amount_reason
        
        # Copy SEPA mandate details
        new_membership.sepa_mandate = self.sepa_mandate
        new_membership.mandate_reference = self.mandate_reference
        new_membership.mandate_status = self.mandate_status
        
        # The renewal date will be calculated automatically in validate()
        # which includes the 1-year minimum logic
        new_membership.validate()
        
        # Save as draft
        new_membership.insert(ignore_permissions=True)
        
        frappe.msgprint(_("Renewal Membership {0} created").format(new_membership.name))
        return new_membership.name

    def create_subscription_from_membership(self, options=None):
        """Create an ERPNext subscription for this membership with additional options"""
        import frappe
        from frappe import _
        from frappe.utils import getdate, add_days, add_months, nowdate
        
        # Initialize options with defaults if none provided
        if not options:
            options = {
                'follow_calendar_months': 0,
                'generate_invoice_at_period_start': 1,
                'generate_new_invoices_past_due_date': 1,
                'submit_invoice': 1,
                'days_until_due': 27
            }
        
        # Check if member has a customer
        member = frappe.get_doc("Member", self.member)
        
        # Check if there's already an application invoice for this membership
        has_application_invoice = False
        if member.customer:
            # First check for invoices specifically linked to this membership
            existing_invoice = frappe.db.exists(
                "Sales Invoice",
                {
                    "customer": member.customer,
                    "membership": self.name,
                    "docstatus": ["!=", 2]  # Not cancelled
                }
            )
            
            # If no direct link, check for recent invoices for this customer
            if not existing_invoice:
                existing_invoice = frappe.db.exists(
                    "Sales Invoice",
                    {
                        "customer": member.customer,
                        "status": ["in", ["Draft", "Submitted", "Unpaid", "Paid", "Partly Paid"]],
                        "posting_date": [">=", self.start_date],
                        "docstatus": ["!=", 2]  # Not cancelled
                    }
                )
            
            if existing_invoice:
                has_application_invoice = True
                frappe.log_error(
                    f"Application invoice {existing_invoice} exists for membership {self.name} - adjusting subscription to prevent duplicates",
                    "Membership Subscription Creation"
                )
                # Modify options to prevent immediate invoice generation
                options['generate_invoice_at_period_start'] = 0
                options['generate_new_invoices_past_due_date'] = 0
        
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
            
            # Load the subscription plan to get its billing details
            subscription_plan = frappe.get_doc("Subscription Plan", self.subscription_plan)
            
            # Create subscription
            subscription = frappe.new_doc("Subscription")
            
            # Set basic subscription properties
            subscription.party_type = "Customer"
            subscription.party = member.customer
            
            # If application invoice exists, adjust subscription start date to next billing period
            if has_application_invoice:
                # Calculate next billing period start date
                from frappe.utils import add_months, add_days
                if subscription_plan.billing_interval == "Month":
                    next_period_start = add_months(getdate(self.start_date), subscription_plan.billing_interval_count)
                elif subscription_plan.billing_interval == "Year":
                    next_period_start = add_months(getdate(self.start_date), subscription_plan.billing_interval_count * 12)
                else:
                    # Fallback for other intervals
                    next_period_start = add_days(getdate(self.start_date), 30)
                subscription.start_date = next_period_start
                frappe.log_error(
                    f"Adjusted subscription start date to {next_period_start} for membership {self.name} to avoid overlap with application invoice",
                    "Membership Subscription Date Adjustment"
                )
            else:
                subscription.start_date = getdate(self.start_date)
            
            # Set company
            subscription.company = frappe.defaults.get_global_default('company') or '_Test Company'
            
            # Set billing details from the subscription plan
            subscription.billing_interval = subscription_plan.billing_interval
            subscription.billing_interval_count = subscription_plan.billing_interval_count
            
            # Set options from provided parameters
            subscription.follow_calendar_months = options.get('follow_calendar_months', 0)
            if options.get('generate_invoice_at_period_start', 1):
                subscription.generate_invoice_at = "Beginning of the current subscription period"
            else:
                subscription.generate_invoice_at = "End of the current subscription period"
            subscription.generate_new_invoices_past_due_date = options.get('generate_new_invoices_past_due_date', 1)
            subscription.submit_invoice = options.get('submit_invoice', 1)
            subscription.days_until_due = options.get('days_until_due', 27)
            
            # Get the effective amount for this membership
            effective_amount = self.get_billing_amount()
            
            # Get or create the appropriate subscription plan
            subscription_plan_to_use = self.get_subscription_plan_for_amount(effective_amount)
            
            # Add the subscription plan
            subscription.append("plans", {
                "plan": subscription_plan_to_use,
                "qty": 1
            })
            
            # Insert and submit
            subscription.flags.ignore_mandatory = True
            subscription.flags.ignore_permissions = True
            subscription.insert()
            
            # Log the subscription details before submission for debugging
            frappe.logger().info(
                f"Creating subscription for membership {self.name}. Start: {subscription.start_date}"
            )
            
            try:
                subscription.submit()
            except Exception as e:
                frappe.log_error(f"Error submitting subscription: {str(e)}", 
                              "Subscription Submit Error")
                raise
            
            # Link subscription to membership
            self.subscription = subscription.name
            self.db_set('subscription', subscription.name)
            
            if subscription.current_invoice_end:
                self.next_billing_date = add_days(subscription.current_invoice_end, 1)
                self.db_set('next_billing_date', add_days(subscription.current_invoice_end, 1))
            
            # Queue job to process subscription for invoice generation
            if getdate(self.start_date) <= getdate(nowdate()):
                frappe.flags.in_test = False
                frappe.enqueue(
                    "erpnext.accounts.doctype.subscription.subscription.process_all",
                    subscription=subscription.name,
                    enqueue_after_commit=True
                )
                frappe.msgprint(_("Subscription created. Invoice will be generated shortly."))
            else:
                frappe.msgprint(_("Subscription created. Invoice will be generated on {0}").format(
                    frappe.format(subscription.current_invoice_start, {"fieldtype": "Date"})
                ))
            
            frappe.logger().info(
                f"Created subscription {subscription.name} with amount {effective_amount} "
                f"(custom: {self.uses_custom_amount}) for membership {self.name}"
            )
            
            return subscription.name
            
        except Exception as e:
            error_details = f"Error details: Subscription Plan: {self.subscription_plan}, Start Date: {self.start_date}"
            frappe.log_error(f"Error creating subscription: {str(e)}\n{error_details}", 
                          "Membership Subscription Error")
            raise
    
    def get_billing_amount(self):
        """Get the amount that should be used for billing this membership"""
        
        if self.uses_custom_amount and self.custom_amount:
            return self.custom_amount
        else:
            # Use the membership type amount
            if self.membership_type:
                membership_type = frappe.get_doc("Membership Type", self.membership_type)
                return membership_type.amount
            else:
                return 0
    
    def get_subscription_plan_for_amount(self, amount):
        """Get or create a subscription plan for the specified amount"""
        # If using standard amount, use the original subscription plan
        if not self.uses_custom_amount or not self.custom_amount:
            return self.subscription_plan
        
        # For custom amounts, get/create a custom subscription plan
        original_plan = frappe.get_doc("Subscription Plan", self.subscription_plan)
        
        # Create a unique plan name for this amount
        custom_plan_name = f"{original_plan.plan_name} - €{amount:.2f}"
        
        # Check if custom plan already exists
        existing_plan = frappe.db.exists("Subscription Plan", {"plan_name": custom_plan_name})
        if existing_plan:
            return existing_plan
        
        # Create new custom subscription plan
        custom_plan = frappe.get_doc({
            "doctype": "Subscription Plan",
            "plan_name": custom_plan_name,
            "item": original_plan.item,
            "currency": original_plan.currency,
            "price_determination": "Fixed Rate",
            "cost": amount,
            "billing_interval": original_plan.billing_interval,
            "billing_interval_count": original_plan.billing_interval_count,
            "payment_gateway": original_plan.payment_gateway,
            "cost_center": original_plan.cost_center
        })
        
        custom_plan.insert(ignore_permissions=True)
        frappe.log_error(f"Created custom subscription plan {custom_plan_name} with cost {amount} for membership {self.name}")
        
        return custom_plan.name
    
    def update_subscription_amount(self):
        """Update the subscription plan amount when membership amount changes"""
        
        if not self.subscription:
            frappe.logger().info(f"No subscription linked to membership {self.name}")
            return
            
        try:
            subscription = frappe.get_doc("Subscription", self.subscription)
            
            # Calculate the new amount to use
            new_amount = self.get_billing_amount()
            
            # Get the appropriate subscription plan for the new amount
            new_subscription_plan = self.get_subscription_plan_for_amount(new_amount)
            
            # Check if we need to update the subscription plan
            updated = False
            for plan_row in subscription.plans:
                if plan_row.plan != new_subscription_plan:
                    old_plan = plan_row.plan
                    plan_row.plan = new_subscription_plan
                    updated = True
                    
                    frappe.logger().info(
                        f"Updated subscription {subscription.name} plan from {old_plan} to {new_subscription_plan} "
                        f"for membership {self.name} with amount {new_amount}"
                    )
            
            if updated:
                # Save the subscription with updated plan
                subscription.save(ignore_permissions=True)
                
                # Cancel any pending unpaid invoices and regenerate them with new amounts
                self.regenerate_pending_invoices(subscription)
                
                # Show message to user
                frappe.msgprint(
                    _("Subscription updated to use plan for amount {0}. Future invoices will use the new amount.").format(
                        frappe.format_value(new_amount, {"fieldtype": "Currency"})
                    ),
                    indicator="green"
                )
                
        except Exception as e:
            frappe.log_error(f"Error updating subscription amount for membership {self.name}: {str(e)}", 
                          "Subscription Amount Update Error")
            frappe.throw(_("Error updating subscription amount. Please contact system administrator."))
    
    def regenerate_pending_invoices(self, subscription):
        """Cancel pending invoices and regenerate them with new amounts"""
        
        try:
            # Find draft or unpaid invoices for this subscription
            pending_invoices = frappe.get_all(
                "Sales Invoice",
                filters={
                    "subscription": subscription.name,
                    "status": ["in", ["Draft", "Unpaid"]],
                    "docstatus": ["!=", 2]  # Not cancelled
                },
                fields=["name", "docstatus", "grand_total"]
            )
            
            cancelled_count = 0
            for invoice_info in pending_invoices:
                invoice = frappe.get_doc("Sales Invoice", invoice_info.name)
                
                # Only cancel/delete if the amount is different
                new_amount = self.get_billing_amount()
                if abs(invoice.grand_total - new_amount) > 0.01:  # Allow for small rounding differences
                    
                    if invoice.docstatus == 1:  # Submitted
                        invoice.cancel()
                        cancelled_count += 1
                        frappe.logger().info(f"Cancelled invoice {invoice.name} (amount {invoice.grand_total}) for regeneration with new amount {new_amount}")
                        
                    elif invoice.docstatus == 0:  # Draft
                        invoice.delete()
                        cancelled_count += 1
                        frappe.logger().info(f"Deleted draft invoice {invoice.name} for regeneration with new amount {new_amount}")
            
            if cancelled_count > 0:
                # Trigger subscription processing to create new invoices with correct amounts
                frappe.enqueue(
                    "erpnext.accounts.doctype.subscription.subscription.process_all",
                    subscription=subscription.name,
                    enqueue_after_commit=True,
                    queue="short"
                )
                
                frappe.msgprint(
                    _("{0} pending invoices cancelled and will be regenerated with the new amount.").format(cancelled_count),
                    indicator="blue"
                )
                
        except Exception as e:
            frappe.log_error(f"Error regenerating pending invoices: {str(e)}", 
                          "Invoice Regeneration Error")

# Hook functions for doc_events (outside the class)
def on_submit(doc, method=None):
    """
    This is called when a membership document is submitted.
    It simply calls the document's on_submit method.
    """
    # The class already has on_submit method, so this is just a passthrough
    pass

def on_cancel(doc, method=None):
    """
    This is called when a membership document is cancelled.
    It simply calls the document's on_cancel method.
    """
    # The class already has on_cancel method, so this is just a passthrough
    pass

def update_membership_from_subscription(doc, method=None):
    """
    Handler for when a subscription is updated
    Updates the linked membership
    """
    # Find memberships linked to this subscription
    memberships = frappe.get_all(
        "Membership",
        filters={"subscription": doc.name},
        fields=["name"]
    )
    
    if not memberships:
        return
        
    for membership_data in memberships:
        try:
            membership = frappe.get_doc("Membership", membership_data.name)
            
            # Map subscription status to membership status
            status_mapping = {
                "Active": "Active",
                "Cancelled": "Cancelled",
                "Unpaid": "Inactive",
                "Past Due": "Inactive"
            }
            
            # Check if the status needs an update based on the mapping
            new_status = status_mapping.get(doc.status)
            if new_status and membership.status != new_status:
                # Special rules for specific transitions
                
                # Don't change from Expired to Active without explicit renewal
                if membership.status == "Expired" and new_status == "Active":
                    frappe.logger().info(f"Not updating expired membership {membership.name} to Active automatically")
                    continue
                
                # Update the status
                membership.db_set('status', new_status)
                frappe.logger().info(f"Updated membership {membership.name} status from {membership.status} to {new_status}")
            
            # Always sync payment details regardless of status change
            membership.sync_payment_details_from_subscription()
            
            # Update next billing date
            if doc.current_invoice_end:
                membership.db_set('next_billing_date', doc.current_invoice_end)
            
            # Handle cancellation specifics
            if doc.status == "Cancelled" and not membership.cancellation_date:
                membership.db_set('cancellation_date', frappe.utils.today())
                membership.db_set('cancellation_reason', "Subscription cancelled")
                membership.db_set('cancellation_type', "Immediate")
                
        except Exception as e:
            frappe.log_error(f"Error updating membership {membership_data.name} from subscription: {str(e)}", 
                          "Membership Update Error")

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
    
    # For unsubmitted memberships, allow immediate cancellation without restrictions
    if membership.docstatus == 0:
        frappe.msgprint(_("Draft membership can be cancelled without restrictions"))
        return membership.name
    
    # Check 1-year minimum period for submitted memberships
    if membership.docstatus == 1:
        min_membership_period = add_months(getdate(membership.start_date), 12)
        if getdate(cancellation_date) < min_membership_period:
            # Check if user is an admin
            is_admin = "System Manager" in frappe.get_roles(frappe.session.user)
            
            if is_admin:
                # Show warning but allow cancellation
                frappe.msgprint(_("Warning: Membership is being cancelled before the minimum 1-year period. This is allowed for administrators only."), 
                              indicator='yellow', alert=True)
            else:
                frappe.throw(_("Cancellation is only allowed after a minimum membership period of 1 year"))
    
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
            # Use the standard method to cancel subscription
            subscription.flags.ignore_permissions = True
            subscription.cancel_subscription()
    
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
        
    # Get the subscription document
    try:
        subscription = frappe.get_doc("Subscription", membership.subscription)
    except Exception as e:
        frappe.log_error(f"Error fetching subscription {membership.subscription}: {str(e)}", 
                      "Membership Payment History Error")
        return []
    
    payment_history = []
    
    # Access the invoices directly from the subscription document's child table
    if hasattr(subscription, 'invoices') and subscription.invoices:
        for invoice_ref in subscription.invoices:
            try:
                invoice = frappe.get_doc("Sales Invoice", invoice_ref.invoice)
                
                # Get linked payments
                payments = frappe.get_all(
                    "Payment Entry Reference",
                    filters={"reference_name": invoice.name},
                    fields=["parent"]
                )
                
                payment_entries = []
                for payment in payments:
                    try:
                        payment_doc = frappe.get_doc("Payment Entry", payment.parent)
                        payment_entries.append({
                            "payment_entry": payment_doc.name,
                            "amount": payment_doc.paid_amount,
                            "date": payment_doc.posting_date,
                            "mode": payment_doc.mode_of_payment,
                            "status": payment_doc.status
                        })
                    except Exception as e:
                        frappe.log_error(f"Error fetching payment {payment.parent}: {str(e)}", 
                                      "Membership Payment History Error")
                
                payment_history.append({
                    "invoice": invoice.name,
                    "date": invoice.posting_date,
                    "amount": invoice.grand_total,
                    "outstanding": invoice.outstanding_amount,
                    "status": invoice.status,
                    "payments": payment_entries
                })
            except Exception as e:
                frappe.log_error(f"Error fetching invoice {invoice_ref.invoice}: {str(e)}", 
                              "Membership Payment History Error")
                # Add a placeholder entry with basic information
                payment_history.append({
                    "invoice": invoice_ref.invoice,
                    "date": invoice_ref.posting_date if hasattr(invoice_ref, 'posting_date') else None,
                    "amount": 0,
                    "outstanding": 0,
                    "status": "Unknown",
                    "payments": []
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
                'follow_calendar_months': 0,
                'generate_invoice_at_period_start': 1,
                'generate_new_invoices_past_due_date': 1,
                'submit_invoice': 1,
                'days_until_due': 27
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
            elif membership.unpaid_amount and flt(membership.unpaid_amount) > 0 and membership.status != "Inactive":
                membership.status = "Inactive"
                membership.flags.ignore_validate_update_after_submit = True
                membership.save()
                
                frappe.logger().info(f"Marked membership {membership.name} as Inactive due to unpaid amount")
            
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

def verify_signature(data, signature, secret_key=None):
    """
    Verify a signature for webhook data (for donation verification)
    Args:
        data (dict or str): The data to verify
        signature (str): The signature received
        secret_key (str, optional): The secret key to use for verification.
                                   If not provided, will use config value.
    Returns:
        bool: True if signature is valid, False otherwise
    """
    import hmac
    import hashlib
    import frappe
    if not secret_key:
        # Get secret key from configuration
        secret_key = frappe.conf.get("webhook_secret_key")
        if not secret_key:
            frappe.log_error("No webhook_secret_key found in configuration",
                            "Payment Signature Verification Error")
            return False
    # Convert data to string if it's a dict
    if isinstance(data, dict):
        import json
        data = json.dumps(data)
    # Convert to bytes if it's not already
    if isinstance(data, str):
        data = data.encode('utf-8')
    if isinstance(secret_key, str):
        secret_key = secret_key.encode('utf-8')
    # Create signature
    computed_signature = hmac.new(
        secret_key,
        data,
        hashlib.sha256
    ).hexdigest()
    # Compare signatures (using constant-time comparison to prevent timing attacks)
    return hmac.compare_digest(computed_signature, signature)

@frappe.whitelist()
def show_all_invoices(membership_name):
    """
    Get all invoices related to a membership either through subscription
    or direct links
    """
    membership = frappe.get_doc("Membership", membership_name)
    invoices = []
    
    # Get invoices from subscription if available
    if membership.subscription:
        try:
            subscription = frappe.get_doc("Subscription", membership.subscription)
            
            # Access invoices from the subscription's child table
            if hasattr(subscription, 'invoices') and subscription.invoices:
                for invoice_ref in subscription.invoices:
                    try:
                        invoice_doc = frappe.get_doc("Sales Invoice", invoice_ref.invoice)
                        
                        invoices.append({
                            "invoice": invoice_doc.name,
                            "date": invoice_doc.posting_date,
                            "amount": invoice_doc.grand_total,
                            "outstanding": invoice_doc.outstanding_amount,
                            "status": invoice_doc.status,
                            "due_date": invoice_doc.due_date,
                            "source": "Subscription"
                        })
                    except Exception as e:
                        frappe.log_error(f"Error fetching invoice {invoice_ref.invoice}: {str(e)}",
                                      "Membership Invoices Error")
        except Exception as e:
            frappe.log_error(f"Error fetching subscription {membership.subscription}: {str(e)}",
                          "Membership Invoices Error")
    
    # Also look for invoices that might be directly linked to the membership
    # via custom fields or standard references
    direct_invoices = frappe.get_all(
        "Sales Invoice",
        filters={
            "docstatus": 1,
            "membership": membership.name  # Assuming there's a field named "membership" in Sales Invoice
        },
        fields=["name", "posting_date", "grand_total", "outstanding_amount", "status", "due_date"]
    )
    
    for inv in direct_invoices:
        # Check if this invoice is already in our list (to avoid duplicates)
        if not any(existing["invoice"] == inv.name for existing in invoices):
            invoices.append({
                "invoice": inv.name,
                "date": inv.posting_date,
                "amount": inv.grand_total,
                "outstanding": inv.outstanding_amount,
                "status": inv.status,
                "due_date": inv.due_date,
                "source": "Direct Link"
            })
    
    # Look for invoices related to the member (might be relevant for the membership)
    if membership.member:
        member = frappe.get_doc("Member", membership.member)
        
        # If the member has a linked customer
        if member.customer:
            customer_invoices = frappe.get_all(
                "Sales Invoice",
                filters={
                    "docstatus": 1,
                    "customer": member.customer,
                    "posting_date": ["between", [membership.start_date, 
                                                membership.renewal_date or "2099-12-31"]]
                },
                fields=["name", "posting_date", "grand_total", "outstanding_amount", "status", "due_date"]
            )
            
            for inv in customer_invoices:
                # Check if this invoice is already in our list (to avoid duplicates)
                if not any(existing["invoice"] == inv.name for existing in invoices):
                    invoices.append({
                        "invoice": inv.name,
                        "date": inv.posting_date,
                        "amount": inv.grand_total,
                        "outstanding": inv.outstanding_amount,
                        "status": inv.status,
                        "due_date": inv.due_date,
                        "source": "Member/Customer"
                    })
    
    # Sort all invoices by date (newest first)
    invoices.sort(key=lambda x: x["date"] or "1900-01-01", reverse=True)
    
    return invoices

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_member_sepa_mandates(doctype, txt, searchfield, start, page_len, filters):
    """Get SEPA mandates for a specific member"""
    member = filters.get('member')
    
    if not member:
        # Try to get member from membership document
        if filters.get('doctype') == 'Membership' and filters.get('name'):
            membership = frappe.get_doc('Membership', filters.get('name'))
            member = membership.member
    
    if not member:
        return []
    
    # Get active SEPA mandates for this member
    return frappe.db.sql("""
        SELECT 
            sm.name,
            sm.mandate_id,
            sm.status
        FROM `tabSEPA Mandate` sm
        WHERE 
            sm.member = %s
            AND sm.status = 'Active'
            AND sm.used_for_memberships = 1
            AND (sm.name LIKE %s OR sm.mandate_id LIKE %s)
        ORDER BY sm.creation DESC
    """, (member, "%" + txt + "%", "%" + txt + "%"))

def update_membership_from_subscription(doc, method=None):
    """
    Handler for when a subscription is updated
    Updates the linked membership
    
    This function is called via hooks.py
    """
    # Find memberships linked to this subscription
    memberships = frappe.get_all(
        "Membership",
        filters={"subscription": doc.name},
        fields=["name"]
    )
    
    if not memberships:
        return
        
    for membership_data in memberships:
        try:
            membership = frappe.get_doc("Membership", membership_data.name)
            
            # Update membership status and payment details
            membership.sync_payment_details_from_subscription()
            
            # Update status based on subscription status
            if doc.status == "Active" and membership.status not in ["Active", "Expired"]:
                membership.db_set('status', 'Active')
            elif doc.status == "Cancelled" and membership.status != "Cancelled":
                membership.db_set('status', 'Cancelled')
            elif doc.status == "Unpaid" and membership.status == "Active":
                membership.db_set('status', 'Inactive')
                
            frappe.logger().info(f"Updated membership {membership.name} from subscription {doc.name}")
                
        except Exception as e:
            frappe.log_error(f"Error updating membership {membership_data.name} from subscription: {str(e)}", 
                          "Membership Update Error")

# Enhanced set_custom_amount function
@frappe.whitelist()
def set_custom_amount(membership_name, custom_amount, reason=None):
    """Set custom amount for a membership and update subscription"""
    
    membership = frappe.get_doc("Membership", membership_name)
    
    # Check permissions
    if not frappe.has_permission("Membership", "write", membership):
        frappe.throw(_("No permission to modify this membership"))
    
    custom_amount = float(custom_amount)
    old_effective_amount = membership.get_billing_amount()
    
    # Validate against membership type
    membership_type = frappe.get_doc("Membership Type", membership.membership_type)
    
    if not getattr(membership_type, 'allow_custom_amount', False):
        frappe.throw(_("Custom amounts are not allowed for this membership type"))
    
    minimum_amount = getattr(membership_type, 'minimum_amount', None) or membership_type.amount
    if custom_amount < minimum_amount:
        frappe.throw(_("Amount cannot be less than minimum: {0}").format(minimum_amount))
    
    # Update membership
    membership.uses_custom_amount = 1
    membership.custom_amount = custom_amount
    membership.amount_reason = reason or ""
    membership.flags.ignore_validate_update_after_submit = True
    membership.save()
    
    # Get new effective amount
    new_effective_amount = membership.get_billing_amount()
    
    return {
        "success": True,
        "old_amount": old_effective_amount,
        "new_amount": new_effective_amount,
        "difference": new_effective_amount - membership_type.amount,
        "subscription_updated": bool(membership.subscription),
        "message": _("Amount updated successfully. Future invoices will use {0}").format(
            frappe.format_value(new_effective_amount, {"fieldtype": "Currency"})
        )
    }

@frappe.whitelist()
def revert_to_standard_amount(membership_name, reason=None):
    """Revert membership to use standard membership type amount"""
    
    membership = frappe.get_doc("Membership", membership_name)
    
    # Check permissions
    if not frappe.has_permission("Membership", "write", membership):
        frappe.throw(_("No permission to modify this membership"))
    
    if not membership.uses_custom_amount:
        frappe.throw(_("This membership is already using the standard amount"))
    
    old_amount = membership.custom_amount
    
    # Revert to standard amount
    membership.uses_custom_amount = 0
    membership.custom_amount = None
    membership.amount_reason = reason or "Reverted to standard amount"
    membership.flags.ignore_validate_update_after_submit = True
    membership.save()
    
    # Get standard amount
    membership_type = frappe.get_doc("Membership Type", membership.membership_type)
    standard_amount = membership_type.amount
    
    return {
        "success": True,
        "old_amount": old_amount,
        "new_amount": standard_amount,
        "message": _("Reverted to standard amount: {0}").format(
            frappe.format_value(standard_amount, {"fieldtype": "Currency"})
        )
    }

# Utility function to check subscription amounts
@frappe.whitelist()
def check_subscription_amounts():
    """Debug function to check subscription amounts vs membership amounts"""
    
    results = []
    
    # Get all active memberships with subscriptions
    memberships = frappe.get_all(
        "Membership",
        filters={
            "status": "Active",
            "subscription": ["is", "set"]
        },
        fields=["name", "member_name", "uses_custom_amount", "custom_amount", "subscription", "membership_type"]
    )
    
    for membership_info in memberships:
        membership = frappe.get_doc("Membership", membership_info.name)
        expected_amount = membership.get_billing_amount()
        
        # Get subscription amount
        try:
            subscription = frappe.get_doc("Subscription", membership.subscription)
            actual_amount = subscription.plans[0].cost if subscription.plans else 0
            
            results.append({
                "membership": membership.name,
                "member": membership.member_name,
                "expected_amount": expected_amount,
                "actual_amount": actual_amount,
                "matches": abs(expected_amount - actual_amount) < 0.01,
                "uses_custom": membership.uses_custom_amount
            })
            
        except Exception as e:
            results.append({
                "membership": membership.name,
                "member": membership.member_name,
                "error": str(e)
            })
    
    return results

# Function to bulk fix subscription amounts if needed
@frappe.whitelist()
def fix_subscription_amounts():
    """Fix subscription amounts to match membership amounts"""
    
    check_results = check_subscription_amounts()
    fixed_count = 0
    
    for result in check_results:
        if result.get("matches") == False:  # Amount mismatch
            try:
                membership = frappe.get_doc("Membership", result["membership"])
                membership.update_subscription_amount()
                fixed_count += 1
                
            except Exception as e:
                frappe.log_error(f"Error fixing subscription amount for {result['membership']}: {str(e)}")
    
    return {
        "success": True,
        "fixed_count": fixed_count,
        "message": f"Fixed {fixed_count} subscription amounts"
    }
