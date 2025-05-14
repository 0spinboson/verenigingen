import frappe
from frappe import _
import erpnext
from functools import wraps

def setup_subscription_override():
    """
    Set up monkey patching for ERPNext's Subscription module
    Call this from hooks.py on_app_init event or in a patch
    """
    try:
        # Import the original module
        import erpnext.accounts.doctype.subscription.subscription as erpnext_subscription
        
        # Store original methods
        original_process = erpnext_subscription.Subscription.process
        
        # Create wrapped versions that handle the error case
        @wraps(original_process)
        def process_wrapper(self, *args, **kwargs):
            try:
                # First try the standard method
                return original_process(self, *args, **kwargs)
            except frappe.ValidationError as e:
                error_msg = str(e)
                # Check if it's the date change error
                if "Not allowed to change **Current Invoice Start Date**" in error_msg:
                    # Use our custom handler
                    from verenigingen.verenigingen.subscription_handler import SubscriptionHandler
                    handler = SubscriptionHandler(self.name)
                    if handler.process_subscription():
                        return True
                    # If our handler failed, re-raise the error
                    raise
                else:
                    # For other validation errors, re-raise
                    raise
        
        # Apply the monkey patch
        erpnext_subscription.Subscription.process = process_wrapper
        
        # Log successful setup
        frappe.logger().info("Subscription override successfully set up")
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
