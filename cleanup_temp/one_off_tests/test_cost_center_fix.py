#!/usr/bin/env python3
"""
Test script for cost center migration fix
Run with: cd /home/frappe/frappe-bench && python apps/verenigingen/test_cost_center_fix.py
"""

import sys
import os
sys.path.append(os.path.abspath('.'))

import frappe

def test_cost_center_fix():
    """Test the cost center migration fix"""
    # Initialize Frappe
    frappe.init(site='verenigingen')
    frappe.connect()
    
    try:
        # Get settings
        settings = frappe.get_single("E-Boekhouden Settings")
        if not settings.default_company:
            print("ERROR: No default company set in E-Boekhouden Settings")
            return
        
        print(f"Testing cost center fix for company: {settings.default_company}")
        
        # Import the fix functions
        from verenigingen.utils.eboekhouden_cost_center_fix import (
            ensure_root_cost_center,
            cleanup_cost_centers
        )
        
        # 1. Test root cost center creation
        print("\n1. Testing root cost center creation...")
        root_cc = ensure_root_cost_center(settings.default_company)
        if root_cc:
            print(f"   ✓ Root cost center: {root_cc}")
            
            # Check if it's valid
            cc_doc = frappe.get_doc("Cost Center", root_cc)
            print(f"   - Name: {cc_doc.cost_center_name}")
            print(f"   - Company: {cc_doc.company}")
            print(f"   - Is Group: {cc_doc.is_group}")
            print(f"   - Parent: '{cc_doc.parent_cost_center}'")
            
            # Verify it passes validation
            if cc_doc.cost_center_name == cc_doc.company:
                print("   ✓ Root validation: PASS (name equals company)")
            else:
                print("   ✗ Root validation: FAIL (name does not equal company)")
        else:
            print("   ✗ Failed to create/find root cost center")
        
        # 2. Test cleanup function
        print("\n2. Testing cleanup of orphaned cost centers...")
        cleanup_result = cleanup_cost_centers(settings.default_company)
        if cleanup_result["success"]:
            print(f"   ✓ Cleanup successful")
            print(f"   - Fixed: {cleanup_result['fixed']} cost centers")
            if cleanup_result.get("errors"):
                print(f"   - Errors: {len(cleanup_result['errors'])}")
                for err in cleanup_result["errors"][:3]:
                    print(f"     • {err}")
        else:
            print(f"   ✗ Cleanup failed: {cleanup_result.get('error')}")
        
        # 3. Check current cost center status
        print("\n3. Current cost center status:")
        
        # Count total cost centers
        total_ccs = frappe.db.count("Cost Center", {"company": settings.default_company})
        print(f"   - Total cost centers: {total_ccs}")
        
        # Count orphaned cost centers
        orphaned = frappe.db.count("Cost Center", {
            "company": settings.default_company,
            "parent_cost_center": ["in", ["", None]],
            "name": ["!=", root_cc] if root_cc else None
        })
        print(f"   - Orphaned cost centers: {orphaned}")
        
        # List first few orphaned ones
        if orphaned > 0:
            orphaned_list = frappe.db.get_all("Cost Center", 
                filters={
                    "company": settings.default_company,
                    "parent_cost_center": ["in", ["", None]],
                    "name": ["!=", root_cc] if root_cc else None
                },
                fields=["name", "cost_center_name"],
                limit=5
            )
            print("   - Examples of orphaned:")
            for cc in orphaned_list:
                print(f"     • {cc.name} ({cc.cost_center_name})")
        
        print("\n✓ Test completed")
        
    except Exception as e:
        print(f"\n✗ Error during test: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        frappe.destroy()

if __name__ == "__main__":
    test_cost_center_fix()