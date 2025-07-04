"""
Test COGS mapping for inkoop materiaal
"""

import frappe
from frappe import _

@frappe.whitelist()
def test_cogs_mapping():
    """Test that inkoop materiaal gets mapped correctly"""
    
    try:
        from verenigingen.utils.smart_tegenrekening_mapper import SmartTegenrekeningMapper
        
        mapper = SmartTegenrekeningMapper()
        
        # Test with account code 70000 (inkoop materiaal webshop)
        result = mapper.get_item_for_tegenrekening(
            account_code="70000",
            description="Inkoop materiaal webshop",
            transaction_type="purchase",
            amount=100
        )
        
        response = {
            "mapping_result": result,
            "tests": []
        }
        
        # Test 1: Check if item was created/found
        if result:
            response["tests"].append({
                "test": "Item mapping",
                "passed": True,
                "item_code": result.get("item_code"),
                "item_group": result.get("item_group")
            })
            
            # Test 2: Check if it's in COGS group
            is_cogs = result.get("item_group") == "Cost of Goods Sold Items"
            response["tests"].append({
                "test": "COGS categorization",
                "passed": is_cogs,
                "expected": "Cost of Goods Sold Items",
                "actual": result.get("item_group")
            })
            
            # Test 3: Check the account
            response["tests"].append({
                "test": "Account mapping",
                "passed": bool(result.get("account")),
                "account": result.get("account")
            })
        else:
            response["tests"].append({
                "test": "Item mapping",
                "passed": False,
                "error": "No mapping result returned"
            })
        
        # Check if the item exists in database
        if result and result.get("item_code"):
            item_exists = frappe.db.exists("Item", result["item_code"])
            if item_exists:
                item_doc = frappe.get_doc("Item", result["item_code"])
                response["item_details"] = {
                    "exists": True,
                    "item_code": item_doc.name,
                    "item_name": item_doc.item_name,
                    "item_group": item_doc.item_group,
                    "is_purchase_item": item_doc.is_purchase_item
                }
        
        # Overall success
        all_passed = all(test.get("passed", False) for test in response["tests"])
        response["success"] = all_passed
        response["message"] = "All tests passed" if all_passed else "Some tests failed"
        
        return response
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "traceback": frappe.get_traceback()
        }