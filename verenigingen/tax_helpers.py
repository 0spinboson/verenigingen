# File: verenigingen/tax_helpers.py

import frappe
from frappe import _
from frappe.utils import flt

# Copy the essential functions from dutch_tax_handler.py

def setup_dutch_tax_exemption():
    """
    Main function to set up Dutch tax exemption
    Called from hooks when Verenigingen Settings is updated
    """
    frappe.logger().info("Dutch tax exemption setup triggered")
    # This is a simplified function that just logs the call
    # In production, you can expand this to do what you need

def apply_tax_exemption_from_source(doc, method=None):
    """
    Automatically apply tax exemption based on the source document
    """
    frappe.logger().info(f"Applying tax exemption to {doc.doctype} {doc.name}")
    
    if getattr(doc, 'exempt_from_tax', False):
        return
        
    # Skip if taxes already applied and not a new document
    if doc.taxes and not doc.is_new():
        return
    
    # Very simplified exemption application
    if hasattr(doc, 'membership') and doc.membership:
        # For membership-related invoices
        doc.exempt_from_tax = 1
    elif hasattr(doc, 'donation') and doc.donation:
        # For donation-related invoices
        doc.exempt_from_tax = 1
    else:
        # Default case
        settings = frappe.get_single("Verenigingen Settings")
        if settings.get("tax_exempt_for_contributions", 0):
            doc.exempt_from_tax = 1
    
    # Apply a zero tax template if needed and available
    if doc.exempt_from_tax:
        zero_tax_template = frappe.db.get_single_value("Verenigingen Settings", "default_tax_template")
        if zero_tax_template and frappe.db.exists("Sales Taxes and Charges Template", zero_tax_template):
            doc.taxes_and_charges = zero_tax_template
            try:
                doc.set_taxes()
            except Exception as e:
                frappe.logger().error(f"Error setting taxes: {str(e)}")
    
    return doc
