#!/usr/bin/env python3
"""Compare what fields we use from SOAP API vs what REST API provides"""

import frappe
import json

@frappe.whitelist()
def analyze_soap_field_usage():
    """Check which SOAP fields are actually used in the migration"""
    
    print("=== ANALYZING SOAP FIELD USAGE ===\n")
    
    # Read the migration file to find field accesses
    import os
    migration_file = os.path.join(
        "/home/frappe/frappe-bench/apps/verenigingen/verenigingen/utils",
        "eboekhouden_soap_migration.py"
    )
    
    with open(migration_file, 'r') as f:
        content = f.read()
    
    # Common field access patterns
    field_patterns = [
        'mut.get("', 
        'mutation_dict.get("',
        'mut["',
        'mutation_dict["'
    ]
    
    # Extract field names
    fields_used = set()
    for line in content.split('\n'):
        for pattern in field_patterns:
            if pattern in line:
                # Extract field name
                start = line.find(pattern) + len(pattern)
                end = line.find('"', start)
                if end > start:
                    field = line[start:end]
                    if field and not field.startswith('_'):
                        fields_used.add(field)
    
    print("Fields used from SOAP mutations:")
    for field in sorted(fields_used):
        print(f"  - {field}")
    
    # Check specific transaction processing
    print("\n=== CHECKING KEY FIELD USAGE ===")
    
    # Sales Invoices
    print("\nSales Invoices (FactuurVerstuurd):")
    si_fields = [
        "Factuurnummer", "MutatieNr", "Datum", "RelatieCode",
        "Relatiecode", "Omschrijving", "Bedrag", "OpenstaandSaldo"
    ]
    for field in si_fields:
        if field in fields_used:
            print(f"  ✓ {field}")
        else:
            print(f"  ? {field} (check if used)")
    
    # Payments
    print("\nPayments (FactuurbetalingOntvangen/Verstuurd):")
    payment_fields = [
        "Factuurnummer", "MutatieNr", "Datum", "RelatieCode",
        "Bedrag", "Omschrijving"
    ]
    for field in payment_fields:
        if field in fields_used:
            print(f"  ✓ {field}")
        else:
            print(f"  ? {field} (check if used)")
    
    # Bank transactions
    print("\nBank Transactions (GeldOntvangen/Uitgegeven):")
    bank_fields = [
        "MutatieNr", "Datum", "Rekening", "RelatieCode",
        "Omschrijving", "BedragDebet", "BedragCredit", "MutatieRegels"
    ]
    for field in bank_fields:
        if field in fields_used:
            print(f"  ✓ {field}")
        else:
            print(f"  ? {field} (check if used)")
    
    return "Analysis complete"

@frappe.whitelist()
def check_rest_api_capabilities():
    """Check what the REST API provides based on swagger spec"""
    
    print("=== REST API CAPABILITIES ===\n")
    
    # Based on the swagger.json URL, let's fetch and analyze it
    import requests
    
    try:
        response = requests.get("https://api.e-boekhouden.nl/swagger/v1/swagger.json")
        swagger_spec = response.json()
        
        print("Available REST API endpoints:")
        paths = swagger_spec.get("paths", {})
        
        # Look for mutation-related endpoints
        mutation_endpoints = []
        for path, methods in paths.items():
            if "mutatie" in path.lower() or "transaction" in path.lower():
                mutation_endpoints.append(path)
                print(f"\n{path}:")
                for method, details in methods.items():
                    if method in ["get", "post"]:
                        print(f"  {method.upper()}: {details.get('summary', 'No summary')}")
        
        # Check mutation model definition
        definitions = swagger_spec.get("definitions", {})
        
        # Look for mutation model
        for def_name, definition in definitions.items():
            if "mutatie" in def_name.lower():
                print(f"\n{def_name} model:")
                properties = definition.get("properties", {})
                for prop, details in properties.items():
                    prop_type = details.get("type", "unknown")
                    print(f"  - {prop}: {prop_type}")
        
        # Save full spec for review
        spec_file = "/tmp/eboekhouden_rest_api_spec.json"
        with open(spec_file, 'w') as f:
            json.dump(swagger_spec, f, indent=2)
        print(f"\nFull API spec saved to: {spec_file}")
        
    except Exception as e:
        print(f"Error fetching REST API spec: {e}")
    
    return "Check complete"

@frappe.whitelist()
def compare_mutation_data():
    """Compare actual SOAP mutation data structure"""
    
    print("=== SOAP MUTATION DATA STRUCTURE ===\n")
    
    from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    
    api = EBoekhoudenSOAPAPI()
    
    # Get a few mutations to see their structure
    result = api.get_mutations()
    
    if not result["success"]:
        return f"Failed to get mutations: {result.get('error')}"
    
    mutations = result.get("mutations", [])
    
    # Group by type and show structure
    from collections import defaultdict
    by_type = defaultdict(list)
    
    for mut in mutations[:20]:  # First 20
        mut_type = mut.get("Soort", "Unknown")
        by_type[mut_type].append(mut)
    
    for mut_type, muts in by_type.items():
        print(f"\n{mut_type} structure:")
        if muts:
            # Show first mutation of this type
            mut = muts[0]
            for key, value in sorted(mut.items()):
                if key == "MutatieRegels" and value:
                    print(f"  {key}: [{len(value)} lines]")
                    if value:
                        print("    Line structure:")
                        for line_key in sorted(value[0].keys()):
                            print(f"      - {line_key}")
                else:
                    value_str = str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
                    print(f"  {key}: {value_str}")
    
    return "Comparison complete"

if __name__ == "__main__":
    print("Run with:")
    print("bench --site dev.veganisme.net execute verenigingen.utils.compare_api_fields.analyze_soap_field_usage")
    print("bench --site dev.veganisme.net execute verenigingen.utils.compare_api_fields.check_rest_api_capabilities")
    print("bench --site dev.veganisme.net execute verenigingen.utils.compare_api_fields.compare_mutation_data")