import frappe
from frappe import _

@frappe.whitelist()
def create_operational_cost_center():
    """Create an operational (non-group) cost center for transactions"""
    
    company = frappe.db.get_single_value("E-Boekhouden Settings", "default_company")
    if not company:
        return {"success": False, "error": "No default company set"}
    
    # Find the root cost center
    root_cc = frappe.db.get_value("Cost Center", {
        "company": company,
        "is_group": 1,
        "parent_cost_center": ["in", ["", None]]
    }, "name")
    
    if not root_cc:
        return {"success": False, "error": "No root cost center found"}
    
    # Create operational cost center under root
    operational_cc_name = f"Operations - {company}"
    
    if not frappe.db.exists("Cost Center", {"cost_center_name": "Operations", "company": company}):
        try:
            operational_cc = frappe.new_doc("Cost Center")
            operational_cc.cost_center_name = "Operations"
            operational_cc.parent_cost_center = root_cc
            operational_cc.company = company
            operational_cc.is_group = 0  # Not a group - can be used in transactions
            operational_cc.insert(ignore_permissions=True)
            frappe.db.commit()
            
            return {
                "success": True,
                "cost_center": operational_cc.name,
                "message": f"Created operational cost center: {operational_cc.name}"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    else:
        # Get existing operational cost center
        operational_cc = frappe.db.get_value("Cost Center", {
            "cost_center_name": "Operations",
            "company": company
        }, "name")
        
        # Ensure it's not a group
        frappe.db.set_value("Cost Center", operational_cc, "is_group", 0)
        frappe.db.commit()
        
        return {
            "success": True,
            "cost_center": operational_cc,
            "message": f"Using existing operational cost center: {operational_cc}"
        }

@frappe.whitelist()
def update_migration_cost_center():
    """Update the migration logic to use operational cost center"""
    
    # First create the operational cost center
    result = create_operational_cost_center()
    
    if not result["success"]:
        return result
    
    operational_cc = result["cost_center"]
    
    # Update the eboekhouden_soap_migration.py file to use this cost center
    file_path = "/home/frappe/frappe-bench/apps/verenigingen/verenigingen/utils/eboekhouden_soap_migration.py"
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Update the cost center logic
        old_logic = """        # If still not found, get any cost center for this company
        if not cost_center:
            cost_center = frappe.db.get_value("Cost Center", {
                "company": company,
                "is_group": 1
            }, "name")"""
        
        new_logic = """        # If still not found, get operational cost center
        if not cost_center:
            cost_center = frappe.db.get_value("Cost Center", {
                "company": company,
                "cost_center_name": "Operations",
                "is_group": 0
            }, "name")
        
        # If still not found, get any non-group cost center
        if not cost_center:
            cost_center = frappe.db.get_value("Cost Center", {
                "company": company,
                "is_group": 0
            }, "name")"""
        
        if old_logic in content:
            content = content.replace(old_logic, new_logic)
            
            with open(file_path, 'w') as f:
                f.write(content)
            
            return {
                "success": True,
                "cost_center": operational_cc,
                "message": f"Updated migration to use operational cost center: {operational_cc}"
            }
        else:
            return {
                "success": True,
                "cost_center": operational_cc,
                "message": f"Migration code already updated. Using cost center: {operational_cc}"
            }
            
    except Exception as e:
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def fix_due_date_logic():
    """Fix the due date calculation in migration"""
    
    file_path = "/home/frappe/frappe-bench/apps/verenigingen/verenigingen/utils/eboekhouden_soap_migration.py"
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Fix the due date calculation to ensure it's not before posting date
        old_line = 'si.due_date = frappe.utils.add_days(posting_date, int(mut.get("Betalingstermijn", 30)))'
        new_line = '''payment_terms = int(mut.get("Betalingstermijn", 30))
            si.due_date = frappe.utils.add_days(posting_date, max(0, payment_terms))'''
        
        content = content.replace(old_line, new_line)
        
        with open(file_path, 'w') as f:
            f.write(content)
        
        return {"success": True, "message": "Fixed due date logic"}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def run_migration_with_all_fixes():
    """Run the migration with all fixes applied"""
    
    # First fix the cost center
    fix_result = update_migration_cost_center()
    
    if not fix_result["success"]:
        return fix_result
    
    # Fix due date logic
    due_date_result = fix_due_date_logic()
    
    if not due_date_result["success"]:
        return due_date_result
    
    # Restart to apply changes
    frappe.db.commit()
    
    # Then run the migration
    from verenigingen.api.fix_cost_center_and_run import run_soap_migration_for_may
    
    return run_soap_migration_for_may()