"""
Debug E-Boekhouden categories to see what actually comes from the API
"""

import frappe
import json
from collections import Counter


@frappe.whitelist()
def analyze_actual_categories():
    """
    Analyze what categories actually exist in E-Boekhouden data
    """
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        api = EBoekhoudenAPI()
        result = api.get_chart_of_accounts()
        
        if not result["success"]:
            return {"success": False, "error": "Failed to get chart of accounts"}
        
        data = json.loads(result["data"])
        accounts = data.get("items", [])
        
        # Analyze categories
        categories = Counter()
        category_examples = {}
        missing_category = []
        
        for account in accounts:
            category = account.get("category")
            code = account.get("code", "")
            desc = account.get("description", "")
            
            if category:
                categories[category] += 1
                if category not in category_examples:
                    category_examples[category] = []
                if len(category_examples[category]) < 5:
                    category_examples[category].append({
                        "code": code,
                        "description": desc,
                        "group": account.get("group", "")
                    })
            else:
                missing_category.append({
                    "code": code,
                    "description": desc,
                    "group": account.get("group", "")
                })
        
        # Check for specific accounts mentioned by user
        specific_checks = {
            "80007": None,
            "05000": None,
            "mollie": []
        }
        
        for account in accounts:
            code = account.get("code", "")
            desc = account.get("description", "").lower()
            
            if code == "80007":
                specific_checks["80007"] = {
                    "category": account.get("category"),
                    "description": account.get("description"),
                    "group": account.get("group")
                }
            elif code == "05000":
                specific_checks["05000"] = {
                    "category": account.get("category"),
                    "description": account.get("description"),
                    "group": account.get("group")
                }
            
            if "mollie" in desc:
                specific_checks["mollie"].append({
                    "code": code,
                    "category": account.get("category"),
                    "description": account.get("description"),
                    "group": account.get("group")
                })
        
        # Find all equity accounts
        equity_accounts = []
        for account in accounts:
            desc_lower = account.get("description", "").lower()
            if any(term in desc_lower for term in ["eigen vermogen", "reserve", "kapitaal", "bestemmingsreserve"]):
                equity_accounts.append({
                    "code": account.get("code"),
                    "category": account.get("category"),
                    "description": account.get("description"),
                    "group": account.get("group")
                })
        
        return {
            "success": True,
            "category_counts": dict(categories),
            "category_examples": category_examples,
            "missing_category_count": len(missing_category),
            "missing_category_examples": missing_category[:5],
            "specific_accounts": specific_checks,
            "equity_accounts": equity_accounts,
            "notes": [
                f"Total categories found: {len(categories)}",
                f"Accounts without category: {len(missing_category)}",
                f"Does 'VW' category exist? {'Yes' if 'VW' in categories else 'No'}",
                f"Categories found: {', '.join(sorted(categories.keys()))}"
            ]
        }
        
    except Exception as e:
        frappe.log_error(f"Error analyzing categories: {str(e)}")
        return {"success": False, "error": str(e)}