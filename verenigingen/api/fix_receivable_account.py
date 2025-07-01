import frappe
from frappe import _

@frappe.whitelist()
def fix_receivable_account():
    """Fix the account type for the default receivable account"""
    
    company = frappe.db.get_value("E-Boekhouden Settings", None, "default_company")
    default_receivable = frappe.db.get_value("Company", company, "default_receivable_account")
    
    if default_receivable:
        # Update the account type
        frappe.db.set_value("Account", default_receivable, "account_type", "Receivable")
        frappe.db.commit()
        
        return {
            "success": True,
            "message": f"Updated account {default_receivable} to Receivable type"
        }
    else:
        # Create a new receivable account
        receivable_account = frappe.get_doc({
            "doctype": "Account",
            "account_name": "Debtors",
            "company": company,
            "parent_account": frappe.db.get_value("Account", {
                "company": company,
                "root_type": "Asset",
                "is_group": 1
            }, "name"),
            "account_type": "Receivable",
            "is_group": 0
        })
        receivable_account.insert(ignore_permissions=True)
        
        # Set as default
        frappe.db.set_value("Company", company, "default_receivable_account", receivable_account.name)
        frappe.db.commit()
        
        return {
            "success": True,
            "message": f"Created new receivable account {receivable_account.name}"
        }