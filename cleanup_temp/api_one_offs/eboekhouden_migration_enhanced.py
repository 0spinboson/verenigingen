"""
Enhanced E-Boekhouden Migration with proper sequencing
Ensures parties are imported before transactions
"""

import frappe
from frappe import _

@frappe.whitelist()
def prepare_and_start_migration(migration_name):
    """
    Prepare system and start migration with proper sequencing
    """
    try:
        # Step 1: Prepare the system
        prep_result = prepare_system_for_migration()
        if not prep_result.get("success"):
            return {
                "success": False,
                "error": "System preparation failed",
                "details": prep_result
            }
        
        # Step 2: Get the migration document
        migration = frappe.get_doc("E-Boekhouden Migration", migration_name)
        
        # Ensure proper flags are set for full migration
        if migration.migrate_transactions:
            # Force import of parties when importing transactions
            migration.migrate_customers = 1
            migration.migrate_suppliers = 1
            migration.save()
        
        # Step 3: Apply the patch for enhanced journal entry creation
        from verenigingen.utils.eboekhouden_migration_patch import apply_migration_patch
        patch_result = apply_migration_patch(migration_name)
        if not patch_result.get("success"):
            frappe.log_error(f"Failed to apply migration patch: {patch_result.get('error')}", "E-Boekhouden")
        
        # Step 4: Start the migration using the API method
        from verenigingen.verenigingen.doctype.e_boekhouden_migration.e_boekhouden_migration import start_migration_api
        start_result = start_migration_api(migration_name, dry_run=0)
        
        if start_result.get("success"):
            return {
                "success": True,
                "message": "Migration started with proper sequencing and party handling",
                "preparation": prep_result
            }
        else:
            return {
                "success": False,
                "error": start_result.get("error", "Failed to start migration"),
                "preparation": prep_result
            }
        
    except Exception as e:
        frappe.log_error(f"Migration start error: {str(e)}", "E-Boekhouden Migration")
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def prepare_system_for_migration():
    """
    Comprehensive preparation for E-Boekhouden migration
    """
    results = []
    company = frappe.db.get_single_value("E-Boekhouden Settings", "default_company")
    
    if not company:
        return {
            "success": False,
            "error": "Please set default company in E-Boekhouden Settings first"
        }
    
    # First, try to get the actual date range from E-Boekhouden
    date_range = get_eboekhouden_date_range()
    if date_range.get("success"):
        count_info = f" ({date_range.get('transaction_count', 0)} transactions)" if date_range.get('transaction_count') else ""
        results.append({
            "step": "Date Range Detection",
            "success": True,
            "value": f"Found transactions from {date_range.get('earliest_date')} to {date_range.get('latest_date')}{count_info}"
        })
    else:
        results.append({
            "step": "Date Range Detection", 
            "success": False,
            "value": "Could not detect date range, will use defaults"
        })
    
    # 1. Ensure main cost center exists
    main_cc = ensure_main_cost_center(company)
    results.append({
        "step": "Main Cost Center",
        "success": bool(main_cc),
        "value": main_cc or "Failed to find/create"
    })
    
    # 2. Create default parties
    default_parties = create_default_parties()
    results.append({
        "step": "Default Parties",
        "success": default_parties.get("success"),
        "details": default_parties
    })
    
    # 3. Create suspense account
    suspense = ensure_suspense_account(company)
    results.append({
        "step": "Suspense Account",
        "success": bool(suspense),
        "value": suspense
    })
    
    # 4. Temporarily adjust problematic account types
    account_adjustment = temporarily_adjust_account_types(company)
    results.append({
        "step": "Account Type Adjustment",
        "success": account_adjustment.get("success"),
        "details": account_adjustment
    })
    
    # 5. Add mutation ID field if missing
    field_result = ensure_mutation_id_field()
    results.append({
        "step": "Mutation ID Field",
        "success": field_result.get("success"),
        "details": field_result
    })
    
    # 6. Add entry tracking fields
    from verenigingen.utils.eboekhouden_grouped_migration import add_entry_number_field
    entry_field_result = add_entry_number_field()
    results.append({
        "step": "Entry Tracking Fields",
        "success": entry_field_result.get("success"),
        "details": entry_field_result
    })
    
    # Include date range in response if found
    response = {
        "success": all(r.get("success", False) for r in results),
        "results": results,
        "cost_center": main_cc
    }
    
    if date_range.get("success"):
        response["date_range"] = {
            "earliest_date": date_range.get("earliest_date"),
            "latest_date": date_range.get("latest_date")
        }
    
    return response

def ensure_main_cost_center(company):
    """Ensure main cost center exists and return it"""
    # Try to find existing main cost center
    main_cc = frappe.db.get_value("Cost Center", {
        "company": company,
        "is_group": 1,
        "parent_cost_center": ["in", ["", None]]
    }, "name")
    
    if not main_cc:
        # Try company abbreviation pattern
        abbr = frappe.db.get_value("Company", company, "abbr")
        if abbr:
            main_cc = frappe.db.get_value("Cost Center", f"{company} - {abbr}", "name")
    
    return main_cc

