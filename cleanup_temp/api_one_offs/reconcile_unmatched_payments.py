"""
Reconcile unmatched payments from E-Boekhouden
"""

import frappe
from frappe import _


@frappe.whitelist()
def get_unreconciled_payments():
    """
    Get all unreconciled payment entries from E-Boekhouden import
    """
    company = frappe.db.get_single_value("E-Boekhouden Settings", "default_company")
    if not company:
        return {"error": "No default company set"}
    
    # Find payment entries with [UNRECONCILED] in title
    unreconciled = frappe.db.sql("""
        SELECT 
            pe.name,
            pe.posting_date,
            pe.payment_type,
            pe.party_type,
            pe.party,
            pe.paid_amount,
            pe.reference_no,
            pe.title,
            pe.remarks,
            pe.eboekhouden_invoice_number
        FROM `tabPayment Entry` pe
        WHERE pe.company = %s
        AND pe.docstatus = 1
        AND pe.title LIKE '%%[UNRECONCILED]%%'
        ORDER BY pe.posting_date DESC
    """, company, as_dict=True)
    
    # Extract invoice numbers from remarks
    for payment in unreconciled:
        if payment.remarks and "Unreconciled Invoice:" in payment.remarks:
            # Extract invoice number
            parts = payment.remarks.split("Unreconciled Invoice:")
            if len(parts) > 1:
                payment["unreconciled_invoice"] = parts[1].strip().split("\n")[0]
        elif payment.eboekhouden_invoice_number:
            payment["unreconciled_invoice"] = payment.eboekhouden_invoice_number
    
    # Group by party type
    grouped = {
        "customer_payments": [],
        "supplier_payments": [],
        "total_count": len(unreconciled),
        "total_amount": sum(p.paid_amount for p in unreconciled)
    }
    
    for payment in unreconciled:
        if payment.payment_type == "Receive":
            grouped["customer_payments"].append(payment)
        else:
            grouped["supplier_payments"].append(payment)
    
    return grouped


@frappe.whitelist()
def attempt_auto_reconciliation():
    """
    Attempt to automatically reconcile unmatched payments with invoices
    """
    company = frappe.db.get_single_value("E-Boekhouden Settings", "default_company")
    if not company:
        return {"error": "No default company set"}
    
    reconciled = []
    errors = []
    
    # Get unreconciled payments
    result = get_unreconciled_payments()
    all_payments = result.get("customer_payments", []) + result.get("supplier_payments", [])
    
    for payment in all_payments:
        try:
            invoice_no = payment.get("unreconciled_invoice") or payment.get("eboekhouden_invoice_number")
            if not invoice_no:
                continue
            
            # Try to find matching invoice
            if payment["payment_type"] == "Receive":
                # Look for sales invoice
                si_name = frappe.db.get_value("Sales Invoice", {
                    "eboekhouden_invoice_number": invoice_no,
                    "company": company
                }, "name")
                
                if si_name:
                    # Found matching invoice, attempt to reconcile
                    result = reconcile_payment_with_invoice(payment["name"], si_name, "Sales Invoice")
                    if result["success"]:
                        reconciled.append({
                            "payment": payment["name"],
                            "invoice": si_name,
                            "type": "Customer Payment"
                        })
                    else:
                        errors.append(result["error"])
                        
            else:  # Pay
                # Look for purchase invoice
                pi_name = frappe.db.get_value("Purchase Invoice", {
                    "eboekhouden_invoice_number": invoice_no,
                    "company": company
                }, "name")
                
                if pi_name:
                    # Found matching invoice, attempt to reconcile
                    result = reconcile_payment_with_invoice(payment["name"], pi_name, "Purchase Invoice")
                    if result["success"]:
                        reconciled.append({
                            "payment": payment["name"],
                            "invoice": pi_name,
                            "type": "Supplier Payment"
                        })
                    else:
                        errors.append(result["error"])
                        
        except Exception as e:
            errors.append(f"Payment {payment['name']}: {str(e)}")
    
    return {
        "reconciled": reconciled,
        "reconciled_count": len(reconciled),
        "errors": errors,
        "message": f"Reconciled {len(reconciled)} payments"
    }


