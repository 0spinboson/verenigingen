"""
E-Boekhouden Cost Center Fix
Handles cost center creation and migration issues
"""

import frappe
from frappe import _
from frappe.utils import cstr


@frappe.whitelist()
def create_cost_center_safe(cost_center_name, company, parent_cost_center=None):
    """
    Safely create a cost center with proper error handling
    
    Args:
        cost_center_name: Name of the cost center
        company: Company name
        parent_cost_center: Parent cost center (optional)
    
    Returns:
        dict with success status and cost center name or error
    """
    try:
        # Validate inputs
        if not cost_center_name:
            return {
                "success": False,
                "error": "Cost center name is required"
            }
        
        if not company:
            return {
                "success": False,
                "error": "Company is required"
            }
        
        # Clean the cost center name
        cost_center_name = cstr(cost_center_name).strip()
        
        # Check if cost center already exists
        existing = frappe.db.get_value(
            "Cost Center",
            {
                "cost_center_name": cost_center_name,
                "company": company
            },
            "name"
        )
        
        if existing:
            return {
                "success": True,
                "cost_center": existing,
                "message": "Cost center already exists"
            }
        
        # If no parent specified, try to find the company's main cost center
        if not parent_cost_center:
            # First try to find "Main - Company"
            parent_cost_center = frappe.db.get_value(
                "Cost Center",
                {
                    "cost_center_name": "Main",
                    "company": company,
                    "is_group": 1
                },
                "name"
            )
            
            # If not found, get the root cost center for the company
            if not parent_cost_center:
                parent_cost_center = frappe.db.get_value(
                    "Cost Center",
                    {
                        "company": company,
                        "parent_cost_center": "",
                        "is_group": 1
                    },
                    "name"
                )
        
        if not parent_cost_center:
            return {
                "success": False,
                "error": f"No parent cost center found for company {company}"
            }
        
        # Create the cost center
        cost_center = frappe.get_doc({
            "doctype": "Cost Center",
            "cost_center_name": cost_center_name,
            "parent_cost_center": parent_cost_center,
            "company": company,
            "is_group": 0
        })
        
        cost_center.insert(ignore_permissions=True)
        
        return {
            "success": True,
            "cost_center": cost_center.name,
            "message": f"Cost center {cost_center.name} created successfully"
        }
        
    except frappe.exceptions.DuplicateEntryError:
        # Handle race condition where cost center was created between check and insert
        existing = frappe.db.get_value(
            "Cost Center",
            {
                "cost_center_name": cost_center_name,
                "company": company
            },
            "name"
        )
        
        if existing:
            return {
                "success": True,
                "cost_center": existing,
                "message": "Cost center already exists (created by another process)"
            }
        else:
            return {
                "success": False,
                "error": "Duplicate entry error but cost center not found"
            }
            
    except Exception as e:
        frappe.log_error(
            f"Error creating cost center {cost_center_name}: {str(e)}",
            "Cost Center Creation Error"
        )
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def fix_cost_center_migration(migration_name=None):
    """
    Fix cost center migration issues
    
    Args:
        migration_name: Optional E-Boekhouden Migration name
    
    Returns:
        dict with results
    """
    try:
        results = {
            "fixed": [],
            "errors": [],
            "skipped": []
        }
        
        # Get default company from settings
        settings = frappe.get_single("E-Boekhouden Settings")
        default_company = settings.default_company
        
        if not default_company:
            return {
                "success": False,
                "error": "No default company set in E-Boekhouden Settings"
            }
        
        # If migration specified, get cost centers from that migration
        if migration_name:
            # This would need to be implemented based on how cost centers
            # are stored in the migration
            pass
        
        # Get all cost centers that might need fixing
        problem_cost_centers = frappe.db.sql("""
            SELECT DISTINCT cost_center_name
            FROM `tabCost Center`
            WHERE company = %s
            AND (parent_cost_center IS NULL OR parent_cost_center = '')
            AND name != (
                SELECT name FROM `tabCost Center`
                WHERE company = %s
                AND parent_cost_center = ''
                AND is_group = 1
                LIMIT 1
            )
        """, (default_company, default_company), as_dict=True)
        
        for cc in problem_cost_centers:
            result = create_cost_center_safe(
                cc.cost_center_name,
                default_company
            )
            
            if result["success"]:
                results["fixed"].append(cc.cost_center_name)
            else:
                results["errors"].append({
                    "cost_center": cc.cost_center_name,
                    "error": result["error"]
                })
        
        return {
            "success": True,
            "results": results,
            "summary": f"Fixed {len(results['fixed'])} cost centers, {len(results['errors'])} errors"
        }
        
    except Exception as e:
        frappe.log_error(
            f"Error fixing cost center migration: {str(e)}",
            "Cost Center Migration Fix Error"
        )
        return {
            "success": False,
            "error": str(e)
        }


def get_or_create_cost_center(cost_center_name, company):
    """
    Get existing cost center or create new one
    
    This is a helper function for use in migrations
    """
    result = create_cost_center_safe(cost_center_name, company)
    
    if result["success"]:
        return result["cost_center"]
    else:
        frappe.log_error(
            f"Failed to get/create cost center {cost_center_name}: {result['error']}",
            "Cost Center Creation"
        )
        return None


@frappe.whitelist()
def ensure_root_cost_center(company):
    """
    Ensure a root cost center exists for the company
    
    Args:
        company: Company name
    
    Returns:
        Root cost center name or None
    """
    try:
        # First check if a root cost center already exists
        root_cc = frappe.db.get_value(
            "Cost Center",
            {
                "company": company,
                "is_group": 1,
                "parent_cost_center": ""
            },
            "name"
        )
        
        if root_cc:
            return root_cc
        
        # Try to find the main cost center
        main_cc = frappe.db.get_value(
            "Cost Center",
            {
                "company": company,
                "cost_center_name": "Main",
                "is_group": 1
            },
            "name"
        )
        
        if main_cc:
            return main_cc
        
        # If no root exists, create one
        try:
            # Get company abbreviation
            company_abbr = frappe.db.get_value("Company", company, "abbr")
            if not company_abbr:
                frappe.log_error(
                    f"Company {company} not found or has no abbreviation",
                    "Cost Center Creation"
                )
                return None
            
            # Create root cost center
            root_cc = frappe.get_doc({
                "doctype": "Cost Center",
                "cost_center_name": "Main",
                "company": company,
                "is_group": 1,
                "parent_cost_center": ""
            })
            
            root_cc.insert(ignore_permissions=True)
            
            return root_cc.name
            
        except frappe.exceptions.DuplicateEntryError:
            # Handle race condition - try to find it again
            root_cc = frappe.db.get_value(
                "Cost Center",
                {
                    "company": company,
                    "is_group": 1,
                    "parent_cost_center": ""
                },
                "name"
            )
            return root_cc
            
    except Exception as e:
        frappe.log_error(
            f"Error ensuring root cost center for {company}: {str(e)}",
            "Root Cost Center Creation"
        )
        return None