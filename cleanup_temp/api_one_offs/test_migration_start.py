import frappe

@frappe.whitelist()
def test_migration_start():
    """Test if the migration start function works"""
    try:
        # Get the latest draft migration
        draft_migration = frappe.db.sql("""
            SELECT name 
            FROM `tabE-Boekhouden Migration`
            WHERE migration_status = 'Draft'
            AND docstatus = 0
            ORDER BY creation DESC
            LIMIT 1
        """, as_dict=True)
        
        if not draft_migration:
            return {
                "success": False,
                "error": "No draft migration found. Please create a new migration document."
            }
        
        migration_name = draft_migration[0]['name']
        
        # Try to start it
        from verenigingen.verenigingen.doctype.e_boekhouden_migration.e_boekhouden_migration import start_migration
        result = start_migration(migration_name)
        
        return {
            "success": True,
            "migration_name": migration_name,
            "start_result": result
        }
        
    except Exception as e:
        frappe.log_error(f"Test migration start error: {str(e)}", "Migration Test")
        return {
            "success": False,
            "error": str(e)
        }