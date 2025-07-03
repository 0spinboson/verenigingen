"""
Trace exactly where invoice creation is failing
"""

import frappe
from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
from verenigingen.utils.eboekhouden_soap_migration import (
    process_sales_invoices, process_purchase_invoices,
    get_or_create_supplier, get_or_create_item, get_account_by_code,
    parse_date
)
from frappe.utils import add_days, getdate

@frappe.whitelist()
def trace_single_invoice():
    """Trace a single invoice creation step by step"""
    try:
        # Get settings
        settings = frappe.get_single("E-Boekhouden Settings")
        company = settings.default_company
        
        # Get a cost center
        cost_center = frappe.db.get_value("Cost Center", {
            "company": company,
            "is_group": 0
        }, "name")
        
        # Test data - a failing purchase invoice
        test_mut = {
            "MutatieNr": "7297",
            "Soort": "FactuurOntvangen",
            "Datum": "2025-03-03T00:00:00",
            "Rekening": "19290",
            "RelatieCode": "00019",
            "Factuurnummer": "TEST-20250304",
            "Betalingstermijn": "30",
            "InExBTW": "EX",
            "Omschrijving": "Test invoice",
            "MutatieRegels": [
                {
                    "BedragInvoer": "98",
                    "BedragExclBTW": "98",
                    "BedragBTW": "0.0000",
                    "BedragInclBTW": "98.0000",
                    "BTWCode": "GEEN",
                    "BTWPercentage": "0.0000",
                    "Factuurnummer": "TEST-20250304",
                    "TegenrekeningCode": "44003",
                    "KostenplaatsID": "0"
                }
            ]
        }
        
        trace = {"steps": []}
        
        # Step 1: Parse date
        posting_date = parse_date(test_mut.get("Datum"))
        trace["steps"].append({
            "step": "Parse date",
            "input": test_mut.get("Datum"),
            "output": posting_date,
            "type": type(posting_date).__name__
        })
        
        # Step 2: Get supplier
        supplier_code = test_mut.get("RelatieCode")
        supplier = get_or_create_supplier(supplier_code, test_mut.get("Omschrijving", ""))
        trace["steps"].append({
            "step": "Get supplier",
            "code": supplier_code,
            "supplier": supplier
        })
        
        # Step 3: Create invoice object
        pi = frappe.new_doc("Purchase Invoice")
        pi.company = company
        pi.supplier = supplier
        pi.posting_date = posting_date
        pi.eboekhouden_invoice_number = test_mut.get("Factuurnummer")
        pi.remarks = test_mut.get("Omschrijving", "")
        
        trace["steps"].append({
            "step": "Create invoice",
            "posting_date": pi.posting_date,
            "supplier": pi.supplier
        })
        
        # Step 4: Calculate due date
        payment_terms = int(test_mut.get("Betalingstermijn", 30))
        calculated_due_date = add_days(posting_date, payment_terms)
        
        trace["steps"].append({
            "step": "Calculate due date",
            "payment_terms": payment_terms,
            "calculated": calculated_due_date,
            "comparison": getdate(calculated_due_date) >= getdate(posting_date)
        })
        
        if getdate(calculated_due_date) < getdate(posting_date):
            pi.due_date = posting_date
        else:
            pi.due_date = calculated_due_date
            
        trace["steps"].append({
            "step": "Set due date",
            "final_due_date": pi.due_date
        })
        
        # Step 5: Set accounts
        rekening_code = test_mut.get("Rekening")
        if rekening_code:
            credit_account = get_account_by_code(rekening_code, company)
            if credit_account:
                pi.credit_to = credit_account
            else:
                default_payable = frappe.db.get_value("Company", company, "default_payable_account")
                if default_payable:
                    pi.credit_to = default_payable
                    
        trace["steps"].append({
            "step": "Set credit account",
            "rekening_code": rekening_code,
            "credit_to": pi.credit_to
        })
        
        # Step 6: Add line items
        pi.cost_center = cost_center
        for regel in test_mut.get("MutatieRegels", []):
            amount = float(regel.get("BedragExclBTW", 0))
            if amount > 0:
                item_code = get_or_create_item(regel.get("TegenrekeningCode"))
                expense_account = get_account_by_code(regel.get("TegenrekeningCode"), company)
                
                pi.append("items", {
                    "item_code": item_code,
                    "qty": 1,
                    "rate": amount,
                    "expense_account": expense_account,
                    "cost_center": cost_center
                })
                
                trace["steps"].append({
                    "step": "Add line item",
                    "item": item_code,
                    "amount": amount,
                    "expense_account": expense_account
                })
        
        # Step 7: Try to insert
        try:
            # First validate
            pi.validate()
            trace["validation"] = "Success"
            
            # Don't actually insert to avoid test data
            trace["would_insert"] = True
            
        except Exception as e:
            trace["validation_error"] = str(e)
            trace["error_type"] = type(e).__name__
            
            # Try to get more details
            if hasattr(e, 'args') and len(e.args) > 0:
                trace["error_details"] = e.args[0]
        
        return trace
        
    except Exception as e:
        return {"error": str(e), "trace": trace if 'trace' in locals() else None}

if __name__ == "__main__":
    import json
    print(json.dumps(trace_single_invoice(), indent=2))