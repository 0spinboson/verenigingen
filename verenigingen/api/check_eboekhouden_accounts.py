import frappe
from frappe import _


@frappe.whitelist()
def check_eboekhouden_accounts(company=None):
    """
    Check for E-Boekhouden accounts in the system.
    Returns accounts with eboekhouden_grootboek_nummer field set.
    """
    try:
        filters = {}
        if company:
            filters["company"] = company
            
        # Get all accounts with eboekhouden_grootboek_nummer set (not null and not empty)
        sql_filters = ["eboekhouden_grootboek_nummer IS NOT NULL", "eboekhouden_grootboek_nummer != ''"]
        
        if company:
            sql_filters.append("company = %(company)s")
        
        accounts = frappe.db.sql(f"""
            SELECT name, account_name, account_number, eboekhouden_grootboek_nummer,
                   is_group, parent_account, company, account_type, root_type
            FROM `tabAccount`
            WHERE {' AND '.join(sql_filters)}
            ORDER BY lft
        """, {"company": company}, as_dict=True)
        
        # Group accounts by type
        leaf_accounts = []
        group_accounts = []
        
        for account in accounts:
            if account.is_group:
                group_accounts.append(account)
            else:
                leaf_accounts.append(account)
        
        # Get additional statistics
        account_types = {}
        root_types = {}
        companies = {}
        
        for account in accounts:
            # Count by account type
            if account.account_type:
                account_types[account.account_type] = account_types.get(account.account_type, 0) + 1
            
            # Count by root type
            if account.root_type:
                root_types[account.root_type] = root_types.get(account.root_type, 0) + 1
                
            # Count by company
            if account.company:
                companies[account.company] = companies.get(account.company, 0) + 1
        
        return {
            "success": True,
            "total_accounts": len(accounts),
            "leaf_accounts_count": len(leaf_accounts),
            "group_accounts_count": len(group_accounts),
            "by_account_type": account_types,
            "by_root_type": root_types,
            "by_company": companies,
            "leaf_accounts": leaf_accounts[:10],  # Show first 10 leaf accounts
            "group_accounts": group_accounts[:10],  # Show first 10 group accounts
            "message": f"Found {len(accounts)} E-Boekhouden accounts in the system"
        }
        
    except Exception as e:
        frappe.log_error(f"Error checking E-Boekhouden accounts: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }



@frappe.whitelist()
def debug_cleanup_eboekhouden_accounts(company, dry_run=True):
    """
    Debug and optionally clean up E-Boekhouden accounts.
    
    Args:
        company: Company name to clean up accounts for
        dry_run: If True, only simulate the cleanup without deleting
    """
    try:
        if not company:
            return {"success": False, "error": "Company is required"}
            
        # Get all accounts with eboekhouden_grootboek_nummer set (not null and not empty)
        accounts = frappe.db.sql("""
            SELECT name, is_group, account_name, eboekhouden_grootboek_nummer
            FROM `tabAccount`
            WHERE company = %s
            AND eboekhouden_grootboek_nummer IS NOT NULL
            AND eboekhouden_grootboek_nummer != ''
            ORDER BY lft
        """, company, as_dict=True)
        
        if not accounts:
            return {
                "success": True,
                "message": "No E-Boekhouden accounts found for cleanup",
                "total_accounts": 0
            }
        
        # Sort accounts - leaf accounts first, then parent accounts
        leaf_accounts = [a for a in accounts if not a.is_group]
        group_accounts = [a for a in accounts if a.is_group]
        
        result = {
            "success": True,
            "total_accounts": len(accounts),
            "leaf_accounts": len(leaf_accounts),
            "group_accounts": len(group_accounts),
            "dry_run": dry_run,
            "deleted_accounts": [],
            "failed_accounts": [],
            "accounts_deleted": 0
        }
        
        if dry_run:
            result["message"] = f"DRY RUN: Would delete {len(accounts)} E-Boekhouden accounts"
            result["accounts_to_delete"] = {
                "leaf_accounts": [{"name": a.name, "account_name": a.account_name} for a in leaf_accounts[:5]],
                "group_accounts": [{"name": a.name, "account_name": a.account_name} for a in group_accounts[:5]]
            }
            return result
        
        # Actual deletion
        # Delete leaf accounts first
        for account in leaf_accounts:
            try:
                # Check if account has any transactions
                has_transactions = frappe.db.exists("GL Entry", {"account": account.name})
                
                if has_transactions:
                    result["failed_accounts"].append({
                        "name": account.name,
                        "reason": "Has GL entries"
                    })
                    continue
                    
                frappe.delete_doc("Account", account.name, force=True)
                result["deleted_accounts"].append(account.name)
                result["accounts_deleted"] += 1
                
            except Exception as e:
                result["failed_accounts"].append({
                    "name": account.name,
                    "reason": str(e)
                })
                frappe.log_error(f"Failed to delete account {account.name}: {str(e)}")
        
        # Then delete group accounts
        for account in group_accounts:
            try:
                # Check if account has children
                has_children = frappe.db.exists("Account", {"parent_account": account.name})
                
                if has_children:
                    result["failed_accounts"].append({
                        "name": account.name,
                        "reason": "Has child accounts"
                    })
                    continue
                    
                frappe.delete_doc("Account", account.name, force=True)
                result["deleted_accounts"].append(account.name)
                result["accounts_deleted"] += 1
                
            except Exception as e:
                result["failed_accounts"].append({
                    "name": account.name,
                    "reason": str(e)
                })
                frappe.log_error(f"Failed to delete account {account.name}: {str(e)}")
        
        frappe.db.commit()
        
        result["message"] = f"Deleted {result['accounts_deleted']} out of {len(accounts)} E-Boekhouden accounts"
        
        return result
        
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(f"Error in cleanup E-Boekhouden accounts: {str(e)}")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def get_eboekhouden_account_details(account_name):
    """
    Get detailed information about a specific E-Boekhouden account.
    """
    try:
        if not account_name:
            return {"success": False, "error": "Account name is required"}
            
        account = frappe.get_doc("Account", account_name)
        
        # Check if it's an E-Boekhouden account
        if not account.get("eboekhouden_grootboek_nummer"):
            return {"success": False, "error": "Not an E-Boekhouden account"}
        
        # Get GL entries count
        gl_entries_count = frappe.db.count("GL Entry", {"account": account_name})
        
        # Get child accounts if it's a group
        child_accounts = []
        if account.is_group:
            child_accounts = frappe.get_all("Account",
                filters={"parent_account": account_name},
                fields=["name", "account_name", "eboekhouden_grootboek_nummer"])
        
        # Get recent GL entries
        recent_gl_entries = frappe.get_all("GL Entry",
            filters={"account": account_name},
            fields=["posting_date", "voucher_type", "voucher_no", "debit", "credit", "remarks"],
            order_by="posting_date desc",
            limit=5)
        
        return {
            "success": True,
            "account": {
                "name": account.name,
                "account_name": account.account_name,
                "account_number": account.get("account_number"),
                "eboekhouden_grootboek_nummer": account.eboekhouden_grootboek_nummer,
                "is_group": account.is_group,
                "parent_account": account.parent_account,
                "company": account.company,
                "account_type": account.account_type,
                "root_type": account.root_type,
                "disabled": account.disabled
            },
            "gl_entries_count": gl_entries_count,
            "child_accounts_count": len(child_accounts),
            "child_accounts": child_accounts,
            "recent_gl_entries": recent_gl_entries,
            "can_delete": gl_entries_count == 0 and len(child_accounts) == 0
        }
        
    except Exception as e:
        frappe.log_error(f"Error getting E-Boekhouden account details: {str(e)}")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def debug_group_055():
    """Debug why group 055 accounts aren't being classified as Income"""
    try:
        import json
        
        # Get settings
        settings = frappe.get_single("E-Boekhouden Settings")
        
        # Get E-Boekhouden data  
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        api = EBoekhoudenAPI(settings)
        
        result = api.get_chart_of_accounts()
        if not result["success"]:
            return f"Error getting CoA: {result['error']}"
        
        data = json.loads(result["data"])
        accounts_data = data.get("items", [])
        
        response = []
        response.append("=== GROUP 055 ACCOUNTS ANALYSIS ===")
        response.append(f"Total accounts from API: {len(accounts_data)}")
        
        # Find accounts with group 055
        group_055_accounts = []
        for account in accounts_data:
            group = account.get('group', '')
            if group == '055':
                group_055_accounts.append(account)
        
        response.append(f"Found {len(group_055_accounts)} accounts with group 055:")
        for acc in group_055_accounts:
            response.append(f"  Code: {acc.get('code', 'N/A')}")
            response.append(f"  Description: {acc.get('description', 'N/A')}")
            response.append(f"  Category: {acc.get('category', 'N/A')}")
            response.append(f"  Group: {acc.get('group', 'N/A')}")
            response.append(f"  Balance: {acc.get('balance', 'N/A')}")
            response.append("  ---")
        
        # Also check 8xxx accounts to see their groups
        response.append("\n=== 8XXX ACCOUNTS ANALYSIS ===")
        accounts_8xxx = []
        for account in accounts_data:
            code = account.get('code', '')
            if code.startswith('8'):
                accounts_8xxx.append(account)
        
        response.append(f"Found {len(accounts_8xxx)} accounts starting with 8:")
        for acc in accounts_8xxx[:10]:  # Show first 10
            response.append(f"  Code: {acc.get('code', 'N/A')}")
            response.append(f"  Description: {acc.get('description', 'N/A')}")
            response.append(f"  Category: {acc.get('category', 'N/A')}")
            response.append(f"  Group: {acc.get('group', 'N/A')}")
            response.append("  ---")
        
        # Check current database state
        response.append("\n=== CURRENT DATABASE STATE ===")
        company = settings.default_company
        accounts_in_db = frappe.db.sql("""
            SELECT name, account_name, account_type, root_type, eboekhouden_grootboek_nummer
            FROM `tabAccount`
            WHERE company = %s
            AND eboekhouden_grootboek_nummer LIKE '8%%'
            ORDER BY eboekhouden_grootboek_nummer
        """, company, as_dict=True)
        
        response.append(f"Found {len(accounts_in_db)} accounts in database starting with 8:")
        for acc in accounts_in_db[:10]:  # Show first 10
            response.append(f"  Code: {acc.get('eboekhouden_grootboek_nummer', 'N/A')}")
            response.append(f"  Name: {acc.get('account_name', 'N/A')}")
            response.append(f"  Type: {acc.get('account_type', 'N/A')}")
            response.append(f"  Root: {acc.get('root_type', 'N/A')}")
            response.append("  ---")
        
        # Check group mappings
        response.append("\n=== GROUP MAPPINGS ===")
        group_mappings = settings.account_group_mappings
        if group_mappings:
            response.append("Current group mappings:")
            for line in group_mappings.split('\n'):
                if line.strip():
                    response.append(f"  {line.strip()}")
        else:
            response.append("No group mappings configured")
        
        return "\n".join(response)
            
    except Exception as e:
        return f"Error: {e}\n{frappe.get_traceback()}"


@frappe.whitelist()
def fix_group_055_accounts():
    """Fix existing accounts that should be group 055 (Income) but are classified as Expense"""
    try:
        import json
        
        # Get settings
        settings = frappe.get_single("E-Boekhouden Settings")
        company = settings.default_company
        
        # Get E-Boekhouden data to get the correct groups
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        api = EBoekhoudenAPI(settings)
        
        result = api.get_chart_of_accounts()
        if not result["success"]:
            return f"Error getting CoA: {result['error']}"
        
        data = json.loads(result["data"])
        accounts_data = data.get("items", [])
        
        # Create a mapping of account codes to their correct group
        account_groups = {}
        for account in accounts_data:
            code = account.get('code', '')
            group = account.get('group', '')
            category = account.get('category', '')
            if code and group:
                account_groups[code] = {
                    'group': group,
                    'category': category,
                    'description': account.get('description', '')
                }
        
        # Find all accounts in database that should be group 055 (Income)
        accounts_to_fix = []
        
        # Get all accounts with E-Boekhouden numbers
        all_accounts = frappe.db.sql("""
            SELECT name, account_name, account_type, root_type, eboekhouden_grootboek_nummer
            FROM `tabAccount`
            WHERE company = %s
            AND eboekhouden_grootboek_nummer IS NOT NULL
            AND eboekhouden_grootboek_nummer != ''
        """, company, as_dict=True)
        
        for account in all_accounts:
            eb_code = account.get('eboekhouden_grootboek_nummer')
            if eb_code and eb_code in account_groups:
                eb_data = account_groups[eb_code]
                
                # Check if this should be group 055 (Income)
                if eb_data['group'] == '055':
                    # Check if it's currently incorrectly classified
                    if account.get('account_type') == 'Expense Account' and account.get('root_type') == 'Expense':
                        accounts_to_fix.append({
                            'name': account.name,
                            'account_name': account.account_name,
                            'code': eb_code,
                            'current_type': account.account_type,
                            'current_root': account.root_type,
                            'should_be_type': 'Income Account',
                            'should_be_root': 'Income'
                        })
        
        response = []
        response.append(f"=== GROUP 055 ACCOUNTS FIX ===")
        response.append(f"Found {len(accounts_to_fix)} accounts to fix:")
        
        if not accounts_to_fix:
            response.append("No accounts need fixing!")
            return "\n".join(response)
        
        # Show accounts that will be fixed
        for acc in accounts_to_fix:
            response.append(f"  {acc['code']} - {acc['account_name']}")
            response.append(f"    Current: {acc['current_type']} / {acc['current_root']}")
            response.append(f"    Should be: {acc['should_be_type']} / {acc['should_be_root']}")
        
        # Find the correct parent account for Income accounts
        income_parent = frappe.db.get_value("Account", {
            "company": company,
            "account_name": "Opbrengsten"
        }, "name")
        
        if not income_parent:
            # Try to find any Income root account
            income_parent = frappe.db.get_value("Account", {
                "company": company,
                "root_type": "Income",
                "is_group": 1
            }, "name")
        
        if not income_parent:
            response.append("\nERROR: No Income parent account found!")
            return "\n".join(response)
        
        response.append(f"\nUsing parent account: {income_parent}")
        
        # Fix the accounts
        fixed_count = 0
        errors = []
        
        for acc in accounts_to_fix:
            try:
                # Update the account
                frappe.db.set_value("Account", acc['name'], {
                    "account_type": "Income Account",
                    "root_type": "Income",
                    "parent_account": income_parent
                })
                
                fixed_count += 1
                response.append(f"✓ Fixed: {acc['code']} - {acc['account_name']}")
                
            except Exception as e:
                errors.append(f"✗ Failed to fix {acc['code']}: {str(e)}")
                response.append(f"✗ Failed to fix {acc['code']}: {str(e)}")
        
        # Commit the changes
        frappe.db.commit()
        
        response.append(f"\n=== SUMMARY ===")
        response.append(f"Successfully fixed: {fixed_count}")
        response.append(f"Errors: {len(errors)}")
        
        return "\n".join(response)
        
    except Exception as e:
        return f"Error: {e}\n{frappe.get_traceback()}"


@frappe.whitelist()
def debug_05xxx_accounts():
    """Debug 05xxx equity accounts specifically"""
    try:
        import json
        
        response = []
        response.append("=== 05XXX EQUITY ACCOUNTS ANALYSIS ===")
        
        # Get settings
        settings = frappe.get_single("E-Boekhouden Settings")
        
        # Get E-Boekhouden data  
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        api = EBoekhoudenAPI(settings)
        
        result = api.get_chart_of_accounts()
        if not result["success"]:
            return f"Error getting CoA: {result['error']}"
        
        data = json.loads(result["data"])
        accounts_data = data.get("items", [])
        
        # Find 05xxx accounts
        equity_accounts = []
        for account in accounts_data:
            code = account.get('code', '')
            if code.startswith('05'):
                equity_accounts.append(account)
        
        response.append(f"Found {len(equity_accounts)} accounts starting with 05:")
        for acc in equity_accounts:
            response.append(f"  Code: {acc.get('code', 'N/A')}")
            response.append(f"  Description: {acc.get('description', 'N/A')}")
            response.append(f"  Category: {acc.get('category', 'N/A')}")
            response.append(f"  Group: {acc.get('group', 'N/A')}")
            response.append("  ---")
        
        return "\n".join(response)
        
    except Exception as e:
        return f"Error: {e}\n{frappe.get_traceback()}"


@frappe.whitelist()
def debug_pinv_dependencies():
    """Debug Purchase Invoice creation dependencies"""
    try:
        response = []
        response.append("=== PURCHASE INVOICE DEPENDENCIES CHECK ===")
        
        # Get settings
        settings = frappe.get_single("E-Boekhouden Settings")
        company = settings.default_company
        
        # Check required items
        response.append("\n--- ITEMS CHECK ---")
        
        # Check if ITEM-001 exists
        item_001 = frappe.db.get_value("Item", "ITEM-001", ["name", "item_name"], as_dict=True)
        if item_001:
            response.append(f"✓ ITEM-001 exists: {item_001.item_name}")
        else:
            response.append("✗ ITEM-001 does NOT exist")
        
        # Check if there are any items for expense
        expense_items = frappe.db.get_all("Item", 
            filters={"disabled": 0}, 
            fields=["name", "item_name"], 
            limit=5)
        response.append(f"Found {len(expense_items)} active items:")
        for item in expense_items:
            response.append(f"  - {item.name}: {item.item_name}")
        
        # Check suppliers
        response.append("\n--- SUPPLIERS CHECK ---")
        
        # Check if Miscellaneous supplier exists
        misc_supplier = frappe.db.get_value("Supplier", 
            {"supplier_name": "Miscellaneous"}, 
            ["name", "supplier_name"], as_dict=True)
        if misc_supplier:
            response.append(f"✓ Miscellaneous supplier exists: {misc_supplier.name}")
        else:
            response.append("✗ Miscellaneous supplier does NOT exist")
        
        # Check available suppliers
        suppliers = frappe.db.get_all("Supplier", 
            filters={"disabled": 0}, 
            fields=["name", "supplier_name"], 
            limit=5)
        response.append(f"Found {len(suppliers)} active suppliers:")
        for supplier in suppliers:
            response.append(f"  - {supplier.name}: {supplier.supplier_name}")
        
        # Check accounts
        response.append("\n--- ACCOUNTS CHECK ---")
        
        # Check if there are expense accounts
        expense_accounts = frappe.db.get_all("Account", 
            filters={
                "company": company,
                "account_type": "Expense Account",
                "is_group": 0
            }, 
            fields=["name", "account_name"], 
            limit=5)
        response.append(f"Found {len(expense_accounts)} expense accounts:")
        for acc in expense_accounts:
            response.append(f"  - {acc.name}: {acc.account_name}")
        
        # Check payable accounts  
        response.append("\n--- PAYABLE ACCOUNTS CHECK ---")
        
        payable_accounts = frappe.db.get_all("Account", 
            filters={
                "company": company,
                "account_type": "Payable",
                "is_group": 0
            }, 
            fields=["name", "account_name"], 
            limit=5)
        response.append(f"Found {len(payable_accounts)} payable accounts:")
        for acc in payable_accounts:
            response.append(f"  - {acc.name}: {acc.account_name}")
        
        # Check liability accounts as fallback
        liability_accounts = frappe.db.get_all("Account", 
            filters={
                "company": company,
                "root_type": "Liability",
                "is_group": 0
            }, 
            fields=["name", "account_name"], 
            limit=5)
        response.append(f"Found {len(liability_accounts)} liability accounts:")
        for acc in liability_accounts:
            response.append(f"  - {acc.name}: {acc.account_name}")
        
        # Check cost centers
        response.append("\n--- COST CENTERS CHECK ---")
        
        default_cost_center = settings.default_cost_center
        if default_cost_center:
            cc_exists = frappe.db.exists("Cost Center", default_cost_center)
            if cc_exists:
                response.append(f"✓ Default cost center exists: {default_cost_center}")
            else:
                response.append(f"✗ Default cost center does NOT exist: {default_cost_center}")
        else:
            response.append("✗ No default cost center configured")
        
        # Check any cost centers for company
        cost_centers = frappe.db.get_all("Cost Center", 
            filters={"company": company}, 
            fields=["name", "cost_center_name"], 
            limit=5)
        response.append(f"Found {len(cost_centers)} cost centers for company:")
        for cc in cost_centers:
            response.append(f"  - {cc.name}: {cc.cost_center_name}")
        
        return "\n".join(response)
        
    except Exception as e:
        return f"Error: {e}\n{frappe.get_traceback()}"


@frappe.whitelist()
def debug_05xxx_accounts():
    """Debug 05xxx equity accounts specifically"""
    try:
        import json
        
        response = []
        response.append("=== 05XXX EQUITY ACCOUNTS ANALYSIS ===")
        
        # Get settings
        settings = frappe.get_single("E-Boekhouden Settings")
        
        # Get E-Boekhouden data  
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        api = EBoekhoudenAPI(settings)
        
        result = api.get_chart_of_accounts()
        if not result["success"]:
            return f"Error getting CoA: {result['error']}"
        
        data = json.loads(result["data"])
        accounts_data = data.get("items", [])
        
        # Find 05xxx accounts
        equity_accounts = []
        for account in accounts_data:
            code = account.get('code', '')
            if code.startswith('05'):
                equity_accounts.append(account)
        
        response.append(f"Found {len(equity_accounts)} accounts starting with 05:")
        for acc in equity_accounts:
            response.append(f"  Code: {acc.get('code', 'N/A')}")
            response.append(f"  Description: {acc.get('description', 'N/A')}")
            response.append(f"  Category: {acc.get('category', 'N/A')}")
            response.append(f"  Group: {acc.get('group', 'N/A')}")
            response.append("  ---")
        
        return "\n".join(response)
        
    except Exception as e:
        return f"Error: {e}\n{frappe.get_traceback()}"


@frappe.whitelist()
def test_purchase_invoice_creation():
    """Test Purchase Invoice creation with sample data"""
    try:
        response = []
        response.append("=== PURCHASE INVOICE CREATION TEST ===")
        
        # Get settings
        settings = frappe.get_single("E-Boekhouden Settings")
        company = settings.default_company
        cost_center = settings.default_cost_center
        
        # Import the unified processor functions
        from verenigingen.utils.eboekhouden_unified_processor import get_or_create_supplier, get_default_item
        
        # Test which expense account would be selected
        response.append("\n--- TESTING EXPENSE ACCOUNT SELECTION ---")
        
        try:
            # Check what expense accounts are available for this company
            expense_accounts = frappe.db.get_all("Account", 
                filters={
                    "company": company,
                    "account_type": "Expense Account",
                    "is_group": 0
                }, 
                fields=["name", "account_name", "company"], 
                limit=3)
            
            response.append(f"Available expense accounts for {company}:")
            for acc in expense_accounts:
                response.append(f"  - {acc.name}: {acc.account_name} (Company: {acc.company})")
                
        except Exception as e:
            response.append(f"Error checking expense accounts: {str(e)}")
        
        # Test the helper functions
        response.append("\n--- TESTING HELPER FUNCTIONS ---")
        
        try:
            supplier = get_or_create_supplier({})
            response.append(f"✓ get_or_create_supplier() returned: {supplier}")
        except Exception as e:
            response.append(f"✗ get_or_create_supplier() failed: {str(e)}")
        
        try:
            item = get_default_item("expense")
            response.append(f"✓ get_default_item('expense') returned: {item}")
        except Exception as e:
            response.append(f"✗ get_default_item('expense') failed: {str(e)}")
        
        # Test creating a sample Purchase Invoice
        response.append("\n--- TESTING PURCHASE INVOICE CREATION ---")
        
        try:
            # Create a test mutation
            test_mutation = {
                "id": "TEST-001",
                "date": "2025-01-01",
                "amount": 100.00,
                "description": "Test Purchase Invoice"
            }
            
            # Try to create PI using the same logic as the processor
            pi = frappe.new_doc("Purchase Invoice")
            pi.supplier = get_or_create_supplier(test_mutation)
            pi.posting_date = "2025-01-01"
            pi.company = company
            pi.cost_center = cost_center
            
            # Get a proper expense account for this company
            expense_account = frappe.db.get_value("Account", {
                "company": company,
                "account_type": "Expense Account",
                "is_group": 0
            }, "name")
            
            if not expense_account:
                response.append("✗ No expense account found for this company")
                return "\n".join(response)
            
            # Add line item
            pi.append("items", {
                "item_code": get_default_item("expense"),
                "qty": 1,
                "rate": 100.00,
                "cost_center": cost_center,
                "expense_account": expense_account
            })
            
            # Try to insert (but don't submit to avoid cluttering the system)
            pi.insert(ignore_permissions=True)
            
            response.append(f"✓ Successfully created Purchase Invoice: {pi.name}")
            response.append(f"  Supplier: {pi.supplier}")
            response.append(f"  Amount: {pi.grand_total}")
            response.append(f"  Items: {len(pi.items)}")
            
            # Clean up the test invoice
            pi.delete()
            response.append(f"✓ Cleaned up test invoice")
            
        except Exception as e:
            response.append(f"✗ Purchase Invoice creation failed: {str(e)}")
            response.append(f"  Full error: {frappe.get_traceback()}")
        
        return "\n".join(response)
        
    except Exception as e:
        return f"Error: {e}\n{frappe.get_traceback()}"


@frappe.whitelist()
def debug_05xxx_accounts():
    """Debug 05xxx equity accounts specifically"""
    try:
        import json
        
        response = []
        response.append("=== 05XXX EQUITY ACCOUNTS ANALYSIS ===")
        
        # Get settings
        settings = frappe.get_single("E-Boekhouden Settings")
        
        # Get E-Boekhouden data  
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        api = EBoekhoudenAPI(settings)
        
        result = api.get_chart_of_accounts()
        if not result["success"]:
            return f"Error getting CoA: {result['error']}"
        
        data = json.loads(result["data"])
        accounts_data = data.get("items", [])
        
        # Find 05xxx accounts
        equity_accounts = []
        for account in accounts_data:
            code = account.get('code', '')
            if code.startswith('05'):
                equity_accounts.append(account)
        
        response.append(f"Found {len(equity_accounts)} accounts starting with 05:")
        for acc in equity_accounts:
            response.append(f"  Code: {acc.get('code', 'N/A')}")
            response.append(f"  Description: {acc.get('description', 'N/A')}")
            response.append(f"  Category: {acc.get('category', 'N/A')}")
            response.append(f"  Group: {acc.get('group', 'N/A')}")
            response.append("  ---")
        
        return "\n".join(response)
        
    except Exception as e:
        return f"Error: {e}\n{frappe.get_traceback()}"


@frappe.whitelist()
def fix_payable_accounts():
    """Fix missing payable accounts for Purchase Invoice creation"""
    try:
        response = []
        response.append("=== PAYABLE ACCOUNTS FIX ===")
        
        # Get settings
        settings = frappe.get_single("E-Boekhouden Settings")
        company = settings.default_company
        
        # Check if there are any Payable accounts
        payable_count = frappe.db.count("Account", {
            "company": company,
            "account_type": "Payable",
            "is_group": 0
        })
        
        response.append(f"Current Payable accounts: {payable_count}")
        
        if payable_count > 0:
            response.append("✓ Payable accounts already exist")
            return "\n".join(response)
        
        # Find potential creditors/payable accounts to convert
        potential_accounts = frappe.db.sql("""
            SELECT name, account_name, eboekhouden_grootboek_nummer
            FROM `tabAccount`
            WHERE company = %s
            AND root_type = 'Liability'
            AND is_group = 0
            AND (account_name LIKE '%%crediteuren%%' 
                 OR account_name LIKE '%%leveranciers%%'
                 OR account_name LIKE '%%payable%%'
                 OR eboekhouden_grootboek_nummer LIKE '16%%')
            ORDER BY account_name
        """, company, as_dict=True)
        
        response.append(f"Found {len(potential_accounts)} potential payable accounts:")
        for acc in potential_accounts:
            response.append(f"  - {acc.name}: {acc.account_name} ({acc.eboekhouden_grootboek_nummer})")
        
        if potential_accounts:
            # Convert the first suitable account to Payable
            account_to_convert = potential_accounts[0]
            
            try:
                frappe.db.set_value("Account", account_to_convert.name, "account_type", "Payable")
                frappe.db.commit()
                
                response.append(f"\n✓ Converted '{account_to_convert.account_name}' to Payable account")
                
            except Exception as e:
                response.append(f"\n✗ Failed to convert account: {str(e)}")
        else:
            # Create a new Payable account
            response.append("\nNo suitable accounts found. Creating new Payable account...")
            
            try:
                # Find a suitable parent (liability group)
                liability_parent = frappe.db.get_value("Account", {
                    "company": company,
                    "root_type": "Liability",
                    "is_group": 1
                }, "name")
                
                if not liability_parent:
                    response.append("✗ No liability parent account found")
                    return "\n".join(response)
                
                # Create new payable account
                payable_account = frappe.new_doc("Account")
                payable_account.account_name = "Crediteuren"
                payable_account.account_type = "Payable"
                payable_account.root_type = "Liability"
                payable_account.is_group = 0
                payable_account.parent_account = liability_parent
                payable_account.company = company
                payable_account.account_currency = "EUR"
                payable_account.insert(ignore_permissions=True)
                
                response.append(f"✓ Created new Payable account: {payable_account.name}")
                
            except Exception as e:
                response.append(f"✗ Failed to create Payable account: {str(e)}")
        
        return "\n".join(response)
        
    except Exception as e:
        return f"Error: {e}\n{frappe.get_traceback()}"


@frappe.whitelist()
def debug_05xxx_accounts():
    """Debug 05xxx equity accounts specifically"""
    try:
        import json
        
        response = []
        response.append("=== 05XXX EQUITY ACCOUNTS ANALYSIS ===")
        
        # Get settings
        settings = frappe.get_single("E-Boekhouden Settings")
        
        # Get E-Boekhouden data  
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        api = EBoekhoudenAPI(settings)
        
        result = api.get_chart_of_accounts()
        if not result["success"]:
            return f"Error getting CoA: {result['error']}"
        
        data = json.loads(result["data"])
        accounts_data = data.get("items", [])
        
        # Find 05xxx accounts
        equity_accounts = []
        for account in accounts_data:
            code = account.get('code', '')
            if code.startswith('05'):
                equity_accounts.append(account)
        
        response.append(f"Found {len(equity_accounts)} accounts starting with 05:")
        for acc in equity_accounts:
            response.append(f"  Code: {acc.get('code', 'N/A')}")
            response.append(f"  Description: {acc.get('description', 'N/A')}")
            response.append(f"  Category: {acc.get('category', 'N/A')}")
            response.append(f"  Group: {acc.get('group', 'N/A')}")
            response.append("  ---")
        
        return "\n".join(response)
        
    except Exception as e:
        return f"Error: {e}\n{frappe.get_traceback()}"


@frappe.whitelist()
def analyze_current_coa_structure():
    """Analyze current CoA structure to identify classification issues"""
    try:
        response = []
        response.append("=== CURRENT COA STRUCTURE ANALYSIS ===")
        
        # Get settings
        settings = frappe.get_single("E-Boekhouden Settings")
        company = settings.default_company
        
        # Check root accounts
        response.append("\n--- ROOT ACCOUNTS ---")
        root_accounts = frappe.db.get_all("Account", 
            filters={
                "company": company,
                "is_group": 1,
                "parent_account": ["in", ["", None]]
            }, 
            fields=["name", "account_name", "root_type"], 
            order_by="name")
        
        for root in root_accounts:
            response.append(f"  {root.name}: {root.account_name} (Root: {root.root_type})")
        
        # Check 05xxx accounts (should be equity)
        response.append("\n--- 05XXX ACCOUNTS (SHOULD BE EQUITY) ---")
        equity_accounts = frappe.db.get_all("Account", 
            filters={
                "company": company,
                "eboekhouden_grootboek_nummer": ["like", "05%"]
            }, 
            fields=["name", "account_name", "account_type", "root_type", "parent_account", "eboekhouden_grootboek_nummer"], 
            limit=10)
        
        for acc in equity_accounts:
            response.append(f"  {acc.eboekhouden_grootboek_nummer} - {acc.account_name}")
            response.append(f"    Type: {acc.account_type}, Root: {acc.root_type}")
            response.append(f"    Parent: {acc.parent_account}")
            response.append("    ---")
        
        # Check Opbrengsten structure
        response.append("\n--- OPBRENGSTEN STRUCTURE ---")
        opbrengsten = frappe.db.get_value("Account", {
            "company": company,
            "account_name": ["like", "%Opbrengsten%"]
        }, ["name", "account_name"], as_dict=True)
        
        if opbrengsten:
            response.append(f"Opbrengsten account found: {opbrengsten.name}")
            
            # Check children
            children = frappe.db.get_all("Account", 
                filters={"parent_account": opbrengsten.name}, 
                fields=["name", "account_name", "account_type", "eboekhouden_grootboek_nummer"])
            
            response.append(f"Children under Opbrengsten: {len(children)}")
            for child in children[:5]:
                response.append(f"  - {child.eboekhouden_grootboek_nummer}: {child.account_name} ({child.account_type})")
        else:
            response.append("No Opbrengsten account found!")
        
        # Check account types distribution
        response.append("\n--- ACCOUNT TYPES DISTRIBUTION ---")
        type_counts = frappe.db.sql("""
            SELECT account_type, root_type, COUNT(*) as count
            FROM `tabAccount`
            WHERE company = %s
            AND eboekhouden_grootboek_nummer IS NOT NULL
            GROUP BY account_type, root_type
            ORDER BY count DESC
        """, company, as_dict=True)
        
        for row in type_counts:
            response.append(f"  {row.account_type or 'None'} / {row.root_type}: {row.count}")
        
        return "\n".join(response)
        
    except Exception as e:
        return f"Error: {e}\n{frappe.get_traceback()}"


@frappe.whitelist()
def debug_05xxx_accounts():
    """Debug 05xxx equity accounts specifically"""
    try:
        import json
        
        response = []
        response.append("=== 05XXX EQUITY ACCOUNTS ANALYSIS ===")
        
        # Get settings
        settings = frappe.get_single("E-Boekhouden Settings")
        
        # Get E-Boekhouden data  
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        api = EBoekhoudenAPI(settings)
        
        result = api.get_chart_of_accounts()
        if not result["success"]:
            return f"Error getting CoA: {result['error']}"
        
        data = json.loads(result["data"])
        accounts_data = data.get("items", [])
        
        # Find 05xxx accounts
        equity_accounts = []
        for account in accounts_data:
            code = account.get('code', '')
            if code.startswith('05'):
                equity_accounts.append(account)
        
        response.append(f"Found {len(equity_accounts)} accounts starting with 05:")
        for acc in equity_accounts:
            response.append(f"  Code: {acc.get('code', 'N/A')}")
            response.append(f"  Description: {acc.get('description', 'N/A')}")
            response.append(f"  Category: {acc.get('category', 'N/A')}")
            response.append(f"  Group: {acc.get('group', 'N/A')}")
            response.append("  ---")
        
        return "\n".join(response)
        
    except Exception as e:
        return f"Error: {e}\n{frappe.get_traceback()}"


@frappe.whitelist()
def fix_all_account_classifications():
    """Fix all account classifications based on E-Boekhouden groups"""
    try:
        import json
        
        response = []
        response.append("=== COMPREHENSIVE ACCOUNT CLASSIFICATION FIX ===")
        
        # Get settings
        settings = frappe.get_single("E-Boekhouden Settings")
        company = settings.default_company
        
        # Get E-Boekhouden data to get the correct groups
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        api = EBoekhoudenAPI(settings)
        
        result = api.get_chart_of_accounts()
        if not result["success"]:
            return f"Error getting CoA: {result['error']}"
        
        data = json.loads(result["data"])
        accounts_data = data.get("items", [])
        
        # Create a mapping of account codes to their correct classification
        account_classifications = {}
        for account in accounts_data:
            code = account.get('code', '')
            group = account.get('group', '')
            category = account.get('category', '')
            description = account.get('description', '')
            
            if code and group:
                # Determine correct classification
                account_type = None
                root_type = None
                parent_type = None
                
                # Group-based classification (most reliable)
                if group == "001":  # Vaste activa
                    account_type = 'Fixed Asset'
                    root_type = 'Asset'
                    parent_type = 'Asset'
                elif group == "002":  # Liquide middelen
                    if 'kas' in description.lower() and 'bank' not in description.lower():
                        account_type = 'Cash'
                        root_type = 'Asset'
                        parent_type = 'Asset'
                    else:
                        account_type = 'Bank'
                        root_type = 'Asset'
                        parent_type = 'Asset'
                elif group == "003":  # Voorraden
                    account_type = 'Current Asset'
                    root_type = 'Asset'
                    parent_type = 'Asset'
                elif group == "004":  # Vorderingen
                    account_type = 'Receivable'
                    root_type = 'Asset'
                    parent_type = 'Asset'
                elif group == "005":  # Eigen Vermogen (Equity)
                    account_type = ''
                    root_type = 'Equity'
                    parent_type = 'Equity'
                elif group == "006":  # Kortlopende schulden
                    account_type = 'Current Liability'
                    root_type = 'Liability'
                    parent_type = 'Liability'
                elif group.startswith("05"):  # Eigen vermogen (050, 051, 052, 053, 054)
                    account_type = ''
                    root_type = 'Equity'
                    parent_type = 'Equity'
                elif group == "055":  # Opbrengsten (Income)
                    account_type = 'Income Account'
                    root_type = 'Income'
                    parent_type = 'Income'
                elif group in ["056", "057", "058", "059"]:  # Various cost types
                    account_type = 'Expense Account'
                    root_type = 'Expense'
                    parent_type = 'Expense'
                elif category == 'VW':  # VW without specific group
                    if code.startswith('8') or any(term in description.lower() for term in ['inkomst', 'opbrengst', 'contributie', 'donatie']):
                        account_type = 'Income Account'
                        root_type = 'Income'
                        parent_type = 'Income'
                    else:
                        account_type = 'Expense Account'
                        root_type = 'Expense'
                        parent_type = 'Expense'
                elif category == 'BAL':  # BAL without specific group
                    if code.startswith('0') or code.startswith('1') or code.startswith('2'):
                        account_type = 'Current Asset'
                        root_type = 'Asset'
                        parent_type = 'Asset'
                    elif code.startswith('3') or code.startswith('4'):
                        account_type = 'Current Liability'
                        root_type = 'Liability'
                        parent_type = 'Liability'
                    elif code.startswith('5'):
                        account_type = ''
                        root_type = 'Equity'
                        parent_type = 'Equity'
                    else:
                        account_type = 'Current Asset'
                        root_type = 'Asset'
                        parent_type = 'Asset'
                
                account_classifications[code] = {
                    'account_type': account_type,
                    'root_type': root_type,
                    'parent_type': parent_type,
                    'group': group,
                    'category': category,
                    'description': description
                }
        
        # Get all accounts in database that need fixing
        all_accounts = frappe.db.sql("""
            SELECT name, account_name, account_type, root_type, parent_account, eboekhouden_grootboek_nummer
            FROM `tabAccount`
            WHERE company = %s
            AND eboekhouden_grootboek_nummer IS NOT NULL
            AND eboekhouden_grootboek_nummer != ''
            AND is_group = 0
        """, company, as_dict=True)
        
        # Find appropriate parent accounts
        parent_accounts = {}
        for parent_type in ['Asset', 'Liability', 'Equity', 'Income', 'Expense']:
            parent = frappe.db.get_value("Account", {
                "company": company,
                "root_type": parent_type,
                "is_group": 1,
                "parent_account": ["in", ["", None]]
            }, "name")
            parent_accounts[parent_type] = parent
        
        response.append(f"Found parent accounts: {parent_accounts}")
        
        # Fix accounts
        fixed_accounts = []
        errors = []
        
        for account in all_accounts:
            eb_code = account.get('eboekhouden_grootboek_nummer')
            if eb_code and eb_code in account_classifications:
                classification = account_classifications[eb_code]
                
                # Check if needs fixing
                should_fix = (
                    account.get('account_type') != classification['account_type'] or
                    account.get('root_type') != classification['root_type'] or
                    (classification['parent_type'] and parent_accounts[classification['parent_type']] and 
                     account.get('parent_account') != parent_accounts[classification['parent_type']])
                )
                
                if should_fix:
                    try:
                        updates = {
                            "account_type": classification['account_type'],
                            "root_type": classification['root_type']
                        }
                        
                        # Set correct parent
                        if classification['parent_type'] and parent_accounts[classification['parent_type']]:
                            updates["parent_account"] = parent_accounts[classification['parent_type']]
                        
                        frappe.db.set_value("Account", account.name, updates)
                        
                        fixed_accounts.append({
                            'code': eb_code,
                            'name': account.account_name,
                            'old_type': f"{account.get('account_type')} / {account.get('root_type')}",
                            'new_type': f"{classification['account_type']} / {classification['root_type']}",
                            'group': classification['group']
                        })
                        
                    except Exception as e:
                        errors.append(f"Failed to fix {eb_code}: {str(e)}")
        
        # Commit the changes
        frappe.db.commit()
        
        response.append(f"\n=== RESULTS ===")
        response.append(f"Fixed {len(fixed_accounts)} accounts")
        response.append(f"Errors: {len(errors)}")
        
        response.append(f"\n=== SAMPLE FIXES ===")
        for fix in fixed_accounts[:10]:
            response.append(f"  {fix['code']} - {fix['name']} (Group {fix['group']})")
            response.append(f"    {fix['old_type']} → {fix['new_type']}")
        
        if errors:
            response.append(f"\n=== ERRORS ===")
            for error in errors[:5]:
                response.append(f"  {error}")
        
        return "\n".join(response)
        
    except Exception as e:
        return f"Error: {e}\n{frappe.get_traceback()}"


@frappe.whitelist()
def debug_05xxx_accounts():
    """Debug 05xxx equity accounts specifically"""
    try:
        import json
        
        response = []
        response.append("=== 05XXX EQUITY ACCOUNTS ANALYSIS ===")
        
        # Get settings
        settings = frappe.get_single("E-Boekhouden Settings")
        
        # Get E-Boekhouden data  
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        api = EBoekhoudenAPI(settings)
        
        result = api.get_chart_of_accounts()
        if not result["success"]:
            return f"Error getting CoA: {result['error']}"
        
        data = json.loads(result["data"])
        accounts_data = data.get("items", [])
        
        # Find 05xxx accounts
        equity_accounts = []
        for account in accounts_data:
            code = account.get('code', '')
            if code.startswith('05'):
                equity_accounts.append(account)
        
        response.append(f"Found {len(equity_accounts)} accounts starting with 05:")
        for acc in equity_accounts:
            response.append(f"  Code: {acc.get('code', 'N/A')}")
            response.append(f"  Description: {acc.get('description', 'N/A')}")
            response.append(f"  Category: {acc.get('category', 'N/A')}")
            response.append(f"  Group: {acc.get('group', 'N/A')}")
            response.append("  ---")
        
        return "\n".join(response)
        
    except Exception as e:
        return f"Error: {e}\n{frappe.get_traceback()}"

@frappe.whitelist()
def fix_parent_account_assignments():
    """Fix parent account assignments for properly classified accounts"""
    try:
        response = []
        response.append("=== FIXING PARENT ACCOUNT ASSIGNMENTS ===")
        
        # Find and fix Equity accounts (root_type = Equity) that are under wrong parent
        equity_accounts = frappe.db.sql("""
            SELECT name, account_name, parent_account, eboekhouden_grootboek_nummer
            FROM `tabAccount`
            WHERE root_type = "Equity"
            AND company = "Ned Ver Vegan"
            AND parent_account NOT LIKE "%Eigen Vermogen%"
        """, as_dict=True)
        
        response.append(f"Found {len(equity_accounts)} equity accounts with wrong parent:")
        for account in equity_accounts:
            response.append(f"  - {account.name}: {account.account_name} (Parent: {account.parent_account})")
        
        # Get the correct Eigen Vermogen parent
        eigen_vermogen_parent = frappe.db.get_value("Account", {
            "company": "Ned Ver Vegan",
            "account_name": ["like", "%Eigen Vermogen%"],
            "is_group": 1
        }, "name")
        
        response.append(f"Target Eigen Vermogen parent: {eigen_vermogen_parent}")
        
        # Fix equity accounts
        fixed_equity = 0
        for account in equity_accounts:
            try:
                frappe.db.sql("""
                    UPDATE `tabAccount` 
                    SET parent_account = %s
                    WHERE name = %s
                """, (eigen_vermogen_parent, account.name))
                
                fixed_equity += 1
                response.append(f"  ✅ Fixed equity: {account.name}")
                
            except Exception as e:
                response.append(f"  ❌ Error fixing equity {account.name}: {str(e)}")
        
        # Find and fix Income accounts that are under wrong parent
        income_accounts = frappe.db.sql("""
            SELECT name, account_name, parent_account, eboekhouden_grootboek_nummer
            FROM `tabAccount`
            WHERE account_type = "Income Account"
            AND root_type = "Income"
            AND company = "Ned Ver Vegan"
            AND parent_account NOT LIKE "%Opbrengsten%"
        """, as_dict=True)
        
        response.append(f"\nFound {len(income_accounts)} income accounts with wrong parent:")
        for account in income_accounts:
            response.append(f"  - {account.name}: {account.account_name} (Parent: {account.parent_account})")
        
        # Get the correct Opbrengsten parent
        opbrengsten_parent = frappe.db.get_value("Account", {
            "company": "Ned Ver Vegan",
            "account_name": ["like", "%Opbrengsten%"],
            "is_group": 1
        }, "name")
        
        response.append(f"Target Opbrengsten parent: {opbrengsten_parent}")
        
        # Fix income accounts
        fixed_income = 0
        for account in income_accounts:
            try:
                frappe.db.sql("""
                    UPDATE `tabAccount` 
                    SET parent_account = %s
                    WHERE name = %s
                """, (opbrengsten_parent, account.name))
                
                fixed_income += 1
                response.append(f"  ✅ Fixed income: {account.name}")
                
            except Exception as e:
                response.append(f"  ❌ Error fixing income {account.name}: {str(e)}")
        
        frappe.db.commit()
        
        response.append(f"\n=== SUMMARY ===")
        response.append(f"Equity accounts fixed: {fixed_equity}")
        response.append(f"Income accounts fixed: {fixed_income}")
        response.append(f"Total accounts fixed: {fixed_equity + fixed_income}")
        
        return "\n".join(response)
        
    except Exception as e:
        return f"Error: {e}\n{frappe.get_traceback()}"