def create_default_parties():
    """Create default Customer and Supplier for migration"""
    created = []
    errors = []
    
    # Default customer
    default_customer_name = "E-Boekhouden Import Customer"
    if not frappe.db.exists("Customer", default_customer_name):
        try:
            customer = frappe.new_doc("Customer")
            customer.customer_name = default_customer_name
            customer.customer_type = "Company"
            
            # Get default customer group
            customer_group = frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
            if not customer_group:
                customer_group = "All Customer Groups"
            customer.customer_group = customer_group
            
            # Get default territory
            territory = frappe.db.get_value("Territory", {"is_group": 0}, "name")
            if not territory:
                territory = "All Territories"
            customer.territory = territory
            
            customer.insert(ignore_permissions=True)
            created.append(f"Customer: {customer.name}")
        except Exception as e:
            errors.append(f"Customer creation: {str(e)}")
    
    # Default supplier
    default_supplier_name = "E-Boekhouden Import Supplier"
    if not frappe.db.exists("Supplier", default_supplier_name):
        try:
            supplier = frappe.new_doc("Supplier")
            supplier.supplier_name = default_supplier_name
            
            # Get default supplier group
            supplier_group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
            if not supplier_group:
                supplier_group = "All Supplier Groups"
            supplier.supplier_group = supplier_group
            
            supplier.insert(ignore_permissions=True)
            created.append(f"Supplier: {supplier.name}")
        except Exception as e:
            errors.append(f"Supplier creation: {str(e)}")
    
    return {
        "success": len(errors) == 0,
        "created": created,
        "errors": errors
    }

def ensure_suspense_account(company):
    """Ensure suspense account exists for unclear transactions"""
    suspense_name = "E-Boekhouden Suspense Account"
    
    existing = frappe.db.get_value("Account", {
        "company": company,
        "account_name": suspense_name
    }, "name")
    
    if existing:
        return existing
    
    try:
        # Find parent account
        parent = frappe.db.get_value("Account", {
            "company": company,
            "root_type": "Asset",
            "is_group": 1,
            "account_name": ["like", "%Current Asset%"]
        }, "name")
        
        if not parent:
            parent = frappe.db.get_value("Account", {
                "company": company,
                "root_type": "Asset",
                "is_group": 1
            }, "name")
        
        if parent:
            acc = frappe.new_doc("Account")
            acc.account_name = suspense_name
            acc.company = company
            acc.parent_account = parent
            acc.account_type = "Temporary"
            acc.root_type = "Asset"
            acc.insert(ignore_permissions=True)
            return acc.name
    except Exception as e:
        frappe.log_error(f"Suspense account creation error: {str(e)}", "E-Boekhouden")
        return None

def temporarily_adjust_account_types(company):
    """
    Temporarily change problematic Receivable/Payable accounts
    These will be fixed after migration completes
    """
    # Accounts that cause issues during migration
    problem_accounts = [
        # Receivable accounts that need temporary adjustment
        ("13500", "Receivable", "Current Asset"),  # Te ontvangen contributies
        ("13510", "Receivable", "Current Asset"),  # Te ontvangen donaties
        ("13600", "Receivable", "Current Asset"),  # Vooruitbetaalde kosten
        ("13900", "Receivable", "Current Asset"),  # Te ontvangen bedragen
        ("13990", "Receivable", "Current Asset"),  # Overige vorderingen
        # Payable accounts that need temporary adjustment
        ("19290", "Payable", "Current Liability"),  # Te betalen bedragen
        ("19291", "Payable", "Current Liability"),  # Te betalen kosten
        ("44000", "Payable", "Current Liability"),  # Vooruitontvangen bedragen
        ("44900", "Payable", "Current Liability"),  # Overige schulden
    ]
    
    adjusted = []
    for account_number, current_type, temp_type in problem_accounts:
        account = frappe.db.get_value("Account", {
            "company": company,
            "account_number": account_number,
            "account_type": current_type
        }, "name")
        
        if account:
            frappe.db.set_value("Account", account, "account_type", temp_type)
            adjusted.append({
                "account": account,
                "number": account_number,
                "from": current_type,
                "to": temp_type
            })
    
    frappe.db.commit()
    
    return {
        "success": True,
        "adjusted": len(adjusted),
        "accounts": adjusted,
        "message": f"Temporarily adjusted {len(adjusted)} accounts. Run 'Fix Account Types' after migration."
    }

