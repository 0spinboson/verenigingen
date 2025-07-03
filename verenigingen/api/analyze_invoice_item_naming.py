import frappe
import json

@frappe.whitelist()
def analyze_current_naming():
    """Analyze how items are currently named in imported invoices"""
    frappe.set_user("Administrator")
    
    print("=== Current Invoice Item Naming Analysis ===\n")
    
    # Check sales invoice items
    print("1. Sales Invoice Items:")
    si_items = frappe.db.sql("""
        SELECT DISTINCT 
            sii.item_code, sii.item_name, sii.description,
            si.eboekhouden_invoice_number,
            COUNT(*) as usage_count
        FROM `tabSales Invoice Item` sii
        JOIN `tabSales Invoice` si ON si.name = sii.parent
        WHERE si.eboekhouden_invoice_number IS NOT NULL
        GROUP BY sii.item_code
        ORDER BY usage_count DESC
        LIMIT 20
    """, as_dict=True)
    
    for item in si_items:
        print(f"  {item.item_code} (used {item.usage_count} times)")
        if item.description:
            print(f"    Description: {item.description[:100]}")
    
    # Check purchase invoice items
    print("\n2. Purchase Invoice Items:")
    pi_items = frappe.db.sql("""
        SELECT DISTINCT 
            pii.item_code, pii.item_name, pii.description,
            pi.eboekhouden_invoice_number,
            COUNT(*) as usage_count
        FROM `tabPurchase Invoice Item` pii
        JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
        WHERE pi.eboekhouden_invoice_number IS NOT NULL
        GROUP BY pii.item_code
        ORDER BY usage_count DESC
        LIMIT 20
    """, as_dict=True)
    
    for item in pi_items:
        print(f"  {item.item_code} (used {item.usage_count} times)")
        if item.description:
            print(f"    Description: {item.description[:100]}")
    
    # Check actual E-boekhouden data
    print("\n3. E-boekhouden Account Structure:")
    accounts = frappe.db.sql("""
        SELECT 
            account_number, account_name, account_type
        FROM `tabAccount`
        WHERE company = 'Ned Ver Vegan'
        AND account_number IS NOT NULL
        AND is_group = 0
        AND (account_type LIKE '%Income%' OR account_type LIKE '%Expense%')
        ORDER BY account_number
        LIMIT 20
    """, as_dict=True)
    
    for acc in accounts:
        print(f"  {acc.account_number}: {acc.account_name} [{acc.account_type}]")
    
    # Show mapping issue
    print("\n4. Current Mapping Logic Issues:")
    print("  - Items are named as 'Service XXXX' where XXXX is the account code")
    print("  - This creates meaningless item names like 'Service 80001', 'Service 40011'")
    print("  - The actual account name (e.g., 'Contributie Leden') is not used")
    print("  - Multiple different transactions map to the same generic item")
    
    return {"success": True}

@frappe.whitelist()
def propose_improvement_plan():
    """Propose an improvement plan for item naming"""
    frappe.set_user("Administrator")
    
    print("=== E-boekhouden to ERPNext Item Naming Improvement Plan ===\n")
    
    print("CURRENT ISSUES:")
    print("1. Items are named using account codes (e.g., 'Service 80001')")
    print("2. No meaningful description of what was sold/purchased")
    print("3. Loss of transaction context from E-boekhouden")
    print("4. Same generic items used for different types of transactions")
    
    print("\nDESIGN DIFFERENCES:")
    print("- E-boekhouden: Uses chart of accounts (grootboekrekening) for categorization")
    print("- ERPNext: Uses items (products/services) with separate income/expense accounts")
    print("- E-boekhouden: Transaction description in 'Omschrijving' field")
    print("- ERPNext: Expects specific items with predefined names")
    
    print("\nPROPOSED SOLUTIONS:")
    
    print("\n1. SMART ITEM CREATION:")
    print("   - Use account name instead of code (e.g., 'Contributie Leden' not 'Service 80001')")
    print("   - Create category-based items (e.g., 'Membership Fees', 'Donations', 'Office Supplies')")
    print("   - Use transaction description to enhance item names when possible")
    
    print("\n2. ITEM MAPPING TABLE:")
    print("   - Create mapping of common E-boekhouden accounts to ERPNext items")
    print("   - Example mappings:")
    print("     80001 (Contributie) -> 'Membership Contribution'")
    print("     80005 (Donaties) -> 'Direct Donation'")
    print("     40011 (Lonen) -> 'Salary Expense'")
    
    print("\n3. DESCRIPTION PRESERVATION:")
    print("   - Store original 'Omschrijving' in item description field")
    print("   - Add to invoice remarks for searchability")
    print("   - Consider custom fields for E-boekhouden reference")
    
    print("\n4. IMPLEMENTATION APPROACH:")
    print("   a) Create item groups matching E-boekhouden categories")
    print("   b) Pre-create common items based on chart of accounts")
    print("   c) Update import logic to use intelligent item selection")
    print("   d) Add fallback for unknown accounts with better naming")
    
    print("\n5. BENEFITS:")
    print("   - Meaningful item names in reports")
    print("   - Better tracking of income/expense types")
    print("   - Easier reconciliation with E-boekhouden")
    print("   - Improved user experience")
    
    return {"success": True}