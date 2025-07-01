"""
Add title fields to Payment Entry and Journal Entry
"""

import frappe
from frappe import _


@frappe.whitelist()
def add_title_fields():
    """Add title fields to Payment Entry and Journal Entry if they don't exist"""
    
    fields_added = []
    
    # Add title to Payment Entry if not exists
    if not frappe.db.has_column("Payment Entry", "title"):
        frappe.get_doc({
            "doctype": "Custom Field",
            "dt": "Payment Entry",
            "fieldname": "title",
            "fieldtype": "Data",
            "label": "Title",
            "in_list_view": 1,
            "in_standard_filter": 1,
            "insert_after": "naming_series",
            "description": "Descriptive title for easy identification"
        }).insert(ignore_permissions=True)
        fields_added.append("Payment Entry.title")
    
    # Add title to Journal Entry if not exists
    if not frappe.db.has_column("Journal Entry", "title"):
        frappe.get_doc({
            "doctype": "Custom Field",
            "dt": "Journal Entry",
            "fieldname": "title",
            "fieldtype": "Data",
            "label": "Title",
            "in_list_view": 1,
            "in_standard_filter": 1,
            "insert_after": "naming_series",
            "description": "Descriptive title for easy identification"
        }).insert(ignore_permissions=True)
        fields_added.append("Journal Entry.title")
    
    # Add eboekhouden_invoice_number to Journal Entry if not exists
    if not frappe.db.has_column("Journal Entry", "eboekhouden_invoice_number"):
        frappe.get_doc({
            "doctype": "Custom Field",
            "dt": "Journal Entry",
            "fieldname": "eboekhouden_invoice_number",
            "fieldtype": "Data",
            "label": "E-Boekhouden Invoice Number",
            "insert_after": "eboekhouden_mutation_nr"
        }).insert(ignore_permissions=True)
        fields_added.append("Journal Entry.eboekhouden_invoice_number")
    
    # Add eboekhouden fields to Payment Entry
    if not frappe.db.has_column("Payment Entry", "eboekhouden_mutation_nr"):
        frappe.get_doc({
            "doctype": "Custom Field",
            "dt": "Payment Entry",
            "fieldname": "eboekhouden_mutation_nr",
            "fieldtype": "Data",
            "label": "E-Boekhouden Mutation Nr",
            "insert_after": "reference_date"
        }).insert(ignore_permissions=True)
        fields_added.append("Payment Entry.eboekhouden_mutation_nr")
    
    if not frappe.db.has_column("Payment Entry", "eboekhouden_invoice_number"):
        frappe.get_doc({
            "doctype": "Custom Field",
            "dt": "Payment Entry",
            "fieldname": "eboekhouden_invoice_number",
            "fieldtype": "Data",
            "label": "E-Boekhouden Invoice Number",
            "insert_after": "eboekhouden_mutation_nr"
        }).insert(ignore_permissions=True)
        fields_added.append("Payment Entry.eboekhouden_invoice_number")
    
    return {
        "success": True,
        "fields_added": fields_added,
        "message": f"Added {len(fields_added)} fields"
    }


@frappe.whitelist()
def update_existing_payment_titles():
    """Update titles for existing payments that don't have them"""
    
    company = frappe.db.get_single_value("E-Boekhouden Settings", "default_company")
    if not company:
        return {"error": "No default company set"}
    
    updated_count = 0
    
    # Update Payment Entries without titles
    payment_entries = frappe.get_all("Payment Entry",
        filters={
            "company": company,
            "title": ["in", ["", None]],
            "docstatus": ["!=", 2]
        },
        fields=["name", "payment_type", "party_type", "party", "posting_date", 
                "paid_amount", "reference_no", "remarks"],
        limit=500
    )
    
    for pe in payment_entries:
        try:
            title_parts = []
            
            # Date
            if pe.posting_date:
                title_parts.append(str(pe.posting_date))
            
            # Party
            if pe.party:
                short_name = pe.party[:30] + "..." if len(pe.party) > 30 else pe.party
                title_parts.append(short_name)
            
            # Amount
            if pe.paid_amount:
                title_parts.append(f"€{pe.paid_amount:,.2f}")
            
            # Reference
            if pe.reference_no:
                title_parts.append(f"Ref:{pe.reference_no}")
            
            new_title = " - ".join(title_parts)
            
            frappe.db.set_value("Payment Entry", pe.name, "title", new_title, update_modified=False)
            updated_count += 1
            
        except Exception as e:
            frappe.log_error(f"Error updating payment entry {pe.name}: {str(e)}")
    
    # Update Journal Entries without titles
    journal_entries = frappe.db.sql("""
        SELECT 
            je.name,
            je.posting_date,
            je.user_remark,
            je.total_debit,
            je.eboekhouden_mutation_nr
        FROM `tabJournal Entry` je
        WHERE je.company = %s 
        AND (je.title IS NULL OR je.title = '')
        AND je.docstatus != 2
        LIMIT 500
    """, company, as_dict=True)
    
    for je in journal_entries:
        try:
            title_parts = []
            
            # Date
            if je.posting_date:
                title_parts.append(str(je.posting_date))
            
            # Type from remark
            remark_lower = (je.user_remark or "").lower()
            if "money received" in remark_lower or "geld ontvangen" in remark_lower:
                title_parts.append("Money Received")
            elif "money spent" in remark_lower or "geld uitgegeven" in remark_lower:
                title_parts.append("Money Spent")
            elif "payment" in remark_lower or "betaling" in remark_lower:
                title_parts.append("Payment")
            else:
                title_parts.append("Journal Entry")
            
            # Amount
            if je.total_debit:
                title_parts.append(f"€{je.total_debit:,.2f}")
            
            # Reference
            if je.eboekhouden_mutation_nr:
                title_parts.append(f"Mut#{je.eboekhouden_mutation_nr}")
            
            # Short description
            if je.user_remark:
                short_desc = je.user_remark[:30] + "..." if len(je.user_remark) > 30 else je.user_remark
                title_parts.append(short_desc)
            
            new_title = " - ".join(title_parts)
            
            frappe.db.set_value("Journal Entry", je.name, "title", new_title, update_modified=False)
            updated_count += 1
            
        except Exception as e:
            frappe.log_error(f"Error updating journal entry {je.name}: {str(e)}")
    
    frappe.db.commit()
    
    return {
        "success": True,
        "updated_count": updated_count,
        "message": f"Updated titles for {updated_count} documents"
    }