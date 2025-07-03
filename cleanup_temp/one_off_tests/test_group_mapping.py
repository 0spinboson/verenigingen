#!/usr/bin/env python3

def get_dutch_account_group_mapping():
    """
    Define proper mapping based on Dutch rekeninggroepen (account groups)
    as used in E-Boekhouden and standard Dutch accounting practices
    """
    
    # Dutch Rekeninggroepen mapping based on standard chart of accounts
    rekeninggroepen_mapping = {
        # ACTIVA (Assets)
        "001": {"type": "Fixed Asset", "root_type": "Asset", "description": "Vaste activa"},
        "002": {"type": "Bank", "root_type": "Asset", "description": "Liquide middelen"},  # This is key for 10480, 10620!
        "003": {"type": "Stock", "root_type": "Asset", "description": "Voorraden"},
        "004": {"type": "Current Asset", "root_type": "Asset", "description": "Vorderingen"},
        "005": {"type": "Current Asset", "root_type": "Asset", "description": "Overlopende activa"},
        
        # PASSIVA (Liabilities)
        "006": {"type": "Current Liability", "root_type": "Liability", "description": "Kortlopende schulden"},
        "007": {"type": "Current Liability", "root_type": "Liability", "description": "Langlopende schulden"},
        "008": {"type": "Current Liability", "root_type": "Liability", "description": "Overlopende passiva"},
        
        # EIGEN VERMOGEN (Equity)
        "050": {"type": "Equity", "root_type": "Equity", "description": "Eigen vermogen"},
        "051": {"type": "Equity", "root_type": "Equity", "description": "Resultaat voorgaande jaren"},
        "052": {"type": "Equity", "root_type": "Equity", "description": "Resultaat boekjaar"},
        
        # OPBRENGSTEN (Income) - Group 055 in VW category
        "055": {"type": "Income Account", "root_type": "Income", "description": "Opbrengsten"},
        
        # KOSTEN (Expenses) - Groups 056-059 in VW category  
        "056": {"type": "Expense Account", "root_type": "Expense", "description": "Kosten"},
        "057": {"type": "Expense Account", "root_type": "Expense", "description": "Personeelskosten"},
        "058": {"type": "Expense Account", "root_type": "Expense", "description": "Afschrijvingen"},
        "059": {"type": "Expense Account", "root_type": "Expense", "description": "Financiele kosten"},
    }
    
    return rekeninggroepen_mapping

def should_prioritize_group_over_code():
    """
    This explains why group-based classification should be prioritized:
    
    1. Account codes can be inconsistent between different E-Boekhouden instances
    2. Rekeninggroepen follow Dutch accounting standards (RJ)
    3. E-Boekhouden uses official rekeninggroepen for categorization
    4. Group 002 = "Liquide middelen" = should be Bank accounts regardless of code
    5. Categories (BAL, VW, etc.) + Groups give the official classification
    """
    
    examples = {
        "10480": {
            "name": "Zettle", 
            "current_classification": "Current Asset",
            "correct_group": "002",
            "should_be": "Bank",
            "reason": "Group 002 = Liquide middelen = Bank accounts"
        },
        "10620": {
            "name": "ASN Bank",
            "current_classification": "Current Asset", 
            "correct_group": "002",
            "should_be": "Bank",
            "reason": "Group 002 = Liquide middelen = Bank accounts"
        },
        "40010": {
            "name": "Algemene kosten",
            "current_classification": "Current Liability",
            "correct_category": "VW",
            "correct_group": "056",
            "should_be": "Expense Account",
            "reason": "VW category + Group 056 = Kosten = Expense Account"
        }
    }
    
    return examples

if __name__ == "__main__":
    mapping = get_dutch_account_group_mapping()
    examples = should_prioritize_group_over_code()
    
    print("Dutch Rekeninggroepen Mapping:")
    print("=" * 50)
    for group, info in mapping.items():
        print(f"Group {group}: {info['description']} -> {info['type']} ({info['root_type']})")
    
    print("\nMisclassification Examples:")
    print("=" * 50)
    for code, info in examples.items():
        print(f"Account {code} ({info['name']}):")
        print(f"  Current: {info['current_classification']}")
        print(f"  Should be: {info['should_be']}")
        print(f"  Reason: {info['reason']}")
        print()