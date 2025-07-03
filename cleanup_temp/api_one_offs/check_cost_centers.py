"""
Check cost center setup for eBoekhouden migration
"""

import frappe
from frappe import _

@frappe.whitelist()
def analyze_cost_center_setup():
    """
    Analyze cost center setup for eBoekhouden migration
    
    Returns:
        Dict with analysis
    """
    if not frappe.has_permission("Cost Center", "read"):
        frappe.throw(_("Insufficient permissions"))
    
    # Get company from eBoekhouden settings
    company = frappe.db.get_single_value("E-Boekhouden Settings", "default_company")
    if not company:
        return {"error": "No default company set in E-Boekhouden Settings"}
    
    analysis = {
        "company": company,
        "main_cost_center": None,
        "default_cost_center": None,
        "non_group_cost_centers": [],
        "maanden_cost_centers": [],
        "cost_center_hierarchy": {}
    }
    
    # Check for Main cost center
    main_cc = frappe.db.get_value("Cost Center", {
        "company": company,
        "cost_center_name": "Main",
        "is_group": 0
    }, "name")
    
    if main_cc:
        analysis["main_cost_center"] = main_cc
    
    # Check company's default cost center
    default_cc = frappe.db.get_value("Company", company, "cost_center")
    if default_cc:
        cc_details = frappe.db.get_value("Cost Center", default_cc, 
            ["name", "cost_center_name", "is_group"], as_dict=True)
        analysis["default_cost_center"] = cc_details
    
    # Get all non-group cost centers
    non_group = frappe.db.get_all("Cost Center",
        filters={
            "company": company,
            "is_group": 0
        },
        fields=["name", "cost_center_name"],
        limit=10
    )
    analysis["non_group_cost_centers"] = non_group
    
    # Check for maanden cost centers
    maanden_ccs = frappe.db.get_all("Cost Center",
        filters={
            "company": company,
            "cost_center_name": ["like", "%maanden%"]
        },
        fields=["name", "cost_center_name", "is_group", "parent_cost_center"]
    )
    analysis["maanden_cost_centers"] = maanden_ccs
    
    # Get cost center hierarchy for NVV
    nvv_ccs = frappe.db.get_all("Cost Center",
        filters={
            "company": company,
            "cost_center_name": ["like", "%NVV%"]
        },
        fields=["name", "cost_center_name", "is_group", "parent_cost_center"],
        order_by="lft"
    )
    
    # Build hierarchy
    for cc in nvv_ccs:
        if cc.parent_cost_center:
            parent_name = frappe.db.get_value("Cost Center", cc.parent_cost_center, "cost_center_name")
            cc["parent_name"] = parent_name
        analysis["cost_center_hierarchy"][cc.name] = cc
    
    return analysis

@frappe.whitelist()
def create_proper_default_cost_center():
    """
    Create a proper default cost center for eBoekhouden migration
    
    Returns:
        Dict with results
    """
    if not frappe.has_permission("Cost Center", "create"):
        frappe.throw(_("Insufficient permissions"))
    
    company = frappe.db.get_single_value("E-Boekhouden Settings", "default_company")
    if not company:
        return {"error": "No default company set in E-Boekhouden Settings"}
    
    results = {
        "created": False,
        "cost_center": None,
        "message": ""
    }
    
    # Check if Main cost center exists
    main_cc = frappe.db.get_value("Cost Center", {
        "company": company,
        "cost_center_name": "Main",
        "is_group": 0
    }, "name")
    
    if main_cc:
        results["cost_center"] = main_cc
        results["message"] = f"Main cost center already exists: {main_cc}"
        return results
    
    # Check for Main - Abbreviation pattern
    company_abbr = frappe.db.get_value("Company", company, "abbr")
    main_abbr = f"Main - {company_abbr}"
    
    if frappe.db.exists("Cost Center", main_abbr):
        # Check if it's a group
        is_group = frappe.db.get_value("Cost Center", main_abbr, "is_group")
        if is_group:
            results["message"] = f"Cost center {main_abbr} exists but is a group. Cannot use for transactions."
        else:
            results["cost_center"] = main_abbr
            results["message"] = f"Cost center {main_abbr} exists and is usable"
        return results
    
    # Create new Main cost center
    try:
        # Get parent cost center
        parent_cc = frappe.db.get_value("Cost Center", {
            "company": company,
            "is_group": 1,
            "parent_cost_center": ""
        }, "name")
        
        if not parent_cc:
            # Get company default parent
            parent_cc = company
        
        # Create Main cost center
        cc = frappe.new_doc("Cost Center")
        cc.cost_center_name = "Main"
        cc.company = company
        cc.is_group = 0
        cc.parent_cost_center = parent_cc
        cc.insert(ignore_permissions=True)
        
        results["created"] = True
        results["cost_center"] = cc.name
        results["message"] = f"Created new Main cost center: {cc.name}"
        
        # Set as company default if none exists
        if not frappe.db.get_value("Company", company, "cost_center"):
            frappe.db.set_value("Company", company, "cost_center", cc.name)
            results["message"] += " and set as company default"
        
        frappe.db.commit()
        
    except Exception as e:
        results["error"] = str(e)
    
    return results