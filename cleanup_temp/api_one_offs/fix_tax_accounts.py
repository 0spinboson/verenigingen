import frappe
from frappe import _

@frappe.whitelist()
def fix_tax_accounts():
    """Fix accounts that were incorrectly marked as Receivable when they should be Tax"""
    
    company = frappe.db.get_value("E-Boekhouden Settings", None, "default_company")
    
    # Tax account patterns
    tax_accounts = [
        "1500",  # BTW af te dragen 21%
        "1510",  # BTW af te dragen 6%
        "1520",  # BTW af te dragen overig
        "1530",  # BTW te vorderen
        "1540"   # BTW R/C
    ]
    
    fixed = []
    
    for account_code in tax_accounts:
        # Find account
        account = frappe.db.get_value("Account", {
            "account_number": account_code,
            "company": company
        }, ["name", "account_type"], as_dict=True)
        
        if not account:
            # Try by name pattern
            account = frappe.db.get_value("Account", {
                "name": ["like", f"{account_code}%"],
                "company": company
            }, ["name", "account_type"], as_dict=True)
        
        if account and account.account_type != "Tax":
            frappe.db.set_value("Account", account.name, "account_type", "Tax")
            fixed.append({
                "account": account.name,
                "code": account_code,
                "changed_to": "Tax"
            })
    
    frappe.db.commit()
    
    return {
        "fixed": fixed,
        "total": len(fixed)
    }