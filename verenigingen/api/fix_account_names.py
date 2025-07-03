import frappe

@frappe.whitelist()
def fix_account_names():
    """Fix account names to remove account numbers"""
    frappe.set_user("Administrator")
    
    company = "Ned Ver Vegan"
    company_abbr = "NVV"
    
    print("=== Fixing Account Names ===")
    
    # Get all accounts with account numbers
    accounts = frappe.db.get_list(
        "Account",
        filters={
            "company": company,
            "account_number": ["is", "set"]
        },
        fields=["name", "account_name", "account_number"],
        order_by="account_number"
    )
    
    print(f"Found {len(accounts)} accounts to check")
    
    fixed_count = 0
    errors = []
    
    for acc in accounts:
        try:
            original_name = acc.account_name
            account_number = acc.account_number
            
            # Skip group accounts (they're already clean)
            if original_name.startswith("Groep "):
                continue
            
            # Extract the actual account description
            # Pattern: "XXXXX - Description" or "XXXXX - XXXXX - Description"
            clean_name = original_name
            
            # Remove account number prefix(es)
            if clean_name.startswith(f"{account_number} - "):
                clean_name = clean_name[len(account_number) + 3:]
                
                # Check if it starts with the number again
                if clean_name.startswith(f"{account_number} - "):
                    clean_name = clean_name[len(account_number) + 3:]
            
            # Also check without the dash
            if clean_name.startswith(account_number):
                clean_name = clean_name[len(account_number):].lstrip(" -")
            
            # If the name is empty or just whitespace, use a default
            if not clean_name.strip():
                clean_name = f"Account {account_number}"
            
            # Only update if the name changed
            if clean_name != original_name:
                # Update the account name
                frappe.db.set_value("Account", acc.name, "account_name", clean_name)
                
                # Also need to update the name field (which includes company abbr)
                new_full_name = f"{clean_name} - {company_abbr}"
                
                # Check if new name would conflict
                existing = frappe.db.exists("Account", new_full_name)
                if existing and existing != acc.name:
                    print(f"  WARNING: Cannot rename {acc.name} to {new_full_name} - name already exists")
                    errors.append(f"{account_number}: Name conflict")
                    continue
                
                # Rename the document
                frappe.rename_doc("Account", acc.name, new_full_name, force=True)
                
                fixed_count += 1
                print(f"  Fixed: {account_number} - '{original_name}' -> '{clean_name}'")
                
        except Exception as e:
            errors.append(f"{acc.account_number}: {str(e)}")
            print(f"  ERROR fixing {acc.account_number}: {str(e)}")
    
    frappe.db.commit()
    
    print(f"\n=== Summary ===")
    print(f"Fixed: {fixed_count} accounts")
    print(f"Errors: {len(errors)}")
    
    if errors:
        print("\n=== Errors ===")
        for err in errors[:10]:  # Show first 10 errors
            print(f"  {err}")
    
    # Show some examples of the fixed accounts
    print("\n=== Examples of Fixed Accounts ===")
    examples = frappe.db.get_list(
        "Account",
        filters={
            "company": company,
            "account_number": ["is", "set"],
            "account_name": ["not like", "%Groep%"]
        },
        fields=["name", "account_name", "account_number"],
        limit=20
    )
    
    for ex in examples:
        print(f"  {ex.account_number}: {ex.account_name}")

@frappe.whitelist()
def check_duplicate_numbers():
    """Check for accounts with duplicate numbers in their names"""
    frappe.set_user("Administrator")
    
    company = "Ned Ver Vegan"
    
    print("=== Checking for Duplicate Numbers in Account Names ===")
    
    accounts = frappe.db.get_list(
        "Account",
        filters={
            "company": company,
            "account_number": ["is", "set"]
        },
        fields=["name", "account_name", "account_number"],
        order_by="account_number"
    )
    
    duplicates = []
    
    for acc in accounts:
        account_number = acc.account_number
        account_name = acc.account_name
        
        # Count occurrences of the account number in the name
        count = account_name.count(account_number)
        
        if count > 1:
            duplicates.append({
                "number": account_number,
                "name": account_name,
                "count": count
            })
        elif count == 1 and not account_name.startswith("Groep "):
            # Check if it's at the beginning (which we don't want)
            if account_name.startswith(f"{account_number} - ") or account_name.startswith(account_number):
                duplicates.append({
                    "number": account_number,
                    "name": account_name,
                    "count": 1
                })
    
    print(f"Found {len(duplicates)} accounts with numbers in their names")
    
    if duplicates:
        print("\n=== Accounts with Numbers in Names ===")
        for dup in duplicates[:20]:  # Show first 20
            print(f"  {dup['number']}: {dup['name']} (appears {dup['count']} times)")
    
    return duplicates