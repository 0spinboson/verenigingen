"""
E-Boekhouden REST API Full Migration
Fetches ALL mutations by iterating through IDs and caches them
"""

import frappe
from frappe import _
from datetime import datetime
import json

@frappe.whitelist()
def fetch_and_cache_all_mutations(start_id=None, end_id=None, batch_size=100):
    """
    Fetch and cache all mutations from REST API
    
    Args:
        start_id: Starting mutation ID (defaults to estimated lowest)
        end_id: Ending mutation ID (defaults to estimated highest)
        batch_size: Number of mutations to process before committing
        
    Returns:
        Dict with success status and statistics
    """
    from .eboekhouden_rest_iterator import EBoekhoudenRESTIterator
    
    try:
        iterator = EBoekhoudenRESTIterator()
        
        # If no range specified, estimate it
        if not start_id or not end_id:
            frappe.publish_realtime(
                "eboekhouden_migration_progress",
                {"message": "Estimating mutation ID range..."}
            )
            
            range_result = iterator.estimate_id_range()
            if not range_result["success"]:
                return {
                    "success": False,
                    "error": "Could not estimate mutation range"
                }
            
            start_id = start_id or range_result["lowest_id"]
            end_id = end_id or range_result["highest_id"]
        
        frappe.publish_realtime(
            "eboekhouden_migration_progress",
            {"message": f"Starting to fetch mutations from ID {start_id} to {end_id}..."}
        )
        
        # Statistics
        total_fetched = 0
        total_cached = 0
        already_cached = 0
        errors = []
        current_batch = []
        
        # Progress callback
        def update_progress(info):
            frappe.publish_realtime(
                "eboekhouden_migration_progress",
                {
                    "message": f"Checking ID {info['current_id']} - Found: {info['found']}, Not found: {info['not_found']}",
                    "progress": (info['current_id'] - start_id) / (end_id - start_id) * 100
                }
            )
        
        # Iterate through IDs
        for mutation_id in range(start_id, end_id + 1):
            # Check if already cached
            existing_cache = frappe.db.get_value(
                "EBoekhouden REST Mutation Cache",
                {"mutation_id": mutation_id},
                "name"
            )
            if existing_cache:
                already_cached += 1
                continue
            
            # Try to fetch the mutation
            try:
                # First try detail endpoint (more complete data)
                mutation_data = iterator.fetch_mutation_detail(mutation_id)
                
                if mutation_data:
                    total_fetched += 1
                    
                    # Create cache entry
                    cache_doc = frappe.new_doc("EBoekhouden REST Mutation Cache")
                    cache_doc.mutation_id = mutation_id
                    cache_doc.mutation_data = json.dumps(mutation_data)
                    cache_doc.mutation_type = mutation_data.get("type")
                    cache_doc.mutation_date = mutation_data.get("date")
                    cache_doc.amount = abs(float(mutation_data.get("amount", 0)))
                    cache_doc.ledger_id = mutation_data.get("ledgerId")
                    cache_doc.relation_id = mutation_data.get("relationId")
                    cache_doc.invoice_number = mutation_data.get("invoiceNumber")
                    cache_doc.entry_number = mutation_data.get("entryNumber")
                    cache_doc.description = mutation_data.get("description", "")[:140]  # Truncate for field
                    
                    current_batch.append(cache_doc)
                    
                    # Commit batch
                    if len(current_batch) >= batch_size:
                        _save_batch(current_batch)
                        total_cached += len(current_batch)
                        current_batch = []
                        
                        frappe.publish_realtime(
                            "eboekhouden_migration_progress",
                            {
                                "message": f"Cached {total_cached} mutations so far...",
                                "progress": (mutation_id - start_id) / (end_id - start_id) * 100
                            }
                        )
                
            except Exception as e:
                errors.append({
                    "mutation_id": mutation_id,
                    "error": str(e)
                })
            
            # Progress update every 50 IDs
            if mutation_id % 50 == 0:
                update_progress({
                    "current_id": mutation_id,
                    "found": total_fetched,
                    "not_found": mutation_id - start_id - total_fetched - already_cached,
                    "total_checked": mutation_id - start_id + 1
                })
        
        # Save remaining batch
        if current_batch:
            _save_batch(current_batch)
            total_cached += len(current_batch)
        
        # Final statistics
        result = {
            "success": True,
            "statistics": {
                "range_checked": f"{start_id} to {end_id}",
                "total_ids_checked": end_id - start_id + 1,
                "total_fetched": total_fetched,
                "total_cached": total_cached,
                "already_cached": already_cached,
                "not_found": end_id - start_id + 1 - total_fetched - already_cached,
                "errors": len(errors)
            }
        }
        
        frappe.publish_realtime(
            "eboekhouden_migration_progress",
            {
                "message": f"Completed! Fetched {total_fetched} mutations, cached {total_cached} new entries.",
                "progress": 100
            }
        )
        
        return result
        
    except Exception as e:
        frappe.log_error(f"REST mutation fetch error: {str(e)}", "E-Boekhouden REST Migration")
        return {
            "success": False,
            "error": str(e)
        }


