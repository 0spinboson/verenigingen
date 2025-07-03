"""
Debug Purchase Invoice date validation issue
"""

import frappe
from frappe.utils import getdate, add_days

@frappe.whitelist()
def debug_invoice_validation():
    """Debug the exact validation logic for purchase invoices"""
    
    # Test data
    posting_date = "2025-03-03"
    bill_date = "2025-03-03"
    payment_terms = 30
    due_date = add_days(posting_date, payment_terms)
    
    results = {
        "test_data": {
            "posting_date": posting_date,
            "bill_date": bill_date,
            "payment_terms": payment_terms,
            "calculated_due_date": due_date,
        },
        "comparisons": {}
    }
    
    # What ERPNext does in accounts_controller.py line 861
    validation_posting_date = bill_date or posting_date  # For Purchase Invoice
    results["validation_posting_date"] = validation_posting_date
    
    # What happens in validate_due_date
    results["comparisons"]["due_date_vs_posting_date"] = {
        "due_date": due_date,
        "posting_date": posting_date,
        "getdate(due_date)": str(getdate(due_date)),
        "getdate(posting_date)": str(getdate(posting_date)),
        "is_valid": getdate(due_date) >= getdate(posting_date)
    }
    
    # What happens with bill_date in validation
    results["comparisons"]["due_date_vs_bill_date"] = {
        "due_date": due_date,
        "bill_date": bill_date,
        "getdate(due_date)": str(getdate(due_date)),
        "getdate(bill_date)": str(getdate(bill_date)),
        "is_valid": getdate(due_date) >= getdate(bill_date)
    }
    
    # Create a test invoice to see actual validation
    try:
        # Get test data
        company = "R S P"
        supplier = frappe.db.get_value("Supplier", filters={}, fieldname="name")
        credit_to = frappe.db.get_value("Company", company, "default_payable_account")
        cost_center = frappe.db.get_value("Cost Center", {"company": company, "is_group": 0}, "name")
        item = frappe.db.get_value("Item", {"is_stock_item": 0}, "name")
        expense_account = frappe.db.get_value("Account", {
            "company": company,
            "root_type": "Expense",
            "is_group": 0
        }, "name")
        
        # Create invoice
        pi = frappe.new_doc("Purchase Invoice")
        pi.company = company
        pi.supplier = supplier
        pi.posting_date = posting_date
        pi.bill_date = bill_date
        pi.due_date = due_date
        pi.credit_to = credit_to
        pi.eboekhouden_invoice_number = "DEBUG-TEST"
        
        pi.append("items", {
            "item_code": item,
            "qty": 1,
            "rate": 100,
            "expense_account": expense_account,
            "cost_center": cost_center
        })
        
        # Try to validate
        try:
            pi.validate()
            results["validation_result"] = "Success"
        except Exception as e:
            results["validation_error"] = str(e)
            
            # Try to get more details about the error
            import traceback
            results["traceback"] = traceback.format_exc()
            
    except Exception as e:
        results["setup_error"] = str(e)
    
    # Test with different dates
    test_cases = []
    for days_offset in [0, 1, 7, 30, -1, -7]:
        test_bill_date = add_days(posting_date, days_offset)
        test_due_date = add_days(test_bill_date, 30)
        
        test_cases.append({
            "days_offset": days_offset,
            "bill_date": test_bill_date,
            "due_date": test_due_date,
            "comparison": getdate(test_due_date) >= getdate(test_bill_date)
        })
    
    results["test_cases"] = test_cases
    
    # Check what parse_date actually returns
    from verenigingen.utils.eboekhouden_soap_migration import parse_date
    
    test_dates = [
        "2025-03-03T00:00:00",
        "2025-03-03",
        "2025-03-03 00:00:00",
        None,
        ""
    ]
    
    parsed_results = []
    for date_str in test_dates:
        try:
            parsed = parse_date(date_str)
            parsed_results.append({
                "input": date_str,
                "output": parsed,
                "type": type(parsed).__name__,
                "getdate": str(getdate(parsed)) if parsed else None
            })
        except Exception as e:
            parsed_results.append({
                "input": date_str,
                "error": str(e)
            })
    
    results["parse_date_tests"] = parsed_results
    
    return results

if __name__ == "__main__":
    print(debug_invoice_validation())