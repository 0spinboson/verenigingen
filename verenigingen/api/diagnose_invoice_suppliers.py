"""
Diagnose purchase invoice supplier issues
"""

import frappe
from frappe import _

@frappe.whitelist()
def check_invoice_suppliers():
    """
    Check purchase invoices for supplier code issues
    
    Returns:
        Dict with analysis
    """
    if not frappe.has_permission("Purchase Invoice", "read"):
        frappe.throw(_("Insufficient permissions"))
    
    results = {
        "invoices_with_code_suppliers": [],
        "sample_invoices": [],
        "supplier_analysis": {}
    }
    
    # Check for specific invoices mentioned in errors
    problem_invoices = [
        "1106-25116910",
        "M2025.5.1", 
        "20250304",
        "20250501",
        "8008125556501050",
        "2600115571",
        "20250329",
        "2025030",
        "20250401"
    ]
    
    for invoice_no in problem_invoices:
        # Find by eboekhouden_invoice_number
        pi_data = frappe.db.get_value("Purchase Invoice",
            {"eboekhouden_invoice_number": invoice_no},
            ["name", "supplier", "docstatus", "outstanding_amount"],
            as_dict=True)
        
        if pi_data:
            results["sample_invoices"].append({
                "invoice_no": invoice_no,
                "erp_name": pi_data.name,
                "supplier": pi_data.supplier,
                "docstatus": pi_data.docstatus,
                "outstanding": pi_data.outstanding_amount
            })
            
            # Check if supplier is just a code
            if pi_data.supplier in ['00038', '00019', '00002', '1343', '1344', '197']:
                results["invoices_with_code_suppliers"].append(pi_data)
    
    # Check all purchase invoices for code-based suppliers
    code_suppliers = ['00038', '00019', '00002', '1343', '1344', '197']
    
    for code in code_suppliers:
        count = frappe.db.count("Purchase Invoice", {
            "supplier": code,
            "docstatus": ["!=", 2]
        })
        
        if count > 0:
            results["supplier_analysis"][code] = {
                "invoice_count": count,
                "sample_invoices": frappe.db.get_all("Purchase Invoice",
                    filters={"supplier": code, "docstatus": ["!=", 2]},
                    fields=["name", "eboekhouden_invoice_number"],
                    limit=5)
            }
    
    return results

@frappe.whitelist()
def fix_invoice_suppliers():
    """
    Fix purchase invoices that have supplier codes instead of names
    
    Returns:
        Dict with results
    """
    if not frappe.has_permission("Purchase Invoice", "write"):
        frappe.throw(_("Insufficient permissions"))
    
    results = {
        "fixed": 0,
        "errors": [],
        "details": []
    }
    
    # Mapping of codes to correct supplier names
    supplier_map = {
        "00038": "NL86INGB0002445588 INGBNL2A Belastingdienst TRIO DOS NL 20250530 31751360 STRD 1008125556501040",
        "00019": "René Beemer",
        "00002": "NL10RABO0373122209 RABONL2U Koninklijke PostNL B.V. E REF 070200537218 010000338072 NL96ZZZ273620000000 RE MI USTD 1106-2519359",
        "1343": "Univ Leiden",
        "1344": "Harmke Berghuis",
        "197": "Trai Vegan"
    }
    
    for code, correct_name in supplier_map.items():
        # Find invoices with code as supplier
        invoices = frappe.db.get_all("Purchase Invoice",
            filters={
                "supplier": code,
                "docstatus": ["!=", 2]
            },
            fields=["name", "docstatus", "eboekhouden_invoice_number"])
        
        for inv in invoices:
            try:
                # For submitted invoices, we need to cancel and amend
                if inv.docstatus == 1:
                    results["details"].append(f"Invoice {inv.name} is submitted - needs manual amendment")
                else:
                    # Draft invoice can be updated directly
                    frappe.db.set_value("Purchase Invoice", inv.name, "supplier", correct_name)
                    results["fixed"] += 1
                    results["details"].append(f"Fixed {inv.name} ({inv.eboekhouden_invoice_number}): {code} → {correct_name}")
                    
            except Exception as e:
                results["errors"].append(f"Invoice {inv.name}: {str(e)}")
    
    frappe.db.commit()
    
    return results