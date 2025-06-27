"""
Smart mapping for E-Boekhouden accounts
Handles mixed groups like liquid assets intelligently
"""

import frappe
import json
from frappe import _


@frappe.whitelist()
def get_smart_mapping_proposals():
    """
    Get intelligent mapping proposals that handle mixed groups
    """
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        from verenigingen.utils.eboekhouden_account_level_mapping import suggest_liquid_asset_type
        
        api = EBoekhoudenAPI()
        result = api.get_chart_of_accounts()
        
        if not result["success"]:
            return {"success": False, "error": "Failed to get chart of accounts"}
        
        data = json.loads(result["data"])
        accounts = data.get("items", [])
        
        # First, group by E-Boekhouden groups
        groups = {}
        for account in accounts:
            group_code = account.get("group", "")
            if not group_code:
                continue
                
            if group_code not in groups:
                groups[group_code] = []
            groups[group_code].append(account)
        
        # Analyze each group
        proposals = []
        
        for group_code, group_accounts in groups.items():
            # Check if this is a mixed group
            account_types = {}
            for acc in group_accounts:
                if group_code == "002" or "liquide" in acc.get("description", "").lower():
                    # Special handling for liquid assets
                    suggested = suggest_liquid_asset_type(
                        acc.get("code", ""),
                        acc.get("description", "")
                    )
                    type_key = suggested["type"]
                else:
                    # Use standard detection
                    type_key = detect_standard_type(acc)
                
                if type_key not in account_types:
                    account_types[type_key] = []
                account_types[type_key].append(acc)
            
            # If group has mixed types, create separate proposals
            if len(account_types) > 1:
                # Mixed group - create sub-proposals
                for account_type, type_accounts in account_types.items():
                    # Group similar accounts
                    if account_type == "Cash":
                        name = "Kas accounts"
                        reason = "Physical cash accounts"
                    elif account_type == "Bank" and any("paypal" in a.get("description", "").lower() or "mollie" in a.get("description", "").lower() for a in type_accounts):
                        name = "Payment Service Providers"
                        reason = "Online payment providers (PSPs)"
                    elif account_type == "Bank":
                        name = "Bankrekeningen"
                        reason = "Traditional bank accounts"
                    else:
                        name = f"Group {group_code} - {account_type}"
                        reason = f"Accounts of type {account_type}"
                    
                    proposals.append({
                        "type": "sub_group",
                        "identifier": f"{group_code}_{account_type}",
                        "name": name,
                        "group_code": group_code,
                        "account_count": len(type_accounts),
                        "account_codes": [a.get("code") for a in type_accounts],
                        "sample_accounts": type_accounts[:3],
                        "suggested_mapping": {
                            "type": account_type,
                            "reason": reason,
                            "confidence": "high"
                        }
                    })
            else:
                # Uniform group - single proposal
                account_type = list(account_types.keys())[0] if account_types else None
                proposals.append({
                    "type": "group",
                    "identifier": group_code,
                    "name": get_group_name(group_code, group_accounts),
                    "group_code": group_code,
                    "account_count": len(group_accounts),
                    "sample_accounts": group_accounts[:3],
                    "suggested_mapping": {
                        "type": account_type,
                        "reason": "All accounts in group are similar",
                        "confidence": "medium"
                    }
                })
        
        # Add special note for liquid assets
        liquid_note = {
            "title": "Liquid Assets Mapping",
            "message": "Group 002 (Liquide middelen) has been split into sub-groups for accurate mapping:",
            "details": [
                "• Kas accounts → Cash",
                "• Bank accounts → Bank", 
                "• Payment providers (PayPal, Mollie) → Bank",
                "• Consider creating PSP sub-group under Bank in Chart of Accounts"
            ]
        }
        
        return {
            "success": True,
            "mapping_proposals": proposals,
            "total_proposals": len(proposals),
            "special_notes": [liquid_note] if any(p["group_code"] == "002" for p in proposals) else []
        }
        
    except Exception as e:
        frappe.log_error(f"Error in smart mapping: {str(e)}")
        return {"success": False, "error": str(e)}


