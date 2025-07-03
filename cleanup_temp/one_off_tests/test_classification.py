#!/usr/bin/env python3

import os
import sys

# Add the correct path to sys.path to import frappe
frappe_path = "/home/frappe/frappe-bench/apps/frappe"
sys.path.insert(0, frappe_path)

# Import frappe
import frappe

def test_account_classification():
    """Test the account classification logic with specific examples"""
    
    # Set up frappe (minimal setup)
    frappe.init(site="dev.veganisme.net")
    frappe.connect()
    
    # Test data - examples from the user's report
    test_accounts = [
        {"code": "40010", "name": "Algemene kosten", "root_type": "Liability", "expected": "Expense Account"},
        {"code": "10480", "name": "ASN Bank", "root_type": "Asset", "expected": "Bank"},
        {"code": "10620", "name": "Zettle", "root_type": "Asset", "expected": "Bank"},
        {"code": "14500", "name": "Vooruitontvangen bedragen", "root_type": "Asset", "expected": "Current Liability"},
        {"code": "18100", "name": "Some current asset", "root_type": "Asset", "expected": "Current Asset"},
        {"code": "19290", "name": "Some asset", "root_type": "Asset", "expected": "Current Asset"},
        {"code": "16100", "name": "Reservering vakantiegeld", "root_type": "Liability", "expected": "Current Liability"},
    ]
    
    print("Testing account classification logic...")
    print("=" * 60)
    
    for account in test_accounts:
        # Create a mock account object
        class MockAccount:
            def __init__(self, code, name, root_type):
                self.eboekhouden_grootboek_nummer = code
                self.account_name = name
                self.root_type = root_type
                self.parent_group_number = None
                self.is_group = False
        
        mock_account = MockAccount(account["code"], account["name"], account["root_type"])
        
        # Test the classification logic
        account_code = account["code"]
        account_name = account["name"].lower()
        recommended_type = None
        
        # Apply the same logic as in the file
        
        # VW (Verlies/Winst) accounts - P/L accounts should be classified as expenses/income regardless of root_type
        if account_code.startswith(("4", "6", "7", "8")):
            # Check if it's income (group 055 or "opbrengst" in name)
            if mock_account.parent_group_number == "055" or "opbrengst" in account_name or "omzet" in account_name:
                recommended_type = "Income Account"
            # Check for depreciation expense accounts
            elif "afschrijving" in account_name:
                recommended_type = "Depreciation"
            # All other VW accounts are expense accounts
            else:
                recommended_type = "Expense Account"
        
        # Liquide middelen accounts - specific account codes for bank accounts
        elif account_code in ["10480", "10620"]:
            recommended_type = "Bank"
        
        # Specific account code patterns for commonly misclassified accounts
        elif account_code in ["14500", "14600", "14700"]:
            # These are likely receivables or current assets
            if "te ontvangen" in account_name or "debiteur" in account_name:
                recommended_type = "Receivable"
            else:
                recommended_type = "Current Asset"
        
        elif account_code in ["18100", "18200"]:
            # These are likely current assets or receivables based on account range
            if "te ontvangen" in account_name or "debiteur" in account_name:
                recommended_type = "Receivable"
            else:
                recommended_type = "Current Asset"
        
        # Equity accounts - Account codes starting with 05 (Dutch accounting standard)
        elif account_code.startswith("05"):
            if "reserve" in account_name or "reservering" in account_name or "vermogen" in account_name:
                recommended_type = "Equity"
            else:
                recommended_type = "Equity"  # Default for 05xxx codes
        
        # Receivable accounts - Account codes starting with 13 (te ontvangen)
        elif account_code.startswith("13") and "te ontvangen" in account_name:
            recommended_type = "Receivable"
        
        # Payable accounts - "te betalen" pattern (should be Payable, not Current Liability)
        elif "te betalen" in account_name:
            recommended_type = "Payable"
        
        # Balance sheet logic...
        elif mock_account.root_type in ["Asset", "Liability", "Equity"]:
            if mock_account.root_type == "Asset":
                if "bank" in account_name or "triodos" in account_name or "abn" in account_name or "ing" in account_name:
                    recommended_type = "Bank"
                elif ("kas" in account_name and "bank" not in account_name) or account_code == "10000":
                    recommended_type = "Cash"
                elif "mollie" in account_name or "paypal" in account_name:
                    recommended_type = "Bank"
                else:
                    recommended_type = "Current Asset"
            elif mock_account.root_type == "Liability":
                if "vooruitontvangen" in account_name:
                    recommended_type = "Current Liability"
                elif "reservering" in account_name:
                    recommended_type = "Current Liability"
                else:
                    recommended_type = "Current Liability"
        
        status = "✓" if recommended_type == account["expected"] else "✗"
        print(f"{status} {account['code']:6} | {account['name']:25} | Expected: {account['expected']:15} | Got: {recommended_type or 'None':15}")
    
    frappe.db.close()

if __name__ == "__main__":
    test_account_classification()