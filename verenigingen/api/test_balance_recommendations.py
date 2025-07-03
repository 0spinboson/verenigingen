import frappe
from verenigingen.verenigingen.doctype.e_boekhouden_migration.e_boekhouden_migration import get_account_type_recommendations

@frappe.whitelist()
def test_balance_recommendations():
    """Test the enhanced balance sheet recommendations"""
    frappe.set_user("Administrator")
    
    print("=== Testing Enhanced Balance Sheet Recommendations ===\n")
    
    # Get recommendations
    result = get_account_type_recommendations("Ned Ver Vegan", show_all=True)
    
    if not result["success"]:
        print(f"Error: {result.get('error')}")
        return
    
    recommendations = result["recommendations"]
    
    # Analyze recommendations by type
    recommendation_counts = {}
    examples_by_type = {}
    
    for rec in recommendations:
        rec_type = rec["recommended_type"]
        if rec_type not in recommendation_counts:
            recommendation_counts[rec_type] = 0
            examples_by_type[rec_type] = []
        
        recommendation_counts[rec_type] += 1
        
        # Collect examples for each type
        if len(examples_by_type[rec_type]) < 3:
            examples_by_type[rec_type].append(f"{rec['account_code']}: {rec['account_name']}")
    
    # Display results
    print("=== Recommendation Summary ===")
    for rec_type, count in sorted(recommendation_counts.items()):
        print(f"{rec_type}: {count} accounts")
    
    print("\n=== Examples by Type ===")
    important_types = [
        "Bank", "Cash", "Fixed Asset", "Stock", 
        "Receivable", "Payable", "Tax", "Equity",
        "Income Account", "Expense Account", "Temporary",
        "Accumulated Depreciation"
    ]
    
    for rec_type in important_types:
        if rec_type in examples_by_type and examples_by_type[rec_type]:
            print(f"\n{rec_type}:")
            for example in examples_by_type[rec_type]:
                print(f"  {example}")
    
    # Check specific groups
    print("\n=== Group-Based Recommendations ===")
    
    # Check Group 001 (Fixed Assets)
    group_001 = [r for r in recommendations if r["account_code"].startswith("0") and len(r["account_code"]) > 3]
    if group_001:
        print("\nGroup 001 (Fixed Assets):")
        for acc in group_001[:5]:
            print(f"  {acc['account_code']}: {acc['account_name']} -> {acc['recommended_type']}")
    
    # Check Group 002 (Liquid Assets)
    group_002_accounts = frappe.db.sql("""
        SELECT a.eboekhouden_grootboek_nummer 
        FROM `tabAccount` a
        JOIN `tabAccount` p ON a.parent_account = p.name
        WHERE p.eboekhouden_grootboek_nummer = '002' 
        AND a.is_group = 0
    """, as_dict=True)
    
    group_002_codes = [a.eboekhouden_grootboek_nummer for a in group_002_accounts]
    group_002 = [r for r in recommendations if r["account_code"] in group_002_codes]
    if group_002:
        print("\nGroup 002 (Liquid Assets):")
        for acc in group_002:
            print(f"  {acc['account_code']}: {acc['account_name']} -> {acc['recommended_type']}")
    
    # Check BTW/Tax accounts
    tax_accounts = [r for r in recommendations if r["recommended_type"] == "Tax"]
    if tax_accounts:
        print("\nTax Accounts:")
        for acc in tax_accounts:
            print(f"  {acc['account_code']}: {acc['account_name']} -> {acc['recommended_type']}")
    
    return {"success": True, "total": len(recommendations)}