"""
Validate that the migration system updates are working correctly
"""

import frappe

@frappe.whitelist()
def test_transaction_type_mapping():
    """Test the new transaction type mapping system"""
    from .eboekhouden_transaction_type_mapper import (
        get_erpnext_document_type,
        get_payment_entry_reference_type,
        simplify_migration_process
    )
    
    # Test SOAP types
    soap_tests = [
        ("FactuurOntvangen", "Purchase Invoice"),
        ("FactuurVerstuurd", "Sales Invoice"),
        ("FactuurbetalingOntvangen", "Payment Entry"),
        ("GeldOntvangen", "Journal Entry"),
        ("Memoriaal", "Journal Entry")
    ]
    
    # Test REST numeric types
    rest_tests = [
        (1, "Purchase Invoice"),
        (2, "Sales Invoice"),
        (3, "Payment Entry"),
        (5, "Journal Entry"),
        (7, "Journal Entry")
    ]
    
    results = {
        "soap_tests": [],
        "rest_tests": [],
        "payment_tests": [],
        "migration_tests": []
    }
    
    # Test SOAP types
    for input_type, expected in soap_tests:
        result = get_erpnext_document_type(input_type)
        results["soap_tests"].append({
            "input": input_type,
            "expected": expected,
            "actual": result,
            "pass": result == expected
        })
    
    # Test REST types
    for input_type, expected in rest_tests:
        result = get_erpnext_document_type(input_type)
        results["rest_tests"].append({
            "input": input_type,
            "expected": expected,
            "actual": result,
            "pass": result == expected
        })
    
    # Test payment reference types
    payment_tests = [
        ("FactuurbetalingOntvangen", "Sales Invoice"),
        ("FactuurbetalingVerstuurd", "Purchase Invoice"),
        (3, "Sales Invoice"),
        (4, "Purchase Invoice")
    ]
    
    for input_type, expected in payment_tests:
        result = get_payment_entry_reference_type(input_type)
        results["payment_tests"].append({
            "input": input_type,
            "expected": expected,
            "actual": result,
            "pass": result == expected
        })
    
    # Test the main migration function
    test_mutations = [
        {"Soort": "FactuurOntvangen", "MutatieNr": "TEST1"},
        {"type": 2, "id": "TEST2"},
        {"Soort": "GeldOntvangen", "MutatieNr": "TEST3"}
    ]
    
    for mut in test_mutations:
        result = simplify_migration_process(mut)
        results["migration_tests"].append({
            "input": mut,
            "result": result
        })
    
    # Calculate summary
    all_tests = (results["soap_tests"] + results["rest_tests"] + 
                results["payment_tests"])
    passed = sum(1 for test in all_tests if test["pass"])
    total = len(all_tests)
    
    results["summary"] = {
        "total_tests": total,
        "passed": passed,
        "failed": total - passed,
        "success_rate": f"{(passed/total)*100:.1f}%" if total > 0 else "0%"
    }
    
    return results

@frappe.whitelist()
def check_system_integrity():
    """Check if all required functions are available"""
    try:
        # Test imports
        from .eboekhouden_transaction_type_mapper import simplify_migration_process
        from .eboekhouden_unified_processor import process_sales_invoices
        from .eboekhouden_grouped_migration import migrate_mutations_grouped
        
        return {
            "success": True,
            "message": "All required functions are available",
            "imports_working": True
        }
        
    except ImportError as e:
        return {
            "success": False,
            "error": str(e),
            "imports_working": False
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "imports_working": "unknown"
        }