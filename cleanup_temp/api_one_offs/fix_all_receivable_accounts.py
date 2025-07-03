import frappe
from frappe import _

@frappe.whitelist()
def identify_and_fix_receivable_accounts():
    """Identify all accounts used as receivable in E-Boekhouden and fix their types"""
    
    from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenSOAPAPI(settings)
    company = settings.default_company
    
    # Get mutations to identify receivable accounts
    result = api.get_mutations(date_from="2025-01-01", date_to="2025-12-31")
    
    if not result["success"]:
        return {"error": result.get("error")}
    
    # Collect all unique account codes used for receivables
    receivable_accounts = set()
    
    for mut in result["mutations"]:
        if mut.get("Soort") == "FactuurVerstuurd":
            # Sales invoices use Rekening field as receivable account
            account_code = mut.get("Rekening")
            if account_code:
                receivable_accounts.add(account_code)
    
    # Now fix each account
    fixed_accounts = []
    errors = []
    
    for account_code in receivable_accounts:
        try:
            # Find the account by code
            account = frappe.db.get_value("Account", {
                "account_number": account_code,
                "company": company
            }, ["name", "account_type"], as_dict=True)
            
            if account:
                if account.account_type != "Receivable":
                    # Update to Receivable type
                    frappe.db.set_value("Account", account.name, "account_type", "Receivable")
                    fixed_accounts.append({
                        "account": account.name,
                        "code": account_code,
                        "old_type": account.account_type,
                        "new_type": "Receivable"
                    })
                else:
                    fixed_accounts.append({
                        "account": account.name,
                        "code": account_code,
                        "status": "Already Receivable"
                    })
            else:
                # Account doesn't exist by code, try by name pattern
                account_name = frappe.db.get_value("Account", {
                    "name": ["like", f"{account_code}%"],
                    "company": company
                }, ["name", "account_type"], as_dict=True)
                
                if account_name:
                    if account_name.account_type != "Receivable":
                        frappe.db.set_value("Account", account_name.name, "account_type", "Receivable")
                        fixed_accounts.append({
                            "account": account_name.name,
                            "code": account_code,
                            "old_type": account_name.account_type,
                            "new_type": "Receivable"
                        })
                else:
                    errors.append(f"Account with code {account_code} not found")
                    
        except Exception as e:
            errors.append(f"Error processing account {account_code}: {str(e)}")
    
    frappe.db.commit()
    
    return {
        "success": True,
        "receivable_account_codes": list(receivable_accounts),
        "fixed_accounts": fixed_accounts,
        "errors": errors,
        "total_identified": len(receivable_accounts),
        "total_fixed": len([a for a in fixed_accounts if a.get("old_type")])
    }

@frappe.whitelist()
def check_account_mappings():
    """Check how E-Boekhouden account codes map to ERPNext accounts"""
    
    from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenSOAPAPI(settings)
    company = settings.default_company
    
    # Get some sample mutations
    result = api.get_mutations(date_from="2025-05-01", date_to="2025-05-31")
    
    if not result["success"]:
        return {"error": result.get("error")}
    
    # Collect account mappings
    account_usage = {}
    
    for mut in result["mutations"]:
        if mut.get("Soort") == "FactuurVerstuurd":
            account_code = mut.get("Rekening")
            if account_code:
                if account_code not in account_usage:
                    account_usage[account_code] = {
                        "code": account_code,
                        "usage": "Receivable (Sales Invoice)",
                        "count": 0,
                        "erpnext_account": None
                    }
                account_usage[account_code]["count"] += 1
                
                # Find ERPNext account
                if not account_usage[account_code]["erpnext_account"]:
                    # Try by account number
                    account = frappe.db.get_value("Account", {
                        "account_number": account_code,
                        "company": company
                    }, ["name", "account_type"], as_dict=True)
                    
                    if not account:
                        # Try by name pattern
                        account = frappe.db.get_value("Account", {
                            "name": ["like", f"{account_code}%"],
                            "company": company
                        }, ["name", "account_type"], as_dict=True)
                    
                    if account:
                        account_usage[account_code]["erpnext_account"] = account.name
                        account_usage[account_code]["current_type"] = account.account_type
    
    return {
        "account_usage": account_usage,
        "total_accounts": len(account_usage)
    }