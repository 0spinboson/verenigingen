"""
Enhanced E-Boekhouden migration fixes for handling supplier creation and cost center issues
"""

import frappe
from frappe import _

def ensure_supplier_exists(supplier_code, relation_data=None):
    """
    Ensure a supplier exists, creating it if necessary.
    This handles the case where supplier codes are used directly as supplier names.
    
    Args:
        supplier_code: The supplier code (e.g., "00038", "00019")
        relation_data: Optional relation data from E-Boekhouden
        
    Returns:
        The supplier name in ERPNext
    """
    if not supplier_code:
        return None
    
    # First check if supplier exists with this exact code as name
    if frappe.db.exists("Supplier", supplier_code):
        return supplier_code
    
    # Check if supplier exists with eboekhouden_relation_code
    existing = frappe.db.get_value("Supplier", 
        {"eboekhouden_relation_code": supplier_code}, "name")
    if existing:
        return existing
    
    # Check common naming patterns
    patterns = [
        f"Supplier {supplier_code}",
        f"Leverancier {supplier_code}",
        f"{supplier_code} -"
    ]
    
    for pattern in patterns:
        if frappe.db.exists("Supplier", pattern):
            return pattern
    
    # Create the supplier with the code as the name
    # This ensures compatibility with existing references
    try:
        supplier = frappe.new_doc("Supplier")
        supplier.supplier_name = supplier_code
        supplier.eboekhouden_relation_code = supplier_code
        supplier.supplier_group = frappe.db.get_value("Supplier Group", 
            {"is_group": 0}, "name") or "All Supplier Groups"
        
        # Add relation data if available
        if relation_data:
            if relation_data.get('Bedrijf'):
                supplier.supplier_details = relation_data.get('Bedrijf')
            if relation_data.get('Contactpersoon'):
                supplier.contact_person = relation_data.get('Contactpersoon')
        
        supplier.insert(ignore_permissions=True)
        frappe.db.commit()
        
        return supplier.name
        
    except Exception as e:
        frappe.log_error(f"Failed to create supplier {supplier_code}: {str(e)}", 
                        "E-Boekhouden Supplier Creation")
        return None

def ensure_cost_center_is_group(cost_center_name):
    """
    Ensure a cost center is configured as a group.
    
    Args:
        cost_center_name: The cost center name to check
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Find cost centers by name pattern
        cost_centers = frappe.db.get_all("Cost Center",
            filters={"cost_center_name": ["like", f"%{cost_center_name}%"]},
            fields=["name", "is_group"])
        
        fixed_count = 0
        for cc in cost_centers:
            if not cc.is_group:
                frappe.db.set_value("Cost Center", cc.name, "is_group", 1)
                fixed_count += 1
        
        if fixed_count > 0:
            frappe.db.commit()
            
        return True
        
    except Exception as e:
        frappe.log_error(f"Failed to fix cost center {cost_center_name}: {str(e)}", 
                        "E-Boekhouden Cost Center Fix")
        return False

def pre_process_supplier_payment(mutation, company):
    """
    Pre-process a supplier payment mutation to ensure required entities exist.
    This should be called before processing each supplier payment.
    
    Args:
        mutation: The E-Boekhouden mutation data
        company: The company name
        
    Returns:
        Dict with processed data
    """
    result = {
        "success": True,
        "supplier": None,
        "errors": []
    }
    
    # Get supplier code from mutation
    supplier_code = mutation.get("RelatieCode")
    if supplier_code:
        # Ensure supplier exists
        supplier = ensure_supplier_exists(supplier_code)
        if supplier:
            result["supplier"] = supplier
        else:
            result["success"] = False
            result["errors"].append(f"Could not create supplier for code {supplier_code}")
    
    return result

def enhance_migration_process():
    """
    Enhance the E-Boekhouden migration process to handle common issues.
    This should be called at the start of each migration.
    """
    # Fix known cost center issues
    ensure_cost_center_is_group("maanden - NVV")
    
    # You can add more pre-migration fixes here
    
    return True

@frappe.whitelist()
def fix_failed_supplier_payments(migration_id):
    """
    Fix failed supplier payments from a specific migration.
    
    Args:
        migration_id: The E-Boekhouden migration ID
        
    Returns:
        Dict with results
    """
    if not frappe.has_permission("E-Boekhouden Migration", "write"):
        frappe.throw(_("Insufficient permissions"))
    
    results = {
        "fixed": 0,
        "failed": 0,
        "errors": []
    }
    
    try:
        # Get the migration document
        migration = frappe.get_doc("E-Boekhouden Migration", migration_id)
        
        # Get failed supplier payments from the migration
        # This would need to be implemented based on how failed records are stored
        
        # For now, return a placeholder
        results["message"] = "Fix functionality to be implemented based on migration structure"
        
    except Exception as e:
        results["errors"].append(str(e))
        
    return results