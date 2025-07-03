#!/usr/bin/env python3

import frappe

@frappe.whitelist()
def test_group_mappings():
    """Test the group mapping functionality"""
    try:
        # Get E-Boekhouden settings
        settings = frappe.get_single("E-Boekhouden Settings")
        
        # Test parsing function
        from verenigingen.verenigingen.doctype.e_boekhouden_migration.e_boekhouden_migration import EBoekhoudenMigration
        migration = EBoekhoudenMigration()
        
        # Parse mappings
        mappings = migration.parse_account_group_mappings(settings)
        
        return {
            "success": True,
            "mappings_count": len(mappings),
            "mappings": mappings,
            "settings_field_exists": hasattr(settings, 'account_group_mappings'),
            "settings_value": getattr(settings, 'account_group_mappings', 'Field not found')
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

if __name__ == "__main__":
    frappe.connect()
    result = test_group_mappings()
    print(result)