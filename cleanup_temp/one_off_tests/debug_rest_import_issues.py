import frappe
from verenigingen.utils.eboekhouden_rest_iterator import EBoekhoudenRESTIterator
from verenigingen.utils.eboekhouden_rest_full_migration import EBoekhoudenRESTFullMigration

@frappe.whitelist()
def debug_rest_import_issues():
    """Debug why REST import is stopping early and failing"""
    try:
        # Get the latest migration
        migration = frappe.get_all("E-Boekhouden Migration", 
            filters={"migration_status": ["in", ["Completed", "Failed", "In Progress"]]},
            fields=["name", "migration_status", "imported_records", "failed_records", "error_log"],
            order_by="creation desc",
            limit=1
        )
        
        if not migration:
            return {"success": False, "error": "No migrations found"}
        
        migration = migration[0]
        migration_doc = frappe.get_doc("E-Boekhouden Migration", migration["name"])
        
        result = {
            "migration_info": {
                "name": migration["name"],
                "status": migration["migration_status"],
                "imported": migration["imported_records"],
                "failed": migration["failed_records"]
            }
        }
        
        # 1. Check iterator range estimation
        iterator = EBoekhoudenRESTIterator()
        range_result = iterator.estimate_id_range()
        result["iterator_range"] = range_result
        
        # 2. Test specific mutations around where it might be stopping
        test_points = [600, 650, 679, 680, 700, 750, 1000, 5000, 7000, 7142]
        mutation_tests = {}
        
        for test_id in test_points:
            mutation = iterator.fetch_mutation_detail(test_id)
            mutation_tests[test_id] = {
                "exists": bool(mutation),
                "data": mutation.get("id") if mutation else None,
                "date": mutation.get("date") if mutation else None,
                "type": mutation.get("type") if mutation else None
            }
        
        result["mutation_tests"] = mutation_tests
        
        # 3. Check for account permission issues
        # Find Crediteuren accounts
        crediteuren_accounts = frappe.get_all("Account",
            filters={
                "account_name": ["like", "%Crediteuren%"],
                "company": frappe.get_single("E-Boekhouden Settings").default_company
            },
            fields=["name", "account_name", "account_type", "root_type"]
        )
        result["crediteuren_accounts"] = crediteuren_accounts
        
        # 4. Sample recent error entries from migration log
        if migration_doc.error_log:
            import json
            try:
                error_log = json.loads(migration_doc.error_log)
                # Get last 10 errors
                recent_errors = error_log[-10:] if len(error_log) > 10 else error_log
                result["recent_errors"] = recent_errors
            except:
                result["recent_errors"] = "Could not parse error log"
        
        # 5. Check if consecutive not found limit was hit
        # This would indicate why it stopped at 679
        result["analysis"] = {
            "likely_cause": "Unknown",
            "recommendations": []
        }
        
        if range_result.get("highest_id", 0) < 7142:
            result["analysis"]["likely_cause"] = "Iterator range estimation too low"
            result["analysis"]["recommendations"].append("Update range estimation logic")
        
        if mutation_tests.get(679, {}).get("exists") and not mutation_tests.get(680, {}).get("exists"):
            result["analysis"]["likely_cause"] = "Consecutive not found limit hit at 679"
            result["analysis"]["recommendations"].append("Check max_consecutive_not_found setting")
        
        return {"success": True, "result": result}
        
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

@frappe.whitelist()
def debug_account_permissions():
    """Debug account permission issues for Payment Entry"""
    try:
        # Get all accounts that might be used in payments
        accounts = frappe.get_all("Account",
            filters={
                "company": frappe.get_single("E-Boekhouden Settings").default_company,
                "account_name": ["like", "%Crediteuren%"]
            },
            fields=["name", "account_name", "account_type", "root_type", "is_group"]
        )
        
        result = {"accounts": accounts, "issues": []}
        
        for account in accounts:
            # Check if account type is correct for Payment Entry
            if account["account_type"] not in ["Bank", "Cash", "Receivable", "Payable"]:
                result["issues"].append({
                    "account": account["name"],
                    "issue": f"Account type '{account['account_type']}' not allowed in Payment Entry",
                    "suggestion": "Should be 'Payable' for crediteuren accounts"
                })
            
            if account["is_group"]:
                result["issues"].append({
                    "account": account["name"], 
                    "issue": "Group account cannot be used in transactions",
                    "suggestion": "Use child accounts instead"
                })
        
        return {"success": True, "result": result}
        
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

@frappe.whitelist()
def fix_crediteuren_accounts():
    """Fix Crediteuren accounts to be Payable type"""
    try:
        company = frappe.get_single("E-Boekhouden Settings").default_company
        
        # Find all Crediteuren accounts that are not Payable
        accounts = frappe.get_all("Account",
            filters={
                "company": company,
                "account_name": ["like", "%Crediteuren%"],
                "account_type": ["!=", "Payable"],
                "is_group": 0
            },
            fields=["name", "account_name", "account_type"]
        )
        
        fixed_count = 0
        for account in accounts:
            doc = frappe.get_doc("Account", account["name"])
            doc.account_type = "Payable"
            doc.root_type = "Liability"
            doc.save()
            fixed_count += 1
        
        return {
            "success": True,
            "fixed_count": fixed_count,
            "accounts_fixed": [acc["name"] for acc in accounts]
        }
        
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

@frappe.whitelist()
def test_mutation_range(start_id=650, end_id=750):
    """Test mutations around where import stopped"""
    try:
        iterator = EBoekhoudenRESTIterator()
        
        results = {}
        consecutive_not_found = 0
        
        for mutation_id in range(start_id, end_id + 1):
            mutation = iterator.fetch_mutation_detail(mutation_id)
            
            if mutation:
                results[mutation_id] = {
                    "found": True,
                    "id": mutation.get("id"),
                    "date": mutation.get("date"),
                    "type": mutation.get("type"),
                    "description": mutation.get("description", "")[:50]
                }
                consecutive_not_found = 0
            else:
                results[mutation_id] = {"found": False}
                consecutive_not_found += 1
                
                # Check if we hit the consecutive limit
                if consecutive_not_found >= 100:
                    results[f"stopped_at_{mutation_id}"] = f"Hit consecutive not found limit: {consecutive_not_found}"
                    break
        
        return {"success": True, "results": results}
        
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }