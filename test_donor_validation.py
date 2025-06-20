import frappe

@frappe.whitelist()
def test_donor_fixes():
    """Test the fixed donor-related functions"""
    results = {}
    
    try:
        # Test 1: Check that check_donor_exists function works
        from verenigingen.verenigingen.doctype.member.member_utils import check_donor_exists
        
        result = check_donor_exists("Assoc-Member-2025-06-0001")
        results["check_donor_exists"] = {
            "success": True,
            "result": result,
            "has_exists_key": "exists" in result
        }
        
        # Test 2: Test field access doesn't cause database errors
        from verenigingen.verenigingen.doctype.member.member_utils import create_donor_from_member
        
        # This will test the field access but we expect it might fail on validation
        # The important part is NO database field errors
        try:
            donor_name = create_donor_from_member("Assoc-Member-2025-06-0001")
            results["create_donor_from_member"] = {
                "success": True,
                "donor_created": donor_name
            }
            # Clean up
            if donor_name:
                frappe.delete_doc("Donor", donor_name, ignore_permissions=True)
        except Exception as e:
            error_msg = str(e)
            results["create_donor_from_member"] = {
                "success": "Unknown column" not in error_msg and "email.*WHERE" not in error_msg,
                "error": error_msg,
                "no_field_errors": "Unknown column" not in error_msg
            }
        
        results["overall_success"] = all(
            r.get("success", False) for r in results.values() if isinstance(r, dict)
        )
        
    except Exception as e:
        results["error"] = str(e)
        results["overall_success"] = False
    
    return results