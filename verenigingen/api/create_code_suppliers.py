"""
Create suppliers with exact codes as names for E-Boekhouden compatibility
"""

import frappe
from frappe import _

@frappe.whitelist()
def create_code_named_suppliers():
    """
    Create suppliers with exact codes as names to fix payment entry issues
    
    Returns:
        Dict with results
    """
    if not frappe.has_permission("Supplier", "create"):
        frappe.throw(_("Insufficient permissions"))
    
    results = {
        "created": [],
        "already_exists": [],
        "errors": []
    }
    
    supplier_codes = ['00038', '00019', '00002', '1343', '1344', '197']
    
    for code in supplier_codes:
        try:
            # Check if supplier with exact code name exists
            if frappe.db.exists("Supplier", code):
                results["already_exists"].append(code)
                continue
            
            # Create supplier with code as name
            supplier = frappe.new_doc("Supplier")
            supplier.supplier_name = code
            # Don't set eboekhouden_relation_code if another supplier already has it
            existing_with_code = frappe.db.get_value("Supplier", 
                {"eboekhouden_relation_code": code}, "name")
            
            if not existing_with_code:
                supplier.eboekhouden_relation_code = code
            
            supplier.supplier_group = frappe.db.get_value("Supplier Group", 
                {"is_group": 0}, "name") or "All Supplier Groups"
            
            # Add a note about the actual supplier
            actual_supplier = frappe.db.get_value("Supplier",
                {"eboekhouden_relation_code": code}, "supplier_name")
            
            if actual_supplier:
                supplier.supplier_details = f"E-Boekhouden code reference. Actual supplier: {actual_supplier}"
            
            supplier.insert(ignore_permissions=True)
            results["created"].append({
                "code": code,
                "actual_supplier": actual_supplier or "N/A"
            })
            
        except Exception as e:
            results["errors"].append(f"Code {code}: {str(e)}")
    
    frappe.db.commit()
    
    # Generate summary
    results["summary"] = f"""
    Created {len(results['created'])} code-named suppliers
    Already existed: {len(results['already_exists'])}
    Errors: {len(results['errors'])}
    
    This allows payment entries to find suppliers by their E-Boekhouden codes.
    """
    
    return results