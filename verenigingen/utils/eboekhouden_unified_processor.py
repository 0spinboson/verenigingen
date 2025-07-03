"""
Unified processor for E-boekhouden mutations using native transaction types
"""

import frappe
from frappe import _
from frappe.utils import getdate, flt

def process_sales_invoices(mutations, company, cost_center, migration_doc):
    """Process Sales Invoice mutations"""
    created = 0
    errors = []
    
    for mut in mutations:
        try:
            # Create Sales Invoice
            si = frappe.new_doc("Sales Invoice")
            si.customer = get_or_create_customer(mut)
            si.posting_date = getdate(mut.get("date"))
            si.company = company
            
            # Fix receivable account mapping: use "Te ontvangen bedragen" (13900) instead of "Te ontvangen contributies" (13500)
            # This ensures sales invoices use the correct receivable account for general amounts, not contributions
            correct_receivable_account = get_correct_receivable_account(company)
            if correct_receivable_account:
                si.debit_to = correct_receivable_account
            
            # Add line item
            si.append("items", {
                "item_code": get_default_item("income"),
                "qty": 1,
                "rate": abs(flt(mut.get("amount", 0)))
            })
            
            si.insert(ignore_permissions=True)
            si.submit()
            created += 1
            
        except Exception as e:
            errors.append(f"SI {mut.get('id')}: {str(e)}")
    
    return {"created": created, "errors": errors}

def process_purchase_invoices(mutations, company, cost_center, migration_doc):
    """Process Purchase Invoice mutations"""
    created = 0
    errors = []
    
    for mut in mutations:
        try:
            # Create Purchase Invoice
            pi = frappe.new_doc("Purchase Invoice")
            pi.supplier = get_or_create_supplier(mut)
            pi.posting_date = getdate(mut.get("date"))
            pi.company = company
            pi.cost_center = cost_center
            
            # Add line item
            pi.append("items", {
                "item_code": get_default_item("expense"),
                "qty": 1,
                "rate": abs(flt(mut.get("amount", 0))),
                "cost_center": cost_center
            })
            
            pi.insert(ignore_permissions=True)
            pi.submit()
            created += 1
            
        except Exception as e:
            errors.append(f"PI {mut.get('id')}: {str(e)}")
    
    return {"created": created, "errors": errors}

def process_payment_entries(mutations, company, cost_center, migration_doc):
    """Process Payment Entry mutations"""
    created = 0
    errors = []
    
    for mut in mutations:
        try:
            mapping_info = mut.get("_mapping_info", {})
            reference_type = mapping_info.get("reference_type")
            
            # Create Payment Entry
            pe = frappe.new_doc("Payment Entry")
            pe.payment_type = "Receive" if reference_type == "Sales Invoice" else "Pay"
            pe.posting_date = getdate(mut.get("date"))
            pe.company = company
            
            if reference_type == "Sales Invoice":
                pe.party_type = "Customer"
                pe.party = get_or_create_customer(mut)
            else:
                pe.party_type = "Supplier"
                pe.party = get_or_create_supplier(mut)
            
            pe.paid_amount = abs(flt(mut.get("amount", 0)))
            pe.received_amount = pe.paid_amount
            
            pe.insert(ignore_permissions=True)
            pe.submit()
            created += 1
            
        except Exception as e:
            errors.append(f"PE {mut.get('id')}: {str(e)}")
    
    return {"created": created, "errors": errors}

def process_journal_entries_grouped(mutations, company, cost_center, migration_doc):
    """Process Journal Entry mutations, grouping by entry number"""
    # Group by entry number first
    entry_groups = {}
    for mut in mutations:
        entry_num = mut.get("entryNumber", "SINGLE")
        if entry_num not in entry_groups:
            entry_groups[entry_num] = []
        entry_groups[entry_num].append(mut)
    
    created = 0
    errors = []
    
    for entry_num, muts in entry_groups.items():
        try:
            # Create balanced journal entry
            je = frappe.new_doc("Journal Entry")
            je.posting_date = getdate(muts[0].get("date"))
            je.company = company
            
            for mut in muts:
                je.append("accounts", {
                    "account": get_account_from_ledger(mut),
                    "debit_in_account_currency": flt(mut.get("debit", 0)),
                    "credit_in_account_currency": flt(mut.get("credit", 0)),
                    "cost_center": cost_center
                })
            
            je.insert(ignore_permissions=True)
            je.submit()
            created += 1
            
        except Exception as e:
            errors.append(f"JE {entry_num}: {str(e)}")
    
    return {"created": created, "errors": errors}

# Helper functions (simplified stubs)
def get_or_create_customer(mutation):
    return "Guest"

def get_or_create_supplier(mutation):
    return frappe.db.get_value("Supplier", {"supplier_name": "Miscellaneous"}) or "Miscellaneous"

def get_default_item(item_type):
    return "ITEM-001"

def get_account_from_ledger(mutation):
    return frappe.db.get_value("Account", {"is_group": 0}, "name")

def get_correct_receivable_account(company):
    """
    Get the correct receivable account for sales invoices.
    Returns "Te ontvangen bedragen" (13900) instead of "Te ontvangen contributies" (13500)
    since normal sales invoices should not be categorized as contributions.
    """
    try:
        # Import here to avoid circular imports
        from verenigingen.api.fix_sales_invoice_receivables import get_receivable_account_mapping
        return get_receivable_account_mapping(company)
    except ImportError:
        # Fallback if the module is not available
        return frappe.db.get_value("Account", 
            {"account_number": "13900", "company": company}, "name")