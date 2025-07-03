"""
Debug Chart of Accounts hierarchy creation issues
"""

import frappe
import json

@frappe.whitelist()
def debug_coa_hierarchy_issue():
    """
    Debug why Chart of Accounts creation is failing with parent_account errors
    """
    try:
        # Get E-boekhouden data
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        settings = frappe.get_single("E-Boekhouden Settings")
        company = settings.default_company
        
        api = EBoekhoudenAPI(settings)
        result = api.get_chart_of_accounts()
        
        if not result["success"]:
            return {"success": False, "error": "Failed to get CoA data"}
        
        data = json.loads(result["data"])
        accounts_data = data.get("items", [])
        
        # Analyze the hierarchy structure
        analysis = {
            "total_accounts": len(accounts_data),
            "root_candidates": [],
            "group_summary": {},
            "category_summary": {},
            "code_length_summary": {},
            "problematic_account": None
        }
        
        # Look for the specific failing account
        failing_account = None
        for acc in accounts_data:
            if acc.get("code") == "44470":
                analysis["problematic_account"] = acc
                failing_account = acc
                break
        
        # Analyze all accounts
        for acc in accounts_data:
            code = acc.get("code", "")
            category = acc.get("category", "")
            group = acc.get("group", "")
            
            # Track by group
            if group not in analysis["group_summary"]:
                analysis["group_summary"][group] = []
            analysis["group_summary"][group].append(code)
            
            # Track by category
            if category not in analysis["category_summary"]:
                analysis["category_summary"][category] = []
            analysis["category_summary"][category].append(code)
            
            # Track by code length
            code_len = len(code)
            if code_len not in analysis["code_length_summary"]:
                analysis["code_length_summary"][code_len] = []
            analysis["code_length_summary"][code_len].append(code)
            
            # Identify potential root accounts
            if (len(code) <= 2 or 
                (len(code) == 3 and code.startswith("00")) or
                (group and group in ['001', '002', '003', '004', '005', '006', '007', '008', '009', '010'])):
                analysis["root_candidates"].append({
                    "code": code,
                    "description": acc.get("description", ""),
                    "category": category,
                    "group": group
                })
        
        # Check what root accounts exist in ERPNext (accounts with no parent)
        existing_root_accounts = frappe.db.get_all("Account",
            filters={
                "company": company,
                "parent_account": ["in", ["", None]]
            },
            fields=["name", "account_name", "account_number", "root_type"]
        )
        
        # Try to find what should be the parent of 44470
        parent_analysis = None
        if failing_account:
            parent_analysis = analyze_potential_parent("44470", accounts_data)
        
        return {
            "success": True,
            "analysis": analysis,
            "existing_root_accounts": existing_root_accounts,
            "parent_analysis": parent_analysis,
            "recommendations": generate_recommendations(analysis, existing_root_accounts)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def analyze_potential_parent(account_code, accounts_data):
    """Analyze what the parent account should be for a given account"""
    try:
        # For account 44470, potential parents could be:
        # - 4447 (if it exists)
        # - 444 (if it exists) 
        # - 44 (if it exists)
        # - 4 (if it exists)
        
        potential_parents = []
        code = account_code
        
        # Check progressively shorter codes
        for length in range(len(code) - 1, 0, -1):
            potential_parent = code[:length]
            
            # Check if this potential parent exists in the data
            for acc in accounts_data:
                if acc.get("code") == potential_parent:
                    potential_parents.append({
                        "code": potential_parent,
                        "description": acc.get("description", ""),
                        "category": acc.get("category", ""),
                        "group": acc.get("group", ""),
                        "length": length
                    })
                    break
        
        return {
            "account_code": account_code,
            "potential_parents": potential_parents,
            "parent_search_strategy": "Progressively shorter account codes"
        }
        
    except Exception as e:
        return {"error": str(e)}

def generate_recommendations(analysis, existing_root_accounts):
    """Generate recommendations based on the analysis"""
    recommendations = []
    
    # Check if we have any root accounts
    if len(existing_root_accounts) == 0:
        recommendations.append("No root accounts found - this is likely the main issue")
        recommendations.append("Root accounts must be created before child accounts")
    
    # Check root candidates
    root_count = len(analysis["root_candidates"])
    if root_count == 0:
        recommendations.append("No root account candidates identified in E-boekhouden data")
    else:
        recommendations.append(f"Found {root_count} potential root accounts that should be created first")
    
    # Check group 009 specifically (since failing account is in group 009)
    group_009_accounts = analysis["group_summary"].get("009", [])
    if group_009_accounts:
        recommendations.append(f"Group 009 has {len(group_009_accounts)} accounts: {group_009_accounts[:5]}")
        
        # Check if there's a shorter code in group 009 that could be the parent
        shortest_in_group = min(group_009_accounts, key=len) if group_009_accounts else None
        if shortest_in_group:
            recommendations.append(f"Shortest code in group 009: {shortest_in_group} (might be root for this group)")
    
    return recommendations

@frappe.whitelist()
def fix_coa_creation_order():
    """
    Fix the Chart of Accounts creation by ensuring proper order
    """
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        settings = frappe.get_single("E-Boekhouden Settings")
        company = settings.default_company
        
        api = EBoekhoudenAPI(settings)
        result = api.get_chart_of_accounts()
        
        if not result["success"]:
            return {"success": False, "error": "Failed to get CoA data"}
        
        data = json.loads(result["data"])
        accounts_data = data.get("items", [])
        
        # Sort accounts by code length first, then by code
        # This ensures root accounts (shorter codes) are created first
        sorted_accounts = sorted(accounts_data, key=lambda x: (len(x.get('code', '')), x.get('code', '')))
        
        # Identify which accounts should be created as root accounts
        from verenigingen.utils.eboekhouden_account_group_fix import analyze_account_hierarchy
        group_accounts = analyze_account_hierarchy(accounts_data)
        
        creation_order = []
        for acc in sorted_accounts:
            code = acc.get('code', '')
            is_group = code in group_accounts
            creation_order.append({
                "code": code,
                "description": acc.get('description', ''),
                "category": acc.get('category', ''),
                "group": acc.get('group', ''),
                "is_group": is_group,
                "code_length": len(code)
            })
        
        return {
            "success": True,
            "total_accounts": len(accounts_data),
            "creation_order": creation_order[:20],  # First 20 for review
            "group_accounts_count": len(group_accounts),
            "message": f"Analyzed {len(accounts_data)} accounts, identified {len(group_accounts)} group accounts"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }