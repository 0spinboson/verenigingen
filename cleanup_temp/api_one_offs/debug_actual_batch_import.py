import frappe

@frappe.whitelist()
def debug_actual_batch_import():
    """Debug the actual batch import function that's being called"""
    try:
        response = []
        response.append("=== DEBUGGING ACTUAL BATCH IMPORT ===")
        
        # The log shows DEBUG: Calling _import_rest_mutations_batch with 1267 mutations
        # Let me find this function and test it directly
        
        # Look for the function in different possible locations
        possible_locations = [
            "verenigingen.verenigingen.doctype.e_boekhouden_migration.e_boekhouden_migration",
            "verenigingen.utils.eboekhouden_rest_full_migration",
            "verenigingen.utils.eboekhouden_unified_processor"
        ]
        
        batch_import_function = None
        
        for location in possible_locations:
            try:
                module = frappe.get_module(location)
                if hasattr(module, '_import_rest_mutations_batch'):
                    batch_import_function = getattr(module, '_import_rest_mutations_batch')
                    response.append(f"Found _import_rest_mutations_batch in {location}")
                    break
            except:
                continue
        
        if not batch_import_function:
            response.append("❌ Could not find _import_rest_mutations_batch function")
            
            # Let's search for it manually
            response.append("\nSearching for batch import functions...")
            
            # Check the migration class
            try:
                from verenigingen.verenigingen.doctype.e_boekhouden_migration.e_boekhouden_migration import EBoekhoudenMigration
                migration = EBoekhoudenMigration()
                
                # Check if it has the method
                if hasattr(migration, '_import_rest_mutations_batch'):
                    response.append("Found _import_rest_mutations_batch in EBoekhoudenMigration class")
                    batch_import_function = migration._import_rest_mutations_batch
                else:
                    response.append("❌ _import_rest_mutations_batch not found in EBoekhoudenMigration class")
                    
                    # List all methods that contain 'batch' or 'import'
                    methods = [method for method in dir(migration) if 'batch' in method.lower() or 'import' in method.lower()]
                    response.append(f"Methods containing 'batch' or 'import': {methods}")
                    
            except Exception as e:
                response.append(f"❌ Error loading EBoekhoudenMigration: {str(e)}")
        
        # If we found the function, test it
        if batch_import_function:
            response.append(f"\n=== TESTING BATCH IMPORT FUNCTION ===")
            
            # Create test mutations
            test_mutations = [
                {
                    'id': 17, 
                    'type': 1, 
                    'date': '2019-03-31', 
                    'description': 'Test PINV 1', 
                    'termOfPayment': 30, 
                    'ledgerId': 13201883, 
                    'relationId': 19097433, 
                    'inExVat': 'EX', 
                    'invoiceNumber': 'TEST001', 
                    'entryNumber': '', 
                    'rows': [
                        {
                            'ledgerId': 15916395, 
                            'vatCode': 'GEEN', 
                            'vatAmount': 0.0, 
                            'amount': 100.0, 
                            'description': 'Test line 1'
                        }
                    ], 
                    'vat': [{'vatCode': 'GEEN', 'amount': 0.0}]
                },
                {
                    'id': 18, 
                    'type': 1, 
                    'date': '2019-04-01', 
                    'description': 'Test PINV 2', 
                    'termOfPayment': 30, 
                    'ledgerId': 13201884, 
                    'relationId': 19097434, 
                    'inExVat': 'EX', 
                    'invoiceNumber': 'TEST002', 
                    'entryNumber': '', 
                    'rows': [
                        {
                            'ledgerId': 15916396, 
                            'vatCode': 'GEEN', 
                            'vatAmount': 0.0, 
                            'amount': 200.0, 
                            'description': 'Test line 2'
                        }
                    ], 
                    'vat': [{'vatCode': 'GEEN', 'amount': 0.0}]
                }
            ]
            
            try:
                # Test the batch function
                if hasattr(batch_import_function, '__self__'):
                    # It's a bound method
                    result = batch_import_function(test_mutations, "Purchase Invoice")
                else:
                    # It's an unbound function - try different call signatures
                    try:
                        result = batch_import_function(test_mutations, "Purchase Invoice")
                    except:
                        # Try with migration instance
                        from verenigingen.verenigingen.doctype.e_boekhouden_migration.e_boekhouden_migration import EBoekhoudenMigration
                        migration = EBoekhoudenMigration()
                        result = batch_import_function(migration, test_mutations, "Purchase Invoice")
                
                response.append(f"Batch import result: {result}")
                
            except Exception as e:
                response.append(f"❌ Batch import test failed: {str(e)}")
                response.append(f"Error details: {frappe.get_traceback()}")
        
        # Let's also check what the REST migration actually calls
        response.append(f"\n=== CHECKING REST MIGRATION CALLS ===")
        try:
            # Look for the start_full_rest_import function
            from verenigingen.utils.eboekhouden_rest_full_migration import start_full_rest_import
            response.append("Found start_full_rest_import function")
            
            # Check if we can examine its source
            import inspect
            try:
                source_lines = inspect.getsource(start_full_rest_import)
                # Look for the batch import call
                if '_import_rest_mutations_batch' in source_lines:
                    response.append("✅ start_full_rest_import does call _import_rest_mutations_batch")
                else:
                    response.append("❌ start_full_rest_import does NOT call _import_rest_mutations_batch")
                    response.append("Looking for other import calls...")
                    
                    # Extract key lines
                    lines = source_lines.split('\n')
                    import_lines = [line.strip() for line in lines if 'import' in line.lower() or 'process' in line.lower()]
                    response.append(f"Import/process related lines: {import_lines[:5]}")
                    
            except Exception as e:
                response.append(f"Could not inspect source: {str(e)}")
                
        except Exception as e:
            response.append(f"❌ Error checking REST migration: {str(e)}")
        
        return "\n".join(response)
        
    except Exception as e:
        return f"Error: {e}\n{frappe.get_traceback()}"