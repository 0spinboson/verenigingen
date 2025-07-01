"""
Fix the migration warehouse duplicate issue
"""

import frappe


@frappe.whitelist()
def fix_warehouse_issue():
    """
    Fix the warehouse naming issue where company "R S P" creates warehouse "e-Boekhouden Migration - RSP"
    """
    
    # The existing warehouse
    existing_warehouse = "e-Boekhouden Migration - RSP"
    company = "R S P"
    
    # Check if it exists
    if frappe.db.exists("Warehouse", existing_warehouse):
        print(f"Found existing warehouse: {existing_warehouse}")
        
        # Update the stock migration to use this specific warehouse
        # by creating an alias or updating the lookup logic
        
        # For now, just return the existing warehouse name
        return {
            "success": True,
            "warehouse": existing_warehouse,
            "message": "Existing warehouse found and will be used"
        }
    
    return {
        "success": False,
        "message": "Warehouse not found"
    }


@frappe.whitelist()
def get_migration_warehouse_for_company(company):
    """
    Get the correct migration warehouse for a company, handling name normalization
    """
    
    # First, check if we already have one
    warehouses = frappe.db.sql("""
        SELECT name 
        FROM `tabWarehouse`
        WHERE company = %s
        AND (name LIKE '%%e-Boekhouden Migration%%' 
             OR warehouse_name LIKE '%%e-Boekhouden Migration%%')
        ORDER BY creation ASC
        LIMIT 1
    """, (company,))
    
    if warehouses:
        warehouse_name = warehouses[0][0]
        print(f"Found existing warehouse: {warehouse_name}")
        return warehouse_name
    
    # If not found, create one
    try:
        warehouse = frappe.new_doc("Warehouse")
        warehouse.warehouse_name = "e-Boekhouden Migration"
        warehouse.company = company
        warehouse.warehouse_type = "Transit"
        warehouse.insert(ignore_permissions=True)
        print(f"Created new warehouse: {warehouse.name}")
        return warehouse.name
    except Exception as e:
        print(f"Error creating warehouse: {str(e)}")
        
        # Try to find it again (in case of race condition)
        warehouses = frappe.db.sql("""
            SELECT name 
            FROM `tabWarehouse`
            WHERE company = %s
            AND name LIKE '%%Boekhouden%%'
            LIMIT 1
        """, (company,))
        
        if warehouses:
            return warehouses[0][0]
        
        raise