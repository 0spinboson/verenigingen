"""
Analyze Chart of Accounts migration issues
"""

import frappe

@frappe.whitelist()
def analyze_coa_migration_issue():
    """
    Analyze why Chart of Accounts migration is skipping all accounts
    """
    try:
        # Get the default company
        settings = frappe.get_single("E-Boekhouden Settings")
        company = settings.default_company
        
        if not company:
            return {"success": False, "error": "No default company found"}
        
        # Count existing accounts
        existing_accounts = frappe.db.count("Account", {"company": company})
        
        # Check for specific accounts that might be causing issues
        sample_accounts = frappe.db.get_all("Account", 
            filters={"company": company}, 
            fields=["name", "account_name", "account_number", "is_group", "parent_account"],
            limit=10
        )
        
        # Check for E-boekhouden specific accounts
        eb_accounts = frappe.db.get_all("Account",
            filters={
                "company": company,
                "account_number": ["!=", ""]
            },
            fields=["name", "account_name", "account_number"],
            limit=20
        )
        
        # Check for duplicate account numbers
        duplicate_check = frappe.db.sql("""
            SELECT account_number, COUNT(*) as count 
            FROM `tabAccount` 
            WHERE company = %s AND account_number IS NOT NULL AND account_number != ''
            GROUP BY account_number 
            HAVING count > 1
        """, (company,), as_dict=True)
        
        return {
            "success": True,
            "company": company,
            "total_existing_accounts": existing_accounts,
            "sample_accounts": sample_accounts,
            "eb_accounts": eb_accounts,
            "duplicate_account_numbers": duplicate_check,
            "analysis": {
                "has_existing_accounts": existing_accounts > 0,
                "has_eb_accounts": len(eb_accounts) > 0,
                "has_duplicates": len(duplicate_check) > 0
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def check_migration_skip_logic():
    """
    Check the logic that's causing accounts to be skipped
    """
    try:
        # Get some sample E-boekhouden data to understand the skip logic
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        api = EBoekhoudenAPI()
        coa_result = api.get_chart_of_accounts()
        
        if not coa_result["success"]:
            return {"success": False, "error": "Failed to get E-boekhouden CoA data"}
        
        import json
        coa_data = json.loads(coa_result["data"])
        accounts = coa_data.get("items", [])[:5]  # Get first 5 for analysis
        
        # Check if these accounts exist in ERPNext
        settings = frappe.get_single("E-Boekhouden Settings")
        company = settings.default_company
        
        analysis = []
        for acc in accounts:
            account_code = acc.get("code", "")
            account_name = acc.get("description", "")
            
            # Check if account exists by code
            existing_by_code = frappe.db.exists("Account", {
                "company": company,
                "account_number": account_code
            })
            
            # Check if account exists by name pattern
            existing_by_name = frappe.db.exists("Account", {
                "company": company,
                "account_name": account_name
            })
            
            analysis.append({
                "eb_code": account_code,
                "eb_name": account_name,
                "exists_by_code": bool(existing_by_code),
                "exists_by_name": bool(existing_by_name),
                "existing_account_by_code": existing_by_code,
                "existing_account_by_name": existing_by_name
            })
        
        return {
            "success": True,
            "company": company,
            "sample_analysis": analysis,
            "total_eb_accounts": len(coa_data.get("items", [])),
            "recommendation": "Check if accounts are being skipped due to existing account_number matches"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def force_coa_cleanup_and_reimport():
    """
    Clean up existing Chart of Accounts and force a fresh import
    """
    try:
        settings = frappe.get_single("E-Boekhouden Settings")
        company = settings.default_company
        
        if not company:
            return {"success": False, "error": "No default company found"}
        
        # Get accounts that look like they came from E-boekhouden (have account numbers)
        eb_accounts = frappe.db.get_all("Account",
            filters={
                "company": company,
                "account_number": ["!=", ""],
                "is_group": 0  # Only leaf accounts first
            },
            fields=["name"]
        )
        
        # Delete E-boekhouden accounts (leaf accounts first to avoid dependency issues)
        deleted_count = 0
        errors = []
        
        for acc in eb_accounts:
            try:
                # Check if account has transactions
                has_transactions = frappe.db.exists("GL Entry", {"account": acc.name})
                
                if not has_transactions:
                    frappe.delete_doc("Account", acc.name, force=1)
                    deleted_count += 1
                else:
                    errors.append(f"Account {acc.name} has transactions, cannot delete")
                    
            except Exception as e:
                errors.append(f"Failed to delete {acc.name}: {str(e)}")
        
        frappe.db.commit()
        
        return {
            "success": True,
            "deleted_accounts": deleted_count,
            "total_eb_accounts": len(eb_accounts),
            "errors": errors,
            "message": f"Deleted {deleted_count} E-boekhouden accounts. Ready for fresh import."
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }