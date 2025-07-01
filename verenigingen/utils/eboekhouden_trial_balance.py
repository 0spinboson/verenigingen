"""
E-Boekhouden Trial Balance Functions

Get complete trial balance with proper debit/credit classification
"""

import frappe
from frappe import _
import json
from datetime import datetime


@frappe.whitelist()
def get_trial_balance(date=None, show_zero_balance=False):
    """
    Get a proper trial balance from E-Boekhouden
    
    This analyzes all transactions to build a complete trial balance
    with proper debit/credit columns
    """
    
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        api = EBoekhoudenAPI()
        
        # Default to today if no date provided
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        
        # Get chart of accounts first
        accounts_result = api.get_chart_of_accounts()
        if not accounts_result["success"]:
            return {"success": False, "error": "Failed to get chart of accounts"}
        
        accounts_data = json.loads(accounts_result["data"])
        accounts = accounts_data.get("items", [])
        
        # Create account info lookup
        account_info = {}
        for acc in accounts:
            acc_id = str(acc.get("id", ""))
            account_info[acc_id] = {
                "code": acc.get("code", ""),
                "name": acc.get("description", ""),
                "id": acc_id
            }
        
        # Get ALL transactions from beginning to date
        # We need to process each transaction to determine proper debit/credit
        params = {
            "dateTo": date,
            "pageSize": 1000  # Get more transactions at once
        }
        
        all_mutations = []
        page = 1
        
        while True:
            params["page"] = page
            mutations_result = api.get_mutations(params)
            
            if not mutations_result["success"]:
                break
                
            mutations_data = json.loads(mutations_result["data"])
            items = mutations_data.get("items", [])
            
            if not items:
                break
                
            all_mutations.extend(items)
            
            # Check if there are more pages
            if len(items) < params["pageSize"]:
                break
                
            page += 1
        
        # Process mutations to build trial balance
        # Group by entry number to see complete journal entries
        entries_by_number = {}
        
        for mutation in all_mutations:
            entry_num = mutation.get("entryNumber", mutation.get("id"))
            if entry_num not in entries_by_number:
                entries_by_number[entry_num] = []
            entries_by_number[entry_num].append(mutation)
        
        # Build account balances
        account_balances = {}
        
        # Initialize all accounts
        for acc_id, info in account_info.items():
            account_balances[acc_id] = {
                "code": info["code"],
                "name": info["name"],
                "debit": 0,
                "credit": 0,
                "balance": 0,
                "entries": []
            }
        
        # Process each entry group
        for entry_num, mutations in entries_by_number.items():
            # For each complete entry, determine debits and credits
            entry_total = sum(float(m.get("amount", 0)) for m in mutations)
            
            for mutation in mutations:
                ledger_id = str(mutation.get("ledgerId", ""))
                amount = float(mutation.get("amount", 0))
                
                if ledger_id not in account_balances:
                    # Account not in our lookup, skip
                    continue
                
                # In a balanced entry, positive amounts are debits, negative are credits
                if amount > 0:
                    account_balances[ledger_id]["debit"] += amount
                else:
                    account_balances[ledger_id]["credit"] += abs(amount)
                
                account_balances[ledger_id]["balance"] += amount
                
                # Track entry for debugging
                account_balances[ledger_id]["entries"].append({
                    "entry": entry_num,
                    "date": mutation.get("date"),
                    "amount": amount,
                    "description": mutation.get("description")
                })
        
        # Convert to list format
        trial_balance = []
        total_debit = 0
        total_credit = 0
        
        for acc_id, balance in account_balances.items():
            # Skip zero balance accounts if requested
            if not show_zero_balance and balance["debit"] == 0 and balance["credit"] == 0:
                continue
            
            trial_balance.append({
                "account_code": balance["code"],
                "account_name": balance["name"],
                "debit": balance["debit"],
                "credit": balance["credit"],
                "balance": balance["balance"],
                "entries_count": len(balance["entries"])
            })
            
            total_debit += balance["debit"]
            total_credit += balance["credit"]
        
        # Sort by account code
        trial_balance.sort(key=lambda x: x["account_code"])
        
        return {
            "success": True,
            "date": date,
            "trial_balance": trial_balance,
            "summary": {
                "total_accounts": len(trial_balance),
                "total_debit": round(total_debit, 2),
                "total_credit": round(total_credit, 2),
                "difference": round(total_debit - total_credit, 2),
                "balanced": abs(total_debit - total_credit) < 0.01,
                "total_entries_processed": len(entries_by_number)
            }
        }
        
    except Exception as e:
        import traceback
        frappe.log_error(traceback.format_exc(), "E-Boekhouden Trial Balance Error")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def get_account_ledger(account_code, date_from=None, date_to=None):
    """
    Get detailed ledger for a specific account
    
    This shows all transactions affecting the account
    """
    
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        api = EBoekhoudenAPI()
        
        # First find the account
        accounts_result = api.get_chart_of_accounts()
        if not accounts_result["success"]:
            return {"success": False, "error": "Failed to get chart of accounts"}
        
        accounts_data = json.loads(accounts_result["data"])
        accounts = accounts_data.get("items", [])
        
        # Find our account
        target_account = None
        account_lookup = {}
        
        for acc in accounts:
            acc_code = acc.get("code", "")
            account_lookup[str(acc.get("id", ""))] = acc
            
            if acc_code == account_code:
                target_account = acc
        
        if not target_account:
            return {"success": False, "error": f"Account {account_code} not found"}
        
        target_ledger_id = str(target_account.get("id", ""))
        
        # Get mutations
        params = {}
        if date_from:
            params["dateFrom"] = date_from
        if date_to:
            params["dateTo"] = date_to
        
        mutations_result = api.get_mutations(params)
        if not mutations_result["success"]:
            return {"success": False, "error": "Failed to get mutations"}
        
        mutations_data = json.loads(mutations_result["data"])
        all_mutations = mutations_data.get("items", [])
        
        # Filter for our account and build ledger
        ledger_entries = []
        running_balance = 0
        
        # Group by entry number to show complete entries
        entries_by_number = {}
        for mutation in all_mutations:
            entry_num = mutation.get("entryNumber", mutation.get("id"))
            if entry_num not in entries_by_number:
                entries_by_number[entry_num] = []
            entries_by_number[entry_num].append(mutation)
        
        # Process entries that affect our account
        for entry_num, mutations in entries_by_number.items():
            # Check if our account is in this entry
            our_mutation = None
            other_mutations = []
            
            for mutation in mutations:
                if str(mutation.get("ledgerId", "")) == target_ledger_id:
                    our_mutation = mutation
                else:
                    other_mutations.append(mutation)
            
            if not our_mutation:
                continue
            
            # Build entry info
            amount = float(our_mutation.get("amount", 0))
            running_balance += amount
            
            # Get contra accounts
            contra_accounts = []
            for other in other_mutations:
                other_acc = account_lookup.get(str(other.get("ledgerId", "")), {})
                contra_accounts.append({
                    "code": other_acc.get("code", ""),
                    "name": other_acc.get("description", ""),
                    "amount": float(other.get("amount", 0))
                })
            
            ledger_entries.append({
                "date": our_mutation.get("date"),
                "entry_number": entry_num,
                "description": our_mutation.get("description", ""),
                "debit": amount if amount > 0 else 0,
                "credit": abs(amount) if amount < 0 else 0,
                "balance": running_balance,
                "contra_accounts": contra_accounts,
                "invoice_number": our_mutation.get("invoiceNumber"),
                "relation_id": our_mutation.get("relationId")
            })
        
        # Sort by date
        ledger_entries.sort(key=lambda x: x["date"])
        
        # Recalculate running balance in correct order
        running_balance = 0
        for entry in ledger_entries:
            running_balance += (entry["debit"] - entry["credit"])
            entry["balance"] = running_balance
        
        return {
            "success": True,
            "account": {
                "code": account_code,
                "name": target_account.get("description", ""),
                "id": target_ledger_id
            },
            "ledger": ledger_entries,
            "summary": {
                "total_entries": len(ledger_entries),
                "total_debit": sum(e["debit"] for e in ledger_entries),
                "total_credit": sum(e["credit"] for e in ledger_entries),
                "closing_balance": running_balance
            }
        }
        
    except Exception as e:
        import traceback
        frappe.log_error(traceback.format_exc(), "E-Boekhouden Account Ledger Error")
        return {"success": False, "error": str(e)}