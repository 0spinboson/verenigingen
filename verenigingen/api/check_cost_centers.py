import frappe
from frappe import _

@frappe.whitelist()
def check_cost_center_structure():
    """Check current cost center structure"""
    
    company = frappe.db.get_single_value("E-Boekhouden Settings", "default_company")
    if not company:
        return {"error": "No default company set"}
    
    # Get all cost centers for this company
    cost_centers = frappe.get_all("Cost Center", 
        filters={"company": company},
        fields=["name", "cost_center_name", "parent_cost_center", "is_group"])
    
    # Find root and non-group cost centers
    root_centers = []
    leaf_centers = []
    
    for cc in cost_centers:
        if not cc.parent_cost_center or cc.parent_cost_center == "":
            root_centers.append(cc)
        if not cc.is_group:
            leaf_centers.append(cc)
    
    return {
        "company": company,
        "total_cost_centers": len(cost_centers),
        "root_centers": root_centers,
        "leaf_centers": leaf_centers,
        "all_centers": cost_centers
    }

@frappe.whitelist()
def create_simple_cost_center():
    """Create a simple non-group cost center"""
    
    company = frappe.db.get_single_value("E-Boekhouden Settings", "default_company")
    if not company:
        return {"error": "No default company set"}
    
    # Check if Operations cost center exists
    existing = frappe.db.get_value("Cost Center", {
        "cost_center_name": "Operations",
        "company": company
    })
    
    if existing:
        # Make sure it's not a group
        frappe.db.set_value("Cost Center", existing, "is_group", 0)
        frappe.db.commit()
        return {"success": True, "cost_center": existing, "message": "Updated existing cost center"}
    
    # Find any existing cost center to use as parent
    parent_cc = frappe.db.get_value("Cost Center", {
        "company": company,
        "is_group": 1
    }, "name")
    
    # Create new cost center
    try:
        cc = frappe.new_doc("Cost Center")
        cc.cost_center_name = "Operations"
        cc.company = company
        cc.is_group = 0
        if parent_cc:
            cc.parent_cost_center = parent_cc
        cc.insert(ignore_permissions=True)
        frappe.db.commit()
        
        return {"success": True, "cost_center": cc.name, "message": f"Created cost center: {cc.name}"}
    except Exception as e:
        return {"error": str(e), "traceback": frappe.get_traceback()}