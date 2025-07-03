import frappe

@frappe.whitelist()
def debug_cum_afschrijving():
    """Debug why Cum. Afschrijving accounts aren't matching"""
    frappe.set_user("Administrator")
    
    # Get one of the problem accounts
    account = frappe.db.get_value("Account", {
        "company": "Ned Ver Vegan",
        "account_number": "02401"
    }, ["name", "account_name", "root_type", "parent_account", "eboekhouden_grootboek_nummer"], as_dict=True)
    
    if account:
        # Get parent info
        parent = frappe.db.get_value("Account", account.parent_account, ["account_number", "name"])
        
        account_name = account.account_name.lower()
        
        checks = {
            "account_name": account.account_name,
            "account_name_lower": account_name,
            "has_cum": "cum." in account_name,
            "has_afschrijving": "afschrijving" in account_name,
            "parent_info": parent,
            "starts_with_02": account.eboekhouden_grootboek_nummer.startswith("02") if account.eboekhouden_grootboek_nummer else False
        }
        
        return checks
    
    return {"error": "Account not found"}