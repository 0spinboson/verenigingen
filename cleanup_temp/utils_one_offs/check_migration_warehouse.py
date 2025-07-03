import frappe

@frappe.whitelist()
def check_migration_warehouses():
    """Check existing migration warehouses"""
    warehouses = frappe.db.sql("""
        SELECT name, warehouse_name, company 
        FROM `tabWarehouse` 
        WHERE name LIKE '%Boekhouden%' 
        OR warehouse_name LIKE '%Boekhouden%'
    """, as_dict=True)
    
    for w in warehouses:
        print(f"Name: {w.name}, Warehouse Name: {w.warehouse_name}, Company: {w.company}")
    
    return warehouses