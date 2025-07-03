import frappe

@frappe.whitelist()
def test_amount_extraction():
    """Test amount extraction from mutation structure"""
    try:
        response = []
        response.append("=== TESTING AMOUNT EXTRACTION ===")
        
        # Test mutation from the log
        test_mutation = {
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
        
        # Test current (broken) logic
        current_amount = abs(float(test_mutation.get("amount", 0)))
        response.append(f"Current logic - mutation.get('amount', 0): {current_amount}")
        response.append(f"Passes amount > 0 check: {current_amount > 0}")
        
        # Test correct logic (same as the fix)
        total_amount = 0
        rows = test_mutation.get("rows", [])
        if rows:
            for row in rows:
                total_amount += abs(float(row.get("amount", 0)))
        
        response.append(f"Correct logic - sum of rows amounts: {total_amount}")
        response.append(f"Passes amount > 0 check: {total_amount > 0}")
        
        # Show the mutation structure
        response.append(f"\nMutation structure:")
        response.append(f"  Has 'amount' key: {'amount' in test_mutation}")
        response.append(f"  Has 'rows' key: {'rows' in test_mutation}")
        response.append(f"  Number of rows: {len(test_mutation.get('rows', []))}")
        
        if test_mutation.get("rows"):
            for i, row in enumerate(test_mutation["rows"]):
                response.append(f"  Row {i+1} amount: {row.get('amount', 'N/A')}")
        
        # Test with multiple rows
        multi_row_mutation = {
            'id': 18,
            'type': 1,
            'rows': [
                {'amount': 100.0},
                {'amount': 200.0},
                {'amount': 50.0}
            ]
        }
        
        multi_current = abs(float(multi_row_mutation.get("amount", 0)))
        multi_correct = sum(abs(float(row.get("amount", 0))) for row in multi_row_mutation.get("rows", []))
        
        response.append(f"\nMulti-row test:")
        response.append(f"  Current logic: {multi_current}")
        response.append(f"  Correct logic: {multi_correct}")
        
        return "\n".join(response)
        
    except Exception as e:
        return f"Error: {e}\n{frappe.get_traceback()}"