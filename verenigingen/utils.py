# Add this function to your verenigingen/utils.py (replace the existing one)

def apply_tax_exemption_from_source(doc, method=None):
    """
    Automatically apply tax exemption based on the source document
    Updated with error handling for missing BTW custom fields
    """
    # Check if the attribute exists before using it
    if hasattr(doc, 'exempt_from_tax') and doc.exempt_from_tax:
        return
        
    # Skip if taxes already applied and not a new document
    if doc.taxes and not doc.is_new():
        return
    
    # Check if BTW custom fields exist before trying to use them
    has_btw_fields = (
        hasattr(doc, 'btw_exemption_type') and 
        hasattr(doc, 'btw_exemption_reason') and 
        hasattr(doc, 'btw_reporting_category')
    )
    
    if not has_btw_fields:
        # Fallback to simple tax exemption without BTW fields
        frappe.logger().warning(f"BTW custom fields missing on Sales Invoice. Using simple tax exemption.")
        
        # Apply simple tax exemption
        settings = frappe.get_single("Verenigingen Settings")
        if settings.get("tax_exempt_for_contributions"):
            # Set the basic exempt_from_tax flag
            doc.exempt_from_tax = 1
            
            # Try to apply a basic tax template if available
            if settings.get("default_tax_template"):
                if frappe.db.exists("Sales Taxes and Charges Template", settings.default_tax_template):
                    doc.taxes_and_charges = settings.default_tax_template
                    try:
                        doc.set_taxes()
                    except Exception as e:
                        frappe.logger().error(f"Error setting taxes: {str(e)}")
        return
    
    # If BTW fields exist, use the full Dutch tax handler
    try:
        # Import here to avoid circular imports
        from verenigingen.utils import DutchTaxExemptionHandler
        handler = DutchTaxExemptionHandler()
        
        # For membership-related invoices
        if hasattr(doc, 'membership') and doc.membership:
            exemption_type = frappe.db.get_value("Membership", doc.membership, "btw_exemption_type") or "EXEMPT_MEMBERSHIP"
            handler.apply_exemption_to_invoice(doc, exemption_type)
        
        # For donation-related invoices
        elif hasattr(doc, 'donation') and doc.donation:
            exemption_type = frappe.db.get_value("Donation", doc.donation, "btw_exemption_type") or "EXEMPT_FUNDRAISING"
            handler.apply_exemption_to_invoice(doc, exemption_type)
        
        # Use default exemption for verenigingen-created invoices if tax exempt is enabled
        elif frappe.db.get_single_value("Verenigingen Settings", "tax_exempt_for_contributions"):
            default_exemption = frappe.db.get_single_value("Verenigingen Settings", "default_tax_exemption_type") or "EXEMPT_MEMBERSHIP"
            handler.apply_exemption_to_invoice(doc, default_exemption)
            
    except Exception as e:
        # Log error but don't fail invoice creation
        frappe.log_error(f"Error in BTW tax exemption for {doc.name}: {str(e)}", "BTW Tax Exemption Error")
        
        # Fallback to simple exemption
        settings = frappe.get_single("Verenigingen Settings")
        if settings.get("tax_exempt_for_contributions"):
            doc.exempt_from_tax = 1
