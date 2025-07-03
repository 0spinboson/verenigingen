import frappe

@frappe.whitelist()
def test_afschrijving_recommendations():
    """Test recommendations for afschrijving (depreciation) accounts"""
    frappe.set_user("Administrator")
    
    # Get afschrijving accounts
    accounts = frappe.db.sql("""
        SELECT 
            a.name,
            a.account_name,
            a.account_number,
            a.eboekhouden_grootboek_nummer,
            a.root_type,
            a.account_type,
            pg.account_number as parent_group_number
        FROM `tabAccount` a
        LEFT JOIN `tabAccount` pg ON a.parent_account = pg.name
        WHERE a.company = %s
        AND a.account_name LIKE %s
        ORDER BY a.root_type, a.account_number
    """, ("Ned Ver Vegan", "%afschrijving%"), as_dict=True)
    
    # Get recommendations
    from verenigingen.verenigingen.doctype.e_boekhouden_migration.e_boekhouden_migration import get_account_type_recommendations
    
    result = get_account_type_recommendations("Ned Ver Vegan", show_all=True)
    
    # Filter for afschrijving accounts
    afschrijving_recs = []
    if result.get("success") and result.get("recommendations"):
        for rec in result["recommendations"]:
            if "afschrijving" in rec.get("account_name", "").lower():
                afschrijving_recs.append({
                    "account": rec["account"],
                    "account_name": rec["account_name"],
                    "account_code": rec["account_code"],
                    "root_type": rec.get("root_type"),
                    "current_type": rec.get("current_type"),
                    "recommended_type": rec.get("recommended_type")
                })
    
    return {
        "accounts": accounts,
        "recommendations": afschrijving_recs
    }