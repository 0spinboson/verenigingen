#!/usr/bin/env python3
"""
Debug script to check raw API responses for date analysis
"""

import frappe
import json
from datetime import datetime

def debug_early_mutations():
    """Debug the early mutations to see raw API responses"""
    
    frappe.connect(site="dev.veganisme.net")
    
    from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    
    # Get settings
    settings = frappe.get_single("E-Boekhouden Settings")
    if not settings:
        print("❌ E-Boekhouden Settings not found")
        return
    
    # Initialize API
    api = EBoekhoudenSOAPAPI(settings)
    
    print("🔍 Debugging Early Mutations Date Analysis")
    print("=" * 50)
    
    # Check mutations in the 20-30 range where you say the earliest data is
    print("\n1. Checking mutations 20-30 (where earliest data should be):")
    early_result = api.get_mutations(mutation_nr_from=20, mutation_nr_to=30)
    
    if not early_result["success"]:
        print(f"❌ Failed to fetch mutations 20-30: {early_result.get('error')}")
    else:
        mutations = early_result["mutations"]
        print(f"✅ Found {len(mutations)} mutations in range 20-30")
        
        for i, mut in enumerate(mutations[:5]):  # Show first 5
            print(f"\n--- Mutation {i+1} ---")
            print(f"Raw mutation data: {json.dumps(mut, indent=2, default=str)}")
            
            datum = mut.get("Datum")
            print(f"Datum field: '{datum}' (type: {type(datum)})")
            
            if datum:
                # Try different parsing approaches
                print("Date parsing attempts:")
                
                # Original approach
                date_str = datum
                if 'T' in str(date_str):
                    date_str = str(date_str).split('T')[0]
                try:
                    parsed = datetime.strptime(date_str, "%Y-%m-%d").date()
                    print(f"  ✅ YYYY-MM-DD format: {parsed}")
                except Exception as e:
                    print(f"  ❌ YYYY-MM-DD format failed: {e}")
                
                # Try other common formats
                for fmt in ["%d-%m-%Y", "%m-%d-%Y", "%Y/%m/%d", "%d/%m/%Y"]:
                    try:
                        parsed = datetime.strptime(str(datum), fmt).date()
                        print(f"  ✅ {fmt} format: {parsed}")
                    except:
                        print(f"  ❌ {fmt} format failed")
    
    # Also check mutations 1-10 to see what's there
    print("\n2. Checking mutations 1-10 (original algorithm range):")
    early_result_orig = api.get_mutations(mutation_nr_from=1, mutation_nr_to=10)
    
    if not early_result_orig["success"]:
        print(f"❌ Failed to fetch mutations 1-10: {early_result_orig.get('error')}")
    else:
        mutations = early_result_orig["mutations"]
        print(f"✅ Found {len(mutations)} mutations in range 1-10")
        
        if mutations:
            for i, mut in enumerate(mutations[:3]):  # Show first 3
                datum = mut.get("Datum")
                print(f"Mutation {i+1}: Datum = '{datum}'")
        else:
            print("No mutations found in range 1-10")
    
    # Check highest mutation number
    print("\n3. Checking highest mutation number:")
    highest_result = api.get_highest_mutation_number()
    if highest_result["success"]:
        print(f"✅ Highest mutation number: {highest_result['highest_mutation_number']}")
    else:
        print(f"❌ Failed to get highest mutation: {highest_result.get('error')}")
    
    frappe.db.close()

if __name__ == "__main__":
    debug_early_mutations()