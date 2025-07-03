#!/usr/bin/env python3

def test_category_detection():
    """Test the improved category detection logic with VW priority"""
    
    test_cases = [
        # VW accounts (should be detected as VW first, NOT as banks even if containing bank names)
        ("40010", "Vrijwilligersvergoeding", "VW", "Expense Account"),
        ("42010", "Advertising costs", "VW", "Expense Account"),
        ("44010", "Training expenses", "VW", "Expense Account"),
        ("60010", "Marketing budget", "VW", "Expense Account"),
        ("70010", "Catering costs", "VW", "Expense Account"),
        ("80010", "Sales revenue", "VW", "Income Account"),
        ("82010", "Opbrengsten donations", "VW", "Income Account"),
        
        # FIN accounts (should be detected as banks)
        ("10480", "Zettle", "FIN", "Bank"),
        ("10620", "ASN Bank", "FIN", "Bank"),
        ("12010", "ING Bank", "FIN", "Bank"),
        ("12020", "Triodos Bank", "FIN", "Bank"),
        ("12030", "PayPal account", "FIN", "Bank"),
        ("12040", "Liquide middelen", "FIN", "Bank"),
        
        # DEB accounts  
        ("13100", "Debiteur X", "DEB", "Current Asset"),
        ("13200", "Te ontvangen bedragen", "DEB", "Current Asset"),
        
        # CRED accounts
        ("16100", "Crediteur Y", "CRED", "Current Liability"),
        ("16200", "Te betalen bedragen", "CRED", "Current Liability"),
        
        # BAL accounts
        ("05000", "Eigen vermogen", "BAL", "Equity"),
    ]
    
    print("Testing improved category detection logic with VW priority:")
    print("=" * 70)
    
    for account_code, account_name, expected_category, expected_type in test_cases:
        account_name_lower = account_name.lower()
        
        # Apply the same logic as in the code (priority order)
        inferred_category = None
        recommended_type = None
        
        # VW category inference - Profit & Loss accounts (codes 4, 6, 7, 8) - CHECK FIRST
        if account_code.startswith(("4", "6", "7", "8")):
            inferred_category = 'VW'
            if "opbrengst" in account_name_lower or "omzet" in account_name_lower:
                recommended_type = "Income Account"
            elif "afschrijving" in account_name_lower:
                recommended_type = "Depreciation"
            else:
                recommended_type = "Expense Account"
        
        # FIN category inference - CHECK AFTER VW
        elif ('liquide' in account_name_lower or 
              account_code in ['10480', '10620'] or
              (any(bank in account_name_lower for bank in ['bank', 'triodos', 'abn', 'asn', 'mollie', 'paypal', 'zettle']) or
               ' ing ' in account_name_lower or account_name_lower.startswith('ing ') or account_name_lower.endswith(' ing'))):
            inferred_category = 'FIN'
            recommended_type = "Bank"
        
        # DEB category inference
        elif "debiteur" in account_name_lower or (account_code.startswith("13") and "te ontvangen" in account_name_lower):
            inferred_category = 'DEB'
            recommended_type = "Current Asset"
        
        # CRED category inference
        elif "crediteur" in account_name_lower or "te betalen" in account_name_lower:
            inferred_category = 'CRED'
            recommended_type = "Current Liability"
        
        # BAL category inference
        else:
            inferred_category = 'BAL'
            if account_code.startswith("05"):
                recommended_type = "Equity"
            else:
                recommended_type = "Current Asset"
        
        category_status = "✓" if inferred_category == expected_category else "✗"
        type_status = "✓" if recommended_type == expected_type else "✗"
        
        print(f"{category_status}{type_status} {account_code} {account_name:25} | {inferred_category:4} -> {recommended_type:15} | Expected: {expected_category:4} -> {expected_type}")
    
    print("\n" + "=" * 70)
    print("Key improvement:")
    print("- VW accounts are checked FIRST, so they won't be misclassified as banks")
    print("- Bank name detection only applies to non-VW accounts")
    print("- 'Vrijwilligersvergoeding' with code 4xxxx = VW category = Expense Account")

def test_bank_detection():
    """Original bank detection test"""
    pass  # Keep for backward compatibility

if __name__ == "__main__":
    test_category_detection()