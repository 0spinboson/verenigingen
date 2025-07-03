"""
Fix supplier reference issues in E-Boekhouden migrations
"""

import frappe
from frappe import _

@frappe.whitelist()
def find_and_fix_supplier_references():
    """
    Find suppliers by eboekhouden_relation_code and create aliases if needed
    
    Returns:
        Dict with results
    """
    if not frappe.has_permission("Supplier", "write"):
        frappe.throw(_("Insufficient permissions"))
    
    results = {
        "suppliers_found": {},
        "aliases_created": [],
        "errors": []
    }
    
    try:
        # Supplier codes we're looking for
        supplier_codes = ['00038', '00019', '00002', '1343', '1344', '197']
        
        for code in supplier_codes:
            # Find supplier with this eboekhouden_relation_code
            supplier_name = frappe.db.get_value("Supplier", 
                {"eboekhouden_relation_code": code}, "name")
            
            if supplier_name:
                results["suppliers_found"][code] = supplier_name
                
                # Check if we need to create an alias with just the code
                if supplier_name != code and not frappe.db.exists("Supplier", code):
                    try:
                        # Create alias supplier
                        alias = frappe.new_doc("Supplier")
                        alias.supplier_name = code
                        # Don't set eboekhouden_relation_code to avoid duplicate
                        alias.supplier_group = frappe.db.get_value("Supplier Group", 
                            {"is_group": 0}, "name") or "All Supplier Groups"
                        alias.insert(ignore_permissions=True)
                        results["aliases_created"].append(code)
                    except Exception as e:
                        # Try alternate approach - rename if the name is generic
                        if "Supplier " in supplier_name or "Leverancier " in supplier_name:
                            try:
                                # Rename the existing supplier to just the code
                                frappe.rename_doc("Supplier", supplier_name, code, merge=False)
                                results["aliases_created"].append(f"Renamed {supplier_name} to {code}")
                            except Exception as rename_error:
                                results["errors"].append(f"Could not rename {supplier_name}: {str(rename_error)}")
                        else:
                            results["errors"].append(f"Could not create alias for {code}: {str(e)}")
        
        frappe.db.commit()
        
    except Exception as e:
        results["errors"].append(str(e))
    
    return results

@frappe.whitelist()
def get_supplier_mapping():
    """
    Get mapping of supplier codes to actual supplier names
    
    Returns:
        Dict with mapping
    """
    if not frappe.has_permission("Supplier", "read"):
        frappe.throw(_("Insufficient permissions"))
    
    supplier_codes = ['00038', '00019', '00002', '1343', '1344', '197']
    mapping = {}
    
    for code in supplier_codes:
        # Check if supplier exists with code as name
        if frappe.db.exists("Supplier", code):
            mapping[code] = {
                "primary_name": code,
                "has_direct_match": True
            }
        else:
            # Find by eboekhouden_relation_code
            supplier_name = frappe.db.get_value("Supplier", 
                {"eboekhouden_relation_code": code}, "name")
            
            if supplier_name:
                mapping[code] = {
                    "primary_name": supplier_name,
                    "has_direct_match": False,
                    "needs_alias": True
                }
            else:
                mapping[code] = {
                    "primary_name": None,
                    "has_direct_match": False,
                    "not_found": True
                }
    
    return mapping

@frappe.whitelist()
def update_failed_payments_suppliers(migration_id):
    """
    Update failed payment records to use correct supplier names
    
    Args:
        migration_id: The E-Boekhouden migration ID
        
    Returns:
        Dict with results
    """
    if not frappe.has_permission("Payment Entry", "write"):
        frappe.throw(_("Insufficient permissions"))
    
    results = {
        "updated": 0,
        "errors": []
    }
    
    try:
        # Get supplier mapping
        mapping = get_supplier_mapping()
        
        # Find failed payments that need supplier updates
        # This would need to be implemented based on how failed records are tracked
        
        results["mapping"] = mapping
        
    except Exception as e:
        results["errors"].append(str(e))
    
    return results

@frappe.whitelist()
def create_supplier_name_fixes():
    """
    Create a comprehensive fix for supplier naming issues
    
    Returns:
        Dict with results
    """
    if not frappe.has_permission("Supplier", "write"):
        frappe.throw(_("Insufficient permissions"))
    
    results = {
        "actions_taken": [],
        "errors": []
    }
    
    try:
        supplier_codes = ['00038', '00019', '00002', '1343', '1344', '197']
        
        for code in supplier_codes:
            # Strategy 1: Find existing supplier with eboekhouden_relation_code
            existing = frappe.db.get_value("Supplier", 
                {"eboekhouden_relation_code": code}, ["name", "supplier_name"], as_dict=True)
            
            if existing:
                # Check if we can use the supplier directly
                if existing.name == code:
                    results["actions_taken"].append(f"Code {code}: Already correctly named")
                    continue
                
                # Check if the name is generic and can be renamed
                if any(pattern in existing.name for pattern in ["Supplier ", "Leverancier ", code]):
                    # Check if code is available as a name
                    if not frappe.db.exists("Supplier", code):
                        try:
                            frappe.rename_doc("Supplier", existing.name, code, merge=False)
                            results["actions_taken"].append(f"Code {code}: Renamed '{existing.name}' to '{code}'")
                        except Exception as e:
                            results["errors"].append(f"Could not rename {existing.name}: {str(e)}")
                    else:
                        # Code already exists as a different supplier
                        # Update the eboekhouden_relation_code of the code-named supplier
                        try:
                            frappe.db.set_value("Supplier", code, "eboekhouden_relation_code", code)
                            results["actions_taken"].append(f"Code {code}: Updated existing supplier '{code}' with relation code")
                        except Exception as e:
                            results["errors"].append(f"Could not update {code}: {str(e)}")
                else:
                    # Supplier has a meaningful name, create system note
                    results["actions_taken"].append(f"Code {code}: Maps to '{existing.name}' (keeping meaningful name)")
            else:
                # No supplier with this relation code exists
                if frappe.db.exists("Supplier", code):
                    # Supplier exists with code as name but no relation code
                    try:
                        frappe.db.set_value("Supplier", code, "eboekhouden_relation_code", code)
                        results["actions_taken"].append(f"Code {code}: Added relation code to existing supplier")
                    except Exception as e:
                        results["errors"].append(f"Could not update {code}: {str(e)}")
                else:
                    # Create new supplier
                    try:
                        supplier = frappe.new_doc("Supplier")
                        supplier.supplier_name = code
                        supplier.eboekhouden_relation_code = code
                        supplier.supplier_group = frappe.db.get_value("Supplier Group", 
                            {"is_group": 0}, "name") or "All Supplier Groups"
                        supplier.insert(ignore_permissions=True)
                        results["actions_taken"].append(f"Code {code}: Created new supplier")
                    except Exception as e:
                        results["errors"].append(f"Could not create {code}: {str(e)}")
        
        frappe.db.commit()
        
    except Exception as e:
        results["errors"].append(str(e))
    
    return results