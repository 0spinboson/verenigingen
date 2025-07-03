import frappe

@frappe.whitelist()
def verify_all_classification_fixes():
    """Comprehensive verification of all classification fixes"""
    try:
        response = []
        response.append("=== COMPREHENSIVE CLASSIFICATION VERIFICATION ===")
        
        # Check Equity accounts (should have empty account_type, root_type = 'Equity', parent = Eigen Vermogen)
        equity_accounts = frappe.db.sql("""
            SELECT name, account_name, account_type, root_type, parent_account, eboekhouden_grootboek_nummer
            FROM `tabAccount`
            WHERE root_type = "Equity"
            AND company = "Ned Ver Vegan"
            ORDER BY name
        """, as_dict=True)
        
        response.append(f"\n=== EQUITY ACCOUNTS (root_type = 'Equity') ===")
        response.append(f"Found {len(equity_accounts)} equity accounts:")
        
        correct_equity = 0
        wrong_equity = 0
        for account in equity_accounts:
            # Check if correctly classified
            is_correct = (account.account_type == "" and 
                         account.root_type == "Equity" and 
                         account.parent_account and
                         "Eigen Vermogen" in account.parent_account)
            
            if is_correct:
                correct_equity += 1
                response.append(f"  ✅ {account.name}: {account.account_name}")
            else:
                wrong_equity += 1
                response.append(f"  ❌ {account.name}: {account.account_name}")
                response.append(f"      Type: {account.account_type}, Root: {account.root_type}, Parent: {account.parent_account}")
        
        response.append(f"Correctly classified equity: {correct_equity}")
        response.append(f"Incorrectly classified equity: {wrong_equity}")
        
        # Check Income accounts (should have account_type = 'Income Account', root_type = 'Income', parent = Opbrengsten)
        income_accounts = frappe.db.sql("""
            SELECT name, account_name, account_type, root_type, parent_account, eboekhouden_grootboek_nummer
            FROM `tabAccount`
            WHERE account_type = "Income Account"
            AND root_type = "Income"
            AND company = "Ned Ver Vegan"
            ORDER BY name
        """, as_dict=True)
        
        response.append(f"\n=== INCOME ACCOUNTS (account_type = 'Income Account') ===")
        response.append(f"Found {len(income_accounts)} income accounts:")
        
        correct_income = 0
        wrong_income = 0
        for account in income_accounts:
            # Check if correctly classified
            is_correct = (account.account_type == "Income Account" and 
                         account.root_type == "Income" and 
                         account.parent_account and
                         "Opbrengsten" in account.parent_account)
            
            if is_correct:
                correct_income += 1
                response.append(f"  ✅ {account.name}: {account.account_name}")
            else:
                wrong_income += 1
                response.append(f"  ❌ {account.name}: {account.account_name}")
                response.append(f"      Type: {account.account_type}, Root: {account.root_type}, Parent: {account.parent_account}")
        
        response.append(f"Correctly classified income: {correct_income}")
        response.append(f"Incorrectly classified income: {wrong_income}")
        
        # Check for any accounts that might still be misclassified
        response.append(f"\n=== POTENTIAL ISSUES CHECK ===")
        
        # Check for accounts under wrong parents
        wrong_parent_accounts = frappe.db.sql("""
            SELECT name, account_name, account_type, root_type, parent_account
            FROM `tabAccount`
            WHERE company = "Ned Ver Vegan"
            AND ((root_type = "Equity" AND parent_account NOT LIKE "%Eigen Vermogen%")
                 OR (account_type = "Income Account" AND parent_account NOT LIKE "%Opbrengsten%"))
        """, as_dict=True)
        
        if wrong_parent_accounts:
            response.append(f"❌ Found {len(wrong_parent_accounts)} accounts with wrong parents:")
            for account in wrong_parent_accounts:
                response.append(f"  - {account.name}: {account.account_name} (Type: {account.account_type}, Root: {account.root_type}, Parent: {account.parent_account})")
        else:
            response.append("✅ All accounts have correct parent assignments")
        
        # Summary
        response.append(f"\n=== FINAL SUMMARY ===")
        response.append(f"✅ Correctly classified equity accounts: {correct_equity}")
        response.append(f"✅ Correctly classified income accounts: {correct_income}")
        response.append(f"❌ Total misclassified accounts: {wrong_equity + wrong_income + len(wrong_parent_accounts)}")
        
        if wrong_equity + wrong_income + len(wrong_parent_accounts) == 0:
            response.append("🎉 ALL CLASSIFICATION ISSUES HAVE BEEN RESOLVED!")
        else:
            response.append("⚠️  Some issues remain to be fixed")
        
        return "\n".join(response)
        
    except Exception as e:
        return f"Error: {e}\n{frappe.get_traceback()}"