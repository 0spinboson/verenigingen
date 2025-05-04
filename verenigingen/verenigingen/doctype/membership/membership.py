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
            
        # Save subscription
        subscription.flags.ignore_mandatory = True
        subscription.insert(ignore_permissions=True)
        subscription.submit()
        
        # Link subscription to membership
        self.subscription = subscription.name
        self.save()
        
        frappe.msgprint(_("Subscription {0} created successfully").format(subscription.name))
        return subscription.name
        
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
