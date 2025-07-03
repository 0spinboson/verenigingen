import frappe

@frappe.whitelist()
def check_company_coa():
    """Check company Chart of Accounts setup"""
    company = frappe.get_doc('Company', 'Ned Ver Vegan')
    print(f'Company: {company.name}')
    print(f'Chart of Accounts: {company.chart_of_accounts}')
    print(f'Create Chart of Accounts: {company.create_chart_of_accounts_based_on}')
    
    # Check if basic root accounts exist
    root_types = ["Asset", "Liability", "Equity", "Income", "Expense"]
    
    print("\n=== Checking for Root Accounts ===")
    for root_type in root_types:
        accounts = frappe.db.get_list(
            "Account",
            filters={
                "company": company.name,
                "root_type": root_type,
                "parent_account": ["in", ["", None]],
                "is_group": 1
            },
            fields=["name", "account_name"]
        )
        
        if accounts:
            print(f"{root_type}: {accounts[0].account_name}")
        else:
            print(f"{root_type}: NO ROOT ACCOUNT FOUND")
    
    return company