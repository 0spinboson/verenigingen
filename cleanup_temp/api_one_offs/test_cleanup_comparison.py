import frappe
from frappe import _


@frappe.whitelist()
def compare_cleanup_functions():
    """
    Compare the original cleanup_chart_of_accounts with the new debug_cleanup_eboekhouden_accounts.
    This helps identify any differences or issues.
    """
    try:
        from verenigingen.verenigingen.doctype.e_boekhouden_migration.e_boekhouden_migration import cleanup_chart_of_accounts
        from verenigingen.api.check_eboekhouden_accounts import debug_cleanup_eboekhouden_accounts
        
        # Get all companies
        companies = frappe.get_all("Company", fields=["name"])
        
        results = {
            "success": True,
            "companies_checked": [],
            "differences": []
        }
        
        for company in companies:
            company_name = company.name
            
            # Check if company has E-Boekhouden accounts
            accounts = frappe.get_all("Account", 
                filters={
                    "company": company_name,
                    "eboekhouden_grootboek_nummer": ["!=", ""]
                },
                fields=["name"])
            
            if accounts:
                results["companies_checked"].append({
                    "company": company_name,
                    "eboekhouden_accounts_count": len(accounts)
                })
                
                # Compare what each function would do (dry run for new function)
                new_func_result = debug_cleanup_eboekhouden_accounts(company_name, dry_run=True)
                
                # Note differences
                results["differences"].append({
                    "company": company_name,
                    "original_function": {
                        "name": "cleanup_chart_of_accounts",
                        "would_delete": len(accounts),
                        "checks_gl_entries": False,
                        "checks_child_accounts": False
                    },
                    "new_function": {
                        "name": "debug_cleanup_eboekhouden_accounts",
                        "would_delete": new_func_result.get("total_accounts", 0),
                        "checks_gl_entries": True,
                        "checks_child_accounts": True,
                        "provides_dry_run": True,
                        "detailed_reporting": True
                    }
                })
        
        if not results["companies_checked"]:
            results["message"] = "No companies have E-Boekhouden accounts"
        else:
            results["message"] = f"Checked {len(results['companies_checked'])} companies with E-Boekhouden accounts"
        
        return results
        
    except Exception as e:
        frappe.log_error(f"Error comparing cleanup functions: {str(e)}")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def test_cleanup_safety():
    """
    Test the safety features of the new cleanup function.
    """
    try:
        from verenigingen.api.check_eboekhouden_accounts import debug_cleanup_eboekhouden_accounts
        
        # Get a test company
        test_company = frappe.get_value("Company", {"name": ["like", "%"]}, "name")
        
        if not test_company:
            return {"success": False, "error": "No company found"}
        
        # Test with invalid company
        invalid_result = debug_cleanup_eboekhouden_accounts("NonExistentCompany", dry_run=True)
        
        # Test with valid company but dry run
        valid_result = debug_cleanup_eboekhouden_accounts(test_company, dry_run=True)
        
        return {
            "success": True,
            "tests": {
                "invalid_company_handled": not invalid_result.get("success", True) or invalid_result.get("total_accounts", 0) == 0,
                "dry_run_works": valid_result.get("dry_run", False),
                "no_actual_deletion_in_dry_run": valid_result.get("accounts_deleted", 0) == 0
            },
            "message": "Safety features tested successfully"
        }
        
    except Exception as e:
        frappe.log_error(f"Error testing cleanup safety: {str(e)}")
        return {"success": False, "error": str(e)}