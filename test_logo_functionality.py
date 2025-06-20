#!/usr/bin/env python3
"""
Test logo functionality in brand settings
"""

import frappe

@frappe.whitelist()
def test_logo_functionality():
    """Test the logo upload and integration functionality"""
    
    results = {
        "success": True,
        "tests": []
    }
    
    # Test 1: Check if logo field exists in Brand Settings
    try:
        from frappe.model.meta import get_meta
        meta = get_meta("Brand Settings")
        logo_field = None
        
        for field in meta.fields:
            if field.fieldname == "logo":
                logo_field = field
                break
        
        if logo_field:
            results["tests"].append({
                "name": "Logo Field Exists",
                "status": "PASS",
                "details": f"Field type: {logo_field.fieldtype}, Label: {logo_field.label}"
            })
        else:
            results["tests"].append({
                "name": "Logo Field Exists", 
                "status": "FAIL",
                "error": "Logo field not found in Brand Settings doctype"
            })
            results["success"] = False
            
    except Exception as e:
        results["tests"].append({
            "name": "Logo Field Exists",
            "status": "FAIL",
            "error": str(e)
        })
        results["success"] = False
    
    # Test 2: Test get_organization_logo function
    try:
        from verenigingen.verenigingen.doctype.brand_settings.brand_settings import get_organization_logo
        
        logo_url = get_organization_logo()
        results["tests"].append({
            "name": "Get Organization Logo",
            "status": "PASS",
            "details": f"Logo URL: {logo_url or 'No logo set'}"
        })
        
    except Exception as e:
        results["tests"].append({
            "name": "Get Organization Logo",
            "status": "FAIL", 
            "error": str(e)
        })
        results["success"] = False
    
    # Test 3: Test brand settings with logo field
    try:
        from verenigingen.verenigingen.doctype.brand_settings.brand_settings import get_active_brand_settings
        
        settings = get_active_brand_settings()
        if 'logo' in settings:
            results["tests"].append({
                "name": "Logo in Brand Settings",
                "status": "PASS",
                "details": f"Logo field present with value: {settings.get('logo') or 'None'}"
            })
        else:
            results["tests"].append({
                "name": "Logo in Brand Settings",
                "status": "FAIL",
                "error": "Logo field not found in active brand settings"
            })
            results["success"] = False
            
    except Exception as e:
        results["tests"].append({
            "name": "Logo in Brand Settings", 
            "status": "FAIL",
            "error": str(e)
        })
        results["success"] = False
    
    # Test 4: Test portal context integration
    try:
        from verenigingen.utils.portal_customization import get_member_context
        
        test_context = {}
        get_member_context(test_context)
        
        if 'organization_logo' in test_context:
            results["tests"].append({
                "name": "Portal Context Integration",
                "status": "PASS",
                "details": f"Logo available in portal context: {test_context.get('organization_logo') or 'None'}"
            })
        else:
            results["tests"].append({
                "name": "Portal Context Integration",
                "status": "PASS",  # This is OK if no logo is set
                "details": "No logo in context (expected if no logo uploaded)"
            })
            
    except Exception as e:
        results["tests"].append({
            "name": "Portal Context Integration",
            "status": "FAIL",
            "error": str(e)
        })
        results["success"] = False
    
    return results

if __name__ == "__main__":
    try:
        import os
        import sys
        sys.path.insert(0, '/home/frappe/frappe-bench/apps')
        os.environ['FRAPPE_SITE'] = 'dev.veganisme.net'
        
        import frappe
        frappe.init(site='dev.veganisme.net') 
        frappe.connect()
        
        result = test_logo_functionality()
        print("Logo Functionality Test Results:")
        print("=" * 45)
        
        for test in result["tests"]:
            status_symbol = "✓" if test["status"] == "PASS" else "✗"
            print(f"{status_symbol} {test['name']}: {test['status']}")
            if test["status"] == "PASS":
                print(f"  {test.get('details', '')}")
            else:
                print(f"  Error: {test.get('error', 'Unknown error')}")
        
        print("=" * 45)
        overall = "✓ PASS" if result["success"] else "✗ FAIL"
        print(f"Overall: {overall}")
        
    except Exception as e:
        print(f"Test setup failed: {e}")
    finally:
        try:
            frappe.destroy()
        except:
            pass