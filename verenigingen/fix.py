import frappe
from frappe.utils import getdate, add_days, add_months, now, nowdate

def fix_subscription_correctly(subscription_name="ACC-SUB-2025-00013"):
    """
    Fixed version of the subscription fix script that addresses both:
    1. Date consistency issue
    2. Database schema mismatches
    """
    try:
        # Confirm that the subscription exists
        if not frappe.db.exists("Subscription", subscription_name):
            print(f"Subscription {subscription_name} not found")
            return False
            
        # Get current subscription details
        subscription = frappe.get_doc("Subscription", subscription_name)
        print(f"Current subscription dates: {subscription.current_invoice_start} to {subscription.current_invoice_end}")
        
        # Create invoice for current period
        try:
            invoice = create_invoice_for_subscription(subscription)
            if not invoice:
                print("Failed to create invoice")
                return False
                
            print(f"Successfully created invoice: {invoice}")
            
            # Update the subscription to new period correctly
            # New period is 1 day after current_invoice_end to current_invoice_end + 12 months - 1 day
            next_start = add_days(getdate(subscription.current_invoice_end), 1)
            next_end = add_days(add_months(next_start, 12), -1)  # Make it inclusive (end on the day before the anniversary)
            
            print(f"New dates will be: {next_start} to {next_end}")
            
            # Update subscription directly in the database to avoid validation errors
            frappe.db.set_value(
                "Subscription", 
                subscription_name,
                {
                    "current_invoice_start": next_start,
                    "current_invoice_end": next_end
                },
                update_modified=True
            )
            
            # Link the invoice to the subscription correctly
            link_invoice_to_subscription(subscription, invoice)
            
            frappe.db.commit()
            print(f"Successfully updated subscription {subscription_name} with new dates")
            return True
            
        except Exception as e:
            print(f"Error creating invoice: {str(e)}")
            frappe.db.rollback()
            return False
            
    except Exception as e:
        print(f"Error fixing subscription: {str(e)}")
        frappe.db.rollback()
        return False

def create_invoice_for_subscription(subscription):
    """Create a sales invoice for the subscription period"""
    try:
        # Get subscription plans
        plans = frappe.get_all(
            "Subscription Plan Detail",
            filters={"parent": subscription.name},
            fields=["plan", "qty"]
        )
        
        if not plans:
            print("No subscription plans found")
            return None
            
        # Create invoice
        invoice = frappe.new_doc("Sales Invoice")
        invoice.customer = subscription.party if subscription.party_type == "Customer" else None
        invoice.subscription = subscription.name
        invoice.posting_date = nowdate()
        
        # Set company
        invoice.company = subscription.company
        
        # Add items
        for plan_data in plans:
            plan = frappe.get_doc("Subscription Plan", plan_data.plan)
            
            invoice.append("items", {
                "item_code": plan.item,
                "qty": plan_data.qty,
                "rate": plan.cost,
                "description": f"{subscription.name}: {subscription.current_invoice_start} to {subscription.current_invoice_end}"
            })
            
        # Set cost center if specified
        if subscription.cost_center:
            for item in invoice.items:
                item.cost_center = subscription.cost_center
                
        # Set due date if days_until_due is set
        if subscription.days_until_due:
            invoice.due_date = add_days(invoice.posting_date, subscription.days_until_due)
            
        # Save and submit
        invoice.set_missing_values()
        invoice.flags.ignore_permissions = True
        invoice.save()
        
        if subscription.submit_invoice:
            invoice.submit()
            
        return invoice.name
        
    except Exception as e:
        print(f"Error creating invoice: {str(e)}")
        raise

def link_invoice_to_subscription(subscription, invoice_name):
    """
    Link an invoice to a subscription by adding an entry to the child table
    """
    try:
        # First check the actual schema of the Subscription Invoice table
        table_columns = frappe.db.sql("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'tabSubscription Invoice' 
            ORDER BY ordinal_position
        """, as_dict=1)
        
        column_names = [col.column_name for col in table_columns]
        print(f"Actual columns in tabSubscription Invoice: {column_names}")
        
        # Check if invoice already exists in subscription
        existing = frappe.db.exists(
            "Subscription Invoice", 
            {"parent": subscription.name, "invoice": invoice_name}
        )
        
        if existing:
            print(f"Invoice {invoice_name} already linked to subscription {subscription.name}")
            return
            
        # Create a new child table entry
        invoice_link = frappe.new_doc("Subscription Invoice")
        invoice_link.parent = subscription.name
        invoice_link.parenttype = "Subscription"
        invoice_link.parentfield = "invoices"
        invoice_link.invoice = invoice_name
        invoice_link.document_type = "Sales Invoice"
        
        # These fields are always present in standard doctypes
        invoice_link.owner = frappe.session.user
        invoice_link.modified_by = frappe.session.user
        invoice_link.docstatus = 1
        
        # Save using standard API which handles schema correctly
        invoice_link.insert()
        print(f"Successfully linked invoice {invoice_name} to subscription {subscription.name}")
        
    except Exception as e:
        print(f"Error linking invoice to subscription: {str(e)}")
        raise

# To execute this from the bench console:
# bench --site your_site_name execute vereiningen.fixes.fix_subscription_correctly
