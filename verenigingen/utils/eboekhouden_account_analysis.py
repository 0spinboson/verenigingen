"""
E-Boekhouden Account Analysis

Analyze account structure and groupings from the API
"""

import frappe
from frappe import _
import json


@frappe.whitelist()
def analyze_account_structure():
    """
    Analyze the account structure from E-Boekhouden API
    to understand parent groups and account types
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
        
        # Analyze account structure
        analysis = {
            "total_accounts": len(accounts),
            "account_fields": [],
            "sample_accounts": [],
            "vorderingen_accounts": [],  # Receivables
            "debiteuren_accounts": [],   # Debtors
            "groups_found": {},
            "categories_found": {},
            "parent_groups": {}
        }
        
        # Get all unique fields from first account
        if accounts:
            analysis["account_fields"] = list(accounts[0].keys())
        
        # Analyze accounts
        for account in accounts:
            code = account.get("code", "")
            description = account.get("description", "")
            
            # Check for parent/group information
            parent_id = account.get("parentId")
            parent_code = account.get("parentCode")
            group = account.get("group")
            category = account.get("category")
            account_type = account.get("type")
            is_group = account.get("isGroup", False)
            
            # Track groups and categories
            if group:
                if group not in analysis["groups_found"]:
                    analysis["groups_found"][group] = []
                analysis["groups_found"][group].append(f"{code} - {description}")
            
            if category:
                if category not in analysis["categories_found"]:
                    analysis["categories_found"][category] = []
                analysis["categories_found"][category].append(f"{code} - {description}")
            
            # Track parent relationships
            if parent_id or parent_code:
                analysis["parent_groups"][code] = {
                    "parent_id": parent_id,
                    "parent_code": parent_code,
                    "account": f"{code} - {description}"
                }
            
            # Look for receivables (vorderingen/debiteuren)
            desc_lower = description.lower()
            if "vorderingen" in desc_lower or code.startswith("13"):
                analysis["vorderingen_accounts"].append({
                    "code": code,
                    "description": description,
                    "group": group,
                    "category": category,
                    "parent_id": parent_id,
                    "is_group": is_group,
                    "full_data": account
                })
            
            if "debiteuren" in desc_lower:
                analysis["debiteuren_accounts"].append({
                    "code": code,
                    "description": description,
                    "group": group,
                    "category": category,
                    "parent_id": parent_id,
                    "is_group": is_group,
                    "full_data": account
                })
            
            # Get samples for specific accounts
            if code in ["13500", "13510", "13600", "13900"]:
                analysis["sample_accounts"].append({
                    "code": code,
                    "description": description,
                    "group": group,
                    "category": category,
                    "parent_id": parent_id,
                    "parent_code": parent_code,
                    "is_group": is_group,
                    "type": account_type,
                    "all_fields": account
                })
        
        # Try to find parent accounts for our receivables
        for acc in analysis["sample_accounts"]:
            if acc.get("parent_id"):
                # Find parent account
                parent = next((a for a in accounts if str(a.get("id")) == str(acc["parent_id"])), None)
                if parent:
                    acc["parent_details"] = {
                        "code": parent.get("code"),
                        "description": parent.get("description"),
                        "group": parent.get("group"),
                        "category": parent.get("category")
                    }
        
        return {
            "success": True,
            "analysis": analysis
        }
        
    except Exception as e:
        import traceback
        frappe.log_error(traceback.format_exc(), "E-Boekhouden Account Analysis")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def get_receivable_accounts():
    """
    Get all receivable accounts from E-Boekhouden
    based on group/category information
    """
    
    try:
        result = analyze_account_structure()
        
        if not result["success"]:
            return result
        
        analysis = result["analysis"]
        
        # Extract receivable accounts
        receivables = {
            "vorderingen_group": analysis.get("vorderingen_accounts", []),
            "debiteuren_group": analysis.get("debiteuren_accounts", []),
            "specific_receivables": [
                acc for acc in analysis.get("sample_accounts", [])
                if acc["code"] in ["13500", "13510", "13600", "13900"]
            ]
        }
        
        # Check if they share common parent or group
        parent_groups = set()
        categories = set()
        
        for acc in receivables["specific_receivables"]:
            if acc.get("parent_id"):
                parent_groups.add(acc.get("parent_id"))
            if acc.get("group"):
                parent_groups.add(acc.get("group"))
            if acc.get("category"):
                categories.add(acc.get("category"))
        
        return {
            "success": True,
            "receivables": receivables,
            "common_parents": list(parent_groups),
            "common_categories": list(categories),
            "recommendation": "Use parent group or category information to identify all receivable accounts"
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}