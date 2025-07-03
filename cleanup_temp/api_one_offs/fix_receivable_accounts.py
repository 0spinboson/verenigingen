import frappe
from frappe import _

@frappe.whitelist() 
def fix_receivable_accounts():
    """Fix account types for E-Boekhouden migration"""
    
    company = frappe.db.get_single_value("E-Boekhouden Settings", "default_company")
    if not company:
        return {"success": False, "error": "No default company set"}
    
    # Accounts that should be Receivable
    receivable_accounts = [
        "13500",  # Te ontvangen contributies
        "13510",  # Te ontvangen donaties  
        "13600",  # Vooruitbetaalde kosten
        "13900",  # Te ontvangen bedragen
        "13990",  # Overige vorderingen
    ]
    
    # Accounts that should be Payable
    payable_accounts = [
        "19290",  # Te betalen bedragen
        "19291",  # Te betalen kosten
        "44000",  # Vooruitontvangen bedragen
        "44900",  # Overige schulden
    ]
    
    fixed = []
    errors = []
    
    # Fix Receivable accounts
    for acc_num in receivable_accounts:
        account = frappe.db.get_value("Account", {
            "company": company,
            "account_number": acc_num
        }, ["name", "account_type"], as_dict=True)
        
        if account:
            if account.account_type != "Receivable":
                try:
                    frappe.db.set_value("Account", account.name, "account_type", "Receivable")
                    fixed.append(f"{account.name}: {account.account_type} → Receivable")
                except Exception as e:
                    errors.append(f"{account.name}: {str(e)}")
            else:
                fixed.append(f"{account.name}: Already Receivable")
    
    # Fix Payable accounts
    for acc_num in payable_accounts:
        account = frappe.db.get_value("Account", {
            "company": company,
            "account_number": acc_num
        }, ["name", "account_type"], as_dict=True)
        
        if account:
            if account.account_type != "Payable":
                try:
                    frappe.db.set_value("Account", account.name, "account_type", "Payable")
                    fixed.append(f"{account.name}: {account.account_type} → Payable")
                except Exception as e:
                    errors.append(f"{account.name}: {str(e)}")
            else:
                fixed.append(f"{account.name}: Already Payable")
    
    frappe.db.commit()
    
    # Also fix the default receivable account in Sales Invoice
    default_receivable = frappe.db.get_value("Account", {
        "company": company,
        "account_type": "Receivable",
        "account_number": "13500"
    }, "name")
    
    if default_receivable:
        # Update company default receivable account
        frappe.db.set_value("Company", company, "default_receivable_account", default_receivable)
        frappe.db.commit()
    
    return {
        "success": True,
        "fixed": fixed,
        "errors": errors,
        "message": f"Fixed {len(fixed)} accounts, {len(errors)} errors"
    }

@frappe.whitelist()
def run_migration_after_fix():
    """Run the migration again after fixing accounts"""
    
    # First fix the accounts
    fix_result = fix_receivable_accounts()
    
    if not fix_result["success"]:
        return fix_result
    
    # Then run the migration
    from verenigingen.api.fix_cost_center_and_run import run_soap_migration_for_may
    
    return run_soap_migration_for_may()

if __name__ == "__main__":
    print(fix_receivable_accounts())