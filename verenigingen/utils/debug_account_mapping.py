"""
Debug account mapping issues in E-Boekhouden import
"""

import frappe
from frappe import _
import json

@frappe.whitelist()
def debug_recent_import():
    """Debug recent import to see why accounts are mapped incorrectly"""
    
    try:
        # Get recent Purchase Invoices to see what's happening
        recent_pinvs = frappe.db.sql("""
            SELECT 
                pi.name,
                pi.bill_no,
                pi.supplier,
                pi.posting_date,
                pi.total,
                pii.item_code,
                pii.expense_account,
                pii.description,
                pii.rate
            FROM `tabPurchase Invoice` pi
            JOIN `tabPurchase Invoice Item` pii ON pii.parent = pi.name
            WHERE pi.supplier = 'E-Boekhouden Import'
            AND pi.posting_date >= '2025-01-01'
            ORDER BY pi.creation DESC
            LIMIT 10
        """, as_dict=True)
        
        # Check which accounts have eboekhouden_grootboek_nummer set
        accounts_with_mapping = frappe.db.sql("""
            SELECT 
                name,
                account_name,
                account_number,
                eboekhouden_grootboek_nummer
            FROM `tabAccount`
            WHERE company = 'Ned Ver Vegan'
            AND (eboekhouden_grootboek_nummer IS NOT NULL 
                 AND eboekhouden_grootboek_nummer != '')
            LIMIT 20
        """, as_dict=True)
        
        # Check if the field exists
        field_exists = frappe.db.sql("""
            SELECT 1 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'tabAccount' 
            AND COLUMN_NAME = 'eboekhouden_grootboek_nummer'
            AND TABLE_SCHEMA = DATABASE()
        """)
        
        # Test the smart mapper directly
        from verenigingen.utils.smart_tegenrekening_mapper import SmartTegenrekeningMapper
        mapper = SmartTegenrekeningMapper()
        
        # Test with some known account codes
        test_codes = ["48010", "99998", "18100", "14700", "13900", "10620"]
        mapping_tests = []
        
        for code in test_codes:
            result = mapper.get_item_for_tegenrekening(
                account_code=code,
                description="Test mapping",
                transaction_type="purchase",
                amount=100
            )
            
            # Also check what account is found
            account = mapper._get_account_by_code(code)
            
            mapping_tests.append({
                "code": code,
                "mapping_result": result,
                "account_found": account
            })
        
        return {
            "success": True,
            "recent_purchase_invoices": recent_pinvs,
            "accounts_with_eboekhouden_mapping": accounts_with_mapping,
            "field_exists": bool(field_exists),
            "mapping_tests": mapping_tests
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "traceback": frappe.get_traceback()
        }


@frappe.whitelist()
def check_ledger_mapping():
    """Check how ledger IDs are being used in the import"""
    
    try:
        # Get the import code and see what ledger_id is being passed
        recent_errors = frappe.get_all("Error Log",
            filters={
                "creation": [">", "2025-01-01"],
                "method": ["like", "%tegenrekening%"]
            },
            fields=["name", "error", "creation"],
            limit=5
        )
        
        # Check a specific mutation import
        from verenigingen.utils.eboekhouden_rest_full_migration import _import_rest_mutations_batch
        
        # Create a test mutation to see how it's processed
        test_mutation = {
            "id": 99999,
            "type": 1,  # Purchase Invoice
            "date": "2025-01-01",
            "invoiceNumber": "TEST-001",
            "relationId": "TEST",
            "description": "Test mutation",
            "rows": [
                {
                    "ledgerId": "48010",  # Should map to Afschrijving Inventaris
                    "ledgerName": "Test Ledger",
                    "amount": 100,
                    "debitCredit": "D"
                }
            ]
        }
        
        # Get what would be created (without actually creating)
        from verenigingen.utils.smart_tegenrekening_mapper import create_invoice_line_for_tegenrekening
        
        # Extract ledger ID like the import does
        ledger_id = None
        if test_mutation.get("rows"):
            ledger_id = test_mutation["rows"][0].get("ledgerId")
        
        # Test the mapping
        line_result = create_invoice_line_for_tegenrekening(
            tegenrekening_code=str(ledger_id) if ledger_id else None,
            amount=100,
            description="Test",
            transaction_type="purchase"
        )
        
        return {
            "success": True,
            "recent_errors": recent_errors,
            "test_mutation": test_mutation,
            "extracted_ledger_id": ledger_id,
            "line_mapping_result": line_result
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "traceback": frappe.get_traceback()
        }


@frappe.whitelist()
def fix_account_mappings():
    """Add eboekhouden_grootboek_nummer to accounts based on account_number"""
    
    try:
        # First check if the field exists
        field_exists = frappe.db.sql("""
            SELECT 1 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'tabAccount' 
            AND COLUMN_NAME = 'eboekhouden_grootboek_nummer'
            AND TABLE_SCHEMA = DATABASE()
        """)
        
        if not field_exists:
            # Add the field if it doesn't exist
            frappe.db.sql("""
                ALTER TABLE `tabAccount` 
                ADD COLUMN `eboekhouden_grootboek_nummer` VARCHAR(20)
            """)
            frappe.db.commit()
        
        # Update accounts to set eboekhouden_grootboek_nummer = account_number
        updated = frappe.db.sql("""
            UPDATE `tabAccount`
            SET eboekhouden_grootboek_nummer = account_number
            WHERE company = 'Ned Ver Vegan'
            AND account_number IS NOT NULL
            AND account_number != ''
            AND (eboekhouden_grootboek_nummer IS NULL 
                 OR eboekhouden_grootboek_nummer = '')
        """)
        
        frappe.db.commit()
        
        # Get count of updated records
        count = frappe.db.sql("""
            SELECT COUNT(*) as count
            FROM `tabAccount`
            WHERE company = 'Ned Ver Vegan'
            AND eboekhouden_grootboek_nummer IS NOT NULL
            AND eboekhouden_grootboek_nummer != ''
        """)[0][0]
        
        return {
            "success": True,
            "message": f"Updated {count} accounts with E-Boekhouden mapping",
            "field_added": not bool(field_exists)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "traceback": frappe.get_traceback()
        }