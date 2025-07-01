import frappe
from frappe import _

@frappe.whitelist()
def test_import_single_invoice():
    """Test importing a single invoice to debug the due date issue"""
    
    from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    from verenigingen.utils.eboekhouden_soap_migration import parse_date, get_or_create_customer, get_or_create_item, get_account_by_code
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenSOAPAPI(settings)
    company = settings.default_company
    
    # Get cost center
    cost_center = frappe.db.get_value("Cost Center", {
        "company": company,
        "cost_center_name": "Main",
        "is_group": 0
    }, "name")
    
    if not cost_center:
        return {"error": "No cost center found"}
    
    result = api.get_mutations(date_from="2025-05-01", date_to="2025-05-31")
    
    if not result["success"]:
        return {"error": result.get("error")}
    
    # Find a FactuurVerstuurd mutation
    for mut in result["mutations"]:
        if mut.get("Soort") == "FactuurVerstuurd":
            invoice_no = mut.get("Factuurnummer")
            
            # Skip if already imported
            if frappe.db.exists("Sales Invoice", {"eboekhouden_invoice_number": invoice_no}):
                continue
            
            try:
                # Parse mutation data
                posting_date = parse_date(mut.get("Datum"))
                customer_code = mut.get("RelatieCode")
                description = mut.get("Omschrijving", "")
                
                # Get or create customer
                customer = get_or_create_customer(customer_code, description)
                
                # Create sales invoice
                si = frappe.new_doc("Sales Invoice")
                si.company = company
                si.customer = customer
                si.posting_date = posting_date
                
                # Payment terms handling
                payment_terms_str = mut.get("Betalingstermijn", "30")
                try:
                    payment_terms = int(payment_terms_str)
                except:
                    payment_terms = 30
                
                # Calculate due date
                si.due_date = frappe.utils.add_days(posting_date, max(0, payment_terms))
                
                si.eboekhouden_invoice_number = invoice_no
                si.remarks = description
                
                # Add line items from MutatieRegels
                for regel in mut.get("MutatieRegels", []):
                    amount = float(regel.get("BedragExclBTW", 0))
                    if amount > 0:
                        si.append("items", {
                            "item_code": get_or_create_item(regel.get("TegenrekeningCode")),
                            "qty": 1,
                            "rate": amount,
                            "income_account": get_account_by_code(regel.get("TegenrekeningCode"), company)
                        })
                
                # Try to insert - this is where the error should happen
                si.insert(ignore_permissions=True)
                
                return {
                    "success": True,
                    "invoice": si.name,
                    "posting_date": str(si.posting_date),
                    "due_date": str(si.due_date),
                    "payment_terms": payment_terms
                }
                
            except Exception as e:
                import traceback
                return {
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "invoice_no": invoice_no,
                    "posting_date": str(posting_date),
                    "payment_terms": payment_terms_str,
                    "calculated_due_date": str(frappe.utils.add_days(posting_date, max(0, int(payment_terms_str) if payment_terms_str.isdigit() else 30))),
                    "mutation": mut
                }
    
    return {"error": "No unimported invoices found"}