import frappe
from frappe import _
from datetime import datetime

@frappe.whitelist()
def debug_sales_invoice_dates():
    """Debug the due date validation issue"""
    
    from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenSOAPAPI(settings)
    
    result = api.get_mutations(date_from="2025-05-01", date_to="2025-05-31")
    
    if not result["success"]:
        return {"error": result.get("error")}
    
    # Find a sales invoice that would have issues
    problematic_invoices = []
    
    for mut in result["mutations"]:
        if mut.get("Soort") == "FactuurVerstuurd":
            invoice_no = mut.get("Factuurnummer")
            date_str = mut.get("Datum")
            payment_terms_str = mut.get("Betalingstermijn", "30")
            
            # Parse the date
            if date_str and 'T' in date_str:
                posting_date = datetime.strptime(date_str.split('T')[0], '%Y-%m-%d').date()
            else:
                posting_date = frappe.utils.today()
            
            # Parse payment terms
            try:
                payment_terms = int(payment_terms_str)
            except:
                payment_terms = 30
            
            # Calculate due date
            due_date = frappe.utils.add_days(posting_date, max(0, payment_terms))
            
            # Check if this would fail validation
            if frappe.utils.getdate(due_date) < frappe.utils.getdate(posting_date):
                problematic_invoices.append({
                    "invoice": invoice_no,
                    "date_str": date_str,
                    "posting_date": str(posting_date),
                    "payment_terms": payment_terms,
                    "due_date": str(due_date),
                    "issue": "Due date is before posting date!"
                })
            elif payment_terms == 0:
                problematic_invoices.append({
                    "invoice": invoice_no,
                    "date_str": date_str,
                    "posting_date": str(posting_date),
                    "payment_terms": payment_terms,
                    "due_date": str(due_date),
                    "note": "Zero payment terms"
                })
    
    # Also check existing Sales Invoices
    existing_issues = []
    sales_invoices = frappe.get_all("Sales Invoice", 
        filters={
            "posting_date": ["between", ["2025-05-01", "2025-05-31"]],
            "docstatus": ["!=", 2]
        }, 
        fields=["name", "posting_date", "due_date", "eboekhouden_invoice_number"])
    
    for si in sales_invoices:
        if si.due_date and si.due_date < si.posting_date:
            existing_issues.append({
                "name": si.name,
                "eboekhouden_invoice": si.eboekhouden_invoice_number,
                "posting_date": str(si.posting_date),
                "due_date": str(si.due_date),
                "issue": "Due date is before posting date in existing record!"
            })
    
    return {
        "problematic_invoices": problematic_invoices[:10],
        "existing_issues": existing_issues[:10],
        "total_problematic": len(problematic_invoices),
        "total_existing_issues": len(existing_issues)
    }

@frappe.whitelist()
def check_specific_invoice(invoice_number):
    """Check a specific invoice for date issues"""
    
    from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenSOAPAPI(settings)
    
    result = api.get_mutations(date_from="2025-05-01", date_to="2025-05-31")
    
    if not result["success"]:
        return {"error": result.get("error")}
    
    for mut in result["mutations"]:
        if mut.get("Soort") == "FactuurVerstuurd" and mut.get("Factuurnummer") == invoice_number:
            date_str = mut.get("Datum")
            payment_terms_str = mut.get("Betalingstermijn", "30")
            
            # Parse the date multiple ways
            posting_date_parsed = None
            if date_str:
                if 'T' in date_str:
                    posting_date_parsed = datetime.strptime(date_str.split('T')[0], '%Y-%m-%d').date()
                else:
                    posting_date_parsed = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # Parse payment terms
            try:
                payment_terms = int(payment_terms_str)
            except:
                payment_terms = 30
            
            # Calculate due date multiple ways
            due_date_add_days = frappe.utils.add_days(posting_date_parsed, max(0, payment_terms))
            due_date_direct = frappe.utils.add_days(posting_date_parsed, payment_terms)
            
            # Check existing record
            existing_si = None
            if frappe.db.exists("Sales Invoice", {"eboekhouden_invoice_number": invoice_number}):
                existing_si = frappe.get_doc("Sales Invoice", {"eboekhouden_invoice_number": invoice_number})
            
            return {
                "mutation": mut,
                "date_str": date_str,
                "posting_date_parsed": str(posting_date_parsed),
                "payment_terms_str": payment_terms_str,
                "payment_terms_int": payment_terms,
                "due_date_add_days": str(due_date_add_days),
                "due_date_direct": str(due_date_direct),
                "max_0_payment_terms": max(0, payment_terms),
                "existing_si": {
                    "name": existing_si.name if existing_si else None,
                    "posting_date": str(existing_si.posting_date) if existing_si else None,
                    "due_date": str(existing_si.due_date) if existing_si else None,
                    "docstatus": existing_si.docstatus if existing_si else None
                } if existing_si else None
            }
    
    return {"error": f"Invoice {invoice_number} not found"}