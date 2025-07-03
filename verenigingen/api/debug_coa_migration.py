#!/usr/bin/env python3
import frappe

@frappe.whitelist()
def check_existing_accounts():
    """Check existing accounts in the system"""
    frappe.set_user("Administrator")
    
    settings = frappe.get_single("E-Boekhouden Settings")
    company = settings.default_company
    
    print(f"\n=== Checking Accounts for Company: {company} ===")
    
    # Count accounts by root type
    root_types = ["Asset", "Liability", "Equity", "Income", "Expense"]
    
    for root_type in root_types:
        count = frappe.db.count("Account", {"company": company, "root_type": root_type})
        print(f"{root_type}: {count} accounts")
    
    # Check for root accounts
    root_accounts = frappe.db.get_list(
        "Account",
        filters={
            "company": company,
            "parent_account": ["in", ["", None]],
            "is_group": 1
        },
        fields=["name", "account_name", "account_number", "root_type"],
        order_by="root_type, account_name"
    )
    
    print(f"\n=== Root Accounts ({len(root_accounts)}) ===")
    for acc in root_accounts:
        print(f"  [{acc.root_type}] {acc.account_name} (Number: {acc.account_number or 'N/A'})")
    
    # Check for accounts with short codes (likely root accounts)
    short_code_accounts = frappe.db.sql("""
        SELECT name, account_name, account_number, root_type, is_group, parent_account
        FROM tabAccount
        WHERE company = %s
        AND account_number IS NOT NULL
        AND LENGTH(account_number) <= 3
        ORDER BY LENGTH(account_number), account_number
    """, company, as_dict=True)
    
    print(f"\n=== Short Code Accounts ({len(short_code_accounts)}) ===")
    for acc in short_code_accounts:
        parent = "ROOT" if not acc.parent_account else acc.parent_account
        group = "GROUP" if acc.is_group else "LEAF"
        print(f"  Code {acc.account_number}: {acc.account_name} [{acc.root_type}] {group} (Parent: {parent})")

@frappe.whitelist()
def analyze_eboekhouden_accounts():
    """Analyze the E-boekhouden accounts to understand hierarchy"""
    frappe.set_user("Administrator")
    
    from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenAPI(settings)
    
    print("\n=== Fetching E-boekhouden Accounts ===")
    result = api.get_chart_of_accounts()
    
    if not result["success"]:
        print(f"Failed to fetch accounts: {result['error']}")
        return
    
    import json
    data = json.loads(result["data"])
    accounts = data.get("items", [])
    
    print(f"Found {len(accounts)} accounts")
    
    # Analyze account structure
    code_lengths = {}
    root_candidates = []
    group_codes = set()
    
    for acc in accounts:
        code = acc.get('code', '')
        group = acc.get('group', '')
        
        if group:
            group_codes.add(group)
        
        # Track code lengths
        code_len = len(code)
        if code_len not in code_lengths:
            code_lengths[code_len] = 0
        code_lengths[code_len] += 1
        
        # Identify potential root accounts
        if code_len <= 3 or group in ['001', '002', '003', '004', '005', '006', '007', '008', '009', '010']:
            root_candidates.append({
                'code': code,
                'name': acc.get('description', ''),
                'group': group,
                'category': acc.get('category', '')
            })
    
    print("\n=== Account Code Length Distribution ===")
    for length, count in sorted(code_lengths.items()):
        print(f"  {length} digits: {count} accounts")
    
    print(f"\n=== Unique Group Codes ({len(group_codes)}) ===")
    for gc in sorted(group_codes)[:20]:  # Show first 20
        print(f"  {gc}")
    
    print(f"\n=== Potential Root Accounts ({len(root_candidates)}) ===")
    for rc in sorted(root_candidates, key=lambda x: (len(x['code']), x['code'])):
        print(f"  Code {rc['code']}: {rc['name']} (Group: {rc['group']}, Category: {rc['category']})")
    
    # Check parent-child relationships
    print("\n=== Checking Parent-Child Relationships ===")
    account_codes = set(acc.get('code', '') for acc in accounts)
    
    # Find accounts that have children
    has_children = set()
    for code in account_codes:
        # Check if any other code starts with this code
        for other_code in account_codes:
            if other_code != code and other_code.startswith(code):
                has_children.add(code)
                break
    
    print(f"Found {len(has_children)} accounts that have children")
    
    # Show some examples
    print("\n=== Example Parent Accounts ===")
    for parent in sorted(has_children)[:10]:
        children = [c for c in account_codes if c != parent and c.startswith(parent)]
        print(f"  {parent} has {len(children)} children")

