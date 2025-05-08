import frappe
from frappe import _

def handle_tax_exemption():
    """
    Handle tax exemption setting and create 0% tax template if needed
    """
    settings = frappe.get_single("Verenigingen Settings")
    if not settings.get("tax_exempt_for_contributions"):
        return
    
    # Check for existing 0% tax template
    tax_template_name = "Tax Exempt - 0%"
    if frappe.db.exists("Sales Taxes and Charges Template", tax_template_name):
        # Template already exists, no need to create it again
        return
    
    # Create the tax template only if it doesn't exist
    create_tax_exempt_template(tax_template_name)
    
    frappe.msgprint(_("Created tax exempt template: {0}").format(tax_template_name))

def create_tax_exempt_template(template_name):
    """Create a 0% tax template for tax-exempt contributions and donations"""
    try:
        # Get company
        settings = frappe.get_single("Verenigingen Settings")
        company = settings.company
        if not company:
            company = frappe.defaults.get_global_default('company')
        
        if not company:
            frappe.msgprint(_("No company found, skipping tax template creation"))
            return
        
        # Create tax template
        tax_template = frappe.new_doc("Sales Taxes and Charges Template")
        tax_template.title = template_name
        tax_template.name = template_name
        tax_template.is_default = 0
        tax_template.company = company
        
        # Add the 0% tax row
        tax_template.append("taxes", {
            "charge_type": "On Net Total",
            "account_head": get_tax_account(company),
            "description": _("Tax Exempt - 0%"),
            "rate": 0
        })
        
        tax_template.save()
    except Exception as e:
        frappe.log_error(f"Error creating tax exempt template: {str(e)}", 
                       "Tax Exemption Handler Error")

def get_tax_account(company):
    """Get appropriate tax account for the company"""
    # Try to find a VAT/BTW account
    tax_accounts = frappe.get_all(
        "Account",
        filters={
            "company": company,
            "account_type": "Tax",
            "is_group": 0
        },
        fields=["name"]
    )
    
    if tax_accounts:
        return tax_accounts[0].name
    
    # If no tax account found, use a default expense account
    expense_accounts = frappe.get_all(
        "Account",
        filters={
            "company": company,
            "root_type": "Expense",
            "is_group": 0
        },
        fields=["name"],
        limit=1
    )
    
    if expense_accounts:
        return expense_accounts[0].name
    
    # If still no account found, throw an error
    frappe.throw(_("No appropriate tax or expense account found for company {0}").format(company))

# Hook this function to verenigingen_settings.py
def on_update_verenigingen_settings(doc, method=None):
    """Hook to handle tax exemption setting when Verenigingen Settings is updated"""
    handle_tax_exemption()
