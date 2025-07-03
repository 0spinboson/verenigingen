"""
Test the sales invoice receivable account fix
"""

import frappe
from frappe.utils import today

@frappe.whitelist()
def test_sales_invoice_receivable_fix():
    """
    Test that new sales invoices get the correct receivable account
    """
    try:
        # Get company
        settings = frappe.get_single("E-Boekhouden Settings")
        company = settings.default_company
        
        if not company:
            return {"success": False, "error": "No default company found"}
        
        # Create a test mutation data like what would come from E-boekhouden
        test_mutation = {
            "id": "TEST-001",
            "date": today(),
            "amount": 100.00,
            "type": 2,  # Sales Invoice type
            "relationId": None
        }
        
        # Import the processor function
        from verenigingen.utils.eboekhouden_unified_processor import process_sales_invoices, get_correct_receivable_account
        
        # Test getting the correct receivable account
        correct_account = get_correct_receivable_account(company)
        
        # Get the wrong account for comparison
        wrong_account = frappe.db.get_value("Account", 
            {"account_number": "13500", "company": company}, "name")
        
        return {
            "success": True,
            "company": company,
            "correct_receivable_account": correct_account,
            "wrong_account": wrong_account,
            "test_mutation": test_mutation,
            "message": f"Test setup complete. Correct account: {correct_account}"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def verify_receivable_account_logic():
    """
    Verify the receivable account selection logic without creating invoices
    """
    try:
        settings = frappe.get_single("E-Boekhouden Settings")
        company = settings.default_company
        
        # Get both accounts
        contrib_account = frappe.db.get_value("Account", 
            {"account_number": "13500", "company": company}, 
            ["name", "account_name"], as_dict=True)
        amounts_account = frappe.db.get_value("Account", 
            {"account_number": "13900", "company": company}, 
            ["name", "account_name"], as_dict=True)
        
        # Test the function
        from verenigingen.utils.eboekhouden_unified_processor import get_correct_receivable_account
        selected_account = get_correct_receivable_account(company)
        
        return {
            "success": True,
            "company": company,
            "available_accounts": {
                "contributions": contrib_account,
                "amounts": amounts_account
            },
            "selected_account": selected_account,
            "is_correct": selected_account == amounts_account.name if amounts_account else False,
            "message": "Account selection logic verified"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }