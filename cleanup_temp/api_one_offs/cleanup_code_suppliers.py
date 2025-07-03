"""
Clean up code-named suppliers and implement proper fix
"""

import frappe
from frappe import _

@frappe.whitelist()
def remove_code_suppliers():
    """
    Remove the code-named suppliers we created as a workaround
    
    Returns:
        Dict with results
    """
    if not frappe.has_permission("Supplier", "delete"):
        frappe.throw(_("Insufficient permissions"))
    
    results = {
        "deleted": [],
        "errors": [],
        "kept": []
    }
    
    supplier_codes = ['00038', '00019', '00002', '1343', '1344', '197']
    
    for code in supplier_codes:
        try:
            # Check if this is a code-named supplier we created
            if frappe.db.exists("Supplier", code):
                supplier = frappe.get_doc("Supplier", code)
                
                # Check if it has any linked documents
                has_links = False
                
                # Check for linked purchase invoices
                pi_count = frappe.db.count("Purchase Invoice", {"supplier": code})
                # Check for linked payment entries
                pe_count = frappe.db.count("Payment Entry", {"party": code, "party_type": "Supplier"})
                
                if pi_count > 0 or pe_count > 0:
                    results["kept"].append({
                        "code": code,
                        "reason": f"Has {pi_count} invoices and {pe_count} payments"
                    })
                else:
                    # Safe to delete
                    frappe.delete_doc("Supplier", code)
                    results["deleted"].append(code)
                    
        except Exception as e:
            results["errors"].append(f"Code {code}: {str(e)}")
    
    frappe.db.commit()
    
    return results

@frappe.whitelist()
def get_proper_supplier_mapping():
    """
    Get the proper mapping of codes to human-readable supplier names
    
    Returns:
        Dict with mapping
    """
    mapping = {}
    
    supplier_codes = ['00038', '00019', '00002', '1343', '1344', '197']
    
    for code in supplier_codes:
        # Find supplier with this eboekhouden_relation_code
        supplier_data = frappe.db.get_value("Supplier",
            {"eboekhouden_relation_code": code},
            ["name", "supplier_name"],
            as_dict=True)
        
        if supplier_data:
            mapping[code] = {
                "system_name": supplier_data.name,
                "display_name": supplier_data.supplier_name,
                "is_human_readable": not (supplier_data.name == code or 
                                         supplier_data.name.startswith("Supplier ") or
                                         supplier_data.name.startswith("NL"))
            }
    
    return mapping