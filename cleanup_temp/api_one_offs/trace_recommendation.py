import frappe

@frappe.whitelist()
def trace_recommendation_logic():
    """Trace through the recommendation logic for a specific account"""
    frappe.set_user("Administrator")
    
    # Get the problem account
    account = frappe.db.sql("""
        SELECT 
            a.name, a.account_name, a.eboekhouden_grootboek_nummer,
            a.account_type, a.is_group, a.parent_account, a.root_type,
            p.eboekhouden_grootboek_nummer as parent_group_number
        FROM `tabAccount` a
        LEFT JOIN `tabAccount` p ON a.parent_account = p.name
        WHERE a.company = %s
        AND a.account_number = '02401'
    """, "Ned Ver Vegan", as_dict=True)[0]
    
    account_code = account.eboekhouden_grootboek_nummer
    account_name = account.account_name.lower()
    
    trace = {
        "account": account,
        "account_name_lower": account_name,
        "checks": []
    }
    
    # Trace through the logic
    recommended_type = None
    
    if account.root_type in ["Asset", "Liability", "Equity"]:
        trace["checks"].append(f"Matched balance sheet: {account.root_type}")
        
        if "btw" in account_name or "vat" in account_name:
            trace["checks"].append("Would match: Tax (btw/vat)")
        
        elif account.root_type == "Asset":
            trace["checks"].append("Entered Asset section")
            
            if "bank" in account_name:
                trace["checks"].append(f"Checking 'bank' in '{account_name}': {'bank' in account_name}")
            if "triodos" in account_name:
                trace["checks"].append(f"Checking 'triodos' in '{account_name}': {'triodos' in account_name}")
                
            if "bank" in account_name or "triodos" in account_name or "abn" in account_name or "ing" in account_name:
                trace["checks"].append("Would match: Bank")
                recommended_type = "Bank"
            elif ("kas" in account_name and "bank" not in account_name) or account_code == "10000":
                trace["checks"].append("Would match: Cash")
            elif "mollie" in account_name or "paypal" in account_name:
                trace["checks"].append("Would match: Bank (payment processor)")
            elif "cum." in account_name.lower() and "afschrijving" in account_name:
                trace["checks"].append(f"Checking accumulated depreciation: cum.={'cum.' in account_name.lower()}, afschrijving={'afschrijving' in account_name}")
                recommended_type = "Accumulated Depreciation"
            elif account.parent_group_number == "001" or (account_code.startswith("0") and len(account_code) > 3):
                trace["checks"].append(f"Matched group 001 or code pattern: parent={account.parent_group_number}, code={account_code}")
                if "afschrijving" in account_name:
                    recommended_type = "Accumulated Depreciation"
                else:
                    recommended_type = "Fixed Asset"
    
    trace["final_recommendation"] = recommended_type
    
    return trace