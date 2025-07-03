import frappe

@frappe.whitelist()
def analyze_group_names():
    """Get the original E-boekhouden group names"""
    frappe.set_user("Administrator")
    
    # Get the E-boekhouden data
    from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenAPI(settings)
    
    result = api.get_chart_of_accounts()
    if not result["success"]:
        print(f"Failed to fetch accounts: {result['error']}")
        return
    
    import json
    accounts_data = json.loads(result["data"])
    accounts = accounts_data.get("items", [])
    
    # Find unique groups and their descriptions
    groups = {}
    for acc in accounts:
        group_code = acc.get('group', '')
        if group_code and group_code not in groups:
            # Find the description for this group from accounts that have it
            for check_acc in accounts:
                if check_acc.get('code') == group_code:
                    groups[group_code] = check_acc.get('description', '')
                    break
    
    print("=== E-boekhouden Group Names ===")
    for code in sorted(groups.keys()):
        print(f"Group {code}: {groups.get(code, 'Unknown')}")
    
    # Specifically check 004 and 006
    print("\n=== Specific Groups ===")
    for acc in accounts:
        if acc.get('code') in ['004', '006']:
            print(f"Group {acc['code']}: {acc.get('description', '')}")
    
    return {"success": True}