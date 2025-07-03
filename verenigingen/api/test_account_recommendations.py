import frappe

@frappe.whitelist()
def test_recommendations():
    """Test the updated recommendation logic"""
    frappe.set_user("Administrator")
    
    print("=== Testing Account Type Recommendations ===\n")
    
    # Get some P/L accounts to check
    pl_accounts = frappe.db.sql("""
        SELECT 
            a.name, a.account_name, a.eboekhouden_grootboek_nummer,
            a.root_type, a.parent_account,
            p.eboekhouden_grootboek_nummer as parent_group_number
        FROM `tabAccount` a
        LEFT JOIN `tabAccount` p ON a.parent_account = p.name
        WHERE a.company = 'Ned Ver Vegan'
        AND a.root_type IN ('Income', 'Expense')
        AND a.is_group = 0
        ORDER BY a.eboekhouden_grootboek_nummer
        LIMIT 20
    """, as_dict=True)
    
    print(f"Found {len(pl_accounts)} P/L accounts\n")
    
    group_055_count = 0
    other_pl_count = 0
    
    for acc in pl_accounts:
        if acc.parent_group_number == "055":
            group_055_count += 1
            print(f"Group 055 child: {acc.eboekhouden_grootboek_nummer} - {acc.account_name}")
        else:
            other_pl_count += 1
            if other_pl_count <= 5:  # Show first 5
                print(f"Other P/L account: {acc.eboekhouden_grootboek_nummer} - {acc.account_name} (parent: {acc.parent_group_number})")
    
    print(f"\n=== Summary ===")
    print(f"Accounts under group 055: {group_055_count} (should be Income)")
    print(f"Other P/L accounts: {other_pl_count} (should be Expense)")
    
    # Now test the actual recommendations
    from verenigingen.verenigingen.doctype.e_boekhouden_migration.e_boekhouden_migration import get_account_type_recommendations
    
    result = get_account_type_recommendations("Ned Ver Vegan", show_all=True)
    
    if result["success"]:
        recommendations = result["recommendations"]
        
        # Check recommendations for P/L accounts
        income_recommendations = 0
        expense_recommendations = 0
        
        for rec in recommendations:
            if rec["recommended_type"] == "Income Account":
                income_recommendations += 1
            elif rec["recommended_type"] == "Expense Account":
                expense_recommendations += 1
        
        print(f"\n=== Recommendation Results ===")
        print(f"Total recommendations: {len(recommendations)}")
        print(f"Income Account recommendations: {income_recommendations}")
        print(f"Expense Account recommendations: {expense_recommendations}")
        
        # Show some examples
        print("\n=== Example Recommendations ===")
        for rec in recommendations[:10]:
            if rec["recommended_type"] in ["Income Account", "Expense Account"]:
                print(f"{rec['account_code']}: {rec['account_name']} -> {rec['recommended_type']}")
    
    return {"success": True}