import frappe
from frappe import _

@frappe.whitelist()
def get_sample_accounts():
    """Get sample E-boekhouden accounts for testing"""
    frappe.set_user("Administrator")
    
    accounts = frappe.db.sql("""
        SELECT 
            account_number,
            account_name,
            root_type
        FROM `tabAccount`
        WHERE company = %s
        AND account_number IS NOT NULL
        AND account_number != ''
        AND is_group = 0
        AND root_type IN ('Income', 'Expense')
        ORDER BY account_number
        LIMIT 20
    """, "Nederlandse Vereniging voor Veganisme", as_dict=True)
    
    return accounts

@frappe.whitelist()
def test_item_creation():
    """Test the improved item naming"""
    frappe.set_user("Administrator")
    
    # Test with a known account
    from verenigingen.utils.eboekhouden_improved_item_naming import get_or_create_item_improved
    
    # Get first account
    account = frappe.db.get_value("Account", {
        "company": "Nederlandse Vereniging voor Veganisme",
        "account_number": ["!=", ""],
        "is_group": 0
    }, ["account_number", "account_name"], as_dict=True)
    
    if account:
        # Test item creation
        item_code = get_or_create_item_improved(
            account.account_number,
            "Nederlandse Vereniging voor Veganisme",
            "Sales",
            "Test transaction"
        )
        
        return {
            "account": account,
            "created_item": item_code,
            "item_exists": frappe.db.exists("Item", item_code)
        }
    
    return {"error": "No accounts found"}

@frappe.whitelist()
def create_sample_mapping():
    """Create a sample mapping for testing"""
    frappe.set_user("Administrator")
    
    # Find contributie account
    account = frappe.db.get_value("Account", {
        "company": "Nederlandse Vereniging voor Veganisme",
        "account_name": ["like", "%contributie%"],
        "is_group": 0
    }, ["account_number", "account_name"], as_dict=True)
    
    if account:
        # Create or get membership contribution item
        if not frappe.db.exists("Item", "Membership Contribution"):
            item = frappe.new_doc("Item")
            item.item_code = "Membership Contribution"
            item.item_name = "Membership Contribution"
            item.item_group = "Services"
            item.stock_uom = "Nos"
            item.is_stock_item = 0
            item.description = "Annual membership contribution"
            item.insert(ignore_permissions=True)
        
        # Create mapping
        mapping = frappe.new_doc("E-Boekhouden Item Mapping")
        mapping.company = "Nederlandse Vereniging voor Veganisme"
        mapping.account_code = account.account_number
        mapping.account_name = account.account_name
        mapping.item_code = "Membership Contribution"
        mapping.transaction_type = "Sales"
        mapping.is_active = 1
        mapping.insert(ignore_permissions=True)
        
        frappe.db.commit()
        
        return {
            "success": True,
            "mapping": mapping.name,
            "account": account
        }
    
    return {"error": "No contributie account found"}