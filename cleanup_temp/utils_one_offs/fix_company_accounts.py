"""
Fix company account settings for E-Boekhouden migration
"""

import frappe

@frappe.whitelist()
def fix_company_accounts():
    """Set required default accounts for company"""
    try:
        company = "R S P"
        
        # Check if stock received but not billed account exists
        stock_account = frappe.db.get_value("Account", {
            "company": company,
            "account_name": ["like", "%Stock Received%"],
            "is_group": 0
        }, "name")
        
        if not stock_account:
            # Create the account
            stock_account = frappe.new_doc("Account")
            stock_account.account_name = "Stock Received But Not Billed"
            stock_account.company = company
            stock_account.parent_account = frappe.db.get_value("Account", {
                "company": company,
                "root_type": "Liability",
                "is_group": 1
            }, "name")
            stock_account.account_type = "Stock Received But Not Billed"
            stock_account.is_group = 0
            stock_account.insert(ignore_permissions=True)
            stock_account = stock_account.name
        
        # Update company
        frappe.db.set_value("Company", company, "stock_received_but_not_billed", stock_account)
        frappe.db.commit()
        
        return {"success": True, "message": f"Set stock received but not billed account to: {stock_account}"}
        
    except Exception as e:
        frappe.log_error(f"Failed to fix company accounts: {str(e)}")
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    print(fix_company_accounts())