def _save_batch(batch):
    """Save a batch of cache documents"""
    for doc in batch:
        try:
            doc.insert(ignore_permissions=True)
        except Exception as e:
            frappe.log_error(
                f"Failed to cache mutation {doc.mutation_id}: {str(e)}",
                "E-Boekhouden Cache Error"
            )
    frappe.db.commit()


@frappe.whitelist()
def get_cache_statistics():
    """Get statistics about cached mutations"""
    try:
        total_cached = frappe.db.count("EBoekhouden REST Mutation Cache")
        
        if total_cached == 0:
            return {
                "success": True,
                "total_cached": 0,
                "message": "No mutations cached yet"
            }
        
        # Get date range
        oldest = frappe.db.sql("""
            SELECT MIN(mutation_date) as oldest_date,
                   MIN(mutation_id) as lowest_id
            FROM `tabEBoekhouden REST Mutation Cache`
        """, as_dict=True)[0]
        
        newest = frappe.db.sql("""
            SELECT MAX(mutation_date) as newest_date,
                   MAX(mutation_id) as highest_id
            FROM `tabEBoekhouden REST Mutation Cache`
        """, as_dict=True)[0]
        
        # Get type distribution
        type_distribution = frappe.db.sql("""
            SELECT mutation_type, COUNT(*) as count
            FROM `tabEBoekhouden REST Mutation Cache`
            GROUP BY mutation_type
            ORDER BY count DESC
        """, as_dict=True)
        
        # Map type numbers to names (based on REST API documentation)
        type_names = {
            0: "Opening Balance",
            1: "Invoice received",  # Purchase Invoice
            2: "Invoice sent",      # Sales Invoice
            3: "Invoice payment received",  # Customer Payment
            4: "Invoice payment sent",      # Supplier Payment
            5: "Money received",
            6: "Money sent",
            7: "General journal entry"
        }
        
        for item in type_distribution:
            item["type_name"] = type_names.get(item["mutation_type"], f"Type {item['mutation_type']}")
        
        return {
            "success": True,
            "total_cached": total_cached,
            "date_range": {
                "oldest": oldest["oldest_date"],
                "newest": newest["newest_date"]
            },
            "id_range": {
                "lowest": oldest["lowest_id"],
                "highest": newest["highest_id"]
            },
            "type_distribution": type_distribution
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def clear_cache():
    """Clear all cached mutations"""
    try:
        frappe.db.sql("DELETE FROM `tabEBoekhouden REST Mutation Cache`")
        frappe.db.commit()
        
        return {
            "success": True,
            "message": "Cache cleared successfully"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def fetch_sample_batch(start_id=100, end_id=200):
    """Fetch a small batch for testing"""
    return fetch_and_cache_all_mutations(
        start_id=int(start_id),
        end_id=int(end_id),
        batch_size=10
    )


@frappe.whitelist()
def check_cache_table():
    """Check if cache table exists"""
    try:
        # Check if the DocType exists
        doctype_exists = frappe.db.exists("DocType", "EBoekhouden REST Mutation Cache")
        
        # Check if the table exists
        table_exists = False
        try:
            frappe.db.sql("SELECT 1 FROM `tabEBoekhouden REST Mutation Cache` LIMIT 1")
            table_exists = True
        except:
            pass
        
        return {
            "doctype_exists": doctype_exists,
            "table_exists": table_exists
        }
    except Exception as e:
        return {"error": str(e)}


@frappe.whitelist()
def start_full_rest_import(migration_name):
    """Start full transaction import via REST API"""
    try:
        migration = frappe.get_doc("E-Boekhouden Migration", migration_name)
        
        # Update status
        migration.db_set({
            "migration_status": "In Progress",
            "start_time": frappe.utils.now_datetime(),
            "current_operation": "Starting REST API transaction import...",
            "progress_percentage": 0
        })
        frappe.db.commit()
        
        # Phase 1: Import any new customers/suppliers first
        frappe.publish_realtime(
            "eboekhouden_migration_progress",
            {"message": "Importing customers and suppliers..."}
        )
        
        # Import customers and suppliers via standard SOAP method
        settings = frappe.get_single("E-Boekhouden Settings")
        
        # Import customers
        if getattr(migration, 'migrate_customers', 0):
            migrate_method = getattr(migration.__class__, 'migrate_customers')
            customer_result = migrate_method(migration, settings)
            migration.db_set({"current_operation": f"Imported customers: {customer_result}"})
            frappe.db.commit()
        
        # Import suppliers  
        if getattr(migration, 'migrate_suppliers', 0):
            migrate_method = getattr(migration.__class__, 'migrate_suppliers')
            supplier_result = migrate_method(migration, settings)
            migration.db_set({"current_operation": f"Imported suppliers: {supplier_result}"})
            frappe.db.commit()
        
        # Phase 2: Fetch and cache all mutations
        migration.db_set({
            "current_operation": "Fetching all transactions via REST API...",
            "progress_percentage": 20
        })
        frappe.db.commit()
        
        # Estimate ID range and fetch all mutations
        from .eboekhouden_rest_iterator import EBoekhoudenRESTIterator
        iterator = EBoekhoudenRESTIterator()
        
        # Get estimated range
        range_result = iterator.estimate_id_range()
        if not range_result["success"]:
            raise Exception(f"Could not estimate mutation range: {range_result.get('error')}")
        
        start_id = range_result["lowest_id"]
        end_id = range_result["highest_id"]
        
        frappe.publish_realtime(
            "eboekhouden_migration_progress",
            {"message": f"Found mutation range: ID {start_id} to {end_id}"}
        )
        
        # Phase 3: Import mutations by type (optimized approach)
        # Import all mutation types with smart tegenrekening mapping
        mutation_types = [1, 2, 3, 4, 5, 6, 7]  # All mutation types
        type_names = {
            1: "Purchase Invoices",
            2: "Sales Invoices", 
            3: "Customer Payments",
            4: "Supplier Payments",
            5: "Money Received",
            6: "Money Sent",
            7: "Journal Entries"
        }
        
        total_imported = 0
        failed_imports = []
        debug_info = []
        
        for i, mutation_type in enumerate(mutation_types):
            type_name = type_names.get(mutation_type, f"Type {mutation_type}")
            
            migration.db_set({
                "current_operation": f"Fetching {type_name}...",
                "progress_percentage": 20 + (i / len(mutation_types) * 70)
            })
            frappe.db.commit()
            
            frappe.publish_realtime(
                "eboekhouden_migration_progress",
                {"message": f"Processing {type_name}..."}
            )
            
            # Fetch all mutations of this type
            try:
                def progress_callback(info):
                    progress_msg = f"{type_name}: Fetched {info['total_fetched']} mutations"
                    frappe.publish_realtime(
                        "eboekhouden_migration_progress",
                        {"message": progress_msg}
                    )
                    debug_info.append(progress_msg)
                
                # Fetch all mutations of this type (no limit for full migration)
                type_mutations = iterator.fetch_mutations_by_type(mutation_type, progress_callback=progress_callback)
                
                debug_info.append(f"DEBUG: fetch_mutations_by_type returned {len(type_mutations) if type_mutations else 0} mutations")
                
                if type_mutations:
                    debug_info.append(f"DEBUG: Sample mutation keys: {list(type_mutations[0].keys()) if type_mutations[0] else 'None'}")
                    debug_info.append(f"DEBUG: Sample mutation: {type_mutations[0] if type_mutations[0] else 'None'}")
                    
                    frappe.publish_realtime(
                        "eboekhouden_migration_progress",
                        {"message": f"Processing {len(type_mutations)} {type_name}..."}
                    )
                    
                    # Import this batch
                    debug_info.append(f"Calling _import_rest_mutations_batch with {len(type_mutations)} mutations")
                    import_result = _import_rest_mutations_batch(migration_name, type_mutations, settings)
                    debug_info.append(f"Import result: {import_result}")
                    
                    total_imported += import_result.get("imported", 0)
                    
                    if import_result.get("errors"):
                        failed_imports.extend(import_result["errors"])
                        debug_info.append(f"Errors occurred: {len(import_result['errors'])}")
                        
                else:
                    debug_info.append(f"No mutations returned for {type_name}")
                    frappe.publish_realtime(
                        "eboekhouden_migration_progress",
                        {"message": f"No {type_name} found"}
                    )
                    
            except Exception as e:
                error_msg = f"Failed to process {type_name}: {str(e)}"
                failed_imports.append(error_msg)
                debug_info.append(error_msg)
                frappe.log_error(error_msg, "REST Migration Type Processing")
        
        # Log all debug info
        debug_log = "\n".join(debug_info)
        frappe.log_error(f"DEBUG REST Import Log:\n{debug_log}", "REST Debug")
        
        # Phase 4: Complete
        migration.db_set({
            "migration_status": "Completed",
            "end_time": frappe.utils.now_datetime(),
            "current_operation": f"Import completed. Total mutations imported: {total_imported}",
            "progress_percentage": 100,
            "imported_records": total_imported,
            "failed_records": len(failed_imports)
        })
        frappe.db.commit()
        
        frappe.publish_realtime(
            "eboekhouden_migration_progress",
            {
                "message": f"REST API import completed! Imported {total_imported} transactions.",
                "progress": 100,
                "completed": True
            }
        )
        
        return {
            "success": True,
            "total_imported": total_imported,
            "failed": len(failed_imports)
        }
        
    except Exception as e:
        import traceback
        full_error = f"Error: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        frappe.log_error(f"REST import failed: {full_error}", "E-Boekhouden REST Import")
        
        # Update migration status
        migration = frappe.get_doc("E-Boekhouden Migration", migration_name)
        migration.db_set({
            "migration_status": "Failed",
            "error_log": full_error,
            "end_time": frappe.utils.now_datetime()
        })
        frappe.db.commit()
        
        return {
            "success": False,
            "error": str(e)
        }


def _import_rest_mutations_batch(migration_name, mutations, settings):
    """Import a batch of REST API mutations with smart tegenrekening mapping"""
    imported = 0
    errors = []
    debug_info = []
    
    debug_info.append(f"Starting import with {len(mutations) if mutations else 0} mutations")
    
    if not mutations:
        debug_info.append("No mutations provided, returning early")
        frappe.log_error(f"BATCH Log:\n" + "\n".join(debug_info), "REST Batch Debug")
        return {"imported": 0, "failed": 0, "errors": []}
    
    # migration_doc = frappe.get_doc("E-Boekhouden Migration", migration_name)  # Not needed for batch processing
    company = settings.default_company
    debug_info.append(f"Company: {company}")
    
    # Get cost center
    cost_center = frappe.db.get_value("Cost Center", {
        "company": company,
        "is_group": 0
    }, "name")
    
    debug_info.append(f"Cost center found: {cost_center}")
    
    if not cost_center:
        errors.append("No cost center found")
        debug_info.append("ERROR - No cost center found")
        frappe.log_error(f"BATCH Log:\n" + "\n".join(debug_info), "REST Batch Debug")
        return {"imported": 0, "failed": len(mutations), "errors": errors}
    
    for i, mutation in enumerate(mutations):
        try:
            mutation_type = mutation.get("type")
            mutation_id = mutation.get("id")
            
            debug_info.append(f"Processing mutation {i+1}/{len(mutations)}: ID={mutation_id}, Type={mutation_type}")
            
            # Skip opening balance entries for now
            if mutation_type == 0:
                debug_info.append(f"Skipping opening balance mutation {mutation_id}")
                continue
            
            # Extract amount from rows (correct structure for REST API mutations)
            amount = 0
            rows = mutation.get("rows", [])
            if rows:
                for row in rows:
                    amount += abs(float(row.get("amount", 0)))
            
            description = mutation.get("description", f"Mutation {mutation_id}")
            
            debug_info.append(f"Calculated amount for mutation {mutation_id}: {amount}")
            
            if amount > 0:
                # Import smart tegenrekening mapping
                from verenigingen.utils.smart_tegenrekening_mapper import create_invoice_line_for_tegenrekening
                
                # Extract ledger ID from mutation rows
                ledger_id = None
                if rows:
                    ledger_id = rows[0].get("ledgerId")
                
                if mutation_type == 1:  # Purchase Invoice (FactuurOntvangen)
                    debug_info.append(f"Creating Purchase Invoice for mutation {mutation_id}")
                    
                    # Create Purchase Invoice
                    pi = frappe.new_doc("Purchase Invoice")
                    pi.company = company
                    pi.posting_date = mutation.get("date")
                    pi.bill_no = mutation.get("invoiceNumber", f"EBH-{mutation_id}")
                    pi.bill_date = mutation.get("date")
                    
                    # Try to find supplier from relation_id
                    relation_id = mutation.get("relationId")
                    supplier = _get_or_create_supplier(relation_id, debug_info)
                    pi.supplier = supplier
                    
                    # Set correct payable account for credit_to
                    pi.credit_to = _get_payable_account(company)
                    
                    # Add item line using smart tegenrekening mapping
                    try:
                        line_dict = create_invoice_line_for_tegenrekening(
                            tegenrekening_code=str(ledger_id) if ledger_id else None,
                            amount=amount,
                            description=description,
                            transaction_type="purchase"
                        )
                        if line_dict and isinstance(line_dict, dict):
                            pi.append("items", line_dict)
                        else:
                            debug_info.append(f"Smart mapping returned invalid result: {line_dict}")
                            # Fallback to basic item
                            pi.append("items", {
                                "item_code": "E-Boekhouden Import Item",
                                "qty": 1,
                                "rate": amount,
                                "description": description
                            })
                    except Exception as e:
                        debug_info.append(f"Smart mapping error: {str(e)}")
                        # Fallback to basic item
                        pi.append("items", {
                            "item_code": "E-Boekhouden Import Item", 
                            "qty": 1,
                            "rate": amount,
                            "description": description
                        })
                    
                    # Save and submit
                    pi.save()
                    pi.submit()
                    imported += 1
                    debug_info.append(f"Successfully created Purchase Invoice for mutation {mutation_id}")
                    
                elif mutation_type == 2:  # Sales Invoice (FactuurVerstuurd)
                    debug_info.append(f"Creating Sales Invoice for mutation {mutation_id}")
                    
                    # Create Sales Invoice
                    si = frappe.new_doc("Sales Invoice")
                    si.company = company
                    si.posting_date = mutation.get("date")
                    
                    # Try to find customer from relation_id
                    relation_id = mutation.get("relationId")
                    customer = _get_or_create_customer(relation_id, debug_info)
                    si.customer = customer
                    
                    # Add item line using smart tegenrekening mapping
                    try:
                        line_dict = create_invoice_line_for_tegenrekening(
                            tegenrekening_code=str(ledger_id) if ledger_id else None,
                            amount=amount,
                            description=description,
                            transaction_type="sales"
                        )
                        if line_dict and isinstance(line_dict, dict):
                            si.append("items", line_dict)
                        else:
                            debug_info.append(f"Smart mapping returned invalid result: {line_dict}")
                            # Fallback to basic item
                            si.append("items", {
                                "item_code": "E-Boekhouden Import Item",
                                "qty": 1,
                                "rate": amount,
                                "description": description
                            })
                    except Exception as e:
                        debug_info.append(f"Smart mapping error: {str(e)}")
                        # Fallback to basic item
                        si.append("items", {
                            "item_code": "E-Boekhouden Import Item",
                            "qty": 1,
                            "rate": amount,
                            "description": description
                        })
                    
                    # Save and submit
                    si.save()
                    si.submit()
                    imported += 1
                    debug_info.append(f"Successfully created Sales Invoice for mutation {mutation_id}")
                    
                elif mutation_type in [3, 4]:  # Payment Entries (Customer/Supplier Payments)
                    debug_info.append(f"Creating Payment Entry for mutation {mutation_id}")
                    
                    # Create Payment Entry
                    pe = frappe.new_doc("Payment Entry")
                    pe.company = company
                    pe.posting_date = mutation.get("date")
                    pe.paid_amount = amount
                    pe.received_amount = amount
                    pe.reference_no = mutation.get("invoiceNumber", f"EBH-{mutation_id}")
                    pe.reference_date = mutation.get("date")
                    
                    if mutation_type == 3:  # Customer Payment
                        pe.payment_type = "Receive"
                        pe.party_type = "Customer"
                        relation_id = mutation.get("relationId")
                        customer = _get_or_create_customer(relation_id, debug_info)
                        pe.party = customer
                    else:  # Supplier Payment
                        pe.payment_type = "Pay"
                        pe.party_type = "Supplier"
                        relation_id = mutation.get("relationId")
                        supplier = _get_or_create_supplier(relation_id, debug_info)
                        pe.party = supplier
                    
                    # Set bank account (default cash account)
                    if pe.payment_type == "Receive":  # Customer Payment
                        pe.paid_from = _get_receivable_account(company)
                        pe.paid_to = _get_bank_account(company)
                    else:  # Supplier Payment
                        pe.paid_from = _get_bank_account(company)
                        pe.paid_to = _get_payable_account(company)
                    
                    pe.save()
                    pe.submit()
                    imported += 1
                    debug_info.append(f"Successfully created Payment Entry for mutation {mutation_id}")
                    
                else:  # Journal Entries (Money Received/Sent, General)
                    debug_info.append(f"Creating Journal Entry for mutation {mutation_id} (Type {mutation_type})")
                    
                    je = frappe.new_doc("Journal Entry")
                    je.company = company
                    je.posting_date = mutation.get("date")
                    je.user_remark = f"E-Boekhouden REST Import - Mutation {mutation_id} (Type {mutation_type})"
                    je.voucher_type = "Journal Entry"
                    
                    # Use smart mapping to get proper accounts
                    line_dict = create_invoice_line_for_tegenrekening(
                        tegenrekening_code=str(ledger_id) if ledger_id else None,
                        amount=amount,
                        description=description,
                        transaction_type="purchase"  # Default to purchase for expense account
                    )
                    
                    # Create balanced journal entry
                    je.append("accounts", {
                        "account": line_dict.get("expense_account") or "8000 - Algemene kosten - NVV",
                        "debit_in_account_currency": amount,
                        "credit_in_account_currency": 0,
                        "cost_center": cost_center,
                        "user_remark": description
                    })
                    
                    je.append("accounts", {
                        "account": _get_bank_account(company),
                        "debit_in_account_currency": 0,
                        "credit_in_account_currency": amount,
                        "cost_center": cost_center,
                        "user_remark": description
                    })
                    
                    je.save()
                    je.submit()
                    imported += 1
                    debug_info.append(f"Successfully created Journal Entry for mutation {mutation_id}")
                
        except Exception as e:
            error_msg = f"Failed to import mutation {mutation.get('id', 'unknown')}: {str(e)}"
            errors.append(error_msg)
            debug_info.append(f"ERROR importing mutation {mutation.get('id', 'unknown')}: {str(e)}")
            frappe.log_error(error_msg, "REST Mutation Import")
    
    debug_info.append(f"Completed batch - Imported: {imported}, Failed: {len(errors)}")
    frappe.log_error(f"BATCH Log:\n" + "\n".join(debug_info), "REST Batch Debug")
    
    return {"imported": imported, "failed": len(errors), "errors": errors}


def _get_or_create_supplier(relation_id, debug_info):
    """Get or create supplier for mutation"""
    supplier = None
    
    # Skip relation_id lookup for now since custom field may not exist
    # if relation_id:
    #     # Look for existing supplier with this relation_id
    #     supplier = frappe.db.get_value("Supplier", 
    #         {"custom_eboekhouden_relation_id": relation_id}, "name")
    
    if not supplier:
        # Create default supplier or use existing default
        supplier = frappe.db.get_value("Supplier", 
            {"supplier_name": "E-Boekhouden Import"}, "name")
        
        if not supplier:
            # Create default supplier
            supplier_doc = frappe.new_doc("Supplier")
            supplier_doc.supplier_name = "E-Boekhouden Import"
            supplier_doc.supplier_group = "All Supplier Groups"
            supplier_doc.save()
            supplier = supplier_doc.name
            debug_info.append(f"Created default supplier: {supplier}")
    
    return supplier


def _get_or_create_customer(relation_id, debug_info):
    """Get or create customer for mutation"""
    customer = None
    
    # Skip relation_id lookup for now since custom field may not exist
    # if relation_id:
    #     # Look for existing customer with this relation_id
    #     customer = frappe.db.get_value("Customer", 
    #         {"custom_eboekhouden_relation_id": relation_id}, "name")
    
    if not customer:
        # Create default customer or use existing default
        customer = frappe.db.get_value("Customer", 
            {"customer_name": "E-Boekhouden Import"}, "name")
        
        if not customer:
            # Create default customer
            customer_doc = frappe.new_doc("Customer")
            customer_doc.customer_name = "E-Boekhouden Import"
            customer_doc.customer_group = "All Customer Groups"
            customer_doc.save()
            customer = customer_doc.name
            debug_info.append(f"Created default customer: {customer}")
    
    return customer


def _get_bank_account(company):
    """Get bank account for company"""
    bank_account = frappe.db.get_value("Account", {
        "company": company,
        "account_type": "Bank",
        "is_group": 0
    }, "name")
    
    if not bank_account:
        # Fallback to cash account
        bank_account = frappe.db.get_value("Account", {
            "company": company,
            "account_type": "Cash",
            "is_group": 0
        }, "name")
    
    return bank_account or "1100 - Kas - NVV"  # Final fallback


def _get_receivable_account(company):
    """Get receivable account for company"""
    receivable_account = frappe.db.get_value("Account", {
        "company": company,
        "account_type": "Receivable",
        "is_group": 0
    }, "name")
    
    return receivable_account or "1300 - Debiteuren - NVV"  # Fallback


def _get_payable_account(company):
    """Get payable account for company (needed for Purchase Invoice credit_to)"""
    payable_account = frappe.db.get_value("Account", {
        "company": company,
        "account_type": "Payable",
        "is_group": 0
    }, "name")
    
    return payable_account or "1600 - Crediteuren - NVV"  # Fallback


def map_rest_type_to_soap_type(rest_type):
    """Map REST API mutation types to SOAP type names"""
    type_mapping = {
        0: "Opening",
        1: "FactuurOntvangen", 
        2: "FactuurVerstuurd",
        3: "FactuurBetaaldOntvangen",
        4: "FactuurBetaaldVerstuurd", 
        5: "GeldOntvangen",
        6: "GeldVerstuurd",
        7: "Memoriaal"
    }
    return type_mapping.get(rest_type, "Unknown")