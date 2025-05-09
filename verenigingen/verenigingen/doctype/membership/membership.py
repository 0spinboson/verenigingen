import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today, date_diff, add_to_date, nowdate, flt

class Membership(Document):
    def validate(self):
        self.validate_dates()
        self.validate_membership_type()
        self.set_status()
        
    def validate_dates(self):
        # Ensure start date is before end date
        if self.end_date and getdate(self.start_date) > getdate(self.end_date):
            frappe.throw(_("Start Date cannot be after End Date"))
            
        # If no end date is set, check if the membership type has a duration
        if not self.end_date and self.membership_type:
            membership_type = frappe.get_doc("Membership Type", self.membership_type)
            
            if membership_type.subscription_period != "Lifetime":
                # Set end date based on subscription period
                months = self.get_months_from_period(membership_type.subscription_period, 
                                                  membership_type.subscription_period_in_months)
                
                if months:
                    self.end_date = add_to_date(self.start_date, months=months)
    
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
                
            # Set fee amount if not already set
            if not self.fee_amount and membership_type.amount:
                self.fee_amount = membership_type.amount
                self.currency = membership_type.currency
                
    def set_status(self):
        if self.docstatus == 0:
            self.status = "New"
        elif self.docstatus == 2:
            self.status = "Cancelled"
        elif self.cancellation_date:
            self.status = "Cancelled"
        elif self.end_date and getdate(self.end_date) < getdate(today()):
            self.status = "Expired"
        else:
            # Check if payment is made, if required
            if self.fee_amount and flt(self.fee_amount) > 0:
                if self.payment_status not in ["Paid", "Refunded"]:
                    self.status = "Pending"
                else:
                    self.status = "Active"
            else:
                self.status = "Active"
                
    def on_submit(self):
        # Update member's current membership
        self.update_member_status()
        frappe.logger().debug(f"Before submit - Status: {self.status}, Cancellation Date: {self.cancellation_date}")
        
        self.cancellation_date = None

        # Set proper status
        if self.fee_amount and flt(self.fee_amount) > 0:
            if self.payment_status not in ["Paid", "Refunded"]:
                self.status = "Pending"
            else:
                self.status = "Active"
        else:
            self.status = "Active"
        # Force update to database
        self.db_set('status', self.status)
        self.db_set('cancellation_date', None)

        frappe.logger().debug(f"After submit fixes - Status: {self.status}, Cancellation Date: {self.cancellation_date}")
    
        # Update member's current membership
        self.update_member_status()

        # Link to subscription if configured
        if not self.subscription and self.subscription_plan:
            self.create_subscription_from_membership()
    
    def on_cancel(self):
        self.status = "Cancelled"
        self.cancellation_date = self.cancellation_date or nowdate()
        
        # Update member status
        self.update_member_status()
        
        # Cancel linked subscription
        if self.subscription:
            try:
                subscription = frappe.get_doc("Subscription", self.subscription)
                if subscription.status != "Cancelled":
                    # The key fix - ensure the cancelation_date is a date object not a string
                    if not subscription.cancelation_date:
                        # Store as date object using getdate
                        subscription.db_set('cancelation_date', getdate(self.cancellation_date))
                    elif isinstance(subscription.cancelation_date, str):
                        # Convert to date object if it's a string
                        subscription.db_set('cancelation_date', getdate(subscription.cancelation_date))
                
                    # Use db_set to directly update database and bypass validation
                    subscription.flags.ignore_permissions = True
                
                    # Now cancel the subscription
                    # Let's catch any specific errors in the cancel_subscription method
                    try:
                        subscription.cancel_subscription()
                    except TypeError as e:
                        # If we still get a type error, try to fix it manually
                        if ">=' not supported between instances of 'str' and 'datetime.date" in str(e):
                            # Directly set status to cancelled as a fallback
                            subscription.db_set('status', 'Cancelled')
                            frappe.db.commit()
                            frappe.msgprint(_("Subscription {0} has been cancelled").format(subscription.name))
                        else:
                            raise
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

    def renew_membership(self):
        """Create a new membership as a renewal of the current one"""
        # Calculate new dates
        new_start_date = self.end_date or today()
        
        # Get duration from membership type
        membership_type = frappe.get_doc("Membership Type", self.membership_type)
        months = self.get_months_from_period(membership_type.subscription_period, 
                                          membership_type.subscription_period_in_months)
        
        new_end_date = None
        if months:
            new_end_date = add_to_date(new_start_date, months=months)
            
        # Create new membership
        new_membership = frappe.new_doc("Membership")
        new_membership.member = self.member
        new_membership.membership_type = self.membership_type
        new_membership.start_date = new_start_date
        new_membership.end_date = new_end_date
        new_membership.auto_renew = self.auto_renew
        new_membership.fee_amount = self.fee_amount
        new_membership.currency = self.currency
        new_membership.subscription_plan = self.subscription_plan
        
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
        
        # Debug the function call
        frappe.logger().debug(f"create_subscription_from_membership called with options={options}")
        
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
            
            # Set the end date if defined in membership
            if self.end_date:
                subscription.end_date = getdate(self.end_date)
            
            # Set next billing date (1 month from start by default)
            subscription.next_billing_date = add_months(getdate(self.start_date), 1)
            
            # Set billing interval defaults
            subscription.billing_interval = "Month"
            subscription.billing_interval_count = 1
            
            # Explicitly add requested options
            subscription.follow_calendar_months = 1 if options.get('follow_calendar_months') else 0
            subscription.generate_invoice_at_period_start = 1 if options.get('generate_invoice_at_period_start') else 0
            subscription.generate_new_invoices_past_due_date = 1 if options.get('generate_new_invoices_past_due_date') else 0
            subscription.submit_invoice = 1 if options.get('submit_invoice') else 0
            
            if options.get('days_until_due'):
                subscription.days_until_due = options.get('days_until_due')
            
            # Safely add the subscription plan
            table_fields = [d.fieldname for d in frappe.get_meta("Subscription").get_table_fields()]
            
            if 'plans' in table_fields:
                # Check if the plans table exists
                try:
                    # Use append for plans table - basic required fields only
                    subscription.append("plans", {
                        "subscription_plan": self.subscription_plan,
                        "qty": 1
                    })
                except Exception as e:
                    frappe.log_error(
                        f"Error appending plan to subscription: {str(e)}", 
                        "Membership Subscription Error"
                    )
                    raise
            else:
                frappe.throw(_("The Subscription DocType structure has changed. Please update your app."))
            
            # For debugging
            frappe.logger().debug(f"About to insert subscription with minimal fields")
            frappe.logger().debug(f"Subscription dict: {subscription.as_dict()}")
            
            # Insert with ignore_mandatory to bypass validation issues
            subscription.flags.ignore_mandatory = True
            subscription.insert(ignore_permissions=True, ignore_mandatory=True)
            
            # Log success
            frappe.logger().debug(f"Subscription inserted with ID: {subscription.name}")
            
            # Now submit the subscription
            subscription.submit()
            
            # Link subscription to membership
            self.subscription = subscription.name
            self.save()
            
            frappe.msgprint(_("Subscription {0} created successfully").format(subscription.name))
            return subscription.name
            
        except Exception as e:
            error_details = f"Error details: Subscription Plan: {self.subscription_plan}"
            frappe.log_error(f"Error creating subscription: {str(e)}\n{error_details}", 
                          "Membership Subscription Error")
            raise

