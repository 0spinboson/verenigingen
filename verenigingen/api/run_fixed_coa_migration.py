import frappe
import json

@frappe.whitelist()
def run_fixed_coa_migration():
    """Run the E-boekhouden CoA migration with proper hierarchy"""
    frappe.set_user("Administrator")
    
    from verenigingen.utils.eboekhouden_coa_fix import prepare_coa_hierarchy
    
    # Step 1: Prepare the hierarchy
    print("=== Step 1: Preparing CoA Hierarchy ===")
    hierarchy_result = prepare_coa_hierarchy()
    
    if not hierarchy_result:
        print("Failed to prepare hierarchy")
        return
    
    print(f"\nHierarchy prepared:")
    print(f"- Root accounts: {len(hierarchy_result['roots'])}")
    print(f"- Group accounts: {len(hierarchy_result['groups'])}")
    
    # Step 2: Monkey patch the migration to fix the root account logic
    print("\n=== Step 2: Patching Migration Logic ===")
    
    from verenigingen.verenigingen.doctype.e_boekhouden_migration.e_boekhouden_migration import EBoekhoudenMigration
    
    # Store the original create_account method
    original_create_account = EBoekhoudenMigration.create_account
    
    def patched_create_account(self, account_data, use_enhanced=False):
        """Patched version that properly handles E-boekhouden hierarchy"""
        
        try:
            account_code = account_data.get('code', '')
            account_name = account_data.get('description', '')
            category = account_data.get('category', '')
            group_code = account_data.get('group', '')
            
            if not account_code or not account_name:
                self.log_error(f"Invalid account data: code={account_code}, name={account_name}")
                return False
            
            # Clean up account name
            if account_name.startswith(f"{account_code} - "):
                account_name = account_name[len(account_code) + 3:]
            
            if account_name.startswith(account_code):
                account_name = account_name[len(account_code):].lstrip(" -")
            
            if not account_name.strip():
                account_name = f"Account {account_code}"
            
            # Truncate if too long
            if len(account_name) > 120:
                account_name = account_name[:120] + "..."
            
            full_account_name = f"{account_code} - {account_name}"
            if len(full_account_name) > 140:
                max_desc_length = 140 - len(account_code) - 3
                account_name = account_name[:max_desc_length]
                full_account_name = f"{account_code} - {account_name}"
            
            # Get company settings
            settings = frappe.get_single("E-Boekhouden Settings")
            company = settings.default_company
            
            if not company:
                self.log_error("No default company set in E-Boekhouden Settings")
                return False
            
            # Check if account already exists
            existing_by_number = frappe.db.exists("Account", {"account_number": account_code, "company": company})
            
            company_abbr = frappe.db.get_value("Company", company, "abbr")
            existing_by_name = frappe.db.exists("Account", {"name": f"{full_account_name} - {company_abbr}"})
            
            if existing_by_number or existing_by_name:
                frappe.logger().info(f"SKIPPING - Account {account_code} already exists")
                return False
            
            # Determine account type and root type (same logic as original)
            from verenigingen.utils.eboekhouden_coa_fix import get_eboekhouden_hierarchy_mapping
            hierarchy = get_eboekhouden_hierarchy_mapping()
            
            # Map categories to types
            category_mapping = {
                'BTWRC': {'account_type': 'Tax', 'root_type': 'Liability'},
                'AF6': {'account_type': 'Tax', 'root_type': 'Liability'},
                'AF19': {'account_type': 'Tax', 'root_type': 'Liability'},
                'AFOVERIG': {'account_type': 'Tax', 'root_type': 'Liability'},
                'AF': {'account_type': 'Tax', 'root_type': 'Liability'},
                'VOOR': {'account_type': 'Tax', 'root_type': 'Asset'},
                'BAL': {'account_type': '', 'root_type': None},
                'FIN': {'account_type': 'Bank', 'root_type': 'Asset'},
                'DEB': {'account_type': '', 'root_type': 'Asset'},
                'CRED': {'account_type': '', 'root_type': 'Liability'},
                'VW': {'account_type': '', 'root_type': None},
            }
            
            mapping = category_mapping.get(category, {'account_type': '', 'root_type': None})
            account_type = mapping['account_type']
            root_type = mapping['root_type']
            
            # Determine root type from category and code
            if root_type is None:
                if category == 'BAL':
                    if account_code.startswith(('0', '1', '2')):
                        root_type = 'Asset'
                    elif account_code.startswith(('3', '4')):
                        root_type = 'Liability'
                    elif account_code.startswith('5'):
                        root_type = 'Equity'
                    else:
                        root_type = 'Asset'
                elif category == 'VW':
                    if account_code.startswith('8'):
                        root_type = 'Income'
                    elif account_code.startswith(('6', '7')):
                        root_type = 'Expense'
                    elif account_code.startswith('9'):
                        root_type = 'Expense'
                    else:
                        root_type = 'Expense'
            
            # IMPORTANT: E-boekhouden accounts are NEVER root accounts
            # They always belong to a group
            is_root_account = False
            
            # Find the parent account - it should be the group account
            parent_account = None
            
            if group_code:
                # Look for the group account we created
                parent_account = frappe.db.get_value("Account", {
                    "company": company,
                    "account_number": group_code,
                    "is_group": 1
                }, "name")
                
                if parent_account:
                    frappe.logger().info(f"Found parent group {group_code} for account {account_code}")
                else:
                    frappe.logger().warning(f"Group {group_code} not found for account {account_code}")
            
            # If no parent found via group, try to find appropriate parent by root type
            if not parent_account:
                parent_account = self.get_parent_account(account_type, root_type, company)
            
            # Determine if this should be a group account
            is_group = 0
            
            if hasattr(self, '_group_accounts') and account_code in self._group_accounts:
                is_group = 1
                frappe.logger().info(f"Creating account {account_code} as group (has children)")
            
            # Create the account
            account_doc = {
                'doctype': 'Account',
                'account_name': full_account_name,
                'account_number': account_code,
                'company': company,
                'root_type': root_type,
                'is_group': is_group,
                'parent_account': parent_account,
                'disabled': 0
            }
            
            if account_type:
                account_doc['account_type'] = account_type
            
            account = frappe.get_doc(account_doc)
            
            frappe.logger().info(f"Creating account: {account_code} - {account_name}, is_group={is_group}, parent={parent_account}, root_type={root_type}")
            
            account.insert(ignore_permissions=True)
            frappe.logger().info(f"Successfully created account: {account_code} - {account_name}")
            return True
            
        except Exception as e:
            account_ref = account_data.get('code', 'Unknown')
            self.log_error(f"Failed to create account {account_ref}: {str(e)}", "account", account_data)
            return False
    
    # Apply the patch
    EBoekhoudenMigration.create_account = patched_create_account
    
    print("Migration logic patched")
    
    # Step 3: Run the migration
    print("\n=== Step 3: Running CoA Migration ===")
    
    # Create a new migration document
    migration = frappe.new_doc("E-Boekhouden Migration")
    migration.migration_name = "Fixed CoA Migration"
    migration.migration_type = "Partial Migration"
    migration.migrate_accounts = 1
    migration.migrate_cost_centers = 0
    migration.migrate_transactions = 0
    migration.dry_run = 0
    migration.clear_existing_accounts = 0
    
    migration.save()
    
    # Get settings
    settings = frappe.get_single("E-Boekhouden Settings")
    
    try:
        # Run the migration
        result = migration.migrate_chart_of_accounts(settings)
        print(f"\nMigration result: {result}")
        
        # Check results
        print("\n=== Migration Results ===")
        
        # Count accounts by type
        for root_type in ["Asset", "Liability", "Equity", "Income", "Expense"]:
            count = frappe.db.count("Account", {
                "company": settings.default_company,
                "root_type": root_type
            })
            print(f"{root_type}: {count} accounts")
        
        # Count accounts with account numbers
        numbered_accounts = frappe.db.count("Account", {
            "company": settings.default_company,
            "account_number": ["is", "set"]
        })
        
        print(f"\nTotal accounts with account numbers: {numbered_accounts}")
        
        # Show some examples
        examples = frappe.db.get_list("Account", {
            "company": settings.default_company,
            "account_number": ["is", "set"]
        }, ["name", "account_name", "account_number", "parent_account", "is_group"], limit=10)
        
        print("\n=== Example Accounts Created ===")
        for acc in examples:
            group_status = "GROUP" if acc.is_group else "LEAF"
            print(f"{acc.account_number}: {acc.account_name} [{group_status}] (Parent: {acc.parent_account})")
        
    except Exception as e:
        print(f"\nMigration failed: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Restore original method
        EBoekhoudenMigration.create_account = original_create_account
        print("\nOriginal migration logic restored")