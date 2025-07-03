import frappe

@frappe.whitelist()
def test_pinv_import():
    """Test Purchase Invoice import with a sample mutation"""
    try:
        response = []
        response.append("=== TESTING PURCHASE INVOICE IMPORT ===")
        
        # Get settings
        settings = frappe.get_single("E-Boekhouden Settings")
        company = settings.default_company
        
        # Test with the sample mutation from the log
        sample_mutation = {
            'id': 17, 
            'type': 1, 
            'date': '2019-03-31', 
            'description': 'Waku Waku - diner (kaartjes voor verkocht)', 
            'termOfPayment': 30, 
            'ledgerId': 13201883, 
            'relationId': 19097433, 
            'inExVat': 'EX', 
            'invoiceNumber': '042019', 
            'entryNumber': '', 
            'rows': [
                {
                    'ledgerId': 15916395, 
                    'vatCode': 'GEEN', 
                    'vatAmount': 0.0, 
                    'amount': 456.7, 
                    'description': 'Waku Waku - diner (kaartjes voor verkocht)'
                }
            ], 
            'vat': [
                {
                    'vatCode': 'GEEN', 
                    'amount': 0.0
                }
            ]
        }
        
        response.append(f"Testing with sample mutation: ID {sample_mutation['id']}")
        response.append(f"Description: {sample_mutation['description']}")
        response.append(f"Amount: {sample_mutation['rows'][0]['amount']}")
        
        # Try to process this mutation using the unified processor
        try:
            from verenigingen.utils.eboekhouden_unified_processor import process_purchase_invoices
            
            # Get default cost center
            cost_center = frappe.db.get_value("Cost Center", {"company": company}, "name")
            
            result = process_purchase_invoices([sample_mutation], company, cost_center, None)
            
            response.append(f"\nProcess result:")
            response.append(f"  Created: {result.get('created', 0)}")
            response.append(f"  Errors: {len(result.get('errors', []))}")
            
            if result.get('errors'):
                response.append(f"  Error details:")
                for error in result.get('errors', [])[:3]:  # Show first 3 errors
                    response.append(f"    - {error}")
                    
        except Exception as e:
            response.append(f"❌ Processing error: {str(e)}")
            response.append(f"Traceback: {frappe.get_traceback()}")
        
        # Check the prerequisites again
        response.append(f"\n=== CHECKING PREREQUISITES ===")
        
        # Check for Payable account
        payable_account = frappe.db.get_value("Account", {
            "company": company,
            "account_type": "Payable",
            "is_group": 0
        }, "name")
        response.append(f"Payable account found: {payable_account}")
        
        # Check for Expense account
        expense_account = frappe.db.get_value("Account", {
            "company": company,
            "account_type": "Expense Account",
            "is_group": 0
        }, "name")
        response.append(f"Expense account found: {expense_account}")
        
        # Check for default supplier
        supplier = frappe.db.get_value("Supplier", {"disabled": 0}, "name")
        response.append(f"Supplier found: {supplier}")
        
        # Check for default item
        item = frappe.db.get_value("Item", {"disabled": 0}, "name")
        response.append(f"Item found: {item}")
        
        # Check cost center
        response.append(f"Cost center: {cost_center}")
        
        return "\n".join(response)
        
    except Exception as e:
        return f"Error: {e}\n{frappe.get_traceback()}"