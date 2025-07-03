#!/usr/bin/env python3
"""Analyze if REST API can replace SOAP API for e-boekhouden migration"""

import frappe
import json
import requests

@frappe.whitelist()
def analyze_rest_api_viability():
    """Check if REST API provides all fields needed for migration"""
    
    print("=== REST API VIABILITY ANALYSIS ===\n")
    
    # Load swagger spec
    with open("/tmp/eboekhouden_rest_api_spec.json", 'r') as f:
        swagger = json.load(f)
    
    # Required fields from SOAP analysis
    required_fields = {
        "core": ["MutatieNr", "Datum", "Soort", "Omschrijving"],
        "financial": ["BedragDebet", "BedragCredit", "Rekening", "MutatieRegels"],
        "relations": ["RelatieCode", "Factuurnummer"],
        "vat": ["InExBTW", "BTWCode", "BTWPercentage"],
        "payment": ["Betalingstermijn"]
    }
    
    print("1. CHECKING AVAILABLE ENDPOINTS:\n")
    
    # Look for relevant endpoints
    paths = swagger.get("paths", {})
    relevant_endpoints = []
    
    for path, methods in paths.items():
        path_lower = path.lower()
        if any(term in path_lower for term in ["mutatie", "transaction", "booking", "invoice", "factuur"]):
            relevant_endpoints.append(path)
            print(f"Found: {path}")
            for method, details in methods.items():
                if method in ["get", "post"]:
                    print(f"  {method.upper()}: {details.get('summary', 'No summary')}")
    
    if not relevant_endpoints:
        print("No mutation-related endpoints found!")
    
    print("\n2. CHECKING DATA MODELS:\n")
    
    # Check definitions/components
    definitions = swagger.get("definitions", {})
    components = swagger.get("components", {}).get("schemas", {})
    all_schemas = {**definitions, **components}
    
    # Look for relevant models
    relevant_models = []
    for model_name, model_def in all_schemas.items():
        model_lower = model_name.lower()
        if any(term in model_lower for term in ["mutatie", "transaction", "booking", "invoice", "factuur"]):
            relevant_models.append(model_name)
            print(f"\nModel: {model_name}")
            properties = model_def.get("properties", {})
            
            # Check which required fields are present
            found_fields = []
            missing_fields = []
            
            for category, fields in required_fields.items():
                for field in fields:
                    field_found = False
                    # Check exact match and case variations
                    for prop_name in properties.keys():
                        if prop_name.lower() == field.lower():
                            found_fields.append(field)
                            field_found = True
                            break
                    if not field_found:
                        missing_fields.append(field)
            
            print(f"  Found fields: {', '.join(found_fields) if found_fields else 'None'}")
            print(f"  Missing fields: {', '.join(missing_fields) if missing_fields else 'None'}")
    
    print("\n3. CRITICAL ANALYSIS:\n")
    
    # Check for mutation line items support
    mutation_line_support = False
    for model_name, model_def in all_schemas.items():
        properties = model_def.get("properties", {})
        for prop_name, prop_def in properties.items():
            if "items" in prop_def or prop_def.get("type") == "array":
                if any(term in prop_name.lower() for term in ["regel", "line", "item"]):
                    mutation_line_support = True
                    print(f"Found line items support in {model_name}.{prop_name}")
    
    if not mutation_line_support:
        print("WARNING: No clear support for mutation line items (MutatieRegels)")
    
    # Check for pagination/range support  
    print("\n4. CHECKING PAGINATION SUPPORT:\n")
    
    for path, methods in paths.items():
        if "get" in methods:
            params = methods["get"].get("parameters", [])
            pagination_params = []
            for param in params:
                param_name = param.get("name", "").lower()
                if any(term in param_name for term in ["limit", "offset", "page", "from", "to", "start", "end"]):
                    pagination_params.append(param.get("name"))
            
            if pagination_params:
                print(f"{path}: {', '.join(pagination_params)}")
    
    print("\n5. CONCLUSION:\n")
    
    can_replace_soap = len(relevant_endpoints) > 0 and len(relevant_models) > 0 and mutation_line_support
    
    if can_replace_soap:
        print("REST API might be viable, but requires:")
        print("- Field mapping between SOAP and REST")
        print("- Testing if pagination overcomes 500 limit")
        print("- Verifying all transaction types are supported")
    else:
        print("REST API does NOT appear viable because:")
        if not relevant_endpoints:
            print("- No mutation/transaction endpoints found")
        if not relevant_models:
            print("- No suitable data models found")
        if not mutation_line_support:
            print("- No support for line items (MutatieRegels)")
    
    return {
        "viable": can_replace_soap,
        "endpoints": relevant_endpoints,
        "models": relevant_models,
        "has_line_items": mutation_line_support
    }

@frappe.whitelist()
def test_rest_api_directly():
    """Test the REST API directly to see what data it returns"""
    
    print("=== TESTING REST API DIRECTLY ===\n")
    
    from verenigingen.models.e_boekhouden_settings import EboekhoudenSettings
    
    # Get settings
    settings = EboekhoudenSettings.get_settings()
    if not settings:
        return "No E-Boekhouden settings found"
    
    # REST API base URL
    base_url = "https://api.e-boekhouden.nl/v1"
    
    # Headers
    headers = {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    print(f"Testing with API key: {settings.api_key[:10]}...")
    
    # Try common endpoints
    test_endpoints = [
        "/mutaties",
        "/mutations", 
        "/transactions",
        "/boekingen",
        "/bookings",
        "/facturen",
        "/invoices"
    ]
    
    for endpoint in test_endpoints:
        try:
            url = base_url + endpoint
            print(f"\nTrying {url}...")
            response = requests.get(url, headers=headers, timeout=10)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"Response type: {type(data)}")
                if isinstance(data, list) and len(data) > 0:
                    print(f"Found {len(data)} items")
                    print(f"First item keys: {list(data[0].keys())}")
                elif isinstance(data, dict):
                    print(f"Response keys: {list(data.keys())}")
                break
                
        except Exception as e:
            print(f"Error: {str(e)}")
    
    return "REST API test complete"

if __name__ == "__main__":
    print("Run with:")
    print("bench --site dev.veganisme.net execute verenigingen.utils.analyze_rest_api_alternatives.analyze_rest_api_viability")
    print("bench --site dev.veganisme.net execute verenigingen.utils.analyze_rest_api_alternatives.test_rest_api_directly")