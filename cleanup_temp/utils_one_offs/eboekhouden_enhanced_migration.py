"""
Enhanced E-Boekhouden Migration for Proper Payment Handling

This module extends the basic migration to properly identify and create
Payment Entries for bank and cash transactions.
"""

import frappe
from frappe import _
from frappe.utils import getdate, flt
import json


@frappe.whitelist()
def test_enhanced_migration(limit=5):
    """
    Test the enhanced migration logic by analyzing recent transactions
    Shows how transactions would be categorized
    """
    
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        # Get API instance
        api = EBoekhoudenAPI()
        
        # Get recent transactions
        from datetime import datetime, timedelta
        today = datetime.now()
        last_month = today - timedelta(days=30)
        
        params = {
            "dateFrom": last_month.strftime("%Y-%m-%d"),
            "dateTo": today.strftime("%Y-%m-%d")
        }
        
        # Get transactions
        trans_result = api.get_mutations(params)
        if not trans_result["success"]:
            return {"success": False, "error": "Failed to get transactions"}
        
        transactions = json.loads(trans_result["data"]).get("items", [])[:limit]
        
        # Get accounts for analysis
        accounts_result = api.get_chart_of_accounts()
        if not accounts_result["success"]:
            return {"success": False, "error": "Failed to get accounts"}
        
        accounts = json.loads(accounts_result["data"]).get("items", [])
        
        # Build account lookup
        account_lookup = {str(acc["id"]): acc for acc in accounts}
        
        # Analyze transactions
        analysis = []
        for trans in transactions:
            ledger_id = str(trans.get("ledgerId", ""))
            account = account_lookup.get(ledger_id, {})
            account_code = account.get("code", "")
            
            # Determine transaction type
            is_bank = account_code.startswith("15")
            is_cash = account_code.startswith("16")
            is_payment = is_bank or is_cash
            
            trans_analysis = {
                "date": trans.get("date"),
                "description": trans.get("description"),
                "amount": trans.get("amount"),
                "account_code": account_code,
                "account_name": account.get("description", ""),
                "is_payment_account": is_payment,
                "payment_type": "Bank" if is_bank else "Cash" if is_cash else "Other",
                "has_relation": bool(trans.get("relationId")),
                "relation_id": trans.get("relationId"),
                "invoice_number": trans.get("invoiceNumber"),
                "suggested_entry_type": "Payment Entry" if is_payment and trans.get("relationId") else "Journal Entry"
            }
            
            analysis.append(trans_analysis)
        
        return {
            "success": True,
            "transactions_analyzed": len(analysis),
            "analysis": analysis,
            "summary": {
                "payment_entries": sum(1 for a in analysis if a["suggested_entry_type"] == "Payment Entry"),
                "journal_entries": sum(1 for a in analysis if a["suggested_entry_type"] == "Journal Entry")
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Enhanced migration test error: {str(e)}")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def get_migration_settings_recommendation():
    """
    Analyze E-Boekhouden data and provide recommendations for migration settings
    """
    
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        api = EBoekhoudenAPI()
        
        # Get accounts
        accounts_result = api.get_chart_of_accounts()
        if not accounts_result["success"]:
            return {"success": False, "error": "Failed to get accounts"}
        
        accounts = json.loads(accounts_result["data"]).get("items", [])
        
        # Analyze account structure
        recommendations = {
            "bank_accounts": [],
            "cash_accounts": [],
            "receivable_accounts": [],
            "payable_accounts": [],
            "payment_related_accounts": []
        }
        
        for account in accounts:
            code = account.get("code", "")
            name = account.get("description", "")
            
            if code.startswith("15"):
                recommendations["bank_accounts"].append(f"{code} - {name}")
                recommendations["payment_related_accounts"].append(code)
            elif code.startswith("16"):
                recommendations["cash_accounts"].append(f"{code} - {name}")
                recommendations["payment_related_accounts"].append(code)
            elif code.startswith("13"):
                recommendations["receivable_accounts"].append(f"{code} - {name}")
            elif code.startswith("44"):
                recommendations["payable_accounts"].append(f"{code} - {name}")
        
        return {
            "success": True,
            "recommendations": recommendations,
            "summary": {
                "total_accounts": len(accounts),
                "bank_accounts_found": len(recommendations["bank_accounts"]),
                "cash_accounts_found": len(recommendations["cash_accounts"]),
                "payment_accounts_total": len(recommendations["payment_related_accounts"])
            },
            "migration_rules": {
                "payment_entry_rules": [
                    "Transactions with account codes starting with 15 (Bank) + relation = Customer/Supplier Payment",
                    "Transactions with account codes starting with 16 (Cash) + relation = Cash Payment/Receipt",
                    "Bank/Cash transactions without relations = Bank/Cash Transfer (Journal Entry)"
                ],
                "journal_entry_rules": [
                    "All other transactions",
                    "Adjusting entries",
                    "Non-payment related entries"
                ]
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Migration settings recommendation error: {str(e)}")
        return {"success": False, "error": str(e)}