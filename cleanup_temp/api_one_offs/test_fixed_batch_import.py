import frappe

@frappe.whitelist()
def test_fixed_batch_import():
    """Test the fixed batch import function"""
    try:
        response = []
        response.append("=== TESTING FIXED BATCH IMPORT ===")
        
        # Get the fixed function
        from verenigingen.utils.eboekhouden_rest_full_migration import _import_rest_mutations_batch
        
        # Create test mutations
        test_mutations = [
            {
                'id': 99001, 
                'type': 1, 
                'date': '2019-03-31', 
                'description': 'Test PINV Import Fix', 
                'termOfPayment': 30, 
                'ledgerId': 13201883, 
                'relationId': 19097433, 
                'inExVat': 'EX', 
                'invoiceNumber': 'FIX001', 
                'entryNumber': '', 
                'rows': [
                    {
                        'ledgerId': 15916395, 
                        'vatCode': 'GEEN', 
                        'vatAmount': 0.0, 
                        'amount': 123.45, 
                        'description': 'Test line for fix verification'
                    }
                ], 
                'vat': [{'vatCode': 'GEEN', 'amount': 0.0}]
            },
            {
                'id': 99002, 
                'type': 1, 
                'date': '2019-04-01', 
                'description': 'Test PINV Import Fix 2', 
                'termOfPayment': 30, 
                'ledgerId': 13201884, 
                'relationId': 19097434, 
                'inExVat': 'EX', 
                'invoiceNumber': 'FIX002', 
                'entryNumber': '', 
                'rows': [
                    {
                        'ledgerId': 15916396, 
                        'vatCode': 'GEEN', 
                        'vatAmount': 0.0, 
                        'amount': 67.89, 
                        'description': 'Test line 2 for fix verification'
                    }
                ], 
                'vat': [{'vatCode': 'GEEN', 'amount': 0.0}]
            }
        ]
        
        # Test the fixed batch import
        settings = frappe.get_single("E-Boekhouden Settings")
        
        # Create a temporary migration for testing
        migration_name = "Test-PINV-Fix-Import"
        if frappe.db.exists("E-Boekhouden Migration", migration_name):
            frappe.delete_doc("E-Boekhouden Migration", migration_name)
        
        migration = frappe.new_doc("E-Boekhouden Migration")
        migration.migration_name = migration_name
        migration.migration_type = "Debug Test"
        migration.save()
        frappe.db.commit()  # Commit so the batch function can find it
        
        response.append(f"Created test migration: {migration_name}")
        
        # Test the batch import function
        result = _import_rest_mutations_batch(migration_name, test_mutations, settings)
        
        response.append(f"Batch import result:")
        response.append(f"  Imported: {result.get('imported', 0)}")
        response.append(f"  Failed: {result.get('failed', 0)}")
        response.append(f"  Errors: {len(result.get('errors', []))}")
        
        if result.get('errors'):
            response.append(f"  Error details:")
            for error in result.get('errors', [])[:3]:
                response.append(f"    - {error}")
        
        # Check if Purchase Invoices were actually created
        created_pinvs = frappe.db.get_all("Purchase Invoice",
            filters={
                "bill_no": ["in", ["FIX001", "FIX002"]]
            },
            fields=["name", "bill_no", "grand_total", "docstatus"])
        
        response.append(f"\nPurchase Invoices created: {len(created_pinvs)}")
        for pinv in created_pinvs:
            response.append(f"  - {pinv.name}: {pinv.bill_no} ({pinv.grand_total}) Status: {pinv.docstatus}")
        
        # Clean up test migration
        frappe.delete_doc("E-Boekhouden Migration", migration_name)
        
        return "\n".join(response)
        
    except Exception as e:
        return f"Error: {e}\n{frappe.get_traceback()}"