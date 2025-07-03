#!/usr/bin/env python3

import frappe
from verenigingen.verenigingen.doctype.e_boekhouden_migration.e_boekhouden_migration import EBoekhoudenMigration

def test_vw_account_mapping():
    """Test VW account classification with the fixed logic"""
    
    # Test cases: VW accounts with different code patterns
    test_accounts = [
        # Expense accounts (4xxx-7xxx)
        {'code': '42301', 'description': 'Groepsgesprekken', 'category': 'VW', 'group': ''},
        {'code': '60000', 'description': 'Algemene kosten', 'category': 'VW', 'group': ''},
        {'code': '70000', 'description': 'Personeelskosten', 'category': 'VW', 'group': ''},
        
        # Income accounts (8xxx-9xxx)
        {'code': '80000', 'description': 'Omzet', 'category': 'VW', 'group': ''},
        {'code': '90000', 'description': 'Overige opbrengsten', 'category': 'VW', 'group': ''},
        
        # Group 055 (should be income regardless of code)
        {'code': '88000', 'description': 'Contributies', 'category': 'VW', 'group': '055'},
        
        # Group 056 (should be expense regardless of code)
        {'code': '60100', 'description': 'Kantoorkosten', 'category': 'VW', 'group': '056'},
    ]
    
    # Create migration instance
    migration = EBoekhoudenMigration()
    
    results = []
    for account_data in test_accounts:
        # Simulate the mapping logic from create_account method
        account_code = account_data.get('code', '')
        account_name = account_data.get('description', '')
        category = account_data.get('category', '')
        group_code = account_data.get('group', '')
        
        # Apply the category mapping logic
        category_mapping = {
            'VW': {'account_type': 'Expense Account', 'root_type': 'Expense'},
        }
        
        mapping = category_mapping.get(category, {'account_type': '', 'root_type': None})
        account_type = mapping['account_type']
        root_type = mapping['root_type']
        
        # Apply VW-specific logic
        if category == 'VW':
            if account_code.startswith('8') or account_code.startswith('9'):
                root_type = 'Income'
                account_type = 'Income Account'
            elif account_code.startswith(('4', '5', '6', '7')):
                root_type = 'Expense'
                account_type = 'Expense Account'
            else:
                if 'opbrengst' in account_name.lower() or 'omzet' in account_name.lower():
                    root_type = 'Income'
                    account_type = 'Income Account'
                else:
                    root_type = 'Expense'
                    account_type = 'Expense Account'
        
        # Apply group code overrides
        if group_code == "055":  # Opbrengsten (Income)
            account_type = 'Income Account'
            root_type = 'Income'
        elif group_code in ["056", "057", "058", "059"]:  # Various cost types
            account_type = 'Expense Account'
            root_type = 'Expense'
            
        results.append({
            'code': account_code,
            'description': account_name,
            'category': category,
            'group': group_code,
            'final_account_type': account_type,
            'final_root_type': root_type
        })
    
    return results

if __name__ == "__main__":
    frappe.connect()
    results = test_vw_account_mapping()
    
    print("VW Account Mapping Test Results:")
    print("=" * 80)
    for result in results:
        print(f"Code: {result['code']:6} | Group: {result['group']:3} | "
              f"Type: {result['final_account_type']:15} | Root: {result['final_root_type']:7} | "
              f"Desc: {result['description']}")