def on_membership_update(doc, method=None):
    """
    Handler for when a membership is updated
    This is referenced in hooks.py > doc_events
    """
    if doc.docstatus == 1:  # If document is submitted
        # Update the member document to refresh status
        if doc.member:
            member = frappe.get_doc("Member", doc.member)
            member.update_membership_status()
            member.save(ignore_permissions=True)

def on_membership_submit(doc, method=None):
    """
    Handler for when a membership is submitted
    This is referenced in hooks.py > doc_events
    """
    # The main logic is already in doc.on_submit()
    pass

def on_membership_cancel(doc, method=None):
    """
    Handler for when a membership is cancelled
    This is referenced in hooks.py > doc_events
    """
    # The main logic is already in doc.on_cancel()
    pass

def update_membership_from_subscription(doc, method=None):
    """
    Handler for when a subscription is updated
    Updates the linked membership
    This is referenced in hooks.py > doc_events
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
        membership = frappe.get_doc("Membership", membership_data.name)
        
        # Update membership status based on subscription
        if doc.status == "Active":
            if membership.status != "Active":
                membership.status = "Active"
                membership.save(ignore_permissions=True)
        elif doc.status == "Cancelled":
            if membership.status != "Cancelled":
                membership.status = "Cancelled"
                membership.save(ignore_permissions=True)
        elif doc.status == "Unpaid":
            if membership.status != "Pending":
                membership.status = "Pending" 
                membership.save(ignore_permissions=True)

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
def renew_membership(membership_name):
    """Renew a membership and return the new membership doc"""
    membership = frappe.get_doc("Membership", membership_name)
    return membership.renew_membership()
@frappe.whitelist()
def create_subscription(membership_name, options=None):
    """Create a subscription from a membership with additional options"""
    try:
        frappe.logger().debug(f"create_subscription called with membership_name={membership_name}, options={options}")
        
        # Parse options if provided as string
        if options and isinstance(options, str):
            import json
            try:
                options = json.loads(options)
                frappe.logger().debug(f"Parsed options from string: {options}")
            except json.JSONDecodeError:
                frappe.logger().error(f"Error parsing options JSON: {options}")
                options = {
                    'follow_calendar_months': 1,
                    'generate_invoice_at_period_start': 1,
                    'generate_new_invoices_past_due_date': 1,
                    'submit_invoice': 1,
                    'days_until_due': 30
                }
                frappe.logger().debug(f"Using default options instead: {options}")
        elif not options:
            options = {
                'follow_calendar_months': 1,
                'generate_invoice_at_period_start': 1,
                'generate_new_invoices_past_due_date': 1,
                'submit_invoice': 1,
                'days_until_due': 30
            }
            frappe.logger().debug(f"No options provided, using defaults: {options}")
        
        # Get the membership    
        membership = frappe.get_doc("Membership", membership_name)
        
        # Check if subscription already exists
        if membership.subscription:
            frappe.logger().warning(f"Membership {membership_name} already has subscription {membership.subscription}")
            return membership.subscription
            
        # Ensure subscription plan is set
        if not membership.subscription_plan:
            frappe.logger().error(f"Membership {membership_name} has no subscription plan set")
            frappe.throw(_("Subscription Plan is required to create a subscription"))
            
        # Call the create_subscription_directly function instead of a method on the membership object
        result = create_subscription_directly(membership, options)
        frappe.logger().debug(f"create_subscription_directly returned: {result}")
        return result
    except Exception as e:
        frappe.logger().error(f"Error in create_subscription: {str(e)}", exc_info=True)
        raise

def create_subscription_directly(membership, options=None):
    """Create an ERPNext subscription for this membership with additional options"""
    import frappe
    from frappe import _
    from frappe.utils import getdate, add_days, add_months, nowdate
    
    # Debug the function call
    frappe.logger().debug(f"create_subscription_directly called with options={options}")
    
    # Initialize options with defaults if none provided
    if not options:
        options = {}
    
    # Check if member has a customer
    member = frappe.get_doc("Member", membership.member)
    
    if not member.customer:
        # Create a customer for this member
        member.create_customer()
        member.reload()
    
    if not member.customer:
        frappe.throw(_("Please create a customer for this member first"))
    
    try:
        # Get subscription plan details
        if not membership.subscription_plan:
            frappe.throw(_("Subscription Plan is required to create a subscription"))
        
        # Get plan details
        plan = frappe.get_doc("Subscription Plan", membership.subscription_plan)
        
        # Create subscription with minimal required fields
        subscription = frappe.new_doc("Subscription")
        
        # Set basic subscription properties
        subscription.party_type = "Customer"
        subscription.party = member.customer
        subscription.start_date = getdate(membership.start_date)
        
        # Set the end date if defined in membership
        if membership.end_date:
            subscription.end_date = getdate(membership.end_date)
        
        # Set billing interval properties based on plan
        # These must be set properly for ERPNext's subscription logic to work
        # Default to monthly if not specified
        interval_unit = getattr(plan, 'billing_interval', getattr(plan, 'billing_interval_unit', 'Month'))
        interval_count = getattr(plan, 'billing_interval_count', getattr(plan, 'billing_interval_value', 1))
        
        subscription.billing_interval = interval_unit
        subscription.billing_interval_count = interval_count
        
        # Set current invoice dates - this is critical for ERPNext's subscription handling
        subscription.current_invoice_start = getdate(membership.start_date)
        
        # Calculate current invoice end based on start date and billing interval
        if interval_unit == "Day":
            invoice_end = add_days(subscription.current_invoice_start, interval_count)
        elif interval_unit == "Week":
            invoice_end = add_days(subscription.current_invoice_start, interval_count * 7)
        elif interval_unit == "Month":
            invoice_end = add_months(subscription.current_invoice_start, interval_count)
        elif interval_unit == "Year":
            invoice_end = add_months(subscription.current_invoice_start, interval_count * 12)
        else:
            # Default to monthly
            invoice_end = add_months(subscription.current_invoice_start, 1)
            
        # Adjust for calendar months if requested
        if options.get('follow_calendar_months'):
            # If follow_calendar_months is enabled, adjust the end date to end of month
            invoice_end = getdate(invoice_end)
            invoice_end = getdate(f"{invoice_end.year}-{invoice_end.month}-{frappe.utils.get_last_day(invoice_end)}")
        
        subscription.current_invoice_end = invoice_end
        subscription.next_billing_date = add_days(invoice_end, 1)
        
        # Set additional options requested
        subscription.follow_calendar_months = 1 if options.get('follow_calendar_months') else 0
        subscription.generate_invoice_at_period_start = 1 if options.get('generate_invoice_at_period_start') else 0
        subscription.generate_new_invoices_past_due_date = 1 if options.get('generate_new_invoices_past_due_date') else 0
        subscription.submit_invoice = 1 if options.get('submit_invoice') else 0
        
        if options.get('days_until_due'):
            subscription.days_until_due = options.get('days_until_due')
        
        # Add plans table entry
        subscription.append("plans", {
            "subscription_plan": membership.subscription_plan,
            "qty": 1
        })
        
        # For debugging
        frappe.logger().debug(f"About to insert subscription with fields:")
        frappe.logger().debug(f"- start_date: {subscription.start_date}")
        frappe.logger().debug(f"- billing_interval: {subscription.billing_interval}")
        frappe.logger().debug(f"- billing_interval_count: {subscription.billing_interval_count}")
        frappe.logger().debug(f"- current_invoice_start: {subscription.current_invoice_start}")
        frappe.logger().debug(f"- current_invoice_end: {subscription.current_invoice_end}")
        frappe.logger().debug(f"- next_billing_date: {subscription.next_billing_date}")
        
        # Insert the subscription
        subscription.insert(ignore_permissions=True)
        
        # Log success
        frappe.logger().debug(f"Subscription inserted with ID: {subscription.name}")
        
        # Now submit the subscription
        subscription.submit()
        
        # Link subscription to membership
        membership.subscription = subscription.name
        membership.save()
        
        frappe.msgprint(_("Subscription {0} created successfully").format(subscription.name))
        return subscription.name
        
    except Exception as e:
        error_details = f"Error details: Subscription Plan: {membership.subscription_plan}"
        frappe.log_error(f"Error creating subscription: {str(e)}\n{error_details}", 
                      "Membership Subscription Error")
        frappe.throw(_("Error creating subscription: {0}").format(str(e)))
