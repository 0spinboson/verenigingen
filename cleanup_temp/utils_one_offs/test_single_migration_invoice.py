"""
Test migrating a single purchase invoice
"""

import frappe
from verenigingen.utils.eboekhouden_soap_migration import process_purchase_invoices

@frappe.whitelist() 
def test_single_migration():
    """Test migrating one invoice that was failing"""
    
    # Use exact data from failed record
    test_mutation = {
        "MutatieNr": "7297",
        "Soort": "FactuurOntvangen", 
        "Datum": "2025-03-03T00:00:00",
        "Rekening": "19290",
        "RelatieCode": "00019",
        "Factuurnummer": "20250304-TEST",  # Add TEST suffix to avoid duplicate
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
                "Factuurnummer": "20250304-TEST",
                "TegenrekeningCode": "44003",
                "KostenplaatsID": "0"
            }
        ]
    }
    
    company = "R S P"
    cost_center = frappe.db.get_value("Cost Center", {"company": company, "is_group": 0}, "name")
    
    # Create a mock migration doc
    class MockMigrationDoc:
        def log_error(self, message, record_type, data):
            print(f"ERROR: {message}")
    
    migration_doc = MockMigrationDoc()
    
    # Process the single mutation
    result = process_purchase_invoices([test_mutation], company, cost_center, migration_doc)
    
    # Clean up if successful
    if result["created"] > 0:
        invoice = frappe.db.get_value("Purchase Invoice", {"eboekhouden_invoice_number": "20250304-TEST"}, "name")
        if invoice:
            # Get the invoice to check its data
            pi = frappe.get_doc("Purchase Invoice", invoice)
            invoice_data = {
                "name": pi.name,
                "posting_date": pi.posting_date,
                "bill_date": pi.bill_date,
                "due_date": pi.due_date,
                "supplier": pi.supplier,
                "total": pi.total
            }
            # Delete it
            frappe.delete_doc("Purchase Invoice", invoice)
            frappe.db.commit()
            result["invoice_data"] = invoice_data
    
    return result

if __name__ == "__main__":
    print(test_single_migration())