def ensure_mutation_id_field():
    """Ensure mutation ID field exists on Journal Entry"""
    try:
        # Check if field exists
        if not frappe.db.has_column("Journal Entry", "eboekhouden_mutation_id"):
            # Create custom field
            custom_field = frappe.new_doc("Custom Field")
            custom_field.dt = "Journal Entry"
            custom_field.label = "E-Boekhouden Mutation ID"
            custom_field.fieldname = "eboekhouden_mutation_id"
            custom_field.fieldtype = "Data"
            custom_field.unique = 1
            custom_field.no_copy = 1
            custom_field.insert_after = "cheque_date"
            custom_field.insert(ignore_permissions=True)
            
            return {
                "success": True,
                "created": True,
                "message": "Created mutation ID field"
            }
        else:
            return {
                "success": True,
                "created": False,
                "message": "Field already exists"
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def check_migration_readiness():
    """
    Check if system is ready for migration
    """
    company = frappe.db.get_single_value("E-Boekhouden Settings", "default_company")
    if not company:
        return {
            "ready": False,
            "error": "No default company set"
        }
    
    checks = {
        "company": bool(company),
        "cost_center": bool(ensure_main_cost_center(company)),
        "default_customer": frappe.db.exists("Customer", "E-Boekhouden Import Customer"),
        "default_supplier": frappe.db.exists("Supplier", "E-Boekhouden Import Supplier"),
        "suspense_account": bool(frappe.db.get_value("Account", {
            "company": company,
            "account_name": "E-Boekhouden Suspense Account"
        }, "name")),
        "mutation_field": frappe.db.has_column("Journal Entry", "eboekhouden_mutation_id")
    }
    
    return {
        "ready": all(checks.values()),
        "checks": checks,
        "missing": [k for k, v in checks.items() if not v]
    }

@frappe.whitelist()
def restore_account_types():
    """
    Restore Receivable/Payable account types after migration
    """
    company = frappe.db.get_single_value("E-Boekhouden Settings", "default_company")
    if not company:
        return {
            "success": False,
            "error": "No default company set"
        }
    
    # Account patterns to restore
    restore_patterns = [
        # Receivable patterns
        (["13500", "13510", "13600", "13900", "13990"], "Receivable"),
        # Payable patterns
        (["19290", "19291", "44000", "44900"], "Payable")
    ]
    
    restored = []
    for account_numbers, target_type in restore_patterns:
        for acc_num in account_numbers:
            account = frappe.db.get_value("Account", {
                "company": company,
                "account_number": acc_num
            }, ["name", "account_type"], as_dict=True)
            
            if account and account.account_type != target_type:
                frappe.db.set_value("Account", account.name, "account_type", target_type)
                restored.append({
                    "account": account.name,
                    "number": acc_num,
                    "to": target_type
                })
    
    frappe.db.commit()
    
    return {
        "success": True,
        "restored": len(restored),
        "accounts": restored
    }

def get_eboekhouden_date_range():
    """
    Get the actual date range of transactions from E-Boekhouden
    """
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        from datetime import datetime
        import json
        
        settings = frappe.get_single("E-Boekhouden Settings")
        if not settings.api_token:
            return {
                "success": False,
                "error": "E-Boekhouden API not configured"
            }
        
        api = EBoekhoudenAPI(settings)
        
        # Get all mutations to find the actual date range
        # E-Boekhouden API might not support proper sorting, so we'll get a larger sample
        all_dates = []
        
        # Try to get multiple pages to find the actual range
        for offset in [0, 100, 200, 500, 1000]:
            params = {
                "limit": 100,
                "offset": offset
            }
            
            result = api.get_mutations(params)
            if result["success"]:
                try:
                    data = json.loads(result["data"])
                    items = data.get("items", [])
                    
                    # Extract all dates
                    for item in items:
                        date_str = item.get("date", "")
                        if date_str:
                            try:
                                if 'T' in date_str:
                                    date_obj = datetime.strptime(date_str.split('T')[0], '%Y-%m-%d').date()
                                else:
                                    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                                all_dates.append(date_obj)
                            except:
                                pass
                    
                    # If we got less than limit, we've reached the end
                    if len(items) < 100:
                        break
                        
                except Exception as e:
                    frappe.log_error(f"Error parsing dates at offset {offset}: {str(e)}", "E-Boekhouden")
            else:
                # Stop if we can't fetch more
                break
        
        if all_dates:
            # Find actual min and max
            oldest_date = min(all_dates)
            newest_date = max(all_dates)
            
            # Add some buffer to ensure we don't miss anything
            # Go back 30 days from oldest and forward to today
            oldest_date = frappe.utils.add_days(oldest_date, -30)
            newest_date = frappe.utils.today()
            
            return {
                "success": True,
                "earliest_date": str(oldest_date),
                "latest_date": str(newest_date),
                "message": f"Found {len(all_dates)} transactions spanning from {oldest_date} to {newest_date}",
                "transaction_count": len(all_dates)
            }
        else:
            # No transactions found, use a reasonable default
            today = frappe.utils.today()
            five_years_ago = frappe.utils.add_days(today, -1825)
            
            return {
                "success": True,
                "earliest_date": str(five_years_ago),
                "latest_date": str(today),
                "message": "No transactions found, using default 5-year range",
                "transaction_count": 0
            }
        
    except Exception as e:
        frappe.log_error(f"Error getting date range: {str(e)}", "E-Boekhouden")
        return {
            "success": False,
            "error": str(e)
        }