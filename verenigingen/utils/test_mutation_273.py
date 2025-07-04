"""
Test importing mutation 273 directly
"""

import frappe
from frappe import _
import json

@frappe.whitelist() 
def test_import_mutation_273():
    """Test importing mutation 273 which is failing"""
    
    # Create test data that mimics mutation 273
    mutation_data = {
        "id": 273,
        "type": 2,  # Sales Invoice
        "date": "2019-01-03",
        "invoiceNumber": "TEST-273",
        "relationId": "12345",
        "description": "Test Sales Invoice",
        "rows": [{
            "ledgerId": "80010",  
            "amount": 100.0
        }]
    }
    
    results = {
        "mutation_data": mutation_data,
        "tests": []
    }
    
    # Test 1: Create Sales Invoice directly
    try:
        si = frappe.new_doc("Sales Invoice")
        si.company = "Ned Ver Vegan"
        si.posting_date = mutation_data["date"]
        
        # Get or create customer
        customer = frappe.db.get_value("Customer", {"customer_group": "All Customer Groups"}, "name")
        if not customer:
            cust = frappe.new_doc("Customer")
            cust.customer_name = "Test Customer 273"
            cust.customer_group = "All Customer Groups"
            cust.territory = "All Territories"
            cust.save(ignore_permissions=True)
            customer = cust.name
        
        si.customer = customer
        
        # Add item using smart mapper
        from verenigingen.utils.smart_tegenrekening_mapper import create_invoice_line_for_tegenrekening
        
        line_dict = create_invoice_line_for_tegenrekening(
            tegenrekening_code="80010",
            amount=100,
            description="Test line",
            transaction_type="sales"
        )
        
        results["line_dict"] = line_dict
        
        si.append("items", line_dict)
        si.save()
        
        results["tests"].append({
            "test": "Direct Sales Invoice creation",
            "success": True,
            "invoice": si.name
        })
        
    except Exception as e:
        results["tests"].append({
            "test": "Direct Sales Invoice creation", 
            "success": False,
            "error": str(e),
            "traceback": frappe.get_traceback()
        })
    
    # Test 2: Import using batch function
    try:
        from verenigingen.utils.eboekhouden_rest_full_migration import _import_rest_mutations_batch
        
        settings = frappe.get_single("E-Boekhouden Settings")
        import_result = _import_rest_mutations_batch("TEST-MIGRATION", [mutation_data], settings)
        
        results["tests"].append({
            "test": "Batch import function",
            "success": True,
            "result": import_result
        })
        
    except Exception as e:
        results["tests"].append({
            "test": "Batch import function",
            "success": False,
            "error": str(e),
            "error_lines": str(e).split('\n')[:5]  # First 5 lines of error
        })
    
    # Test 3: Check what items exist with EB- prefix
    eb_items = frappe.db.sql("""
        SELECT name, item_name, item_group
        FROM `tabItem`
        WHERE name LIKE 'EB-%'
        LIMIT 10
    """, as_dict=True)
    results["eb_items"] = eb_items
    
    # Test 4: Check item defaults for EB-80010
    if frappe.db.exists("Item", "EB-80010"):
        item_defaults = frappe.db.sql("""
            SELECT company, expense_account, income_account
            FROM `tabItem Default`
            WHERE parent = 'EB-80010'
        """, as_dict=True)
        results["eb_80010_defaults"] = item_defaults
    
    return results


@frappe.whitelist()
def analyze_error_source():
    """Try to find where the Kostprijs text is coming from"""
    
    # Check if there's any default expense account set somewhere
    results = {
        "company_defaults": {},
        "item_group_defaults": {},
        "system_settings": {}
    }
    
    # Check company defaults
    company = frappe.get_doc("Company", "Ned Ver Vegan")
    results["company_defaults"] = {
        "default_expense_account": company.get("default_expense_account"),
        "cost_of_goods_sold_account": company.get("default_cost_of_goods_sold_account"),
        "stock_adjustment_account": company.get("stock_adjustment_account")
    }
    
    # Check item group defaults
    item_groups = frappe.get_all("Item Group", 
        filters={"name": ["in", ["E-Boekhouden Import", "Revenue Items"]]},
        fields=["name"]
    )
    
    for ig in item_groups:
        ig_doc = frappe.get_doc("Item Group", ig.name)
        defaults = []
        if hasattr(ig_doc, "item_group_defaults"):
            for d in ig_doc.item_group_defaults:
                defaults.append({
                    "company": d.get("company"),
                    "expense_account": d.get("expense_account"),
                    "income_account": d.get("income_account")
                })
        results["item_group_defaults"][ig.name] = defaults
    
    # Check if there's a default in Stock Settings
    if frappe.db.exists("Stock Settings", None):
        stock_settings = frappe.get_single("Stock Settings")
        results["stock_settings"] = {
            "default_warehouse": stock_settings.get("default_warehouse"),
            "auto_insert_price_list_rate": stock_settings.get("auto_insert_price_list_rate_if_missing")
        }
    
    return results