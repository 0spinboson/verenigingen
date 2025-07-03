import frappe

@frappe.whitelist()
def debug_batch_import():
    """Debug the batch import process that's failing"""
    try:
        response = []
        response.append("=== DEBUGGING BATCH IMPORT ===")
        
        # Check recent Purchase Invoices
        recent_pinvs = frappe.db.get_all("Purchase Invoice",
            filters={
                "creation": [">=", "2025-07-03"]
            },
            fields=["name", "supplier", "grand_total", "creation"],
            order_by="creation desc",
            limit=5)
        
        response.append(f"Recent Purchase Invoices (last 5): {len(recent_pinvs)}")
        for pinv in recent_pinvs:
            response.append(f"  - {pinv.name}: {pinv.supplier} ({pinv.grand_total}) at {pinv.creation}")
        
        # Check what the import function is actually doing
        response.append(f"\n=== TESTING BATCH IMPORT LOGIC ===")
        
        # Get a few sample mutations from the API
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        settings = frappe.get_single("E-Boekhouden Settings")
        
        try:
            api = EBoekhoudenAPI(settings)
            
            # Test fetching mutations
            mutations = api.fetch_mutations_by_type(
                date_from="2019-01-01",
                date_to="2019-12-31",
                mutation_type=1,  # Purchase invoices
                limit=5  # Just get a few for testing
            )
            
            response.append(f"Fetched {len(mutations)} test mutations")
            
            if mutations:
                response.append(f"Sample mutation structure:")
                sample = mutations[0]
                response.append(f"  Keys: {list(sample.keys())}")
                response.append(f"  ID: {sample.get('id')}")
                response.append(f"  Type: {sample.get('type')}")
                response.append(f"  Date: {sample.get('date')}")
                response.append(f"  Amount: {sample.get('rows', [{}])[0].get('amount', 'N/A') if sample.get('rows') else 'N/A'}")
                
                # Test the actual import function that was called
                response.append(f"\n=== TESTING _import_rest_mutations_batch ===")
                
                # Import the function that handles the batch
                try:
                    # Find the actual import function
                    from verenigingen.verenigingen.doctype.e_boekhouden_migration.e_boekhouden_migration import EBoekhoudenMigration
                    
                    # Create a test migration instance
                    migration = EBoekhoudenMigration()
                    
                    # Test with just 2 mutations
                    test_mutations = mutations[:2]
                    result = migration._import_rest_mutations_batch(test_mutations, "Purchase Invoice")
                    
                    response.append(f"Batch import result:")
                    response.append(f"  Imported: {result.get('imported', 0)}")
                    response.append(f"  Failed: {result.get('failed', 0)}")
                    response.append(f"  Errors: {len(result.get('errors', []))}")
                    
                    if result.get('errors'):
                        response.append(f"  Error details:")
                        for error in result.get('errors', [])[:3]:
                            response.append(f"    - {error}")
                
                except Exception as batch_error:
                    response.append(f"❌ Batch import error: {str(batch_error)}")
                    response.append(f"Traceback: {frappe.get_traceback()}")
            
        except Exception as api_error:
            response.append(f"❌ API error: {str(api_error)}")
        
        return "\n".join(response)
        
    except Exception as e:
        return f"Error: {e}\n{frappe.get_traceback()}"