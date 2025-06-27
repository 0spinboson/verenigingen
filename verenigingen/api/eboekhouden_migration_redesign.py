"""
Redesigned E-Boekhouden Migration Interface
Simplifies the migration process with sensible defaults
"""

import frappe
from frappe import _

@frappe.whitelist()
def get_migration_options():
    """
    Get simplified migration options based on what makes sense
    """
    return {
        "migration_types": [
            {
                "value": "full_initial",
                "label": "Full Initial Migration",
                "description": "Complete migration of all data from E-Boekhouden (first time setup)",
                "includes": ["accounts", "relations", "transactions", "opening_balance"],
                "date_range_required": False,
                "recommended_for": "First time migration"
            },
            {
                "value": "transactions_update", 
                "label": "Transaction Update",
                "description": "Import new transactions for a specific date range",
                "includes": ["transactions"],
                "date_range_required": True,
                "recommended_for": "Regular updates or catching up on recent transactions"
            },
            {
                "value": "full_rebuild",
                "label": "Full Rebuild", 
                "description": "Rebuild everything (useful if data was corrupted)",
                "includes": ["accounts", "relations", "transactions"],
                "date_range_required": False,
                "recommended_for": "Fixing data issues"
            },
            {
                "value": "preview",
                "label": "Preview Only",
                "description": "Preview what would be imported without making changes",
                "includes": ["preview"],
                "date_range_required": True,
                "recommended_for": "Testing and verification"
            }
        ],
        "notes": [
            "Chart of Accounts is always imported first as it's required for everything else",
            "Customer/Supplier data is imported automatically when referenced in transactions",
            "All mutations are tracked by their MutatieNr to prevent duplicates"
        ]
    }

@frappe.whitelist()
def check_migration_readiness():
    """
    Check if the system is ready for migration
    """
    checks = {
        "api_configured": False,
        "company_set": False,
        "duplicate_tracking_enabled": False,
        "last_migration": None,
        "mutation_tracking_available": False
    }
    
    # Check API configuration
    try:
        settings = frappe.get_single("E-Boekhouden Settings")
        checks["api_configured"] = bool(settings.api_url and settings.get_password('api_token'))
        checks["company_set"] = bool(settings.default_company)
    except:
        pass
    
    # Check if we have mutation tracking field
    meta = frappe.get_meta("Journal Entry")
    for field in meta.fields:
        if field.fieldname == "eboekhouden_mutation_id":
            checks["mutation_tracking_available"] = True
            break
    
    # Get last migration info
    last_migration = frappe.db.sql("""
        SELECT name, migration_status, end_time, imported_records
        FROM `tabE-Boekhouden Migration`
        WHERE migration_status = 'Completed'
        ORDER BY end_time DESC
        LIMIT 1
    """, as_dict=True)
    
    if last_migration:
        checks["last_migration"] = {
            "name": last_migration[0].name,
            "date": last_migration[0].end_time,
            "records": last_migration[0].imported_records
        }
    
    return checks

@frappe.whitelist()
def setup_mutation_tracking():
    """
    Add mutation ID tracking to relevant doctypes
    """
    doctypes_to_update = [
        ("Journal Entry", "eboekhouden_mutation_id", "E-Boekhouden Mutation ID"),
        ("Sales Invoice", "eboekhouden_invoice_number", "E-Boekhouden Invoice Number"),
        ("Purchase Invoice", "eboekhouden_invoice_number", "E-Boekhouden Invoice Number"),
        ("Payment Entry", "eboekhouden_mutation_id", "E-Boekhouden Mutation ID")
    ]
    
    results = []
    
    for doctype, fieldname, label in doctypes_to_update:
        try:
            # Check if field already exists
            meta = frappe.get_meta(doctype)
            field_exists = any(field.fieldname == fieldname for field in meta.fields)
            
            if not field_exists:
                # Add custom field
                custom_field = frappe.get_doc({
                    "doctype": "Custom Field",
                    "dt": doctype,
                    "fieldname": fieldname,
                    "label": label,
                    "fieldtype": "Data",
                    "insert_after": "amended_from",
                    "allow_in_quick_entry": 0,
                    "allow_on_submit": 0,
                    "bold": 0,
                    "collapsible": 0,
                    "columns": 0,
                    "fetch_from": None,
                    "fetch_if_empty": 0,
                    "hidden": 0,
                    "ignore_user_permissions": 0,
                    "ignore_xss_filter": 0,
                    "in_global_search": 0,
                    "in_list_view": 0,
                    "in_standard_filter": 0,
                    "no_copy": 1,
                    "options": None,
                    "print_hide": 1,
                    "print_hide_if_no_value": 0,
                    "print_width": None,
                    "read_only": 1,
                    "report_hide": 0,
                    "reqd": 0,
                    "search_index": 1,
                    "translatable": 0,
                    "unique": 1 if "mutation_id" in fieldname else 0,
                    "width": None
                })
                custom_field.insert()
                
                results.append({
                    "doctype": doctype,
                    "status": "created",
                    "field": fieldname
                })
            else:
                results.append({
                    "doctype": doctype,
                    "status": "exists",
                    "field": fieldname
                })
                
        except Exception as e:
            results.append({
                "doctype": doctype,
                "status": "error",
                "error": str(e)
            })
    
    return {
        "success": True,
        "results": results
    }

@frappe.whitelist()
def get_migration_statistics():
    """
    Get statistics about migrations and imported data
    """
    stats = {}
    
    # Migration history
    stats["migrations"] = frappe.db.sql("""
        SELECT 
            migration_status,
            COUNT(*) as count,
            SUM(imported_records) as total_records,
            SUM(failed_records) as total_failed
        FROM `tabE-Boekhouden Migration`
        GROUP BY migration_status
    """, as_dict=True)
    
    # Check for duplicates
    stats["duplicate_mutations"] = frappe.db.sql("""
        SELECT 
            eboekhouden_mutation_id,
            COUNT(*) as count
        FROM `tabJournal Entry`
        WHERE eboekhouden_mutation_id IS NOT NULL
        AND eboekhouden_mutation_id != ''
        GROUP BY eboekhouden_mutation_id
        HAVING COUNT(*) > 1
    """, as_dict=True)
    
    # Account statistics
    stats["accounts"] = {
        "total": frappe.db.count("Account", {"account_number": ["!=", ""]}),
        "by_type": frappe.db.sql("""
            SELECT account_type, COUNT(*) as count
            FROM `tabAccount`
            WHERE account_number IS NOT NULL
            AND account_number != ''
            GROUP BY account_type
        """, as_dict=True)
    }
    
    return stats