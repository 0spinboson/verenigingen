#!/usr/bin/env python3

import frappe

def analyze_data():
    """Analyze E-Boekhouden data"""
    frappe.connect()
    
    doc = frappe.get_doc({
        'doctype': 'E-Boekhouden Migration',
        'migration_name': 'Test Analysis'
    })
    
    result = doc.analyze_eboekhouden_data()
    print("Analysis Result:")
    print("=" * 50)
    
    if result['success']:
        print(f"Total accounts: {result['total_accounts']}")
        print(f"\nCategories: {result['categories']}")
        print(f"\nGroups: {result['groups']}")
        print(f"\nSample accounts:")
        for account in result['sample_accounts'][:10]:
            print(f"  {account['code']:6} | {account['category']:4} | {account['group']:3} | {account['description']}")
        
        print(f"\nGroup details:")
        for group, accounts in result['group_details'].items():
            print(f"  Group {group}:")
            for acc in accounts:
                print(f"    {acc}")
    else:
        print(f"Error: {result['error']}")

if __name__ == "__main__":
    analyze_data()