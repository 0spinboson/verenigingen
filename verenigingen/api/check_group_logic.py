import frappe

@frappe.whitelist()
def check_group_logic():
    """Check if there's an issue with group number logic"""
    frappe.set_user("Administrator")
    
    # Get accounts starting with 02
    accounts = frappe.db.sql("""
        SELECT 
            a.name, 
            a.account_name, 
            a.account_number,
            a.eboekhouden_grootboek_nummer,
            a.parent_account,
            p.account_number as parent_group_number,
            p.name as parent_name
        FROM `tabAccount` a
        LEFT JOIN `tabAccount` p ON a.parent_account = p.name
        WHERE a.company = %s
        AND a.account_number LIKE '02%%'
        AND a.is_group = 0
        ORDER BY a.account_number
    """, "Ned Ver Vegan", as_dict=True)
    
    return accounts