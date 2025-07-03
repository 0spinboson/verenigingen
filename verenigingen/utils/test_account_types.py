#!/usr/bin/env python
"""Test account type recommendations"""

import frappe

@frappe.whitelist()
def test_account_recommendations():
    """Test the get_account_type_recommendations function"""
    from verenigingen.verenigingen.doctype.e_boekhouden_migration.e_boekhouden_migration import get_account_type_recommendations
    
    # Get settings to find company
    settings = frappe.get_single("E-Boekhouden Settings")
    company = settings.default_company if settings else None
    
    if not company:
        return {"error": "No default company configured"}
    
    # Test the function
    result = get_account_type_recommendations(company, show_all=True)
    
    # Check if any accounts exist
    account_count = frappe.db.count("Account", {
        "company": company,
        "eboekhouden_grootboek_nummer": ["!=", ""]
    })
    
    return {
        "company": company,
        "function_result": result,
        "total_eboekhouden_accounts": account_count,
        "sample_accounts": frappe.db.get_all("Account", 
            filters={
                "company": company,
                "eboekhouden_grootboek_nummer": ["!=", ""]
            },
            fields=["name", "account_name", "eboekhouden_grootboek_nummer", "account_type"],
            limit=5
        )
    }


if __name__ == "__main__":
    print("Testing account recommendations...")
    result = test_account_recommendations()
    import json
    print(json.dumps(result, indent=2))