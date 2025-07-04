"""
Test why all accounts are falling back to the same expense account
"""

import frappe
from frappe import _

@frappe.whitelist()
def test_fallback_account_logic():
    """Test the fallback account selection logic"""
    
    try:
        company = "Ned Ver Vegan"
        
        # Test the fallback query that's used in the import
        fallback_account = frappe.db.get_value("Account", {
            "company": company,
            "account_type": "Expense Account",
            "is_group": 0
        }, "name")
        
        # Get all expense accounts to see what's available
        all_expense_accounts = frappe.db.sql("""
            SELECT 
                name,
                account_name,
                account_number,
                account_type
            FROM `tabAccount`
            WHERE company = %s
            AND account_type = 'Expense Account'
            AND is_group = 0
            ORDER BY account_number
            LIMIT 20
        """, company, as_dict=True)
        
        # Test what create_invoice_line_for_tegenrekening returns
        from verenigingen.utils.smart_tegenrekening_mapper import create_invoice_line_for_tegenrekening
        
        # Test with various ledger IDs
        test_results = []
        test_ledgers = ["48010", "44009", "42000", "99998", None, ""]
        
        for ledger in test_ledgers:
            result = create_invoice_line_for_tegenrekening(
                tegenrekening_code=str(ledger) if ledger else None,
                amount=100,
                description="Test",
                transaction_type="purchase"
            )
            test_results.append({
                "ledger_id": ledger,
                "result": result
            })
        
        return {
            "success": True,
            "fallback_account_query_result": fallback_account,
            "available_expense_accounts": all_expense_accounts[:10],
            "test_results": test_results
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "traceback": frappe.get_traceback()
        }


@frappe.whitelist()
def check_actual_mutations():
    """Check what ledger IDs are actually in the mutations"""
    
    try:
        # Look at the debug logs to see what ledger_ids were used
        recent_logs = frappe.db.sql("""
            SELECT 
                name,
                error,
                creation
            FROM `tabError Log`
            WHERE method LIKE '%REST%'
            AND creation > '2025-01-01'
            ORDER BY creation DESC
            LIMIT 5
        """, as_dict=True)
        
        # Get a sample of different transactions to see ledger variety
        sample_transactions = frappe.db.sql("""
            SELECT DISTINCT
                pii.expense_account,
                COUNT(*) as count
            FROM `tabPurchase Invoice` pi
            JOIN `tabPurchase Invoice Item` pii ON pii.parent = pi.name
            WHERE pi.supplier = 'E-Boekhouden Import'
            AND pi.posting_date >= '2025-01-01'
            GROUP BY pii.expense_account
            ORDER BY count DESC
            LIMIT 10
        """, as_dict=True)
        
        return {
            "success": True,
            "recent_debug_logs": recent_logs,
            "expense_account_distribution": sample_transactions
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "traceback": frappe.get_traceback()
        }