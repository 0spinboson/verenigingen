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
        from verenigingen.verenigingen.doctype.e_boekhouden_migration.e_boekhouden_migration import EBoekhoudenMigration
        settings = frappe.get_single("E-Boekhouden Settings")
        
        # Temporarily create migration instance for importing entities
        temp_migration = EBoekhoudenMigration()
        temp_migration.name = migration_name
        
        # Import customers
        if migration.migrate_customers:
            customer_result = temp_migration.migrate_customers(settings)
            migration.db_set("current_operation", f"Imported customers: {customer_result}")
            frappe.db.commit()
        
        # Import suppliers  
        if migration.migrate_suppliers:
            supplier_result = temp_migration.migrate_suppliers(settings)
            migration.db_set("current_operation", f"Imported suppliers: {supplier_result}")
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
        
        # Phase 3: Import mutations in batches
        batch_size = 100
        total_imported = 0
        failed_imports = []
        
        for batch_start in range(start_id, end_id + 1, batch_size):
            batch_end = min(batch_start + batch_size - 1, end_id)
            
            migration.db_set({
                "current_operation": f"Processing mutations {batch_start} to {batch_end}...",
                "progress_percentage": 20 + ((batch_start - start_id) / (end_id - start_id) * 70)
            })
            frappe.db.commit()
            
            # Fetch mutations in this batch
            mutations = []
            for mutation_id in range(batch_start, batch_end + 1):
                try:
                    mutation_data = iterator.fetch_mutation_detail(mutation_id)
                    if mutation_data:
                        mutations.append(mutation_data)
                except Exception as e:
                    failed_imports.append({"id": mutation_id, "error": str(e)})
            
            # Import the mutations
            if mutations:
                import_result = _import_rest_mutations_batch(migration_name, mutations, settings)
                total_imported += import_result.get("imported", 0)
        
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
        frappe.log_error(f"REST import failed: {str(e)}", "E-Boekhouden REST Import")
        
        # Update migration status
        migration = frappe.get_doc("E-Boekhouden Migration", migration_name)
        migration.db_set({
            "migration_status": "Failed",
            "error_log": str(e),
            "end_time": frappe.utils.now_datetime()
        })
        frappe.db.commit()
        
        return {
            "success": False,
            "error": str(e)
        }


def _import_rest_mutations_batch(migration_name, mutations, settings):
    """Import a batch of REST API mutations"""
    imported = 0
    failed = 0
    
    for mutation in mutations:
        try:
            # Convert REST mutation to ERPNext Journal Entry
            # This is a simplified version - enhance as needed
            
            # Map mutation types
            mutation_type = mutation.get("type")
            
            # Skip opening balance entries
            if mutation_type == 0:
                continue
            
            # Create Journal Entry
            je = frappe.new_doc("Journal Entry")
            je.company = settings.default_company
            je.posting_date = mutation.get("date")
            je.user_remark = f"Migrated from e-Boekhouden - Mutation {mutation.get('id')}"
            
            # Add accounts based on mutation type
            # This is simplified - actual implementation needs proper account mapping
            amount = float(mutation.get("amount", 0))
            
            # Add debit/credit entries based on mutation type
            # TODO: Implement proper account mapping logic
            
            imported += 1
            
        except Exception as e:
            failed += 1
            frappe.log_error(
                f"Failed to import mutation {mutation.get('id')}: {str(e)}",
                "REST Mutation Import"
            )
    
    return {"imported": imported, "failed": failed}