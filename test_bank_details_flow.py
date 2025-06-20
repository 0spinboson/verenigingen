#!/usr/bin/env python3
"""
Test the bank details confirmation flow
"""

import frappe

@frappe.whitelist()
def test_bank_details_flow():
    """Test the new bank details confirmation flow"""
    
    results = {
        "success": True,
        "tests": []
    }
    
    # Test 1: Check if bank_details_confirm page files exist
    try:
        import os
        html_path = "/home/frappe/frappe-bench/apps/verenigingen/verenigingen/templates/pages/bank_details_confirm.html"
        py_path = "/home/frappe/frappe-bench/apps/verenigingen/verenigingen/templates/pages/bank_details_confirm.py"
        
        html_exists = os.path.exists(html_path)
        py_exists = os.path.exists(py_path)
        
        if html_exists and py_exists:
            results["tests"].append({
                "name": "Confirmation Page Files",
                "status": "PASS", 
                "details": "HTML and Python files exist"
            })
        else:
            results["tests"].append({
                "name": "Confirmation Page Files",
                "status": "FAIL",
                "error": f"HTML exists: {html_exists}, Python exists: {py_exists}"
            })
            results["success"] = False
    except Exception as e:
        results["tests"].append({
            "name": "Confirmation Page Files",
            "status": "FAIL",
            "error": str(e)
        })
        results["success"] = False
    
    # Test 2: Test session data handling
    try:
        # Simulate session data
        test_data = {
            "new_iban": "NL91ABNA0417164300",
            "new_bic": "ABNANL2A",
            "new_account_holder": "Test User",
            "enable_dd": True,
            "action_needed": "create_mandate"
        }
        
        frappe.session["bank_details_update"] = test_data
        
        # Test retrieval
        retrieved_data = frappe.session.get("bank_details_update")
        if retrieved_data and retrieved_data["new_iban"] == test_data["new_iban"]:
            results["tests"].append({
                "name": "Session Data Handling",
                "status": "PASS",
                "details": "Session data stored and retrieved correctly"
            })
        else:
            results["tests"].append({
                "name": "Session Data Handling", 
                "status": "FAIL",
                "error": "Session data not retrieved correctly"
            })
            results["success"] = False
            
        # Clean up
        if "bank_details_update" in frappe.session:
            del frappe.session["bank_details_update"]
            
    except Exception as e:
        results["tests"].append({
            "name": "Session Data Handling",
            "status": "FAIL", 
            "error": str(e)
        })
        results["success"] = False
    
    # Test 3: Test IBAN validation function
    try:
        from verenigingen.templates.pages.bank_details import validate_iban_format
        
        valid_iban = "NL91ABNA0417164300"
        invalid_iban = "INVALID"
        
        valid_result = validate_iban_format(valid_iban)
        invalid_result = validate_iban_format(invalid_iban)
        
        if valid_result and not invalid_result:
            results["tests"].append({
                "name": "IBAN Validation",
                "status": "PASS",
                "details": "IBAN validation working correctly"
            })
        else:
            results["tests"].append({
                "name": "IBAN Validation",
                "status": "FAIL", 
                "error": f"Valid: {valid_result}, Invalid: {invalid_result}"
            })
            results["success"] = False
            
    except Exception as e:
        results["tests"].append({
            "name": "IBAN Validation",
            "status": "FAIL",
            "error": str(e)
        })
        results["success"] = False
    
    return results

if __name__ == "__main__":
    try:
        # Initialize Frappe context
        import os
        import sys
        sys.path.insert(0, '/home/frappe/frappe-bench/apps')
        os.environ['FRAPPE_SITE'] = 'dev.veganisme.net'
        
        import frappe
        frappe.init(site='dev.veganisme.net')
        frappe.connect()
        
        result = test_bank_details_flow()
        print("Bank Details Flow Test Results:")
        print("=" * 40)
        
        for test in result["tests"]:
            status_symbol = "✓" if test["status"] == "PASS" else "✗"
            print(f"{status_symbol} {test['name']}: {test['status']}")
            if test["status"] == "PASS":
                print(f"  {test.get('details', '')}")
            else:
                print(f"  Error: {test.get('error', 'Unknown error')}")
        
        print("=" * 40)
        overall = "✓ PASS" if result["success"] else "✗ FAIL"
        print(f"Overall: {overall}")
        
    except Exception as e:
        print(f"Test setup failed: {e}")
    finally:
        try:
            frappe.destroy()
        except:
            pass