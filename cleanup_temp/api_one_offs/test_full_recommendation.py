import frappe

@frappe.whitelist()  
def test_full_recommendation():
    """Test the full recommendation function to see what's happening"""
    frappe.set_user("Administrator")
    
    # Call the actual function but limit to just our test account
    from verenigingen.verenigingen.doctype.e_boekhouden_migration.e_boekhouden_migration import get_account_type_recommendations
    
    # First get all recommendations
    result = get_account_type_recommendations("Ned Ver Vegan", show_all=True)
    
    # Find our specific account
    target_recs = []
    if result.get("success") and result.get("recommendations"):
        for rec in result["recommendations"]:
            if rec.get("account_code") in ["02401", "02501"]:
                target_recs.append(rec)
    
    # Also manually check what the query returns
    manual_check = frappe.db.sql("""
        SELECT 
            a.name, a.account_name, a.eboekhouden_grootboek_nummer,
            a.account_type, a.is_group, a.parent_account, a.root_type,
            p.eboekhouden_grootboek_nummer as parent_group_number
        FROM `tabAccount` a
        LEFT JOIN `tabAccount` p ON a.parent_account = p.name
        WHERE a.company = %s
        AND a.eboekhouden_grootboek_nummer IN ('02401', '02501')
    """, "Ned Ver Vegan", as_dict=True)
    
    return {
        "recommendations": target_recs,
        "manual_query": manual_check
    }