import frappe
from frappe import _

@frappe.whitelist()
def test_account_type_fixes():
    """Test the account type fixing logic"""
    
    from verenigingen.utils.eboekhouden_soap_migration import fix_account_types_for_migration
    
    company = frappe.db.get_value("E-Boekhouden Settings", None, "default_company")
    
    # Get current state
    before_state = get_account_states(company)
    
    # Run the fix
    fix_account_types_for_migration(company)
    
    # Get after state
    after_state = get_account_states(company)
    
    # Find changes
    changes = []
    for code, before in before_state.items():
        after = after_state.get(code)
        if after and before["account_type"] != after["account_type"]:
            changes.append({
                "account": before["name"],
                "code": code,
                "before": before["account_type"],
                "after": after["account_type"]
            })
    
    return {
        "company": company,
        "changes": changes,
        "total_changes": len(changes),
        "receivable_accounts": [a for a in after_state.values() if a["account_type"] == "Receivable"],
        "payable_accounts": [a for a in after_state.values() if a["account_type"] == "Payable"]
    }

def get_account_states(company):
    """Get current state of all accounts with numbers"""
    accounts = frappe.db.get_all("Account", {
        "company": company,
        "is_group": 0,
        "account_number": ["is", "set"]
    }, ["name", "account_number", "account_type"])
    
    return {acc["account_number"]: acc for acc in accounts if acc["account_number"]}

@frappe.whitelist()
def test_single_invoice_with_fix():
    """Test importing a single invoice with the new account type fix"""
    
    from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    from verenigingen.utils.eboekhouden_soap_migration import parse_date, get_or_create_customer, get_or_create_item, get_account_by_code
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenSOAPAPI(settings)
    company = settings.default_company
    
    # Get cost center
    cost_center = frappe.db.get_value("Cost Center", {
        "company": company,
        "cost_center_name": "Main",
        "is_group": 0
    }, "name")
    
    result = api.get_mutations(date_from="2025-05-01", date_to="2025-05-31")
    
    if not result["success"]:
        return {"error": result.get("error")}
    
    # Find a FactuurVerstuurd mutation
    for mut in result["mutations"]:
        if mut.get("Soort") == "FactuurVerstuurd":
            invoice_no = mut.get("Factuurnummer")
            
            # Skip if already imported
            if frappe.db.exists("Sales Invoice", {"eboekhouden_invoice_number": invoice_no}):
                continue
            
            # Check the account that would be used
            rekening_code = mut.get("Rekening")
            account_info = None
            
            if rekening_code:
                account = get_account_by_code(rekening_code, company)
                if account:
                    account_type = frappe.db.get_value("Account", account, "account_type")
                    account_info = {
                        "code": rekening_code,
                        "account": account,
                        "type_before": account_type,
                        "will_be_fixed": account_type != "Receivable"
                    }
            
            return {
                "invoice_no": invoice_no,
                "rekening_code": rekening_code,
                "account_info": account_info,
                "mutation": mut
            }
    
    return {"error": "No unimported invoices found"}