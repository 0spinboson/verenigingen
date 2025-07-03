#!/usr/bin/env python
"""
Script to fix orphaned cost centers in the database
Run this to clean up any cost centers with missing parent references
"""

import frappe

def fix_all_orphaned_cost_centers():
    """
    Fix all orphaned cost centers across all companies
    """
    frappe.init(site='verenigingen')
    frappe.connect()
    
    try:
        # Get all companies
        companies = frappe.get_all("Company", pluck="name")
        
        total_fixed = 0
        all_errors = []
        
        for company in companies:
            print(f"\nProcessing company: {company}")
            
            # Import the cleanup function
            from verenigingen.utils.eboekhouden_cost_center_fix import cleanup_cost_centers
            
            result = cleanup_cost_centers(company)
            
            if result["success"]:
                print(f"  Fixed {result['fixed']} orphaned cost centers")
                total_fixed += result["fixed"]
                
                if result.get("errors"):
                    all_errors.extend([f"{company}: {e}" for e in result["errors"]])
            else:
                print(f"  Error: {result.get('error')}")
                all_errors.append(f"{company}: {result.get('error')}")
        
        print(f"\n\nTotal fixed: {total_fixed} cost centers")
        
        if all_errors:
            print("\nErrors encountered:")
            for error in all_errors:
                print(f"  - {error}")
        
        frappe.db.commit()
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        frappe.destroy()

if __name__ == "__main__":
    fix_all_orphaned_cost_centers()