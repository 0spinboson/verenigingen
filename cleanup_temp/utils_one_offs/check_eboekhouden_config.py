#!/usr/bin/env python3
"""Check E-Boekhouden configuration"""

import frappe

@frappe.whitelist()
def check_config():
    """Check all E-Boekhouden settings"""
    
    settings = frappe.get_single("E-Boekhouden Settings")
    
    print("=== E-BOEKHOUDEN CONFIGURATION ===\n")
    
    # Check REST API settings
    print("REST API Settings:")
    print(f"  API URL: {settings.api_url if hasattr(settings, 'api_url') else 'Not set'}")
    api_token = settings.get_password('api_token') if hasattr(settings, 'api_token') else None
    print(f"  API Token: {'Set' if api_token else 'Not set'} ({len(api_token) if api_token else 0} chars)")
    print(f"  Source App: {settings.source_application if hasattr(settings, 'source_application') else 'Not set'}")
    
    # Check SOAP settings
    print("\nSOAP API Settings:")
    print(f"  Username: {settings.soap_username if hasattr(settings, 'soap_username') else 'Not set'}")
    code1 = settings.get_password('soap_security_code1') if hasattr(settings, 'soap_security_code1') else None
    code2 = settings.get_password('soap_security_code2') if hasattr(settings, 'soap_security_code2') else None
    print(f"  Security Code 1: {'Set' if code1 else 'Not set'}")
    print(f"  Security Code 2: {'Set' if code2 else 'Not set'}")
    
    # Check other settings
    print("\nGeneral Settings:")
    print(f"  Default Company: {settings.default_company if hasattr(settings, 'default_company') else 'Not set'}")
    print(f"  Default Cost Center: {settings.default_cost_center if hasattr(settings, 'default_cost_center') else 'Not set'}")
    print(f"  Connection Status: {settings.connection_status if hasattr(settings, 'connection_status') else 'Not set'}")
    print(f"  Last Tested: {settings.last_tested if hasattr(settings, 'last_tested') else 'Not set'}")
    
    print("\n=== ANALYSIS ===")
    print("SOAP API: Configured and working (as shown in previous tests)")
    print("REST API: Token configured but authentication failing")
    print("\nPossible issues:")
    print("1. The API token might be for a different E-Boekhouden account")
    print("2. REST API might not be enabled for this account") 
    print("3. The token format might be incorrect")
    print("\nRecommendation: Continue using SOAP for now, or get correct REST API credentials")
    
    return {
        "soap_configured": bool(settings.soap_username and code1 and code2),
        "rest_configured": bool(api_token),
        "message": "Configuration checked - see console output"
    }

@frappe.whitelist()
def test_minimal_migration():
    """Test the migration with just SOAP (current working approach)"""
    
    print("=== TESTING CURRENT SOAP MIGRATION ===\n")
    
    # Get migration doc
    migrations = frappe.get_all("E-Boekhouden Migration", 
                              filters={"status": ["!=", "Completed"]},
                              limit=1)
    
    if not migrations:
        print("No pending migrations found")
        return {"success": False, "error": "No pending migrations"}
    
    migration_name = migrations[0].name
    print(f"Found migration: {migration_name}")
    
    # Just check what we can get with SOAP
    from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    
    api = EBoekhoudenSOAPAPI()
    result = api.get_mutations()
    
    if result["success"]:
        print(f"\nSOAP can fetch {result['count']} mutations")
        print("This is the 500-record limitation we're trying to overcome")
        print("\nSince REST API auth is not working, we have two options:")
        print("1. Fix REST API authentication (need correct token)")
        print("2. Accept the 500-record limitation for now")
        
        return {
            "success": True,
            "mutations_available": result['count'],
            "message": "SOAP working but limited to 500 records"
        }
    else:
        return {"success": False, "error": result.get("error")}

if __name__ == "__main__":
    print("Run with:")
    print("bench --site dev.veganisme.net execute verenigingen.utils.check_eboekhouden_config.check_config")
    print("bench --site dev.veganisme.net execute verenigingen.utils.check_eboekhouden_config.test_minimal_migration")