"""
Test Chart of Accounts migration with existing root accounts
"""

import frappe

@frappe.whitelist()
def test_chart_of_accounts_migration_with_roots():
    """
    Test the Chart of Accounts migration now that root accounts exist
    """
    try:
        # Get settings
        settings = frappe.get_single("E-Boekhouden Settings")
        if not settings.api_token:
            return {"success": False, "error": "E-Boekhouden API not configured"}
        
        # Create a test migration document
        migration = frappe.new_doc("E-Boekhouden Migration")
        migration.migration_name = f"Test CoA Migration {frappe.utils.now()}"
        migration.migration_type = "Chart of Accounts Only"
        migration.company = settings.default_company
        migration.migrate_accounts = 1
        migration.clear_existing_accounts = 0  # Don't clear since we just created root accounts
        migration.dry_run = 0  # Run actual migration to test it works
        
        # Initialize counters like start_migration() does
        migration.total_records = 0
        migration.imported_records = 0
        migration.failed_records = 0
        
        # Test the migration
        result = migration.migrate_chart_of_accounts(settings)
        
        # Check current account status
        account_count = frappe.db.count("Account", {"company": settings.default_company})
        
        return {
            "success": True,
            "migration_result": result,
            "current_account_count": account_count,
            "test_mode": "actual_migration"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist() 
def test_single_account_creation():
    """
    Test creating a single E-boekhouden account to check if the hierarchy works
    """
    try:
        settings = frappe.get_single("E-Boekhouden Settings")
        migration = frappe.new_doc("E-Boekhouden Migration")
        migration.company = settings.default_company
        
        # Initialize counters
        migration.total_records = 0
        migration.imported_records = 0
        migration.failed_records = 0
        
        # Create test account data matching E-boekhouden format
        test_account = {
            "code": "8000",
            "description": "Test Opbrengsten Account",
            "category": "VW",
            "group": "80"
        }
        
        # Set up group accounts (this should be done by the migration)
        migration._group_accounts = set(["80"])  # Mark 80 as group
        migration._all_account_codes = set(["80", "8000"])
        
        # Try to create the account
        result = migration.create_account(test_account)
        
        return {
            "success": True,
            "account_created": result,
            "test_account": test_account
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def debug_account_classification():
    """
    Debug why accounts are being classified as root accounts incorrectly
    """
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        # Get settings
        settings = frappe.get_single("E-Boekhouden Settings")
        if not settings.api_token:
            return {"success": False, "error": "E-Boekhouden API not configured"}
        
        # Get first few accounts from E-boekhouden
        api = EBoekhoudenAPI(settings)
        result = api.get_chart_of_accounts()
        
        if not result["success"]:
            return {"success": False, "error": f"API failed: {result['error']}"}
        
        import json
        data = json.loads(result["data"])
        accounts_data = data.get("items", [])
        
        # Analyze first 10 accounts
        analysis = []
        for account_data in accounts_data[:10]:
            account_code = account_data.get('code', '')
            group_code = account_data.get('group', '')
            category = account_data.get('category', '')
            description = account_data.get('description', '')
            
            # Apply same logic as create_account method
            is_root_by_code = (len(account_code) <= 2 or 
                              (len(account_code) == 3 and account_code.startswith("00")))
            is_root_by_group = (group_code and group_code in ['001', '002', '003', '004', '005', '006', '007', '008', '009', '010'])
            is_root_account = is_root_by_code or is_root_by_group
            
            analysis.append({
                "code": account_code,
                "description": description[:50],
                "category": category,
                "group": group_code,
                "is_root_by_code": is_root_by_code,
                "is_root_by_group": is_root_by_group,
                "classified_as_root": is_root_account
            })
        
        return {
            "success": True,
            "total_accounts": len(accounts_data),
            "sample_analysis": analysis
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }