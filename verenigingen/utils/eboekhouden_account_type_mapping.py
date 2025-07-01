"""
E-Boekhouden Account Type Mapping

Two-step process for mapping E-Boekhouden accounts to proper ERPNext types
"""

import frappe
from frappe import _
import json


@frappe.whitelist()
def analyze_account_categories(use_groups=True):
    """
    Step 1: Analyze E-Boekhouden accounts and propose mappings
    
    Args:
        use_groups: If True, also analyze by groups for better organization
    
    Returns categories found and suggested ERPNext account types
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
        
        # Analyze categories and groups
        category_analysis = {}
        group_analysis = {}
        
        for account in accounts:
            category = account.get("category", "")
            group = account.get("group", "")
            code = account.get("code", "")
            description = account.get("description", "")
            
            # Analyze by category
            if category:
                if category not in category_analysis:
                    category_analysis[category] = {
                        "accounts": [],
                        "suggested_type": None,
                        "count": 0
                    }
                
                category_analysis[category]["accounts"].append({
                    "code": code,
                    "description": description,
                    "group": group
                })
                category_analysis[category]["count"] += 1
            
            # Analyze by group
            if group:
                if group not in group_analysis:
                    group_analysis[group] = {
                        "accounts": [],
                        "categories": set(),
                        "count": 0
                    }
                
                group_analysis[group]["accounts"].append({
                    "code": code,
                    "description": description,
                    "category": category
                })
                group_analysis[group]["count"] += 1
                if category:
                    group_analysis[group]["categories"].add(category)
        
        # Convert sets to lists for JSON serialization
        for group in group_analysis:
            group_analysis[group]["categories"] = list(group_analysis[group]["categories"])
        
        # Add suggested mappings based on known patterns
        suggested_mappings = {
            "DEB": {
                "type": "Receivable",
                "reason": "Debiteuren (Debtors) - Customer receivables",
                "action": "Will require party (Customer) for journal entries"
            },
            "CRED": {
                "type": "Payable", 
                "reason": "Crediteuren (Creditors) - Supplier payables",
                "action": "Will require party (Supplier) for journal entries"
            },
            "FIN": {
                "type": "Bank",
                "reason": "Financial accounts - Bank accounts",
                "action": "No change needed, already mapped correctly"
            },
            "KAS": {
                "type": "Cash",
                "reason": "Cash accounts",
                "action": "No change needed, already mapped correctly"
            },
            "BAL": {
                "type": "Various",
                "reason": "Balance sheet accounts - Mixed types",
                "action": "Review individual accounts"
            },
            "VW": {
                "type": "Expense",
                "reason": "Verbruiksrekeningen (Expense accounts)",
                "action": "No change needed for expense accounts"
            }
        }
        
        # Create mapping proposals
        mapping_proposals = []
        
        # If using groups, enhance with group information
        if use_groups:
            from .eboekhouden_group_analysis import get_group_mapping
            group_result = get_group_mapping()
            
            if group_result.get("success"):
                # Create group-based proposals
                for group_info in group_result["groups"]:
                    proposal = {
                        "type": "group",
                        "identifier": group_info["group_code"],
                        "name": group_info["inferred_name"],
                        "categories": group_info["categories"],
                        "account_count": group_info["account_count"],
                        "account_range": group_info["account_range"],
                        "sample_accounts": group_info["sample_accounts"],
                        "current_type": "Various",
                        "suggested_mapping": None
                    }
                    
                    # Suggest mapping based on group
                    if "Vorderingen" in group_info["inferred_name"] or "DEB" in group_info["categories"]:
                        proposal["suggested_mapping"] = {
                            "type": "Receivable",
                            "reason": "Vorderingen/Debiteuren group - Customer receivables",
                            "action": "Will require party (Customer) for journal entries"
                        }
                    elif "Crediteuren" in group_info["inferred_name"] or "CRED" in group_info["categories"]:
                        proposal["suggested_mapping"] = {
                            "type": "Payable",
                            "reason": "Crediteuren group - Supplier payables",
                            "action": "Will require party (Supplier) for journal entries"
                        }
                    elif "Bank" in group_info["inferred_name"] or "FIN" in group_info["categories"]:
                        proposal["suggested_mapping"] = {
                            "type": "Bank",
                            "reason": "Financial/Bank accounts",
                            "action": "No change needed, already mapped correctly"
                        }
                    
                    mapping_proposals.append(proposal)
        
        # Add category-based proposals (only if not using groups or as fallback)
        if not use_groups:
            for category, data in category_analysis.items():
                proposal = {
                    "type": "category",
                    "identifier": category,
                    "name": category,
                    "category": category,
                    "account_count": data["count"],
                    "sample_accounts": data["accounts"][:5],  # Show first 5 as samples
                    "current_type": "Various",
                    "suggested_mapping": suggested_mappings.get(category, {})
                }
                
                # Check current ERPNext types for these accounts
                sample_types = set()
                for acc in data["accounts"][:10]:
                    erpnext_type = frappe.db.get_value(
                        "Account", 
                        {"account_number": acc["code"]},
                        "account_type"
                    )
                    if erpnext_type:
                        sample_types.add(erpnext_type)
                
                if sample_types:
                    proposal["current_erpnext_types"] = list(sample_types)
                
                mapping_proposals.append(proposal)
        
        return {
            "success": True,
            "total_accounts": len(accounts),
            "categories_found": len(category_analysis),
            "groups_found": len(group_analysis),
            "mapping_proposals": mapping_proposals,
            "category_details": category_analysis,
            "group_details": group_analysis
        }
        
    except Exception as e:
        import traceback
        frappe.log_error(traceback.format_exc(), "Account Category Analysis")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def apply_account_type_mappings(mappings):
    """
    Step 2: Apply the user-confirmed mappings
    
    Args:
        mappings: Dict of category -> target_type mappings
                 e.g., {"DEB": "Receivable", "CRED": "Payable"}
    """
    
    try:
        if isinstance(mappings, str):
            mappings = json.loads(mappings)
        
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        api = EBoekhoudenAPI()
        
        # Get chart of accounts
        accounts_result = api.get_chart_of_accounts()
        if not accounts_result["success"]:
            return {"success": False, "error": "Failed to get chart of accounts"}
        
        accounts_data = json.loads(accounts_result["data"])
        accounts = accounts_data.get("items", [])
        
        results = {
            "updated": {},
            "skipped": [],
            "not_found": [],
            "errors": []
        }
        
        # Initialize result categories
        for category in mappings:
            results["updated"][category] = []
        
        # Process accounts
        for account_data in accounts:
            account_code = account_data.get("code", "")
            category = account_data.get("category", "")
            description = account_data.get("description", "")
            
            # Skip if category not in mappings
            if category not in mappings:
                continue
            
            target_type = mappings[category]
            
            # Skip if target type is "skip" or empty
            if not target_type or target_type.lower() == "skip":
                results["skipped"].append(f"{account_code} - {description} ({category})")
                continue
            
            # Find the account in ERPNext
            account_info = frappe.db.get_value(
                "Account",
                {"account_number": account_code},
                ["name", "account_type", "root_type"],
                as_dict=True
            )
            
            if not account_info:
                results["not_found"].append(f"{account_code} - {description} ({category})")
                continue
            
            # Skip if already correct type
            if account_info.account_type == target_type:
                results["skipped"].append(
                    f"{account_code} - {description} already {target_type}"
                )
                continue
            
            # Update the account
            try:
                account = frappe.get_doc("Account", account_info.name)
                old_type = account.account_type
                account.account_type = target_type
                
                # Ensure correct root type
                if target_type == "Receivable":
                    account.root_type = "Asset"
                elif target_type == "Payable":
                    account.root_type = "Liability"
                # Other types keep their existing root type
                
                account.save(ignore_permissions=True)
                
                results["updated"][category].append({
                    "code": account_code,
                    "name": account.account_name,
                    "old_type": old_type,
                    "new_type": target_type
                })
                
            except Exception as e:
                results["errors"].append({
                    "account": f"{account_code} - {description}",
                    "error": str(e)
                })
        
        # Commit changes
        frappe.db.commit()
        
        # Calculate summary
        total_updated = sum(len(updates) for updates in results["updated"].values())
        
        # Set default accounts if needed
        if "DEB" in mappings and mappings["DEB"] == "Receivable":
            # Try to set 13900 as default receivable account
            _set_default_account("13900", "default_receivable_account")
        
        if "CRED" in mappings and mappings["CRED"] == "Payable":
            # Try to set a common payable account as default
            _set_default_account("19290", "default_payable_account")
        
        return {
            "success": len(results["errors"]) == 0,
            "results": results,
            "summary": {
                "total_updated": total_updated,
                "total_skipped": len(results["skipped"]),
                "total_not_found": len(results["not_found"]),
                "total_errors": len(results["errors"])
            }
        }
        
    except Exception as e:
        import traceback
        frappe.log_error(traceback.format_exc(), "Apply Account Type Mappings")
        return {"success": False, "error": str(e)}


def _set_default_account(account_code, field_name):
    """
    Helper to set default account in company settings
    """
    try:
        account_name = frappe.db.get_value(
            "Account",
            {"account_number": account_code},
            "name"
        )
        
        if not account_name:
            return
        
        account = frappe.get_doc("Account", account_name)
        company = account.company
        
        if company:
            company_doc = frappe.get_doc("Company", company)
            setattr(company_doc, field_name, account_name)
            company_doc.save(ignore_permissions=True)
            
    except Exception:
        pass  # Silently fail, not critical


@frappe.whitelist()
def get_mapping_preview(mappings):
    """
    Preview what will happen with the proposed mappings
    """
    
    try:
        if isinstance(mappings, str):
            mappings = json.loads(mappings)
        
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        api = EBoekhoudenAPI()
        
        # Get chart of accounts
        accounts_result = api.get_chart_of_accounts()
        if not accounts_result["success"]:
            return {"success": False, "error": "Failed to get chart of accounts"}
        
        accounts_data = json.loads(accounts_result["data"])
        accounts = accounts_data.get("items", [])
        
        preview = {}
        
        for category, target_type in mappings.items():
            if not target_type or target_type.lower() == "skip":
                continue
                
            preview[category] = {
                "target_type": target_type,
                "accounts_to_update": [],
                "accounts_already_correct": [],
                "accounts_not_found": []
            }
            
            # Find accounts in this category
            category_accounts = [a for a in accounts if a.get("category") == category]
            
            for account_data in category_accounts:
                account_code = account_data.get("code", "")
                description = account_data.get("description", "")
                
                # Check current state in ERPNext
                account_info = frappe.db.get_value(
                    "Account",
                    {"account_number": account_code},
                    ["name", "account_type"],
                    as_dict=True
                )
                
                if not account_info:
                    preview[category]["accounts_not_found"].append(
                        f"{account_code} - {description}"
                    )
                elif account_info.account_type == target_type:
                    preview[category]["accounts_already_correct"].append(
                        f"{account_code} - {description}"
                    )
                else:
                    preview[category]["accounts_to_update"].append({
                        "code": account_code,
                        "description": description,
                        "current_type": account_info.account_type,
                        "new_type": target_type
                    })
        
        return {
            "success": True,
            "preview": preview
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}