@frappe.whitelist()
def run_coa_migration_test():
    """Run CoA migration and capture output"""
    frappe.set_user("Administrator")
    
    # Get recent migrations
    migrations = frappe.db.get_list(
        "E-Boekhouden Migration", 
        fields=["name", "migration_name", "migration_status", "current_operation", "progress_percentage"],
        order_by="creation desc",
        limit=5
    )
    
    print("\n=== Recent E-Boekhouden Migrations ===")
    for m in migrations:
        print(f"\nMigration: {m.name}")
        print(f"  Name: {m.migration_name}")
        print(f"  Status: {m.migration_status}")
        print(f"  Operation: {m.current_operation}")
        print(f"  Progress: {m.progress_percentage}%")
    
    # Check if there's a draft migration we can use
    draft_migration = frappe.db.get_value(
        "E-Boekhouden Migration",
        {"migration_status": "Draft"},
        "name"
    )
    
    if draft_migration:
        print(f"\n=== Using Draft Migration: {draft_migration} ===")
        migration = frappe.get_doc("E-Boekhouden Migration", draft_migration)
    else:
        print("\n=== Creating New Test Migration ===")
        # Create a new migration for testing
        migration = frappe.new_doc("E-Boekhouden Migration")
        migration.migration_name = "Debug CoA Migration Test"
        migration.migration_type = "Partial Migration"
        migration.migrate_accounts = 1
        migration.migrate_cost_centers = 0
        migration.migrate_transactions = 0
        migration.dry_run = 0
        migration.clear_existing_accounts = 0
        
        migration.save()
        print(f"Created new migration: {migration.name}")
    
    # Get settings
    settings = frappe.get_single("E-Boekhouden Settings")
    if not settings.api_token:
        print("ERROR: E-Boekhouden Settings not configured. Please configure API token first.")
        return
    
    print(f"Using company: {settings.default_company}")
    
    # Enable verbose logging
    import logging
    frappe.logger().setLevel(logging.DEBUG)
    
    # Run the migration method directly
    try:
        print("\n=== Starting CoA Migration ===")
        result = migration.migrate_chart_of_accounts(settings)
        print(f"\n=== Migration Result ===")
        print(result)
        
        # Check for any error logs
        error_logs = frappe.db.get_list(
            "Error Log",
            filters={
                "creation": [">=", frappe.utils.add_days(frappe.utils.now(), -1)]
            },
            fields=["name", "method", "error"],
            order_by="creation desc",
            limit=5
        )
        
        if error_logs:
            print("\n=== Recent Error Logs ===")
            for log in error_logs:
                print(f"\nError in {log.method}:")
                print(log.error[:500])
        
        # Check the log file
        import os
        log_path = "/home/frappe/frappe-bench/logs/frappe.log"
        if os.path.exists(log_path):
            print("\n=== Last 50 lines of frappe.log ===")
            os.system(f"tail -50 {log_path} | grep -E 'Account|account|CoA|coa|root|Root|GROUP'")
        
    except Exception as e:
        print(f"\n=== Migration Failed ===")
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()

@frappe.whitelist() 
def clear_test_accounts():
    """Clear test accounts for debugging"""
    frappe.set_user("Administrator")
    
    settings = frappe.get_single("E-Boekhouden Settings")
    company = settings.default_company
    
    # Get non-standard accounts
    accounts = frappe.db.get_list(
        "Account",
        filters={
            "company": company,
            "account_number": ["is", "set"]
        },
        fields=["name", "account_name", "account_number"],
        order_by="account_number"
    )
    
    print(f"\n=== Found {len(accounts)} accounts with account numbers ===")
    
    if input("\nDo you want to delete these accounts? (yes/no): ").lower() == "yes":
        for acc in accounts:
            try:
                frappe.delete_doc("Account", acc.name, force=True)
                print(f"Deleted: {acc.account_number} - {acc.account_name}")
            except Exception as e:
                print(f"Failed to delete {acc.name}: {str(e)}")
        
        frappe.db.commit()
        print("\nDeletion complete")