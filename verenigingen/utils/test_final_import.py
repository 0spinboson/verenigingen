"""
Test the final import with fixed expense account
"""

import frappe
from frappe import _

@frappe.whitelist()
def test_final_import():
    """Test importing transactions after fixing expense account"""
    
    try:
        # Get existing migration or use the latest one
        migrations = frappe.db.sql("""
            SELECT name, migration_status
            FROM `tabE-Boekhouden Migration`
            ORDER BY creation DESC
            LIMIT 5
        """, as_dict=True)
        
        result = {
            "existing_migrations": migrations,
            "expense_account_fixed": True,
            "company_defaults": {}
        }
        
        # Check company defaults
        company = frappe.get_doc("Company", "Ned Ver Vegan")
        result["company_defaults"] = {
            "default_expense_account": company.get("default_expense_account"),
            "stock_adjustment_account": company.get("stock_adjustment_account")
        }
        
        # Check if the problematic account exists
        bad_account = "Kostprijs omzet grondstoffen - NVV"
        result["bad_account_exists"] = frappe.db.exists("Account", bad_account)
        
        # Count existing invoices
        result["existing_invoices"] = {
            "sales_invoices": frappe.db.count("Sales Invoice"),
            "purchase_invoices": frappe.db.count("Purchase Invoice")
        }
        
        # Test import a few specific mutations that were failing
        test_mutations = [
            {"id": 273, "type": 2, "date": "2019-01-03", "invoiceNumber": "INV-273", "relationId": "12345", 
             "description": "Test Sales Invoice 273", "rows": [{"ledgerId": "80010", "amount": 100.0}]},
            {"id": 460, "type": 2, "date": "2019-02-15", "invoiceNumber": "INV-460", "relationId": "12346",
             "description": "Test Sales Invoice 460", "rows": [{"ledgerId": "80005", "amount": 250.0}]},
            {"id": 461, "type": 2, "date": "2019-02-16", "invoiceNumber": "INV-461", "relationId": "12347",
             "description": "Test Sales Invoice 461", "rows": [{"ledgerId": "80006", "amount": 150.0}]}
        ]
        
        from verenigingen.utils.eboekhouden_rest_full_migration import _import_rest_mutations_batch
        settings = frappe.get_single("E-Boekhouden Settings")
        
        import_result = _import_rest_mutations_batch("TEST-IMPORT", test_mutations, settings)
        result["test_import_result"] = import_result
        
        # Check if invoices were created
        result["invoices_after_test"] = {
            "sales_invoices": frappe.db.count("Sales Invoice"),
            "purchase_invoices": frappe.db.count("Purchase Invoice")
        }
        
        return result
        
    except Exception as e:
        return {
            "error": str(e),
            "traceback": frappe.get_traceback()
        }


@frappe.whitelist()
def create_test_migration():
    """Create a test migration record"""
    
    try:
        # Check if test migration exists
        if frappe.db.exists("E-Boekhouden Migration", "TEST-MIGRATION-FINAL"):
            frappe.delete_doc("E-Boekhouden Migration", "TEST-MIGRATION-FINAL", force=True)
        
        # Create new migration
        migration = frappe.new_doc("E-Boekhouden Migration")
        migration.migration_name = "TEST-MIGRATION-FINAL"
        migration.migration_type = "Transactions Only"
        migration.date_from = "2019-01-01"
        migration.date_to = "2019-12-31"
        migration.migrate_transactions = 1
        migration.save()
        
        return {
            "success": True,
            "migration_name": migration.name,
            "message": "Test migration created successfully"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }