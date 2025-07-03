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
            
            # Set creditors account to avoid account currency validation errors
            creditors_account = get_creditors_account(company)
            if creditors_account:
                pi.credit_to = creditors_account
            
            # Get a proper expense account for this company
            expense_account = frappe.db.get_value("Account", {
                "company": company,
                "account_type": "Expense Account",
                "is_group": 0
            }, "name")
            
            # Add line item
            pi.append("items", {
                "item_code": get_default_item("expense"),
                "qty": 1,
                "rate": abs(flt(mut.get("amount", 0))),
                "cost_center": cost_center,
                "expense_account": expense_account  # Explicitly set expense account
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
    """Get or create supplier for mutation"""
    # Try to find existing supplier first 
    existing_supplier = frappe.db.get_value("Supplier", {"disabled": 0}, "name")
    if existing_supplier:
        return existing_supplier
    
    # Create a default supplier if none exists
    supplier_name = "Default Supplier"
    try:
        if not frappe.db.exists("Supplier", supplier_name):
            supplier = frappe.new_doc("Supplier")
            supplier.supplier_name = supplier_name
            supplier.supplier_group = "All Supplier Groups"
            supplier.insert(ignore_permissions=True)
            return supplier.name
        else:
            return supplier_name
    except Exception:
        # Fallback to any existing supplier
        return frappe.db.get_value("Supplier", {"disabled": 0}, "name")

def get_default_item(item_type):
    """Get default item for the given type"""
    # Try to find existing item first
    existing_item = frappe.db.get_value("Item", {"disabled": 0}, "name")
    if existing_item:
        return existing_item
    
    # Create a default item if none exists
    item_name = f"Default {item_type.title()} Item"
    try:
        if not frappe.db.exists("Item", item_name):
            item = frappe.new_doc("Item")
            item.item_code = item_name
            item.item_name = item_name
            item.item_group = "All Item Groups"
            item.stock_uom = "Nos"
            item.insert(ignore_permissions=True)
            return item.name
        else:
            return item_name
    except Exception:
        # Fallback to any existing item
        return frappe.db.get_value("Item", {"disabled": 0}, "name")

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

def get_creditors_account(company):
    """Get the default creditors account for purchase invoices"""
    # First try to find a Payable account
    creditors_account = frappe.db.get_value("Account", {
        "company": company,
        "account_type": "Payable",
        "is_group": 0
    }, "name")
    
    if creditors_account:
        return creditors_account
    
    # Fallback to any liability account
    creditors_account = frappe.db.get_value("Account", {
        "company": company,
        "root_type": "Liability",
        "is_group": 0
    }, "name")
    
    return creditors_account