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
            subscription = frappe.get_doc("Subscription", self.subscription)
            if subscription.status != "Cancelled":
                subscription.cancel_subscription()
    
    def update_member_status(self):
        """Update the membership status in the Member document"""
        if self.member:
            member = frappe.get_doc("Member", self.member)
            member.save()  # This will trigger the update_membership_status method
            
    def create_subscription_from_membership(self):
        """Create an ERPNext subscription for this membership"""
        # Check if member has a customer
        member = frappe.get_doc("Member", self.member)
    
        if not member.customer:
        # Create a customer for this member
            member.create_customer()
            member.reload()
        
        if not member.customer:
            frappe.throw(_("Please create a customer for this member first"))
        
        # Create subscription
        subscription = frappe.new_doc("Subscription")
        subscription.party_type = "Customer"
        subscription.party = member.customer
    
        # Set dates
        subscription.start_date = self.start_date
        subscription.end_date = self.end_date
    
        # Add subscription plan
        if not self.subscription_plan:
            frappe.throw(_("Subscription Plan is required to create a subscription"))
        
        plan_doc = frappe.get_doc("Subscription Plan", self.subscription_plan)

        # Explicitly set billing cycle information
        # This is critical to avoid the NoneType error
        if hasattr(plan_doc, 'billing_interval'):
            subscription.billing_interval = plan_doc.billing_interval
            subscription.billing_interval_count = plan_doc.billing_interval_count or 1
        else:
            # Default billing information based on membership duration
            if self.end_date and self.start_date:
                # Calculate months between start and end dates
                from dateutil.relativedelta import relativedelta
                start = getdate(self.start_date)
                end = getdate(self.end_date)
                diff = relativedelta(end, start)
                total_months = diff.years * 12 + diff.months
            
                if total_months == 0:
                    total_months = 1  # Minimum 1 month
                
                if total_months % 12 == 0 and total_months > 0:
                    # Annual billing
                    subscription.billing_interval = "Year"
                    subscription.billing_interval_count = total_months // 12
                else:
                    # Monthly billing
                    subscription.billing_interval = "Month"
                    subscription.billing_interval_count = total_months
            else:
                # Default to annual if no dates specified
                subscription.billing_interval = "Year"
                subscription.billing_interval_count = 1
    
        subscription_item = {
            "subscription_plan": self.subscription_plan,
            "qty": 1
        }
        subscription.append("plans", subscription_item)
    
        # Additional settings
        membership_type = frappe.get_doc("Membership Type", self.membership_type)
        if membership_type.allow_auto_renewal and self.auto_renew:
            subscription.generate_invoice_at_period_start = 1
            subscription.submit_invoice = 1
        
        # Save subscription - use ignore_permissions=True to bypass permissions
        subscription.flags.ignore_permissions = True
        subscription.flags.ignore_mandatory = True
    
        # Set billing cycle explicitly if needed
        # This addresses the NoneType error in add_to_date
        if not hasattr(subscription, 'billing_cycle_info') or not subscription.billing_cycle_info:
            # Set default billing cycle based on plan's billing interval
            if hasattr(plan_doc, 'billing_interval'):
                if plan_doc.billing_interval == 'Month':
                    subscription.billing_interval = 'Month'
                    subscription.billing_interval_count = 1
                elif plan_doc.billing_interval == 'Year':
                    subscription.billing_interval = 'Year'
                    subscription.billing_interval_count = 1
                else:
                    # Default to monthly if unknown
                    subscription.billing_interval = 'Month'
                    subscription.billing_interval_count = 1
    
        try:
            subscription.insert(ignore_permissions=True)
            subscription.submit()
        
            # Link subscription to membership
            self.subscription = subscription.name
            self.save()
        
            frappe.msgprint(_("Subscription {0} created successfully").format(subscription.name))
            return subscription.name
        except Exception as e:
            frappe.log_error(f"Error creating subscription: {str(e)}", "Membership Subscription Error")
            frappe.throw(_("Error creating subscription: {0}").format(str(e)))
        
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
def create_subscription(membership_name):
    """Create a subscription from a membership"""
    membership = frappe.get_doc("Membership", membership_name)
    return membership.create_subscription_from_membership()
        
@frappe.whitelist()
def renew_membership(membership_name):
    """Renew a membership and return the new membership doc"""
    membership = frappe.get_doc("Membership", membership_name)
    return membership.renew_membership()