def detect_standard_type(account):
    """Detect account type for non-liquid accounts"""
    desc_lower = account.get("description", "").lower()
    category = account.get("category", "")
    
    if category == "DEB":
        return "Receivable"
    elif category == "CRED":
        return "Payable"
    elif "btw" in desc_lower:
        return "Tax"
    elif "kosten" in desc_lower:
        return "Expense"
    elif "opbrengst" in desc_lower or "omzet" in desc_lower:
        return "Income"
    elif "eigen vermogen" in desc_lower:
        return "Equity"
    else:
        return "Current Asset"  # Default


def get_group_name(group_code, accounts):
    """Get a descriptive name for the group"""
    # Try to find common pattern
    from verenigingen.utils.eboekhouden_group_analysis_improved import find_common_phrases
    
    descriptions = [acc.get("description", "") for acc in accounts]
    phrases = find_common_phrases(descriptions)
    
    if phrases:
        return phrases[0][0].title()
    else:
        return f"Group {group_code}"


@frappe.whitelist()
def apply_smart_mappings(mappings):
    """
    Apply mappings that may include sub-groups
    
    Args:
        mappings: Dict where keys might be "group_code_type" format
    """
    try:
        if isinstance(mappings, str):
            mappings = json.loads(mappings)
        
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        api = EBoekhoudenAPI()
        
        # Get all accounts
        accounts_result = api.get_chart_of_accounts()
        if not accounts_result["success"]:
            return {"success": False, "error": "Failed to get chart of accounts"}
        
        accounts_data = json.loads(accounts_result["data"])
        accounts = accounts_data.get("items", [])
        
        results = {
            "updated": [],
            "skipped": [],
            "errors": []
        }
        
        # Process each mapping
        for mapping_key, target_type in mappings.items():
            if target_type == "Skip" or not target_type:
                continue
            
            # Check if this is a sub-group mapping
            if "_" in mapping_key and mapping_key.count("_") >= 1:
                # Format: groupcode_accounttype
                parts = mapping_key.split("_", 1)
                group_code = parts[0]
                
                # Find accounts in this sub-group
                for account in accounts:
                    if account.get("group") == group_code:
                        # Check if this account matches the sub-group type
                        suggested = suggest_liquid_asset_type(
                            account.get("code", ""),
                            account.get("description", "")
                        )
                        
                        if suggested["type"] == parts[1] or mapping_key.endswith(suggested["type"]):
                            # This account belongs to this sub-group
                            result = update_account_type(
                                account.get("code"),
                                target_type,
                                account.get("description", "")
                            )
                            
                            if result["success"]:
                                results["updated"].append(result["message"])
                            else:
                                results["errors"].append(result["message"])
            else:
                # Regular group mapping
                group_accounts = [a for a in accounts if a.get("group") == mapping_key]
                
                for account in group_accounts:
                    result = update_account_type(
                        account.get("code"),
                        target_type,
                        account.get("description", "")
                    )
                    
                    if result["success"]:
                        results["updated"].append(result["message"])
                    else:
                        results["errors"].append(result["message"])
        
        return {
            "success": True,
            "summary": {
                "total_updated": len(results["updated"]),
                "total_errors": len(results["errors"]),
                "details": results
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Error applying smart mappings: {str(e)}")
        return {"success": False, "error": str(e)}


def update_account_type(account_code, target_type, description=""):
    """Update a single account's type"""
    try:
        # Find the account in ERPNext
        account_name = frappe.db.get_value(
            "Account",
            {"account_number": account_code},
            "name"
        )
        
        if not account_name:
            return {
                "success": False,
                "message": f"Account {account_code} not found in ERPNext"
            }
        
        # Update the account
        account = frappe.get_doc("Account", account_name)
        old_type = account.account_type
        
        if old_type == target_type:
            return {
                "success": True,
                "message": f"Account {account_code} already has type {target_type}"
            }
        
        account.account_type = target_type
        
        # Ensure correct root type for special types
        if target_type == "Receivable":
            account.root_type = "Asset"
        elif target_type == "Payable":
            account.root_type = "Liability"
        elif target_type == "Equity":
            account.root_type = "Equity"
        
        account.save(ignore_permissions=True)
        
        return {
            "success": True,
            "message": f"Updated {account_code} - {description}: {old_type} → {target_type}"
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"Error updating {account_code}: {str(e)}"
        }