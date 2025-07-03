#!/usr/bin/env python
"""Test cleanup with delete_all_accounts option"""

import frappe

@frappe.whitelist()
def test_cleanup_all():
    """Test the cleanup function with delete_all_accounts option"""
    
    # Get default company
    settings = frappe.get_single("E-Boekhouden Settings")
    company = settings.default_company if settings else None
    
    if not company:
        return {"error": "No default company configured"}
    
    results = {}
    
    # 1. Test E-Boekhouden only cleanup
    print("Testing E-Boekhouden only cleanup...")
    eb_accounts_before = frappe.db.count("Account", {
        "company": company,
        "eboekhouden_grootboek_nummer": ["is", "set"]
    })
    
    from verenigingen.verenigingen.doctype.e_boekhouden_migration.e_boekhouden_migration import cleanup_chart_of_accounts
    
    eb_result = cleanup_chart_of_accounts(company, delete_all_accounts=False)
    results["eb_cleanup"] = {
        "before": eb_accounts_before,
        "result": eb_result
    }
    
    # 2. Check total accounts
    total_accounts = frappe.db.sql("""
        SELECT COUNT(*) as count
        FROM `tabAccount`
        WHERE company = %s
        AND root_type IS NOT NULL
    """, company, as_dict=True)[0]['count']
    
    print(f"\nTotal accounts in company: {total_accounts}")
    
    # 3. Show sample of non-E-Boekhouden accounts
    non_eb_accounts = frappe.db.sql("""
        SELECT name, account_name, is_group, parent_account
        FROM `tabAccount`
        WHERE company = %s
        AND (eboekhouden_grootboek_nummer IS NULL OR eboekhouden_grootboek_nummer = '')
        AND root_type IS NOT NULL
        ORDER BY lft
        LIMIT 10
    """, company, as_dict=True)
    
    print("\nSample non-E-Boekhouden accounts:")
    for acc in non_eb_accounts:
        print(f"  - {acc.account_name} (Group: {acc.is_group})")
    
    results["total_accounts"] = total_accounts
    results["sample_non_eb"] = non_eb_accounts
    
    # 4. Test delete_all_accounts (commented out for safety)
    # WARNING: This would delete ALL accounts!
    # Uncomment only if you really want to test this
    # all_result = cleanup_chart_of_accounts(company, delete_all_accounts=True)
    # results["all_cleanup"] = all_result
    
    return results


@frappe.whitelist()
def test_delete_all_dry_run():
    """Dry run to see what would be deleted with delete_all_accounts=True"""
    
    settings = frappe.get_single("E-Boekhouden Settings")
    company = settings.default_company if settings else None
    
    if not company:
        return {"error": "No default company configured"}
    
    # Get ALL accounts that would be deleted
    all_accounts = frappe.db.sql("""
        SELECT 
            name, 
            account_name,
            is_group,
            account_type,
            root_type,
            (SELECT COUNT(*) FROM `tabGL Entry` WHERE account = a.name) as gl_entries
        FROM `tabAccount` a
        WHERE company = %s
        AND root_type IS NOT NULL
        ORDER BY lft DESC
    """, company, as_dict=True)
    
    # Categorize accounts
    deletable = []
    protected = []
    
    for acc in all_accounts:
        if acc.gl_entries > 0:
            protected.append({
                "name": acc.account_name,
                "reason": f"Has {acc.gl_entries} GL entries"
            })
        else:
            deletable.append(acc.account_name)
    
    return {
        "total_accounts": len(all_accounts),
        "deletable_count": len(deletable),
        "protected_count": len(protected),
        "sample_deletable": deletable[:10],
        "sample_protected": protected[:10]
    }


if __name__ == "__main__":
    result = test_cleanup_all()
    print(f"\nResult: {result}")