"""
E-Boekhouden Group Analysis

Analyze and retrieve group information from E-Boekhouden API
"""

import frappe
from frappe import _
import json


@frappe.whitelist()
def get_group_mapping():
    """
    Get group mapping with names and accounts
    
    Note: The E-Boekhouden API returns group codes (like "004"), not descriptive names.
    We'll need to infer group purposes from the accounts they contain.
    """
    
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        api = EBoekhoudenAPI()
        
        # Get chart of accounts
        accounts_result = api.get_chart_of_accounts()
        if not accounts_result["success"]:
            return {"success": False, "error": "Failed to get chart of accounts"}
        
        accounts_data = json.loads(accounts_result["data"])
        accounts = accounts_data.get("items", [])
        
        # Build group mapping
        groups = {}
        
        for account in accounts:
            group_code = account.get("group", "")
            if not group_code:
                continue
                
            if group_code not in groups:
                groups[group_code] = {
                    "code": group_code,
                    "accounts": [],
                    "categories": set(),
                    "inferred_name": "",
                    "account_range": {"min": "99999", "max": "00000"}
                }
            
            groups[group_code]["accounts"].append({
                "code": account.get("code", ""),
                "description": account.get("description", ""),
                "category": account.get("category", "")
            })
            
            # Track categories in this group
            if account.get("category"):
                groups[group_code]["categories"].add(account.get("category"))
            
            # Track account code range
            acc_code = account.get("code", "")
            if acc_code:
                if acc_code < groups[group_code]["account_range"]["min"]:
                    groups[group_code]["account_range"]["min"] = acc_code
                if acc_code > groups[group_code]["account_range"]["max"]:
                    groups[group_code]["account_range"]["max"] = acc_code
        
        # Infer group names based on accounts
        for group_code, group_data in groups.items():
            groups[group_code]["categories"] = list(group_data["categories"])
            
            # Infer name based on account descriptions and codes
            accounts_in_group = group_data["accounts"]
            
            # Common patterns in Dutch accounting
            if all(acc["code"].startswith("13") for acc in accounts_in_group):
                groups[group_code]["inferred_name"] = "Vorderingen (Receivables)"
            elif all(acc["code"].startswith("10") for acc in accounts_in_group):
                groups[group_code]["inferred_name"] = "Liquide middelen (Cash & Bank)"
            elif all(acc["code"].startswith("40") for acc in accounts_in_group):
                groups[group_code]["inferred_name"] = "Personeelskosten (Personnel)"
            elif all(acc["code"].startswith("44") for acc in accounts_in_group):
                groups[group_code]["inferred_name"] = "Algemene kosten (General Expenses)"
            elif all(acc["code"].startswith("46") for acc in accounts_in_group):
                groups[group_code]["inferred_name"] = "Projectkosten (Project Costs)"
            elif any("btw" in acc["description"].lower() for acc in accounts_in_group):
                groups[group_code]["inferred_name"] = "BTW (VAT)"
            elif group_data["categories"] == ["DEB"]:
                groups[group_code]["inferred_name"] = "Debiteuren (Debtors)"
            elif group_data["categories"] == ["CRED"]:
                groups[group_code]["inferred_name"] = "Crediteuren (Creditors)"
            elif group_data["categories"] == ["FIN"]:
                groups[group_code]["inferred_name"] = "Bank rekeningen (Bank Accounts)"
            else:
                # Try to find common words in descriptions
                descriptions = [acc["description"] for acc in accounts_in_group]
                common_words = find_common_words(descriptions)
                if common_words:
                    groups[group_code]["inferred_name"] = common_words[0].title()
                else:
                    groups[group_code]["inferred_name"] = f"Group {group_code}"
        
        # Convert to list for easier display
        group_list = []
        for group_code, group_data in sorted(groups.items()):
            group_list.append({
                "group_code": group_code,
                "inferred_name": group_data["inferred_name"],
                "account_count": len(group_data["accounts"]),
                "categories": group_data["categories"],
                "account_range": f"{group_data['account_range']['min']} - {group_data['account_range']['max']}",
                "sample_accounts": group_data["accounts"][:3]  # First 3 as samples
            })
        
        return {
            "success": True,
            "groups": group_list,
            "total_groups": len(groups),
            "group_details": groups
        }
        
    except Exception as e:
        import traceback
        frappe.log_error(traceback.format_exc(), "E-Boekhouden Group Analysis")
        return {"success": False, "error": str(e)}


def find_common_words(descriptions, min_length=4):
    """
    Find common words in a list of descriptions
    """
    if not descriptions:
        return []
    
    # Split all descriptions into words
    all_words = []
    for desc in descriptions:
        words = desc.lower().split()
        all_words.extend([w for w in words if len(w) >= min_length])
    
    # Count word frequency
    word_count = {}
    for word in all_words:
        word_count[word] = word_count.get(word, 0) + 1
    
    # Find words that appear in at least half the descriptions
    threshold = len(descriptions) / 2
    common_words = [word for word, count in word_count.items() if count >= threshold]
    
    # Sort by frequency
    common_words.sort(key=lambda w: word_count[w], reverse=True)
    
    return common_words


@frappe.whitelist()
def get_enhanced_account_mapping():
    """
    Get account mapping enhanced with group information
    """
    
    try:
        # First get groups
        group_result = get_group_mapping()
        if not group_result["success"]:
            return group_result
        
        # Then get account categories
        from verenigingen.utils.eboekhouden_account_type_mapping import analyze_account_categories
        category_result = analyze_account_categories()
        
        if not category_result["success"]:
            return category_result
        
        # Enhance proposals with group information
        enhanced_proposals = []
        
        # Create proposals by group instead of just category
        for group_info in group_result["groups"]:
            proposal = {
                "group_code": group_info["group_code"],
                "group_name": group_info["inferred_name"],
                "categories": group_info["categories"],
                "account_count": group_info["account_count"],
                "account_range": group_info["account_range"],
                "sample_accounts": group_info["sample_accounts"],
                "suggested_type": None
            }
            
            # Suggest account type based on group
            if "Vorderingen" in group_info["inferred_name"] or "DEB" in group_info["categories"]:
                proposal["suggested_type"] = "Receivable"
            elif "Crediteuren" in group_info["inferred_name"] or "CRED" in group_info["categories"]:
                proposal["suggested_type"] = "Payable"
            elif "Bank" in group_info["inferred_name"] or "FIN" in group_info["categories"]:
                proposal["suggested_type"] = "Bank"
            elif "Liquide" in group_info["inferred_name"] and any(acc["code"].startswith("10") for acc in group_info["sample_accounts"]):
                proposal["suggested_type"] = "Cash"
            elif "Personeelskosten" in group_info["inferred_name"]:
                proposal["suggested_type"] = "Expense"
            elif "kosten" in group_info["inferred_name"].lower():
                proposal["suggested_type"] = "Expense"
            
            enhanced_proposals.append(proposal)
        
        return {
            "success": True,
            "enhanced_proposals": enhanced_proposals,
            "group_mapping": group_result["group_details"],
            "category_mapping": category_result.get("mapping_proposals", [])
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}