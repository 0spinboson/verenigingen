import frappe

@frappe.whitelist()
def check_receivable_accounts():
    """Check current receivable accounts configuration"""
    try:
        # Get all receivable accounts
        accounts = frappe.db.get_all('Account', 
            filters={'company': 'Ned Ver Vegan', 'account_type': 'Receivable'}, 
            fields=['name', 'account_name', 'account_number']
        )
        
        # Check default receivable account
        company_doc = frappe.get_doc("Company", "Ned Ver Vegan")
        default_receivable = getattr(company_doc, 'default_receivable_account', 'Not set')
        
        # Check specific accounts
        acc_13500 = frappe.db.get_value("Account", 
            {"account_number": "13500", "company": "Ned Ver Vegan"}, 
            ["name", "account_name"], as_dict=True)
        acc_13900 = frappe.db.get_value("Account", 
            {"account_number": "13900", "company": "Ned Ver Vegan"}, 
            ["name", "account_name"], as_dict=True)
        
        return {
            "success": True,
            "all_receivable_accounts": accounts,
            "default_receivable_account": default_receivable,
            "account_13500": acc_13500,
            "account_13900": acc_13900
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }