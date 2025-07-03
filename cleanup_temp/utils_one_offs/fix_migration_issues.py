"""
Fix common migration issues with E-Boekhouden import
"""

import frappe
from frappe import _

@frappe.whitelist()
def fix_cost_center_structure():
    """
    Ensure proper cost center hierarchy exists
    """
    company = frappe.db.get_single_value("E-Boekhouden Settings", "default_company")
    if not company:
        return {"success": False, "error": "No default company set"}
    
    # Get the root cost center for the company
    main_cc = frappe.db.get_value("Cost Center", {
        "company": company,
        "is_group": 1,
        "parent_cost_center": ["in", ["", None]]
    }, "name")
    
    if not main_cc:
        # This should not happen as cost center is created with company
        # But if it doesn't exist, we can't create it without complex logic
        return {
            "success": False,
            "error": f"No root cost center found for company {company}"
        }
    
    return {
        "success": True,
        "main_cost_center": main_cc
    }

@frappe.whitelist()
def temporarily_disable_receivable_payable():
    """
    Temporarily change Receivable/Payable accounts to Current Asset/Liability
    for migration purposes
    """
    company = frappe.db.get_single_value("E-Boekhouden Settings", "default_company")
    if not company:
        return {"success": False, "error": "No default company set"}
    
    # Find problematic accounts
    receivables = frappe.db.sql("""
        SELECT name, account_type 
        FROM `tabAccount`
        WHERE company = %s
        AND account_type = 'Receivable'
        AND account_number IN ('13500', '13510', '13600', '13900')
    """, company, as_dict=True)
    
    payables = frappe.db.sql("""
        SELECT name, account_type
        FROM `tabAccount`
        WHERE company = %s
        AND account_type = 'Payable'
        AND account_number = '19290'
    """, company, as_dict=True)
    
    changed = []
    
    # Temporarily change to Current Asset/Liability
    for acc in receivables:
        frappe.db.set_value("Account", acc.name, "account_type", "Current Asset")
        changed.append({"account": acc.name, "from": "Receivable", "to": "Current Asset"})
    
    for acc in payables:
        frappe.db.set_value("Account", acc.name, "account_type", "Current Liability")
        changed.append({"account": acc.name, "from": "Payable", "to": "Current Liability"})
    
    frappe.db.commit()
    
    return {
        "success": True,
        "changed": changed,
        "message": f"Temporarily changed {len(changed)} accounts. Run 'Fix Account Types' after migration completes."
    }

@frappe.whitelist()
def prepare_for_migration():
    """
    Prepare system for E-Boekhouden migration
    """
    results = []
    
    # 1. Fix cost center structure
    cc_result = fix_cost_center_structure()
    results.append({
        "step": "Cost Center Structure",
        "success": cc_result.get("success"),
        "details": cc_result
    })
    
    # 2. Temporarily disable receivable/payable
    rp_result = temporarily_disable_receivable_payable()
    results.append({
        "step": "Account Types",
        "success": rp_result.get("success"),
        "details": rp_result
    })
    
    return {
        "success": all(r["success"] for r in results),
        "results": results
    }

@frappe.whitelist()
def create_default_parties():
    """
    Create default Customer and Supplier for migration
    """
    company = frappe.db.get_single_value("E-Boekhouden Settings", "default_company")
    if not company:
        return {"success": False, "error": "No default company set"}
    
    created = []
    
    # Create default customer
    if not frappe.db.exists("Customer", "E-Boekhouden Import"):
        customer = frappe.new_doc("Customer")
        customer.customer_name = "E-Boekhouden Import"
        customer.customer_type = "Company"
        customer.customer_group = frappe.db.get_value("Customer Group", {"is_group": 0}, "name") or "All Customer Groups"
        customer.territory = frappe.db.get_value("Territory", {"is_group": 0}, "name") or "All Territories"
        customer.insert(ignore_permissions=True)
        created.append({"type": "Customer", "name": customer.name})
    
    # Create default supplier
    if not frappe.db.exists("Supplier", "E-Boekhouden Import"):
        supplier = frappe.new_doc("Supplier")
        supplier.supplier_name = "E-Boekhouden Import"
        supplier.supplier_group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name") or "All Supplier Groups"
        supplier.insert(ignore_permissions=True)
        created.append({"type": "Supplier", "name": supplier.name})
    
    return {
        "success": True,
        "created": created
    }