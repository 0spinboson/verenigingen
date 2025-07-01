"""
Test unreconciled payment creation
"""

import frappe
from frappe import _


@frappe.whitelist()
def test_unreconciled_payment_creation():
    """
    Test creating unreconciled payments from sample E-Boekhouden data
    """
    from verenigingen.utils.create_unreconciled_payment import create_unreconciled_payment_entry
    
    company = frappe.db.get_single_value("E-Boekhouden Settings", "default_company")
    cost_center = frappe.db.get_value("Cost Center", {
        "company": company,
        "is_group": 0
    }, "name")
    
    if not company or not cost_center:
        return {"error": "Company or cost center not configured"}
    
    # Test data for customer payment without matching invoice
    customer_mutation = {
        "MutatieNr": "TEST-001",
        "Soort": "FactuurbetalingOntvangen",
        "Datum": "2025-01-15",
        "Factuurnummer": "NONEXISTENT-001",
        "RelatieCode": "TEST-CUST-001",
        "Omschrijving": "Test Customer Payment - Should create unreconciled PE",
        "MutatieRegels": [
            {
                "BedragInclBTW": 150.00
            }
        ],
        "Rekening": "1000"  # Bank account code
    }
    
    # Test data for supplier payment without matching invoice
    supplier_mutation = {
        "MutatieNr": "TEST-002",
        "Soort": "FactuurbetalingVerstuurd",
        "Datum": "2025-01-16",
        "Factuurnummer": "NONEXISTENT-002",
        "RelatieCode": "TEST-SUPP-001",
        "Omschrijving": "Test Supplier Payment - Should create unreconciled PE",
        "MutatieRegels": [
            {
                "BedragInvoer": 250.00
            }
        ],
        "Rekening": "1000"
    }
    
    results = {
        "customer_payment": None,
        "supplier_payment": None,
        "errors": []
    }
    
    # Test customer payment
    try:
        result = create_unreconciled_payment_entry(customer_mutation, company, cost_center, "Customer")
        if result["success"]:
            results["customer_payment"] = result["payment_entry"]
            # Verify it was created correctly
            pe = frappe.get_doc("Payment Entry", result["payment_entry"])
            results["customer_details"] = {
                "name": pe.name,
                "title": pe.title,
                "party": pe.party,
                "amount": pe.paid_amount,
                "has_unreconciled_tag": "[UNRECONCILED]" in pe.title,
                "invoice_in_remarks": "NONEXISTENT-001" in (pe.remarks or "")
            }
        else:
            results["errors"].append(f"Customer payment: {result['error']}")
    except Exception as e:
        results["errors"].append(f"Customer payment exception: {str(e)}")
    
    # Test supplier payment
    try:
        result = create_unreconciled_payment_entry(supplier_mutation, company, cost_center, "Supplier")
        if result["success"]:
            results["supplier_payment"] = result["payment_entry"]
            # Verify it was created correctly
            pe = frappe.get_doc("Payment Entry", result["payment_entry"])
            results["supplier_details"] = {
                "name": pe.name,
                "title": pe.title,
                "party": pe.party,
                "amount": pe.paid_amount,
                "has_unreconciled_tag": "[UNRECONCILED]" in pe.title,
                "invoice_in_remarks": "NONEXISTENT-002" in (pe.remarks or "")
            }
        else:
            results["errors"].append(f"Supplier payment: {result['error']}")
    except Exception as e:
        results["errors"].append(f"Supplier payment exception: {str(e)}")
    
    # Check if we can find these unreconciled payments
    from verenigingen.api.reconcile_unmatched_payments import get_unreconciled_summary
    results["unreconciled_summary"] = get_unreconciled_summary()
    
    return results


@frappe.whitelist()
def cleanup_test_payments():
    """
    Clean up test payment entries
    """
    test_payments = frappe.get_all("Payment Entry", 
        filters={
            "reference_no": ["in", ["TEST-001", "TEST-002"]],
            "docstatus": 1
        },
        fields=["name"]
    )
    
    cancelled = []
    for payment in test_payments:
        try:
            pe = frappe.get_doc("Payment Entry", payment.name)
            pe.cancel()
            cancelled.append(payment.name)
        except Exception as e:
            frappe.log_error(f"Failed to cancel {payment.name}: {str(e)}")
    
    # Also clean up test customers/suppliers
    test_customers = frappe.get_all("Customer",
        filters={"customer_name": ["like", "%TEST-%"]},
        fields=["name"]
    )
    
    test_suppliers = frappe.get_all("Supplier",
        filters={"supplier_name": ["like", "%TEST-%"]},
        fields=["name"]
    )
    
    deleted = []
    for cust in test_customers:
        try:
            frappe.delete_doc("Customer", cust.name, ignore_permissions=True)
            deleted.append(f"Customer: {cust.name}")
        except:
            pass
    
    for supp in test_suppliers:
        try:
            frappe.delete_doc("Supplier", supp.name, ignore_permissions=True)
            deleted.append(f"Supplier: {supp.name}")
        except:
            pass
    
    return {
        "cancelled_payments": cancelled,
        "deleted_parties": deleted
    }