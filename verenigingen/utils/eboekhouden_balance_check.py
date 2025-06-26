"""
E-Boekhouden Balance Check

Functions to properly retrieve and understand balance data
"""

import frappe
from frappe import _
import json
from datetime import datetime


@frappe.whitelist()  
def analyze_mutations_structure(limit=50):
    """
    Analyze the structure of mutations to understand how E-Boekhouden represents balances
    """
    
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        api = EBoekhoudenAPI()
        
        # Get some mutations to analyze their structure
        params = {
            "dateTo": "2018-12-31",
            "pageSize": limit
        }
        
        mutations_result = api.get_mutations(params)
        if not mutations_result["success"]:
            return {"success": False, "error": "Failed to get mutations"}
        
        mutations_data = json.loads(mutations_result["data"])
        mutations = mutations_data.get("items", [])
        
        # Also get accounts for reference
        accounts_result = api.get_chart_of_accounts()
        accounts_data = json.loads(accounts_result["data"])
        accounts = accounts_data.get("items", [])
        account_lookup = {str(acc["id"]): acc for acc in accounts}
        
        # Analyze mutations
        analysis = []
        entry_groups = {}
        
        for mutation in mutations[:20]:  # First 20 for detailed analysis
            entry_num = mutation.get("entryNumber", mutation.get("id"))
            
            if entry_num not in entry_groups:
                entry_groups[entry_num] = []
            entry_groups[entry_num].append(mutation)
            
            ledger_id = str(mutation.get("ledgerId", ""))
            account = account_lookup.get(ledger_id, {})
            
            analysis.append({
                "date": mutation.get("date"),
                "entry_number": entry_num,
                "ledger_id": ledger_id,
                "account_code": account.get("code", ""),
                "account_name": account.get("description", ""),
                "amount": mutation.get("amount"),
                "invoice_number": mutation.get("invoiceNumber"),
                "description": mutation.get("description"),
                "relation_id": mutation.get("relationId"),
                "type": mutation.get("type"),
                "all_fields": list(mutation.keys())
            })
        
        # Analyze entry groups to see if they balance
        balanced_entries = []
        for entry_num, muts in entry_groups.items():
            total = sum(float(m.get("amount", 0)) for m in muts)
            balanced_entries.append({
                "entry": entry_num,
                "mutations_count": len(muts),
                "total": total,
                "balanced": abs(total) < 0.01,
                "mutations": muts
            })
        
        return {
            "success": True,
            "total_mutations": len(mutations),
            "mutations_analyzed": len(analysis),
            "analysis": analysis,
            "entry_groups": balanced_entries,
            "metadata": mutations_data.get("metadata", {}),
            "sample_mutation": mutations[0] if mutations else None
        }
        
    except Exception as e:
        import traceback
        frappe.log_error(traceback.format_exc(), "Mutation Structure Analysis")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def get_balance_by_report_api():
    """
    Try to get balance using report endpoints if available
    """
    
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        api = EBoekhoudenAPI()
        
        # Try different potential endpoints for balance/report data
        endpoints_to_try = [
            ("v1/report/balance", "Balance Report"),
            ("v1/report/trialbalance", "Trial Balance"),
            ("v1/balance", "Direct Balance"),
            ("v1/account/balance", "Account Balance"),
            ("v1/report", "General Reports")
        ]
        
        results = {}
        
        for endpoint, description in endpoints_to_try:
            try:
                result = api.make_request(endpoint)
                results[endpoint] = {
                    "description": description,
                    "success": result.get("success", False),
                    "status_code": result.get("status_code"),
                    "has_data": bool(result.get("data")),
                    "data_preview": result.get("data", "")[:500] if result.get("data") else None
                }
            except Exception as e:
                results[endpoint] = {
                    "description": description,
                    "success": False,
                    "error": str(e)
                }
        
        return {
            "success": True,
            "endpoints_tested": len(endpoints_to_try),
            "results": results
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def get_opening_balance_correct(year=2019):
    """
    Get the correct opening balance for a year
    
    For a proper migration, we need the opening balance which should be
    the closing balance of the previous year where debits = credits
    """
    
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        api = EBoekhoudenAPI()
        
        # The opening balance for 2019 would be the position as of 2018-12-31
        # In your case, this should total to €112,365.14 on both debit and credit
        
        # Let's get the closing entries for 2018
        closing_date = f"{year - 1}-12-31"
        opening_date = f"{year}-01-01"
        
        # Get all mutations up to closing date
        params = {
            "dateFrom": f"{year - 1}-01-01",
            "dateTo": closing_date,
            "pageSize": 1000
        }
        
        mutations_result = api.get_mutations(params)
        if not mutations_result["success"]:
            return {"success": False, "error": "Failed to get mutations"}
        
        mutations_data = json.loads(mutations_result["data"])
        all_mutations = mutations_data.get("items", [])
        
        # Get accounts
        accounts_result = api.get_chart_of_accounts()
        accounts_data = json.loads(accounts_result["data"])
        accounts = accounts_data.get("items", [])
        account_lookup = {str(acc["id"]): acc for acc in accounts}
        
        # Process mutations to get net position per account
        account_positions = {}
        
        for mutation in all_mutations:
            ledger_id = str(mutation.get("ledgerId", ""))
            amount = float(mutation.get("amount", 0))
            
            if ledger_id not in account_positions:
                acc_info = account_lookup.get(ledger_id, {})
                account_positions[ledger_id] = {
                    "code": acc_info.get("code", ""),
                    "name": acc_info.get("description", ""),
                    "net_position": 0,
                    "mutations_count": 0
                }
            
            account_positions[ledger_id]["net_position"] += amount
            account_positions[ledger_id]["mutations_count"] += 1
        
        # Now categorize accounts by their nature for proper debit/credit classification
        # In double-entry bookkeeping:
        # Assets & Expenses: Debit balance = positive, Credit balance = negative
        # Liabilities, Equity & Income: Credit balance = positive, Debit balance = negative
        
        opening_balance_entries = []
        total_debit = 0
        total_credit = 0
        
        for ledger_id, position in account_positions.items():
            if position["net_position"] == 0:
                continue
                
            code = position["code"]
            net = position["net_position"]
            
            # Determine account nature based on code
            # Dutch/EU account coding:
            # 0-1: Assets (Debit nature)
            # 2-4: Liabilities & Equity (Credit nature)  
            # 5-6: Expenses (Debit nature)
            # 7-8: Income (Credit nature)
            
            is_debit_nature = False
            if code:
                first_digit = code[0] if code else '9'
                if first_digit in ['0', '1', '5', '6']:
                    is_debit_nature = True
            
            # For opening balance:
            # Debit nature accounts with positive balance -> Debit
            # Debit nature accounts with negative balance -> Credit
            # Credit nature accounts with positive balance -> Credit
            # Credit nature accounts with negative balance -> Debit
            
            if is_debit_nature:
                if net > 0:
                    debit = net
                    credit = 0
                else:
                    debit = 0
                    credit = abs(net)
            else:
                if net > 0:
                    debit = 0
                    credit = net
                else:
                    debit = abs(net)
                    credit = 0
            
            total_debit += debit
            total_credit += credit
            
            opening_balance_entries.append({
                "account_code": code,
                "account_name": position["name"],
                "debit": round(debit, 2),
                "credit": round(credit, 2),
                "net_position": round(net, 2),
                "is_debit_nature": is_debit_nature
            })
        
        # Sort by account code
        opening_balance_entries.sort(key=lambda x: x["account_code"])
        
        # The difference might be the retained earnings/profit for the year
        difference = round(total_debit - total_credit, 2)
        
        return {
            "success": True,
            "year": year,
            "closing_date": closing_date,
            "opening_balance": opening_balance_entries,
            "summary": {
                "total_accounts": len(opening_balance_entries),
                "total_debit": round(total_debit, 2),
                "total_credit": round(total_credit, 2),
                "difference": difference,
                "expected_total": 112365.14,
                "matches_expected": abs(total_debit - 112365.14) < 0.01 or abs(total_credit - 112365.14) < 0.01
            },
            "note": "The difference likely represents the profit/loss that needs to be transferred to equity"
        }
        
    except Exception as e:
        import traceback
        frappe.log_error(traceback.format_exc(), "Opening Balance Calculation")
        return {"success": False, "error": str(e)}