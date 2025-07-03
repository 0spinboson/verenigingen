#!/usr/bin/env python
"""Test the fixed cleanup function"""

import frappe

@frappe.whitelist()
def test_cleanup_fixed():
    """Test the fixed cleanup_chart_of_accounts function"""
    
    # Get default company
    settings = frappe.get_single("E-Boekhouden Settings")
    company = settings.default_company if settings else None
    
    if not company:
        return {"error": "No default company configured"}
    
    # Check E-Boekhouden accounts before cleanup
    eb_accounts_before = frappe.db.sql("""
        SELECT 
            name, 
            account_name, 
            is_group,
            parent_account,
            lft,
            rgt,
            (rgt - lft - 1) / 2 as child_count
        FROM `tabAccount`
        WHERE company = %s
        AND eboekhouden_grootboek_nummer IS NOT NULL
        AND eboekhouden_grootboek_nummer != ''
        ORDER BY lft
        LIMIT 10
    """, company, as_dict=True)
    
    total_before = frappe.db.count("Account", {
        "company": company,
        "eboekhouden_grootboek_nummer": ["is", "set"]
    })
    
    print(f"Before cleanup: {total_before} E-Boekhouden accounts")
    print("\nSample accounts (ordered by hierarchy):")
    for acc in eb_accounts_before:
        indent = "  " * (len(str(acc.lft)) - 1)
        print(f"{indent}- {acc.account_name} (Group: {acc.is_group}, Children: {int(acc.child_count)})")
    
    # Test the cleanup
    from verenigingen.verenigingen.doctype.e_boekhouden_migration.e_boekhouden_migration import cleanup_chart_of_accounts
    
    print("\nRunning cleanup...")
    try:
        result = cleanup_chart_of_accounts(company)
        print(f"\nCleanup result: {result}")
    except Exception as e:
        print(f"\nCleanup failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}
    
    # Check what's left
    total_after = frappe.db.count("Account", {
        "company": company,
        "eboekhouden_grootboek_nummer": ["is", "set"]
    })
    
    print(f"\nAfter cleanup: {total_after} E-Boekhouden accounts remaining")
    
    return {
        "before": total_before,
        "after": total_after,
        "deleted": total_before - total_after,
        "cleanup_result": result
    }


if __name__ == "__main__":
    result = test_cleanup_fixed()
    print(f"\nFinal result: {result}")