#!/usr/bin/env python3

import frappe

@frappe.whitelist()
def test_owl_theme_integration():
    """Test the complete Owl Theme integration"""
    results = {}
    
    try:
        # Test 1: Check Owl Theme detection
        from verenigingen.verenigingen.doctype.brand_settings.brand_settings import check_owl_theme_integration
        status = check_owl_theme_integration()
        results["owl_theme_detection"] = {
            "success": status.get("installed", False),
            "details": status
        }
        
        # Test 2: Test sync functionality
        from verenigingen.verenigingen.doctype.brand_settings.brand_settings import sync_brand_settings_to_owl_theme
        sync_result = sync_brand_settings_to_owl_theme()
        results["sync_functionality"] = {
            "success": sync_result.get("success", False),
            "message": sync_result.get("message", "Unknown error")
        }
        
        # Test 3: Verify sync actually changed Owl Theme Settings
        if sync_result.get("success"):
            owl_settings = frappe.get_single("Owl Theme Settings")
            brand_settings = frappe.get_all("Brand Settings", 
                filters={"is_active": 1}, 
                fields=["primary_color", "navbar_background_color"],
                limit=1)
            
            if brand_settings:
                brand_primary = brand_settings[0].get("primary_color")
                owl_navbar = getattr(owl_settings, 'navbar_background_color', None)
                
                results["sync_verification"] = {
                    "success": brand_primary == owl_navbar,
                    "brand_primary_color": brand_primary,
                    "owl_navbar_color": owl_navbar,
                    "colors_match": brand_primary == owl_navbar
                }
            else:
                results["sync_verification"] = {
                    "success": False,
                    "message": "No active brand settings found"
                }
        
        # Test 4: Test automatic sync trigger
        if results["owl_theme_detection"]["success"]:
            # Get a brand settings document and trigger save to test auto-sync
            brand_doc = frappe.get_all("Brand Settings", 
                filters={"is_active": 1}, 
                limit=1)
            
            if brand_doc:
                doc = frappe.get_doc("Brand Settings", brand_doc[0].name)
                try:
                    # Test the sync_to_owl_theme method directly
                    doc.sync_to_owl_theme()
                    results["auto_sync_trigger"] = {
                        "success": True,
                        "message": "Auto-sync method executed successfully"
                    }
                except Exception as e:
                    results["auto_sync_trigger"] = {
                        "success": False,
                        "error": str(e)
                    }
        
        # Overall test result
        all_tests_passed = all(
            test.get("success", False) 
            for test in results.values() 
            if isinstance(test, dict)
        )
        
        results["overall_success"] = all_tests_passed
        results["summary"] = {
            "owl_theme_installed": results["owl_theme_detection"]["success"],
            "sync_works": results["sync_functionality"]["success"],
            "colors_sync_correctly": results.get("sync_verification", {}).get("success", False),
            "auto_sync_works": results.get("auto_sync_trigger", {}).get("success", False)
        }
        
    except Exception as e:
        results["error"] = str(e)
        results["overall_success"] = False
    
    return results

if __name__ == "__main__":
    frappe.init(site='dev.veganisme.net')
    frappe.connect()
    result = test_owl_theme_integration()
    print(frappe.as_json(result, indent=2))
    frappe.destroy()