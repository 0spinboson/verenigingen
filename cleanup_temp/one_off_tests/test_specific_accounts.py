#!/usr/bin/env python3

import frappe

def test_accounts():
    """Test specific problematic accounts"""
    try:
        frappe.connect()
        
        doc = frappe.get_doc({
            'doctype': 'E-Boekhouden Migration',
            'migration_name': 'Test Specific'
        })
        
        result = doc.analyze_specific_accounts()
        
        if result['success']:
            print("Problem Accounts Analysis:")
            print("=" * 50)
            
            print("\nEquity 05xxx accounts:")
            for acc in result['problem_accounts']:
                if acc['type'] == 'equity_05xxx':
                    print(f"  {acc['code']:6} | {acc['category']:4} | {acc['group']:4} | {acc['description']}")
            
            print("\nIncome 8xxx accounts:")
            for acc in result['problem_accounts']:
                if acc['type'] == 'income_8xxx':
                    print(f"  {acc['code']:6} | {acc['category']:4} | {acc['group']:4} | {acc['description']}")
            
            print("\nEquity pattern accounts:")
            for acc in result['equity_pattern_accounts']:
                print(f"  {acc['code']:6} | {acc['category']:4} | {acc['group']:4} | {acc['description']}")
            
            print("\nIncome pattern accounts:")
            for acc in result['income_pattern_accounts']:
                print(f"  {acc['code']:6} | {acc['category']:4} | {acc['group']:4} | {acc['description']}")
                
        else:
            print(f"Error: {result['error']}")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_accounts()