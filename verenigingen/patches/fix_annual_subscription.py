import frappe
from frappe import _

def process_annual_subscription(subscription_name):
    """
    Special handler for annual subscriptions to avoid the "Current Invoice Start Date" error
    """
    subscription = frappe.get_doc("Subscription", subscription_name)
    
    # Skip if not an annual subscription or if it's not active
    if subscription.status != "Active":
        return False
        
    # Verify if this is indeed an annual subscription
    is_annual = False
    if (subscription.billing_interval == "Year" and subscription.billing_interval_count == 1) or \
       (subscription.billing_interval == "Month" and subscription.billing_interval_count == 12):
        is_annual = True
    
    if not is_annual:
        return False
    
    # Get current dates
    current_start = subscription.current_invoice_start
    current_end = subscription.current_invoice_end
    
    # Check if we need to generate a new invoice (near the end date)
    today = frappe.utils.today()
    days_until_end = frappe.utils.date_diff(current_end, today)
    
    # If we're close to the end date or past it, generate invoice with temporary update
    if days_until_end <= 15 or days_until_end < 0:
        try:
            # Generate the invoice using temporary field manipulation
            with TempSubscriptionUpdate(subscription) as temp_sub:
                # Process subscription to generate invoice
                temp_sub.process()
            
            return True
        except Exception as e:
            frappe.log_error(f"Error processing annual subscription {subscription_name}: {str(e)}", 
                          "Annual Subscription Error")
            return False
            
    return False

class TempSubscriptionUpdate:
    """
    Context manager to temporarily update subscription fields safely
    """
    def __init__(self, subscription):
        self.subscription = subscription
        self.original_values = {
            'current_invoice_start': subscription.current_invoice_start,
            'current_invoice_end': subscription.current_invoice_end
        }
        
    def __enter__(self):
        # Store a backup of DB values
        self.db_values = frappe.db.get_value(
            "Subscription", 
            self.subscription.name, 
            ['current_invoice_start', 'current_invoice_end'],
            as_dict=1
        )
        
        # Temporarily update to allow invoice generation
        frappe.db.set_value(
            "Subscription",
            self.subscription.name,
            {
                'current_invoice_start': self.subscription.current_invoice_start,
                'current_invoice_end': self.subscription.current_invoice_end
            },
            update_modified=False
        )
        
        # Return the subscription for use within the context
        return self.subscription
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore original DB values
        frappe.db.set_value(
            "Subscription",
            self.subscription.name,
            {
                'current_invoice_start': self.db_values['current_invoice_start'],
                'current_invoice_end': self.db_values['current_invoice_end']
            },
            update_modified=False
        )
        
        # Refresh the document to reflect current DB state
        self.subscription.reload()
