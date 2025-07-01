"""
E-Boekhouden Balance API Functions

Functions to retrieve account balances and trial balance data
"""

import frappe
from frappe import _
import json
from datetime import datetime


@frappe.whitelist()
def get_account_balances(date=None):
    """
    Get account balances from E-Boekhouden
    
    The API provides balance information through the mutation endpoint
    by getting transactions up to a specific date
    """
    
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        api = EBoekhoudenAPI()
        
        # If no date provided, use today
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        
        # First get all accounts
        accounts_result = api.get_chart_of_accounts()
        if not accounts_result["success"]:
            return {"success": False, "error": "Failed to get chart of accounts"}
        
        accounts_data = json.loads(accounts_result["data"])
        accounts = accounts_data.get("items", [])
        
        # Create account lookup
        account_lookup = {str(acc["id"]): acc for acc in accounts}
        
        # Get all mutations up to the specified date to calculate balances
        # This gives us the net effect on each account
        params = {
            "dateTo": date
        }
        
        mutations_result = api.get_mutations(params)
        if not mutations_result["success"]:
            return {"success": False, "error": "Failed to get mutations"}
        
        mutations_data = json.loads(mutations_result["data"])
        mutations = mutations_data.get("items", [])
        
        # Calculate balances by account
        account_balances = {}
        
        for mutation in mutations:
            ledger_id = str(mutation.get("ledgerId", ""))
            amount = float(mutation.get("amount", 0))
            
            if ledger_id not in account_balances:
                account_info = account_lookup.get(ledger_id, {})
                account_balances[ledger_id] = {
                    "account_code": account_info.get("code", ""),
                    "account_name": account_info.get("description", ""),
                    "balance": 0,
                    "debit_total": 0,
                    "credit_total": 0,
                    "transaction_count": 0
                }
            
            # E-Boekhouden typically uses positive for debit, negative for credit
            account_balances[ledger_id]["balance"] += amount
            
            if amount > 0:
                account_balances[ledger_id]["debit_total"] += amount
            else:
                account_balances[ledger_id]["credit_total"] += abs(amount)
                
            account_balances[ledger_id]["transaction_count"] += 1
        
        # Convert to list and add zero-balance accounts
        balance_list = []
        
        # Add accounts with transactions
        for ledger_id, balance_info in account_balances.items():
            balance_list.append(balance_info)
        
        # Add accounts without transactions (zero balance)
        for account in accounts:
            ledger_id = str(account.get("id", ""))
            if ledger_id not in account_balances:
                balance_list.append({
                    "account_code": account.get("code", ""),
                    "account_name": account.get("description", ""),
                    "balance": 0,
                    "debit_total": 0,
                    "credit_total": 0,
                    "transaction_count": 0
                })
        
        # Sort by account code
        balance_list.sort(key=lambda x: x["account_code"])
        
        # Calculate totals
        total_debit = sum(b["debit_total"] for b in balance_list)
        total_credit = sum(b["credit_total"] for b in balance_list)
        
        return {
            "success": True,
            "date": date,
            "balances": balance_list,
            "summary": {
                "total_accounts": len(balance_list),
                "accounts_with_balance": sum(1 for b in balance_list if b["balance"] != 0),
                "total_debit": total_debit,
                "total_credit": total_credit,
                "difference": total_debit - total_credit
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Error getting account balances: {str(e)}", "E-Boekhouden Balance API")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def get_opening_balances(year_start_date=None):
    """
    Get opening balances for a specific year
    
    This is useful for migration to set up initial account balances
    """
    
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        from verenigingen.utils.eboekhouden_migration_config import PAYMENT_ACCOUNT_CONFIG
        
        api = EBoekhoudenAPI()
        
        # If no date provided, use start of current year
        if not year_start_date:
            current_year = datetime.now().year
            year_start_date = f"{current_year}-01-01"
        
        # Get balances as of day before year start (closing balance of previous year)
        from datetime import datetime, timedelta
        year_start = datetime.strptime(year_start_date, "%Y-%m-%d")
        previous_day = (year_start - timedelta(days=1)).strftime("%Y-%m-%d")
        
        # Get the account balances
        result = get_account_balances(previous_day)
        
        if not result["success"]:
            return result
        
        # Filter and categorize for opening balance journal entry
        opening_balances = {
            "assets": [],
            "liabilities": [],
            "equity": [],
            "bank_accounts": [],
            "cash_accounts": [],
            "receivables": [],
            "payables": [],
            "other": []
        }
        
        # Categorize accounts
        for balance in result["balances"]:
            if balance["balance"] == 0:
                continue  # Skip zero-balance accounts
            
            account_code = balance["account_code"]
            
            # Check if it's a payment account
            is_bank = account_code in PAYMENT_ACCOUNT_CONFIG["bank_accounts"]
            is_cash = account_code in PAYMENT_ACCOUNT_CONFIG["cash_accounts"]
            
            balance_entry = {
                "account_code": account_code,
                "account_name": balance["account_name"],
                "balance": balance["balance"],
                "is_debit": balance["balance"] > 0
            }
            
            # Categorize based on account code patterns
            if is_bank:
                opening_balances["bank_accounts"].append(balance_entry)
            elif is_cash:
                opening_balances["cash_accounts"].append(balance_entry)
            elif account_code.startswith("0") or account_code.startswith("1"):
                # Assets (except bank/cash already categorized)
                if account_code.startswith("13"):
                    opening_balances["receivables"].append(balance_entry)
                else:
                    opening_balances["assets"].append(balance_entry)
            elif account_code.startswith("2") or account_code.startswith("3"):
                opening_balances["liabilities"].append(balance_entry)
            elif account_code.startswith("4"):
                if account_code.startswith("44"):
                    opening_balances["payables"].append(balance_entry)
                else:
                    opening_balances["liabilities"].append(balance_entry)
            elif account_code.startswith("5"):
                opening_balances["equity"].append(balance_entry)
            else:
                opening_balances["other"].append(balance_entry)
        
        # Calculate totals by category
        summary = {}
        total_debit = 0
        total_credit = 0
        
        for category, entries in opening_balances.items():
            category_total = sum(e["balance"] for e in entries)
            summary[f"{category}_total"] = category_total
            summary[f"{category}_count"] = len(entries)
            
            # Track overall totals
            for entry in entries:
                if entry["balance"] > 0:
                    total_debit += entry["balance"]
                else:
                    total_credit += abs(entry["balance"])
        
        return {
            "success": True,
            "year_start_date": year_start_date,
            "balance_date": previous_day,
            "opening_balances": opening_balances,
            "summary": {
                **summary,
                "total_debit": total_debit,
                "total_credit": total_credit,
                "difference": total_debit - total_credit,
                "balanced": abs(total_debit - total_credit) < 0.01
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Error getting opening balances: {str(e)}", "E-Boekhouden Opening Balance")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def create_opening_balance_journal_entry(year_start_date=None):
    """
    Create opening balance journal entry for migration
    
    This should be run once during initial setup to establish starting balances
    """
    
    try:
        # Get opening balances
        balances_result = get_opening_balances(year_start_date)
        
        if not balances_result["success"]:
            return balances_result
        
        # Check if already exists
        if not year_start_date:
            year_start_date = f"{datetime.now().year}-01-01"
            
        existing = frappe.db.exists("Journal Entry", {
            "posting_date": year_start_date,
            "user_remark": ["like", "%Opening Balance - E-Boekhouden Migration%"]
        })
        
        if existing:
            return {
                "success": False,
                "error": f"Opening balance journal entry already exists: {existing}"
            }
        
        # Get settings
        settings = frappe.get_single("E-Boekhouden Settings")
        
        # Create journal entry
        je = frappe.new_doc("Journal Entry")
        je.posting_date = year_start_date
        je.company = settings.default_company
        je.user_remark = f"Opening Balance - E-Boekhouden Migration as of {balances_result['balance_date']}"
        
        # Add all non-zero balance accounts
        for category, entries in balances_result["opening_balances"].items():
            for entry in entries:
                # Find ERPNext account
                account = frappe.db.get_value(
                    "Account",
                    {"account_number": entry["account_code"]},
                    "name"
                )
                
                if not account:
                    frappe.log_error(
                        f"Account {entry['account_code']} not found in ERPNext",
                        "Opening Balance Creation"
                    )
                    continue
                
                je.append("accounts", {
                    "account": account,
                    "debit_in_account_currency": entry["balance"] if entry["balance"] > 0 else 0,
                    "credit_in_account_currency": abs(entry["balance"]) if entry["balance"] < 0 else 0,
                    "user_remark": f"Opening balance: {entry['account_name']}",
                    "cost_center": settings.default_cost_center
                })
        
        # Check if balanced
        summary = balances_result["summary"]
        if not summary["balanced"]:
            # Add balancing entry to retained earnings or similar
            diff = summary["difference"]
            retained_earnings = frappe.db.get_value(
                "Account",
                {
                    "company": settings.default_company,
                    "account_type": "Accumulated Depreciation",
                    "root_type": "Equity"
                },
                "name"
            )
            
            if not retained_earnings:
                # Try to find any equity account
                retained_earnings = frappe.db.get_value(
                    "Account",
                    {
                        "company": settings.default_company,
                        "root_type": "Equity",
                        "is_group": 0
                    },
                    "name"
                )
            
            if retained_earnings:
                je.append("accounts", {
                    "account": retained_earnings,
                    "debit_in_account_currency": 0 if diff > 0 else abs(diff),
                    "credit_in_account_currency": diff if diff > 0 else 0,
                    "user_remark": "Balancing entry for opening balance",
                    "cost_center": settings.default_cost_center
                })
        
        # Save the journal entry
        if len(je.accounts) >= 2:
            je.insert(ignore_permissions=True)
            
            return {
                "success": True,
                "journal_entry": je.name,
                "message": f"Created opening balance journal entry {je.name}",
                "summary": {
                    "total_accounts": len(je.accounts),
                    "total_debit": sum(acc.debit_in_account_currency for acc in je.accounts),
                    "total_credit": sum(acc.credit_in_account_currency for acc in je.accounts)
                }
            }
        else:
            return {
                "success": False,
                "error": "Not enough accounts with non-zero balances to create journal entry"
            }
            
    except Exception as e:
        frappe.log_error(f"Error creating opening balance entry: {str(e)}", "E-Boekhouden Opening Balance")
        return {"success": False, "error": str(e)}