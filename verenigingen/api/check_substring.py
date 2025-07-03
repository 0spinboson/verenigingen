import frappe

@frappe.whitelist()
def check_substring():
    """Check substring matching"""
    test_string = "cum. afschrijving apparatuur en toebehoren"
    
    return {
        "string": test_string,
        "has_bank": "bank" in test_string,
        "position": test_string.find("bank") if "bank" in test_string else -1
    }