import frappe

@frappe.whitelist()
def debug_mutation_processing():
    """Debug why mutations aren't being processed into Purchase Invoices"""
    try:
        response = []
        response.append("=== DEBUGGING MUTATION PROCESSING ===")
        
        # Create a simple test mutation matching your log format
        test_mutation = {
            'id': 17, 
            'type': 1, 
            'date': '2019-03-31', 
            'description': 'Test mutation for debugging', 
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
                    'description': 'Test line item'
                }
            ], 
            'vat': [
                {
                    'vatCode': 'GEEN', 
                    'amount': 0.0
                }
            ]
        }
        
        # Test 1: Can we create a Purchase Invoice manually with this data?
        response.append("=== TEST 1: MANUAL PURCHASE INVOICE CREATION ===")
        try:
            settings = frappe.get_single("E-Boekhouden Settings")
            company = settings.default_company
            
            # Create Purchase Invoice manually
            pi = frappe.new_doc("Purchase Invoice")
            
            # Get first available supplier
            supplier = frappe.db.get_value("Supplier", {"disabled": 0}, "name")
            if not supplier:
                response.append("❌ No suppliers available!")
                return "\n".join(response)
            
            pi.supplier = supplier
            pi.company = company
            pi.posting_date = test_mutation['date']
            pi.bill_no = test_mutation.get('invoiceNumber', 'TEST')
            
            # Set credit_to (payable account)
            payable_account = frappe.db.get_value("Account", {
                "company": company,
                "account_type": "Payable",
                "is_group": 0
            }, "name")
            
            if not payable_account:
                response.append("❌ No payable accounts available!")
                return "\n".join(response)
            
            pi.credit_to = payable_account
            
            # Get expense account
            expense_account = frappe.db.get_value("Account", {
                "company": company,
                "account_type": "Expense Account",
                "is_group": 0
            }, "name")
            
            # Get cost center
            cost_center = frappe.db.get_value("Cost Center", {"company": company}, "name")
            
            # Get item
            item = frappe.db.get_value("Item", {"disabled": 0}, "name")
            
            # Add line item
            pi.append("items", {
                "item_code": item,
                "qty": 1,
                "rate": test_mutation['rows'][0]['amount'],
                "expense_account": expense_account,
                "cost_center": cost_center,
                "description": test_mutation['rows'][0]['description']
            })
            
            # Try to save
            pi.insert(ignore_permissions=True)
            response.append(f"✅ Manual PI created: {pi.name}")
            
            # Try to submit
            pi.submit()
            response.append(f"✅ Manual PI submitted: {pi.name}")
            
        except Exception as e:
            response.append(f"❌ Manual PI creation failed: {str(e)}")
            response.append(f"Traceback: {frappe.get_traceback()}")
        
        # Test 2: Try using the unified processor
        response.append(f"\n=== TEST 2: UNIFIED PROCESSOR ===")
        try:
            from verenigingen.utils.eboekhouden_unified_processor import process_purchase_invoices
            
            cost_center = frappe.db.get_value("Cost Center", {"company": company}, "name")
            
            result = process_purchase_invoices([test_mutation], company, cost_center, None)
            
            response.append(f"Unified processor result:")
            response.append(f"  Created: {result.get('created', 0)}")
            response.append(f"  Errors: {len(result.get('errors', []))}")
            
            if result.get('errors'):
                for error in result.get('errors', []):
                    response.append(f"    Error: {error}")
                    
        except Exception as e:
            response.append(f"❌ Unified processor failed: {str(e)}")
        
        # Test 3: Check what the actual batch import expects
        response.append(f"\n=== TEST 3: BATCH IMPORT EXPECTATIONS ===")
        
        # Check if there's a type mapping issue
        response.append(f"Mutation type: {test_mutation.get('type')}")
        response.append(f"Mutation keys: {list(test_mutation.keys())}")
        
        # Check for required fields
        required_fields = ['id', 'type', 'date', 'description', 'rows']
        missing_fields = [field for field in required_fields if field not in test_mutation]
        if missing_fields:
            response.append(f"❌ Missing required fields: {missing_fields}")
        else:
            response.append(f"✅ All required fields present")
        
        return "\n".join(response)
        
    except Exception as e:
        return f"Error: {e}\n{frappe.get_traceback()}"