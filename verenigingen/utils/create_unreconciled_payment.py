"""
Create unreconciled Payment Entries for E-Boekhouden payments without matching invoices
"""

import frappe
from frappe import _


def create_unreconciled_payment_entry(mutation, company, cost_center, payment_type="Customer"):
    """
    Create an unreconciled Payment Entry when invoice cannot be found
    
    Args:
        mutation: E-Boekhouden mutation data
        company: Company name
        cost_center: Cost center
        payment_type: "Customer" or "Supplier"
        
    Returns:
        dict with success status and created Payment Entry name or error
    """
    try:
        from .eboekhouden_payment_naming import get_payment_entry_title, enhance_payment_entry_fields
        from .eboekhouden_soap_migration import parse_date, get_bank_account, get_or_create_customer, get_or_create_supplier
        
        # Create payment entry
        pe = frappe.new_doc("Payment Entry")
        
        # Basic settings based on payment type
        if payment_type == "Customer":
            pe.payment_type = "Receive"
            pe.party_type = "Customer"
            
            # Try to identify customer from description or create generic one
            relation_code = mutation.get("RelatieCode")
            description = mutation.get("Omschrijving", "")
            
            if relation_code:
                pe.party = get_or_create_customer(relation_code, description)
            else:
                # Try to extract party info from description
                # For SEPA transfers, the description often contains the party name
                if description and len(description) > 10:
                    # Create customer based on description
                    customer_name = description[:50] + "..." if len(description) > 50 else description
                    customer_name = f"Unmatched Payment - {customer_name}"
                    
                    # Check if this customer already exists
                    existing = frappe.db.get_value("Customer", {"customer_name": customer_name}, "name")
                    if existing:
                        pe.party = existing
                    else:
                        # Create new customer
                        customer = frappe.new_doc("Customer")
                        customer.customer_name = customer_name
                        customer.customer_group = frappe.db.get_value("Customer Group", {"is_group": 0}, "name") or "All Customer Groups"
                        customer.territory = frappe.db.get_value("Territory", {"is_group": 0}, "name") or "All Territories"
                        customer.insert(ignore_permissions=True)
                        pe.party = customer.name
                else:
                    pe.party = get_or_create_customer("UNMATCHED", "Unmatched Customer Payment")
                    
        else:  # Supplier
            pe.payment_type = "Pay"
            pe.party_type = "Supplier"
            
            # Try to identify supplier
            relation_code = mutation.get("RelatieCode")
            description = mutation.get("Omschrijving", "")
            
            if relation_code:
                pe.party = get_or_create_supplier(relation_code, description)
            else:
                # Try to extract party info from description
                if description and len(description) > 10:
                    supplier_name = description[:50] + "..." if len(description) > 50 else description
                    supplier_name = f"Unmatched Payment - {supplier_name}"
                    
                    # Check if this supplier already exists
                    existing = frappe.db.get_value("Supplier", {"supplier_name": supplier_name}, "name")
                    if existing:
                        pe.party = existing
                    else:
                        # Create new supplier
                        supplier = frappe.new_doc("Supplier")
                        supplier.supplier_name = supplier_name
                        supplier.supplier_group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name") or "All Supplier Groups"
                        supplier.insert(ignore_permissions=True)
                        pe.party = supplier.name
                else:
                    pe.party = get_or_create_supplier("UNMATCHED", "Unmatched Supplier Payment")
        
        # Common fields
        pe.company = company
        pe.posting_date = parse_date(mutation.get("Datum"))
        pe.cost_center = cost_center
        
        # Set title with clear indication that it's unreconciled
        original_title = get_payment_entry_title(mutation, pe.party, pe.payment_type)
        if hasattr(pe, 'title'):
            pe.title = f"[UNRECONCILED] {original_title}"
        
        # Enhance with E-Boekhouden data
        pe = enhance_payment_entry_fields(pe, mutation)
        
        # Get amount from mutation lines
        total_amount = 0
        for regel in mutation.get("MutatieRegels", []):
            # Try different amount fields
            amount = float(regel.get("BedragInclBTW", 0) or regel.get("BedragInvoer", 0) or regel.get("BedragExclBTW", 0))
            total_amount += abs(amount)
        
        if total_amount == 0:
            return {"success": False, "error": "No amount found in mutation"}
        
        pe.paid_amount = total_amount
        pe.received_amount = total_amount
        
        # Set reference information
        pe.reference_no = mutation.get("MutatieNr")
        pe.reference_date = pe.posting_date
        
        # Add unreconciled invoice information to remarks
        invoice_no = mutation.get("Factuurnummer")
        if invoice_no:
            additional_remarks = f"\n\nUnreconciled Invoice: {invoice_no}"
            if pe.remarks:
                pe.remarks += additional_remarks
            else:
                pe.remarks = additional_remarks
        
        # Set bank accounts
        bank_code = mutation.get("Rekening")
        bank_account = get_bank_account(bank_code, company)
        
        if pe.payment_type == "Receive":
            pe.paid_to = bank_account
            # Set default receivable account
            default_receivable = frappe.db.get_value("Company", company, "default_receivable_account")
            if not default_receivable:
                # Find any receivable account
                default_receivable = frappe.db.get_value("Account", {
                    "company": company,
                    "account_type": "Receivable",
                    "is_group": 0
                }, "name")
            pe.paid_from = default_receivable
        else:  # Pay
            pe.paid_from = bank_account
            # Set default payable account
            default_payable = frappe.db.get_value("Company", company, "default_payable_account")
            if not default_payable:
                # Find any payable account
                default_payable = frappe.db.get_value("Account", {
                    "company": company,
                    "account_type": "Payable",
                    "is_group": 0
                }, "name")
            pe.paid_to = default_payable
        
        # Set mode of payment (optional)
        default_mode = frappe.db.get_value("Mode of Payment", {"type": "Bank"}, "name")
        if default_mode:
            pe.mode_of_payment = default_mode
        
        # Insert and submit
        pe.insert(ignore_permissions=True)
        pe.submit()
        
        return {"success": True, "payment_entry": pe.name}
        
    except Exception as e:
        frappe.log_error(f"Failed to create unreconciled payment: {str(e)}", "E-Boekhouden Unreconciled Payment")
        return {"success": False, "error": str(e)}