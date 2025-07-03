"""
Debug a specific failed invoice from the migration
"""

import frappe
from verenigingen.utils.eboekhouden_soap_migration import parse_date, get_or_create_supplier, get_or_create_item, get_account_by_code, get_expense_account_by_code
from frappe.utils import add_days, getdate

@frappe.whitelist()
def debug_specific_invoice():
    """Debug invoice that's failing with the exact migration data"""
    
    # Use the exact data from the failed record
    mut = {
        "MutatieNr": "7297",
        "Soort": "FactuurOntvangen",
        "Datum": "2025-03-03T00:00:00",
        "Rekening": "19290",
        "RelatieCode": "00019",
        "Factuurnummer": "20250304",
        "Betalingstermijn": "30",
        "InExBTW": "EX",
        "MutatieRegels": [
            {
                "BedragInvoer": "98",
                "BedragExclBTW": "98",
                "BedragBTW": "0.0000",
                "BedragInclBTW": "98.0000",
                "BTWCode": "GEEN",
                "BTWPercentage": "0.0000",
                "Factuurnummer": "20250304",
                "TegenrekeningCode": "44003",
                "KostenplaatsID": "0"
            }
        ]
    }
    
    company = "R S P"
    cost_center = frappe.db.get_value("Cost Center", {"company": company, "is_group": 0}, "name")
    
    result = {"steps": []}
    
    # Step 1: Parse the date
    posting_date = parse_date(mut.get("Datum"))
    result["steps"].append({
        "step": "Parse posting date",
        "input": mut.get("Datum"),
        "output": posting_date,
        "type": type(posting_date).__name__
    })
    
    # Step 2: Get supplier
    supplier_code = mut.get("RelatieCode")
    description = mut.get("Omschrijving", "")
    supplier = get_or_create_supplier(supplier_code, description)
    result["steps"].append({
        "step": "Get supplier",
        "code": supplier_code,
        "supplier": supplier
    })
    
    # Step 3: Parse payment terms
    try:
        payment_terms = int(mut.get("Betalingstermijn", 30))
    except (ValueError, TypeError):
        payment_terms = 30
    
    if payment_terms < 0:
        payment_terms = 0
    
    result["steps"].append({
        "step": "Parse payment terms",
        "input": mut.get("Betalingstermijn"),
        "output": payment_terms
    })
    
    # Step 4: Calculate due date
    calculated_due_date = add_days(posting_date, payment_terms)
    result["steps"].append({
        "step": "Calculate due date",
        "posting_date": posting_date,
        "payment_terms": payment_terms,
        "calculated": calculated_due_date,
        "calculated_type": type(calculated_due_date).__name__
    })
    
    # Step 5: Check the comparison
    if getdate(calculated_due_date) < getdate(posting_date):
        final_due_date = posting_date
    else:
        final_due_date = calculated_due_date
    
    result["steps"].append({
        "step": "Due date comparison",
        "calculated_due_date": calculated_due_date,
        "posting_date": posting_date,
        "comparison": getdate(calculated_due_date) >= getdate(posting_date),
        "final_due_date": final_due_date
    })
    
    # Step 6: Create the invoice as the migration does
    try:
        pi = frappe.new_doc("Purchase Invoice")
        pi.company = company
        pi.supplier = supplier
        pi.posting_date = posting_date
        pi.bill_date = posting_date  # Set bill_date same as posting_date
        pi.eboekhouden_invoice_number = mut.get("Factuurnummer") + "-DEBUG"
        pi.remarks = description
        pi.due_date = final_due_date
        
        result["invoice_data"] = {
            "posting_date": pi.posting_date,
            "bill_date": pi.bill_date,
            "due_date": pi.due_date,
            "posting_date_type": type(pi.posting_date).__name__,
            "bill_date_type": type(pi.bill_date).__name__,
            "due_date_type": type(pi.due_date).__name__
        }
        
        # Set the credit account
        rekening_code = mut.get("Rekening")
        if rekening_code:
            credit_account = get_account_by_code(rekening_code, company)
            if credit_account:
                pi.credit_to = credit_account
            else:
                default_payable = frappe.db.get_value("Company", company, "default_payable_account")
                if default_payable:
                    pi.credit_to = default_payable
        
        pi.cost_center = cost_center
        
        # Add line items
        for regel in mut.get("MutatieRegels", []):
            amount = float(regel.get("BedragExclBTW", 0))
            if amount > 0:
                pi.append("items", {
                    "item_code": get_or_create_item(regel.get("TegenrekeningCode")),
                    "qty": 1,
                    "rate": amount,
                    "expense_account": get_expense_account_by_code(regel.get("TegenrekeningCode"), company),
                    "cost_center": cost_center
                })
        
        # Try to validate
        try:
            pi.validate()
            result["validation"] = "Success"
        except Exception as e:
            result["validation_error"] = str(e)
            
            # Check what dates are being compared in the validation
            validation_posting_date = pi.bill_date or pi.posting_date
            result["validation_details"] = {
                "validation_posting_date": validation_posting_date,
                "due_date": pi.due_date,
                "comparison": getdate(pi.due_date) >= getdate(validation_posting_date),
                "getdate_due": str(getdate(pi.due_date)),
                "getdate_validation_posting": str(getdate(validation_posting_date))
            }
            
    except Exception as e:
        result["creation_error"] = str(e)
    
    return result

if __name__ == "__main__":
    print(debug_specific_invoice())