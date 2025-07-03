#!/usr/bin/env python3
"""Test the hybrid SOAP/REST migration approach"""

import frappe

@frappe.whitelist()
def test_soap_connection():
    """Test SOAP API is working"""
    from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    
    try:
        api = EBoekhoudenSOAPAPI()
        
        # Test getting relations
        result = api.get_relaties()
        
        if result["success"]:
            return {
                "success": True,
                "message": f"SOAP API working. Found {result['count']} relations"
            }
        else:
            return result
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def test_rest_api_token():
    """Check if REST API token is configured"""
    try:
        settings = frappe.get_single("E-Boekhouden Settings")
        api_token = settings.get_password('api_token') if hasattr(settings, 'api_token') else None
        
        return {
            "success": True,
            "has_token": bool(api_token),
            "token_preview": f"{api_token[:10]}..." if api_token else "Not set",
            "message": "API token is configured" if api_token else "API token not set - please configure in E-Boekhouden Settings"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def test_mutation_count():
    """Compare mutation counts between SOAP and what we expect"""
    from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    
    try:
        api = EBoekhoudenSOAPAPI()
        
        # Get mutations via SOAP
        result = api.get_mutations()
        
        if result["success"]:
            mutations = result.get("mutations", [])
            
            # Get mutation number range
            mutation_numbers = []
            for mut in mutations:
                nr = mut.get("MutatieNr")
                if nr:
                    try:
                        mutation_numbers.append(int(nr))
                    except:
                        pass
            
            if mutation_numbers:
                min_nr = min(mutation_numbers)
                max_nr = max(mutation_numbers)
                
                return {
                    "success": True,
                    "soap_count": len(mutations),
                    "min_mutation_nr": min_nr,
                    "max_mutation_nr": max_nr,
                    "range": max_nr - min_nr + 1,
                    "message": f"SOAP returns {len(mutations)} mutations (range: {min_nr} to {max_nr})"
                }
            else:
                return {
                    "success": True,
                    "soap_count": len(mutations),
                    "message": f"SOAP returns {len(mutations)} mutations (no numbers found)"
                }
        else:
            return result
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def simulate_hybrid_approach():
    """Simulate the hybrid approach without actually migrating"""
    from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    
    try:
        api = EBoekhoudenSOAPAPI()
        
        print("=== HYBRID MIGRATION SIMULATION ===\n")
        
        # Step 1: Get Chart of Accounts via SOAP
        print("1. Getting Chart of Accounts via SOAP...")
        coa_result = api.get_grootboekrekeningen()
        if coa_result["success"]:
            print(f"   ✓ Found {coa_result['count']} accounts")
        else:
            print(f"   ✗ Failed: {coa_result.get('error')}")
        
        # Step 2: Get Relations via SOAP
        print("\n2. Getting Relations via SOAP...")
        rel_result = api.get_relaties()
        if rel_result["success"]:
            print(f"   ✓ Found {rel_result['count']} relations")
        else:
            print(f"   ✗ Failed: {rel_result.get('error')}")
        
        # Step 3: Check mutations via SOAP (for comparison)
        print("\n3. Checking mutations via SOAP...")
        mut_result = api.get_mutations()
        if mut_result["success"]:
            print(f"   ✓ SOAP can access {mut_result['count']} mutations (last 500 only)")
        else:
            print(f"   ✗ Failed: {mut_result.get('error')}")
        
        # Step 4: REST API status
        print("\n4. REST API Status:")
        settings = frappe.get_single("E-Boekhouden Settings")
        api_token = settings.get_password('api_token') if hasattr(settings, 'api_token') else None
        if api_token:
            print(f"   ✓ API token configured")
            print("   → REST API would fetch ALL mutations (no 500 limit)")
            print("   → Expected: 7000+ mutations based on user requirements")
        else:
            print("   ✗ API token not configured")
            print("   → Please set API token in E-Boekhouden Settings")
        
        print("\n=== SUMMARY ===")
        print("SOAP API: Working for CoA and Relations")
        print(f"SOAP Mutations: Limited to last {mut_result.get('count', 0)} records")
        print(f"REST API: {'Ready (token configured)' if api_token else 'Not configured'}")
        print("\nNext step: Configure API token to enable REST mutation fetching")
        
        return {
            "success": True,
            "soap_working": coa_result["success"] and rel_result["success"],
            "accounts_count": coa_result.get("count", 0),
            "relations_count": rel_result.get("count", 0),
            "soap_mutations_count": mut_result.get("count", 0),
            "rest_configured": bool(api_token),
            "message": "Simulation complete - see console output for details"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

if __name__ == "__main__":
    print("Run with:")
    print("bench --site dev.veganisme.net execute verenigingen.utils.test_hybrid_migration.test_soap_connection")
    print("bench --site dev.veganisme.net execute verenigingen.utils.test_hybrid_migration.test_rest_api_token")
    print("bench --site dev.veganisme.net execute verenigingen.utils.test_hybrid_migration.test_mutation_count")
    print("bench --site dev.veganisme.net execute verenigingen.utils.test_hybrid_migration.simulate_hybrid_approach")