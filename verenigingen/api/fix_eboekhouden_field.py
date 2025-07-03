import frappe

@frappe.whitelist()
def check_eboekhouden_field():
    """Check the status of eboekhouden_grootboek_nummer field"""
    frappe.set_user("Administrator")
    
    # Count accounts with account_number
    count_with_number = frappe.db.count("Account", {
        "company": "Ned Ver Vegan",
        "account_number": ["is", "set"]
    })
    
    # Count accounts with eboekhouden_grootboek_nummer
    count_with_ebook = frappe.db.count("Account", {
        "company": "Ned Ver Vegan",
        "eboekhouden_grootboek_nummer": ["is", "set"]
    })
    
    print(f"Accounts with account_number: {count_with_number}")
    print(f"Accounts with eboekhouden_grootboek_nummer: {count_with_ebook}")
    
    # Get a few examples
    examples = frappe.db.get_list("Account", {
        "company": "Ned Ver Vegan",
        "account_number": ["is", "set"]
    }, ["name", "account_name", "account_number", "eboekhouden_grootboek_nummer"], limit=5)
    
    print("\nExample accounts:")
    for ex in examples:
        print(f"  {ex.account_number}: {ex.account_name} (ebook: {ex.eboekhouden_grootboek_nummer})")
    
    return {
        "count_with_number": count_with_number,
        "count_with_ebook": count_with_ebook,
        "examples": examples
    }

@frappe.whitelist()
def sync_eboekhouden_field():
    """Copy account_number to eboekhouden_grootboek_nummer for all accounts"""
    frappe.set_user("Administrator")
    
    print("=== Syncing E-boekhouden Field ===")
    
    # Get all accounts with account_number
    accounts = frappe.db.get_list("Account", {
        "company": "Ned Ver Vegan",
        "account_number": ["is", "set"]
    }, ["name", "account_number"])
    
    print(f"Found {len(accounts)} accounts to sync")
    
    updated = 0
    for acc in accounts:
        try:
            frappe.db.set_value("Account", acc.name, 
                "eboekhouden_grootboek_nummer", acc.account_number)
            updated += 1
        except Exception as e:
            print(f"Error updating {acc.name}: {str(e)}")
    
    frappe.db.commit()
    
    print(f"\nSynced {updated} accounts")
    
    # Verify
    count_after = frappe.db.count("Account", {
        "company": "Ned Ver Vegan",
        "eboekhouden_grootboek_nummer": ["is", "set"]
    })
    
    print(f"Accounts with eboekhouden_grootboek_nummer after sync: {count_after}")
    
    return {
        "success": True,
        "updated": updated,
        "total": len(accounts),
        "count_after": count_after
    }