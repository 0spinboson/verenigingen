"""
Test script to retrieve custom group names from E-Boekhouden API
"""

import frappe
from frappe import _
import json

@frappe.whitelist()
def test_group_retrieval():
    """
    Test retrieving custom group names from E-Boekhouden API
    """
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        # Initialize API
        api = EBoekhoudenAPI()
        
        # Get chart of accounts
        result = api.get_chart_of_accounts()
        
        if not result["success"]:
            return {
                "success": False,
                "error": "Failed to get chart of accounts",
                "details": result.get("error")
            }
        
        # Parse the JSON response
        data = json.loads(result["data"])
        accounts = data.get("items", [])
        
        # Analyze groups found
        groups_map = {}
        sample_accounts = []
        
        for account in accounts:
            # Get group information
            group = account.get("group", "")
            code = account.get("code", "")
            description = account.get("description", "")
            category = account.get("category", "")
            
            # Track unique groups
            if group:
                if group not in groups_map:
                    groups_map[group] = {
                        "group_name": group,
                        "accounts": [],
                        "account_count": 0
                    }
                
                groups_map[group]["accounts"].append({
                    "code": code,
                    "description": description,
                    "category": category
                })
                groups_map[group]["account_count"] += 1
            
            # Collect sample accounts with groups
            if len(sample_accounts) < 10 and group:
                sample_accounts.append({
                    "code": code,
                    "description": description,
                    "category": category,
                    "group": group
                })
        
        # Sort groups by account count
        sorted_groups = sorted(
            groups_map.values(),
            key=lambda x: x["account_count"],
            reverse=True
        )
        
        # Get top 10 groups with sample accounts
        top_groups = []
        for group_data in sorted_groups[:10]:
            top_groups.append({
                "group_name": group_data["group_name"],
                "account_count": group_data["account_count"],
                "sample_accounts": group_data["accounts"][:3]  # First 3 accounts as samples
            })
        
        return {
            "success": True,
            "total_accounts": len(accounts),
            "unique_groups": len(groups_map),
            "sample_accounts_with_groups": sample_accounts,
            "top_groups": top_groups,
            "all_group_names": list(groups_map.keys())
        }
        
    except Exception as e:
        import traceback
        frappe.log_error(traceback.format_exc(), "E-Boekhouden Group Retrieval Test")
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def find_accounts_by_group(group_name):
    """
    Find all accounts that belong to a specific group
    
    Args:
        group_name: The name of the group to search for
    """
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        # Initialize API
        api = EBoekhoudenAPI()
        
        # Get chart of accounts
        result = api.get_chart_of_accounts()
        
        if not result["success"]:
            return {
                "success": False,
                "error": "Failed to get chart of accounts",
                "details": result.get("error")
            }
        
        # Parse the JSON response
        data = json.loads(result["data"])
        accounts = data.get("items", [])
        
        # Find accounts in the specified group
        matching_accounts = []
        
        for account in accounts:
            if account.get("group", "") == group_name:
                matching_accounts.append({
                    "id": account.get("id"),
                    "code": account.get("code"),
                    "description": account.get("description"),
                    "category": account.get("category"),
                    "group": account.get("group")
                })
        
        # Sort by code
        matching_accounts.sort(key=lambda x: x.get("code", ""))
        
        return {
            "success": True,
            "group_name": group_name,
            "account_count": len(matching_accounts),
            "accounts": matching_accounts
        }
        
    except Exception as e:
        import traceback
        frappe.log_error(traceback.format_exc(), "E-Boekhouden Find Accounts by Group")
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def create_group_mapping():
    """
    Create a mapping of E-Boekhouden groups to ERPNext account types
    This can be used to automate account type assignment during migration
    """
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        # Initialize API
        api = EBoekhoudenAPI()
        
        # Get chart of accounts
        result = api.get_chart_of_accounts()
        
        if not result["success"]:
            return {
                "success": False,
                "error": "Failed to get chart of accounts"
            }
        
        # Parse the JSON response
        data = json.loads(result["data"])
        accounts = data.get("items", [])
        
        # Create group analysis
        group_analysis = {}
        
        for account in accounts:
            group = account.get("group", "")
            if not group:
                continue
                
            if group not in group_analysis:
                group_analysis[group] = {
                    "group_name": group,
                    "categories": {},
                    "code_ranges": [],
                    "sample_accounts": []
                }
            
            # Track categories in this group
            category = account.get("category", "")
            if category:
                if category not in group_analysis[group]["categories"]:
                    group_analysis[group]["categories"][category] = 0
                group_analysis[group]["categories"][category] += 1
            
            # Track code ranges
            code = account.get("code", "")
            if code:
                group_analysis[group]["code_ranges"].append(code)
            
            # Keep a few sample accounts
            if len(group_analysis[group]["sample_accounts"]) < 5:
                group_analysis[group]["sample_accounts"].append({
                    "code": code,
                    "description": account.get("description", "")
                })
        
        # Analyze code ranges for each group
        for group_name, group_data in group_analysis.items():
            codes = group_data["code_ranges"]
            if codes:
                # Sort codes
                sorted_codes = sorted(codes)
                group_data["code_range"] = {
                    "min": sorted_codes[0],
                    "max": sorted_codes[-1],
                    "count": len(codes)
                }
                del group_data["code_ranges"]  # Remove raw list
        
        # Suggest ERPNext account types based on group characteristics
        suggestions = {}
        
        for group_name, group_data in group_analysis.items():
            # Simple heuristics based on common patterns
            group_lower = group_name.lower()
            
            suggested_type = "General"  # Default
            
            # Asset-related groups
            if any(term in group_lower for term in ["activa", "asset", "vast", "vlottend"]):
                if "vlottend" in group_lower:
                    suggested_type = "Current Asset"
                else:
                    suggested_type = "Fixed Asset"
            
            # Liability-related groups
            elif any(term in group_lower for term in ["passiva", "schuld", "liability"]):
                if any(term in group_lower for term in ["kort", "current", "vlottend"]):
                    suggested_type = "Current Liability"
                else:
                    suggested_type = "Liability"
            
            # Equity-related groups
            elif any(term in group_lower for term in ["eigen vermogen", "equity", "kapitaal"]):
                suggested_type = "Equity"
            
            # Income-related groups
            elif any(term in group_lower for term in ["omzet", "opbrengst", "income", "revenue"]):
                suggested_type = "Revenue"
            
            # Expense-related groups
            elif any(term in group_lower for term in ["kosten", "expense", "inkoop"]):
                suggested_type = "Expense"
            
            suggestions[group_name] = {
                "suggested_erpnext_type": suggested_type,
                "group_data": group_data
            }
        
        return {
            "success": True,
            "total_groups": len(group_analysis),
            "group_suggestions": suggestions
        }
        
    except Exception as e:
        import traceback
        frappe.log_error(traceback.format_exc(), "E-Boekhouden Group Mapping Creation")
        return {
            "success": False,
            "error": str(e)
        }