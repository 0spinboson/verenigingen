import frappe

@frappe.whitelist()
def check_groups():
    """Check what's in groups 004 and 006"""
    frappe.set_user("Administrator")
    
    # Get accounts in group 004
    print("=== Group 004 Accounts ===")
    group_004 = frappe.db.sql("""
        SELECT a.account_name, a.eboekhouden_grootboek_nummer
        FROM `tabAccount` a
        JOIN `tabAccount` p ON a.parent_account = p.name
        WHERE p.eboekhouden_grootboek_nummer = '004'
        AND a.company = 'Ned Ver Vegan'
        AND a.is_group = 0
        ORDER BY a.account_name
    """, as_dict=True)
    
    for acc in group_004:
        print(f"  {acc.eboekhouden_grootboek_nummer}: {acc.account_name}")
    
    # Get accounts in group 006
    print("\n=== Group 006 Accounts ===")
    group_006 = frappe.db.sql("""
        SELECT a.account_name, a.eboekhouden_grootboek_nummer
        FROM `tabAccount` a
        JOIN `tabAccount` p ON a.parent_account = p.name
        WHERE p.eboekhouden_grootboek_nummer = '006'
        AND a.company = 'Ned Ver Vegan'
        AND a.is_group = 0
        ORDER BY a.account_name
    """, as_dict=True)
    
    for acc in group_006:
        print(f"  {acc.eboekhouden_grootboek_nummer}: {acc.account_name}")
    
    return {"success": True}