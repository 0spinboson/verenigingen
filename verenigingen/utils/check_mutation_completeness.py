#!/usr/bin/env python3
"""Check if mutation data is complete without detail fetch"""

import frappe

@frappe.whitelist()
def check_mutation_data():
    """Check what fields are available in mutation list vs detail"""
    
    from verenigingen.utils.eboekhouden_rest_client import EBoekhoudenRESTClient
    
    client = EBoekhoudenRESTClient()
    
    # Get a few mutations
    result = client.get_mutations(limit=3)
    
    if not result["success"]:
        return result
    
    mutations = result["mutations"]
    
    print("=== MUTATION DATA ANALYSIS ===\n")
    
    for i, mut in enumerate(mutations):
        print(f"Mutation {i+1}:")
        print(f"  ID: {mut.get('id')}")
        print(f"  Type: {mut.get('type')}")
        print(f"  Date: {mut.get('date')}")
        print(f"  Amount: {mut.get('amount')}")
        print(f"  Invoice: {mut.get('invoiceNumber')}")
        print(f"  Ledger ID: {mut.get('ledgerId')}")
        print(f"  Entry: {mut.get('entryNumber')}")
        print(f"  All fields: {list(mut.keys())}")
        print()
    
    # Check if detail endpoint works with id=0
    if mutations and mutations[0].get('id') == 0:
        print("Testing detail endpoint with various IDs...")
        # Try some mutation IDs
        for test_id in [1, 100, 1000, 5000, 7000]:
            try:
                token = client._get_session_token()
                import requests
                url = f"{client.base_url}/v1/mutation/{test_id}"
                headers = {"Authorization": token, "Accept": "application/json"}
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    detail = response.json()
                    print(f"\nID {test_id}: Found!")
                    print(f"  Type: {detail.get('type')}")
                    print(f"  Date: {detail.get('date')}")
                    print(f"  Fields: {list(detail.keys())}")
                    break
                else:
                    print(f"ID {test_id}: {response.status_code}")
            except Exception as e:
                print(f"ID {test_id}: Error - {str(e)}")
    
    return {
        "success": True,
        "mutation_count": len(mutations),
        "sample": mutations[0] if mutations else None
    }