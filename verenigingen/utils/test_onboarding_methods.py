"""
Test onboarding methods
"""

import frappe
from frappe import _

@frappe.whitelist()
def test_generate_members():
    """Test the generate_test_applications method directly"""
    
    try:
        # Import the method directly
        from verenigingen.templates.pages.onboarding_member_setup import generate_test_applications
        
        # Call the method
        result = generate_test_applications()
        
        return {
            "success": True,
            "method_result": result,
            "message": "Method called successfully"
        }
        
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@frappe.whitelist()
def check_member_fields():
    """Check if Member doctype has the required fields"""
    
    try:
        # Get the Member doctype
        meta = frappe.get_meta("Member")
        
        # Check for required fields
        required_fields = [
            "first_name", "last_name", "full_name", "email", 
            "mobile", "postal_code", "city", "birth_date", 
            "gender", "status", "application_status"
        ]
        
        field_info = {}
        missing_fields = []
        
        for field_name in required_fields:
            field = meta.get_field(field_name)
            if field:
                field_info[field_name] = {
                    "exists": True,
                    "fieldtype": field.fieldtype,
                    "label": field.label
                }
            else:
                field_info[field_name] = {"exists": False}
                missing_fields.append(field_name)
        
        # Check if preposition field exists
        preposition_field = meta.get_field("preposition")
        field_info["preposition"] = {
            "exists": bool(preposition_field),
            "fieldtype": preposition_field.fieldtype if preposition_field else None
        }
        
        return {
            "success": True,
            "field_info": field_info,
            "missing_fields": missing_fields,
            "has_all_required": len(missing_fields) == 0
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }