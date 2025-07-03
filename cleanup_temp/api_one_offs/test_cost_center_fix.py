import frappe
import json

@frappe.whitelist()
def test_cost_center_with_empty_name():
    """Test creating a cost center with empty name"""
    
    from verenigingen.utils.eboekhouden_cost_center_fix import create_cost_center_safe
    
    # Test data simulating the problematic cost center
    test_cc_data = {
        "id": 411632,
        "code": "",
        "name": "",  # Empty name
        "description": "Test Description",
        "parentId": 0
    }
    
    # Get test company
    company = frappe.db.get_value("Company", {}, "name")
    
    # Try to create the cost center
    result = create_cost_center_safe(test_cc_data, company, None, {})
    
    return {
        "test_data": test_cc_data,
        "result": result,
        "company": company
    }

@frappe.whitelist()
def check_migration_errors():
    """Check recent migration errors"""
    
    # Get recent error logs
    errors = frappe.db.sql("""
        SELECT name, method, error, creation
        FROM `tabError Log`
        WHERE method LIKE '%E-Boekhouden%'
           OR error LIKE '%Cost center%'
           OR error LIKE '%mutation_type_distribution%'
        ORDER BY creation DESC
        LIMIT 10
    """, as_dict=True)
    
    # Get latest migration status
    latest_migration = frappe.db.get_value(
        "E-Boekhouden Migration",
        {},
        ["name", "migration_status", "current_operation", "error_log"],
        order_by="creation desc",
        as_dict=True
    )
    
    return {
        "recent_errors": errors,
        "latest_migration": latest_migration
    }