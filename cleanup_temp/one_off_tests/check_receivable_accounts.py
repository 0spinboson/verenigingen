#!/usr/bin/env python3

import frappe

def check_receivable_accounts():
    """Check current receivable accounts"""
    frappe.init(site='dev.veganisme.net')
    frappe.connect()
    
    # Get all receivable accounts
    accounts = frappe.db.get_all('Account', 
        filters={'company': 'RSP', 'account_type': 'Receivable'}, 
        fields=['name', 'account_name', 'account_number']
    )
    
    print("=== Receivable Accounts ===")
    for acc in accounts:
        print(f"Name: {acc.name}")
        print(f"Account Name: {acc.account_name}")
        print(f"Account Number: {acc.account_number}")
        print("---")
    
    # Check default receivable account
    company_doc = frappe.get_doc("Company", "RSP")
    print(f"\nDefault Receivable Account: {getattr(company_doc, 'default_receivable_account', 'Not set')}")
    
    # Check which account is 13500 vs 13900
    acc_13500 = frappe.db.get_value("Account", {"account_number": "13500", "company": "RSP"}, ["name", "account_name"], as_dict=True)
    acc_13900 = frappe.db.get_value("Account", {"account_number": "13900", "company": "RSP"}, ["name", "account_name"], as_dict=True)
    
    print(f"\nAccount 13500: {acc_13500}")
    print(f"Account 13900: {acc_13900}")

if __name__ == "__main__":
    check_receivable_accounts()