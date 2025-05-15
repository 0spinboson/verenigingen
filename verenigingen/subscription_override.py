import frappe
from frappe import _
import erpnext
from functools import wraps

def setup_subscription_override():
    """
    Set up monkey patching for ERPNext's Subscription module
    Call this from hooks.py on_app_init event or in a patch
    """
    frappe.logger().info("Setting up subscription override")
    try:
        # Import the original module
        import erpnext.accounts.doctype.subscription.subscription as erpnext_subscription
        
        # Store original methods
        original_process = erpnext_subscription.Subscription.process
        original_cancel = erpnext_subscription.Subscription.cancel_subscription
        
        # Create wrapped versions that handle the error case
        @wraps(original_process)
        def process_wrapper(self, *args, **kwargs):
            try:
                # First try the standard method
                return original_process(self, *args, **kwargs)
            except frappe.ValidationError as e:
                error_msg = str(e)
                frappe.logger().info(f"Subscription validation error caught: {error_msg}")
                
                # More flexible pattern matching for error detection
                if "Current Invoice Start Date" in error_msg and "Not allowed to change" in error_msg:
                    frappe.logger().info(f"Handling Current Invoice Start Date error for subscription {self.name}")
                    # Use our custom handler
                    from verenigingen.subscription_handler import SubscriptionHandler
                    handler = SubscriptionHandler(self.name)
                    if handler.process_subscription():
                        frappe.logger().info(f"Successfully processed subscription {self.name} with custom handler")
                        return True
                    # If our handler failed, log and re-raise
                    frappe.logger().error(f"Custom handler failed for subscription {self.name}")
                    raise
                else:
                    # For other validation errors, re-raise
                    raise
            except Exception as e:
                frappe.logger().error(f"Unexpected error in subscription process override: {str(e)}")
                raise
        
        # Apply the monkey patches
        erpnext_subscription.Subscription.process = process_wrapper
        
        # Apply the cancel wrapper similarly with more flexible error matching
        @wraps(original_cancel)
        def cancel_wrapper(self):
            try:
                return original_cancel(self)
            except frappe.ValidationError as e:
                error_msg = str(e)
                
                # More flexible pattern matching
                if "Status" in error_msg and "Not allowed to change" in error_msg:
                    frappe.logger().info(f"Handling Status change error for subscription {self.name}")
                    self.db_set('status', 'Cancelled')
                    self.db_set('cancelation_date', frappe.utils.today())
                    
                    # Add to doctype log
                    frappe.get_doc({
                        "doctype": "Comment",
                        "comment_type": "Info",
                        "reference_doctype": self.doctype,
                        "reference_name": self.name,
                        "content": "Subscription cancelled via custom override"
                    }).insert(ignore_permissions=True)
                    
                    return True
                else:
                    raise
            except Exception as e:
                frappe.logger().error(f"Unexpected error in subscription cancel override: {str(e)}")
                raise
        
        erpnext_subscription.Subscription.cancel_subscription = cancel_wrapper
        
        # Log successful setup
        frappe.logger().info("Subscription override successfully applied")
        return True
        
    except Exception as e:
        frappe.log_error(f"Error setting up subscription override: {str(e)}", 
                      "Subscription Override Error")
        return False

def update_hooks():
    """
    Add our custom hooks to the app's hooks.py
    This is for documentation only - you'll need to manually add these to hooks.py
    """
    hooks_to_add = """
# Subscription handling
on_app_init = ["verenigingen.verenigingen.subscription_override.setup_subscription_override"]

# Schedule subscription processing
scheduler_events = {
    "daily": [
        # ... your existing daily jobs ...
        "verenigingen.verenigingen.subscription_handler.process_all_subscriptions"
    ]
}
"""
    return hooks_to_add

@frappe.whitelist()
def manual_override_setup():
    """
    Manually trigger the subscription override setup
    Useful for testing or if the app_init hook doesn't work
    """
    result = setup_subscription_override()
    if result:
        frappe.msgprint(_("Subscription override successfully set up"))
    else:
        frappe.msgprint(_("Failed to set up subscription override. Check error logs."))
    
    return result
