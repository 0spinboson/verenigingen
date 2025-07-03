import frappe
from frappe import _

@frappe.whitelist()
def review_account_types(company=None):
    """Review account types and identify potential issues"""
    
    if not company:
        company = frappe.db.get_value("E-Boekhouden Settings", None, "default_company")
    
    # Get all accounts with account numbers
    accounts = frappe.db.get_all("Account", {
        "company": company,
        "is_group": 0
    }, ["name", "account_name", "account_number", "account_type"])
    
    issues = []
    
    for account in accounts:
        account_name_lower = account.account_name.lower()
        current_type = account.account_type
        suggested_type = None
        reason = None
        
        # Check for tax accounts
        tax_keywords = ["btw", "vat", "tax", "belasting", "omzetbelasting"]
        if any(keyword in account_name_lower for keyword in tax_keywords):
            if current_type != "Tax":
                suggested_type = "Tax"
                reason = "Account name contains tax-related keywords"
        
        # Check for bank accounts
        bank_keywords = ["bank", "kas", "cash", "giro"]
        if any(keyword in account_name_lower for keyword in bank_keywords):
            if current_type not in ["Bank", "Cash"]:
                suggested_type = "Bank"
                reason = "Account name contains bank-related keywords"
        
        # Check for receivable patterns
        receivable_keywords = ["debiteur", "debtor", "te ontvangen", "receivable", "vordering"]
        if any(keyword in account_name_lower for keyword in receivable_keywords):
            if current_type != "Receivable":
                suggested_type = "Receivable"
                reason = "Account name contains receivable-related keywords"
        
        # Check for payable patterns
        payable_keywords = ["crediteur", "creditor", "te betalen", "payable", "schuld", "leverancier"]
        if any(keyword in account_name_lower for keyword in payable_keywords):
            if current_type != "Payable":
                suggested_type = "Payable"
                reason = "Account name contains payable-related keywords"
        
        # Check for income patterns
        income_keywords = ["omzet", "revenue", "sales", "verkoop", "inkomsten", "contributie", "donation"]
        if any(keyword in account_name_lower for keyword in income_keywords):
            if current_type != "Income Account":
                # Only suggest if not already receivable (which is correct for invoiced income)
                if current_type != "Receivable":
                    suggested_type = "Income Account"
                    reason = "Account name contains income-related keywords"
        
        # Check for expense patterns
        expense_keywords = ["kosten", "expense", "cost", "uitgaven", "inkoop", "purchase"]
        if any(keyword in account_name_lower for keyword in expense_keywords):
            if current_type != "Expense Account":
                # Only suggest if not already payable (which is correct for invoiced expenses)
                if current_type != "Payable":
                    suggested_type = "Expense Account"
                    reason = "Account name contains expense-related keywords"
        
        # Add to issues if we found a suggestion
        if suggested_type and suggested_type != current_type:
            issues.append({
                "account": account.name,
                "account_name": account.account_name,
                "account_number": account.account_number,
                "current_type": current_type or "Not Set",
                "suggested_type": suggested_type,
                "reason": reason
            })
    
    return {
        "success": True,
        "issues": issues,
        "total_accounts": len(accounts),
        "issues_found": len(issues)
    }

@frappe.whitelist()
def fix_account_type_issues(issues):
    """Fix the identified account type issues"""
    
    if isinstance(issues, str):
        import json
        issues = json.loads(issues)
    
    fixed_count = 0
    errors = []
    
    for issue in issues:
        try:
            frappe.db.set_value("Account", issue["account"], "account_type", issue["suggested_type"])
            fixed_count += 1
        except Exception as e:
            errors.append(f"{issue['account']}: {str(e)}")
    
    frappe.db.commit()
    
    return {
        "success": True,
        "fixed_count": fixed_count,
        "errors": errors
    }