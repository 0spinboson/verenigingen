"""
Test brand management functionality
"""

import frappe
from verenigingen.verenigingen.doctype.brand_settings.brand_settings import get_active_brand_settings, generate_brand_css

@frappe.whitelist()
def test_brand_management():
    """Test the brand management system functionality"""
    
    results = {
        "success": True,
        "tests": []
    }
    
    # Test 1: Get active brand settings
    try:
        settings = get_active_brand_settings()
        results["tests"].append({
            "name": "Active Brand Settings",
            "status": "PASS",
            "details": f"Primary: {settings.get('primary_color')}, Secondary: {settings.get('secondary_color')}"
        })
    except Exception as e:
        results["tests"].append({
            "name": "Active Brand Settings",
            "status": "FAIL",
            "error": str(e)
        })
        results["success"] = False
    
    # Test 2: Generate brand CSS
    try:
        css = generate_brand_css()
        if css and len(css) > 100:
            results["tests"].append({
                "name": "Brand CSS Generation",
                "status": "PASS",
                "details": f"Generated {len(css)} characters of CSS"
            })
        else:
            results["tests"].append({
                "name": "Brand CSS Generation",
                "status": "FAIL",
                "error": "CSS generation returned empty or invalid result"
            })
            results["success"] = False
    except Exception as e:
        results["tests"].append({
            "name": "Brand CSS Generation",
            "status": "FAIL",
            "error": str(e)
        })
        results["success"] = False
    
    # Test 3: Check Brand Settings doctype
    try:
        doctype_exists = frappe.db.exists("DocType", "Brand Settings")
        if doctype_exists:
            settings_count = frappe.db.count("Brand Settings")
            results["tests"].append({
                "name": "Brand Settings Doctype",
                "status": "PASS",
                "details": f"Doctype exists with {settings_count} records"
            })
        else:
            results["tests"].append({
                "name": "Brand Settings Doctype",
                "status": "FAIL",
                "error": "Brand Settings doctype does not exist"
            })
            results["success"] = False
    except Exception as e:
        results["tests"].append({
            "name": "Brand Settings Doctype",
            "status": "FAIL",
            "error": str(e)
        })
        results["success"] = False
    
    return results