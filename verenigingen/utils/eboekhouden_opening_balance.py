"""
E-Boekhouden Opening Balance for Migration

Create proper opening balance journal entry with correct debit/credit sides
"""

import frappe
from frappe import _
import json
from datetime import datetime


@frappe.whitelist()
def get_proper_opening_balance(year=2019):
    """
    Get proper opening balance for migration
    
    Since the API returns net positions, we need to properly classify them
    into debit and credit entries for the opening balance journal entry.
    
    The total should be €112,365.14 on each side.
    """
    
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        from verenigingen.utils.eboekhouden_migration_config import PAYMENT_ACCOUNT_CONFIG
        
        api = EBoekhoudenAPI()
        
        # Get closing balance mutations for previous year
        closing_date = f"{year - 1}-12-31"
        
        params = {
            "dateFrom": closing_date,
            "dateTo": closing_date,
            "pageSize": 1000
        }
        
        mutations_result = api.get_mutations(params)
        if not mutations_result["success"]:
            return {"success": False, "error": "Failed to get mutations"}
        
        mutations_data = json.loads(mutations_result["data"])
        closing_mutations = mutations_data.get("items", [])
        
        # Get accounts for reference
        accounts_result = api.get_chart_of_accounts()
        accounts_data = json.loads(accounts_result["data"])
        accounts = accounts_data.get("items", [])
        account_lookup = {str(acc["id"]): acc for acc in accounts}
        
        # Process closing balances into proper debit/credit entries
        opening_entries = []
        total_debit = 0
        total_credit = 0
        
        # For opening balance, we need to determine which accounts go to debit vs credit
        # Based on the net position and account nature
        
        for mutation in closing_mutations:
            ledger_id = str(mutation.get("ledgerId", ""))
            amount = float(mutation.get("amount", 0))
            
            if amount == 0:
                continue
            
            account = account_lookup.get(ledger_id, {})
            code = account.get("code", "")
            name = account.get("description", "")
            
            # Skip if no account info
            if not code:
                continue
            
            # For opening balance journal entry:
            # Assets (0-1xxx) with positive balance -> DEBIT
            # Liabilities (2-4xxx) with positive balance -> CREDIT (but shown as negative in closing)
            # Equity (5xxx) -> Usually CREDIT side
            # Income (8xxx) -> Not in opening balance (closed to equity)
            # Expenses (4-7xxx) -> Not in opening balance (closed to equity)
            
            entry = {
                "account_code": code,
                "account_name": name,
                "net_amount": amount,
                "debit": 0,
                "credit": 0
            }
            
            # Assets and certain other accounts
            if code.startswith(('0', '1', '3')):
                # These are asset accounts - positive balance goes to debit
                if amount > 0:
                    entry["debit"] = amount
                    total_debit += amount
                else:
                    entry["credit"] = abs(amount)
                    total_credit += abs(amount)
            
            # Liabilities and Equity
            elif code.startswith(('2', '4', '5')):
                # For liabilities/equity, we might need the opposite
                # But since we only see positive amounts, these might need to go to credit
                # However, the data shows positive amounts for equity accounts (05xxx)
                # which suggests these are already showing the debit side
                if code.startswith('5'):  # Equity accounts showing as positive = debit balance
                    entry["debit"] = amount
                    total_debit += amount
                else:
                    entry["credit"] = amount
                    total_credit += amount
            
            # Income/Expense accounts shouldn't appear in opening balance
            elif code.startswith(('6', '7', '8', '9')):
                continue  # Skip these
            
            opening_entries.append(entry)
        
        # The difference needs to be balanced
        # Expected total is €112,365.14 on each side
        expected_total = 112365.14
        
        # If we only have debits, we need to add the credit side
        # This is likely the equity/liability accounts that balance the assets
        if total_credit == 0 and total_debit > 0:
            # We need to add a balancing credit entry
            # This would typically be retained earnings or similar equity account
            balancing_amount = total_debit
            
            # Look for an appropriate equity account to use for balancing
            equity_account = None
            for acc in accounts:
                code = acc.get("code", "")
                if code.startswith("05"):  # Equity account
                    # But we already have these as debits, so we need a different approach
                    pass
            
            # Add note about balancing
            opening_entries.append({
                "account_code": "BALANCE",
                "account_name": "Balancing entry needed - likely equity/liability accounts",
                "net_amount": -balancing_amount,
                "debit": 0,
                "credit": balancing_amount
            })
            total_credit = balancing_amount
        
        return {
            "success": True,
            "year": year,
            "closing_date": closing_date,
            "opening_entries": opening_entries,
            "summary": {
                "total_accounts": len(opening_entries),
                "total_debit": round(total_debit, 2),
                "total_credit": round(total_credit, 2),
                "difference": round(total_debit - total_credit, 2),
                "expected_total": expected_total,
                "note": "The closing mutations appear to show only one side of the balance sheet. For a proper opening balance, you need both debit and credit sides totaling €112,365.14"
            },
            "recommendation": "The E-Boekhouden API seems to return only the asset/debit side balances. For a complete opening balance, you may need to manually add the credit side (liabilities and equity) or check if there's a different API endpoint for complete trial balance."
        }
        
    except Exception as e:
        import traceback
        frappe.log_error(traceback.format_exc(), "Opening Balance Error")
        return {"success": False, "error": str(e)}