def reconcile_payment_with_invoice(payment_name, invoice_name, invoice_type):
    """
    Reconcile a payment entry with an invoice
    """
    try:
        # Get the payment entry
        pe = frappe.get_doc("Payment Entry", payment_name)
        
        # Check if already has references
        if pe.references:
            return {"success": False, "error": "Payment already has references"}
        
        # Get the invoice
        invoice = frappe.get_doc(invoice_type, invoice_name)
        
        # Verify party matches
        if invoice_type == "Sales Invoice":
            if pe.party != invoice.customer:
                return {"success": False, "error": f"Party mismatch: Payment party {pe.party} != Invoice customer {invoice.customer}"}
        else:  # Purchase Invoice
            if pe.party != invoice.supplier:
                return {"success": False, "error": f"Party mismatch: Payment party {pe.party} != Invoice supplier {invoice.supplier}"}
        
        # Cancel the payment to modify
        pe.cancel()
        
        # Create new payment entry with reference
        new_pe = frappe.copy_doc(pe)
        new_pe.title = new_pe.title.replace("[UNRECONCILED] ", "")
        
        # Add reference to invoice
        new_pe.append("references", {
            "reference_doctype": invoice_type,
            "reference_name": invoice_name,
            "allocated_amount": new_pe.paid_amount
        })
        
        # Update remarks
        if new_pe.remarks:
            new_pe.remarks = new_pe.remarks.replace("\n\nUnreconciled Invoice:", "\n\nReconciled with Invoice:")
        
        new_pe.insert(ignore_permissions=True)
        new_pe.submit()
        
        return {"success": True, "new_payment": new_pe.name}
        
    except Exception as e:
        frappe.log_error(f"Failed to reconcile payment {payment_name} with {invoice_name}: {str(e)}")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def get_unreconciled_summary():
    """
    Get a summary of unreconciled payments
    """
    company = frappe.db.get_single_value("E-Boekhouden Settings", "default_company")
    if not company:
        return {"error": "No default company set"}
    
    # Count unreconciled payments
    unreconciled_count = frappe.db.count("Payment Entry", {
        "company": company,
        "docstatus": 1,
        "title": ["like", "%[UNRECONCILED]%"]
    })
    
    # Get total amounts
    amounts = frappe.db.sql("""
        SELECT 
            payment_type,
            SUM(paid_amount) as total_amount,
            COUNT(*) as count
        FROM `tabPayment Entry`
        WHERE company = %s
        AND docstatus = 1
        AND title LIKE '%%[UNRECONCILED]%%'
        GROUP BY payment_type
    """, company, as_dict=True)
    
    summary = {
        "total_unreconciled": unreconciled_count,
        "customer_payments": {"count": 0, "amount": 0},
        "supplier_payments": {"count": 0, "amount": 0}
    }
    
    for row in amounts:
        if row.payment_type == "Receive":
            summary["customer_payments"] = {
                "count": row.count,
                "amount": row.total_amount
            }
        else:
            summary["supplier_payments"] = {
                "count": row.count,
                "amount": row.total_amount
            }
    
    # Get date range
    date_range = frappe.db.sql("""
        SELECT 
            MIN(posting_date) as earliest,
            MAX(posting_date) as latest
        FROM `tabPayment Entry`
        WHERE company = %s
        AND docstatus = 1
        AND title LIKE '%%[UNRECONCILED]%%'
    """, company, as_dict=True)
    
    if date_range and date_range[0].earliest:
        summary["date_range"] = {
            "earliest": str(date_range[0].earliest),
            "latest": str(date_range[0].latest)
        }
    
    return summary