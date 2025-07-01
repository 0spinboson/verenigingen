import frappe
from frappe import _

@frappe.whitelist()
def check_receivable_accounts():
    """Check available receivable accounts"""
    
    company = frappe.db.get_value("E-Boekhouden Settings", None, "default_company")
    
    # Get default receivable account from Company
    default_receivable = frappe.db.get_value("Company", company, "default_receivable_account")
    
    # Get all receivable accounts
    receivable_accounts = frappe.get_all("Account", 
        filters={
            "company": company,
            "account_type": "Receivable",
            "is_group": 0
        },
        fields=["name", "account_name", "account_number"])
    
    # Check if the problematic account exists
    account_13500 = frappe.db.get_value("Account", 
        {"name": "13500 - Te ontvangen contributies - RSP"}, 
        ["account_type", "is_group"], 
        as_dict=True)
    
    return {
        "company": company,
        "default_receivable": default_receivable,
        "receivable_accounts": receivable_accounts,
        "account_13500": account_13500
    }