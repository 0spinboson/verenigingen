"""
Fix account types for Receivable/Payable accounts imported from E-Boekhouden
"""

import frappe
from frappe import _
import json

@frappe.whitelist()
def analyze_and_fix_entries():
    """
    Analyze and fix account types for accounts that should be Receivable/Payable
    """
    try:
        # Import smart typing
        from verenigingen.utils.eboekhouden_smart_account_typing import get_smart_account_type
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        # Get all accounts from E-Boekhouden to analyze
        api = EBoekhoudenAPI()
        eb_accounts_result = api.get_chart_of_accounts()
        
        if not eb_accounts_result["success"]:
            return {
                "success": False,
                "error": "Failed to fetch accounts from E-Boekhouden"
            }
        
        eb_accounts_data = json.loads(eb_accounts_result["data"])
        eb_accounts = eb_accounts_data.get("items", [])
        
        # Create lookup by code
        eb_lookup = {str(acc.get("code")): acc for acc in eb_accounts}
        
        # Get all ERPNext accounts
        company = frappe.db.get_single_value("E-Boekhouden Settings", "default_company")
        if not company:
            return {
                "success": False, 
                "error": "No default company set in E-Boekhouden Settings"
            }
        
        # Find accounts that need fixing
        accounts_to_fix = []
        fixed_accounts = []
        errors = []
        
        # Get all accounts for the company
        all_accounts = frappe.db.sql("""
            SELECT 
                name, account_name, account_number, account_type, root_type
            FROM `tabAccount`
            WHERE company = %s
            AND account_number IS NOT NULL
            AND account_number != ''
            AND disabled = 0
        """, company, as_dict=True)
        
        for account in all_accounts:
            account_number = account.get("account_number", "")
            
            # Skip if no account number
            if not account_number:
                continue
            
            # Get E-Boekhouden data
            eb_account = eb_lookup.get(account_number)
            if not eb_account:
                continue
            
            # Determine what type it should be
            correct_type, correct_root = get_smart_account_type(eb_account)
            
            # Check if it needs fixing
            current_type = account.get("account_type") or ""
            needs_fix = False
            
            # Specific cases that need fixing
            if account_number.startswith("13") and current_type != "Receivable":
                # Check if it should be Receivable
                desc_lower = eb_account.get("description", "").lower()
                if any(term in desc_lower for term in ["te ontvangen", "debiteuren", "vordering"]):
                    if correct_type == "Receivable":
                        needs_fix = True
            
            elif account_number.startswith("44") and current_type != "Payable":
                # Check if it should be Payable
                desc_lower = eb_account.get("description", "").lower()
                if any(term in desc_lower for term in ["te betalen", "crediteuren", "schuld"]):
                    if correct_type == "Payable":
                        needs_fix = True
            
            # Also check if Income/Expense accounts are incorrectly typed
            elif current_type in ["Income", "Expense"]:
                # These should be "Income Account" or "Expense Account"
                if correct_type in ["Income Account", "Expense Account"]:
                    needs_fix = True
            
            # General check - if the smart type differs significantly
            elif current_type != correct_type and correct_type in ["Receivable", "Payable", "Income Account", "Expense Account"]:
                needs_fix = True
            
            if needs_fix:
                accounts_to_fix.append({
                    "name": account["name"],
                    "account_name": account["account_name"],
                    "account_number": account_number,
                    "current_type": current_type,
                    "correct_type": correct_type,
                    "correct_root": correct_root,
                    "description": eb_account.get("description", "")
                })
        
        # Show preview first
        if accounts_to_fix:
            preview_html = "<h5>Accounts that need type correction:</h5>"
            preview_html += "<table class='table table-sm'>"
            preview_html += "<thead><tr><th>Account</th><th>Current Type</th><th>Correct Type</th></tr></thead>"
            preview_html += "<tbody>"
            
            for acc in accounts_to_fix:
                preview_html += f"<tr>"
                preview_html += f"<td>{acc['account_number']} - {acc['description']}</td>"
                preview_html += f"<td>{acc['current_type'] or 'Not Set'}</td>"
                preview_html += f"<td><strong>{acc['correct_type']}</strong></td>"
                preview_html += f"</tr>"
            
            preview_html += "</tbody></table>"
            preview_html += f"<p class='mt-3'>Total accounts to fix: <strong>{len(accounts_to_fix)}</strong></p>"
            
            # Return preview for confirmation
            return {
                "success": True,
                "action": "preview",
                "preview_html": preview_html,
                "accounts_to_fix": accounts_to_fix,
                "summary": f"Found {len(accounts_to_fix)} accounts that need type correction"
            }
        else:
            return {
                "success": True,
                "action": "none_needed",
                "summary": "All accounts already have correct types. No changes needed."
            }
        
    except Exception as e:
        frappe.log_error(f"Error analyzing accounts: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def apply_account_type_fixes(accounts_to_fix):
    """
    Apply the account type fixes
    """
    try:
        if isinstance(accounts_to_fix, str):
            accounts_to_fix = json.loads(accounts_to_fix)
        
        fixed_count = 0
        error_count = 0
        errors = []
        
        for acc_data in accounts_to_fix:
            try:
                # Update the account
                account = frappe.get_doc("Account", acc_data["name"])
                
                # Set the correct type
                account.account_type = acc_data["correct_type"]
                
                # Ensure root type is correct
                if acc_data["correct_type"] in ["Receivable", "Fixed Asset", "Current Asset", "Stock", "Bank", "Cash"]:
                    account.root_type = "Asset"
                elif acc_data["correct_type"] in ["Payable", "Current Liability", "Tax"]:
                    account.root_type = "Liability"
                elif acc_data["correct_type"] == "Income Account":
                    account.root_type = "Income"
                elif acc_data["correct_type"] == "Expense Account":
                    account.root_type = "Expense"
                elif acc_data["correct_type"] == "Equity":
                    account.root_type = "Equity"
                
                account.save(ignore_permissions=True)
                fixed_count += 1
                
            except Exception as e:
                error_count += 1
                errors.append(f"{acc_data['account_number']}: {str(e)}")
        
        # Build summary
        summary = f"Successfully fixed {fixed_count} accounts."
        if error_count > 0:
            summary += f" {error_count} errors occurred."
            if errors:
                summary += "\n\nErrors:\n" + "\n".join(errors[:5])
                if len(errors) > 5:
                    summary += f"\n... and {len(errors) - 5} more"
        
        return {
            "success": True,
            "summary": summary,
            "fixed_count": fixed_count,
            "error_count": error_count
        }
        
    except Exception as e:
        frappe.log_error(f"Error applying fixes: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def check_specific_account(account_number):
    """
    Debug function to check a specific account
    """
    try:
        from verenigingen.utils.eboekhouden_smart_account_typing import get_smart_account_type
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        # Get from E-Boekhouden
        api = EBoekhoudenAPI()
        eb_accounts_result = api.get_chart_of_accounts()
        
        if eb_accounts_result["success"]:
            eb_accounts_data = json.loads(eb_accounts_result["data"])
            eb_accounts = eb_accounts_data.get("items", [])
            
            for acc in eb_accounts:
                if str(acc.get("code")) == str(account_number):
                    # Get smart type
                    smart_type, smart_root = get_smart_account_type(acc)
                    
                    # Get ERPNext account
                    erpnext_account = frappe.db.get_value(
                        "Account",
                        {"account_number": account_number},
                        ["name", "account_type", "root_type"],
                        as_dict=True
                    )
                    
                    return {
                        "success": True,
                        "eboekhouden": acc,
                        "smart_detection": {
                            "type": smart_type,
                            "root": smart_root
                        },
                        "erpnext": erpnext_account
                    }
        
        return {
            "success": False,
            "error": f"Account {account_number} not found"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }