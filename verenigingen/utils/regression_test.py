"""
Regression tests for our changes to ensure existing functionality still works
"""

import frappe
from frappe import _


@frappe.whitelist()
def test_existing_member_functionality():
    """Test that existing member functionality still works after our changes"""
    results = {
        "test_name": "Existing Member Functionality Regression",
        "tests_run": [],
        "passed": 0,
        "failed": 0,
        "errors": []
    }
    
    try:
        # Test 1: Original get_current_membership_fee still works
        test_name = "Original get_current_membership_fee method"
        try:
            member = frappe.get_doc("Member", "Assoc-Member-2025-06-0001")
            fee_info = member.get_current_membership_fee()
            
            if fee_info and "amount" in fee_info and "source" in fee_info:
                results["tests_run"].append(test_name)
                results["passed"] += 1
            else:
                results["tests_run"].append(test_name)
                results["failed"] += 1
                results["errors"].append(f"{test_name}: Invalid fee info structure - {fee_info}")
                
        except Exception as e:
            results["tests_run"].append(test_name)
            results["failed"] += 1
            results["errors"].append(f"{test_name}: Exception - {str(e)}")
        
        # Test 2: Member can be loaded and basic properties work
        test_name = "Member basic properties"
        try:
            member = frappe.get_doc("Member", "Assoc-Member-2025-06-0001")
            
            required_fields = ["name", "full_name", "email", "status"]
            missing_fields = [field for field in required_fields if not hasattr(member, field) or not getattr(member, field)]
            
            if missing_fields:
                results["tests_run"].append(test_name)
                results["failed"] += 1
                results["errors"].append(f"{test_name}: Missing required fields - {missing_fields}")
            else:
                results["tests_run"].append(test_name)
                results["passed"] += 1
                
        except Exception as e:
            results["tests_run"].append(test_name)
            results["failed"] += 1
            results["errors"].append(f"{test_name}: Exception - {str(e)}")
        
        # Test 3: Membership can be retrieved
        test_name = "Membership retrieval"
        try:
            membership = frappe.db.get_value(
                "Membership",
                {"member": "Assoc-Member-2025-06-0001", "status": "Active", "docstatus": 1},
                ["name", "membership_type", "status"],
                as_dict=True
            )
            
            if membership and membership.get("name"):
                results["tests_run"].append(test_name)
                results["passed"] += 1
            else:
                results["tests_run"].append(test_name)
                results["failed"] += 1
                results["errors"].append(f"{test_name}: No active membership found")
                
        except Exception as e:
            results["tests_run"].append(test_name)
            results["failed"] += 1
            results["errors"].append(f"{test_name}: Exception - {str(e)}")
        
        # Test 4: Chapter memberships can be retrieved
        test_name = "Chapter membership retrieval"
        try:
            chapter_memberships = frappe.db.sql("""
                SELECT parent, enabled, member 
                FROM `tabChapter Member` 
                WHERE member = %s
            """, ("Assoc-Member-2025-06-0001",), as_dict=True)
            
            if len(chapter_memberships) > 0:
                results["tests_run"].append(test_name)
                results["passed"] += 1
            else:
                results["tests_run"].append(test_name)
                results["failed"] += 1
                results["errors"].append(f"{test_name}: No chapter memberships found")
                
        except Exception as e:
            results["tests_run"].append(test_name)
            results["failed"] += 1
            results["errors"].append(f"{test_name}: Exception - {str(e)}")
    
    except Exception as e:
        results["errors"].append(f"Critical error in regression tests: {str(e)}")
    
    return results


@frappe.whitelist()
def test_chapter_member_validation():
    """Test our new Chapter Member validation doesn't break existing functionality"""
    results = {
        "test_name": "Chapter Member Validation",
        "tests_run": [],
        "passed": 0,
        "failed": 0,
        "errors": []
    }
    
    try:
        # Test 1: Existing Chapter Member records can be loaded
        test_name = "Existing Chapter Member loading"
        try:
            chapter_members = frappe.db.get_all("Chapter Member", limit=5, fields=["name"])
            
            if len(chapter_members) > 0:
                # Try to load one of them
                cm = frappe.get_doc("Chapter Member", chapter_members[0].name)
                results["tests_run"].append(test_name)
                results["passed"] += 1
            else:
                results["tests_run"].append(test_name)
                results["failed"] += 1
                results["errors"].append(f"{test_name}: No Chapter Member records found")
                
        except Exception as e:
            results["tests_run"].append(test_name)
            results["failed"] += 1
            results["errors"].append(f"{test_name}: Exception - {str(e)}")
        
        # Test 2: Chapter Member validation class exists
        test_name = "Chapter Member validation class"
        try:
            from verenigingen.verenigingen.doctype.chapter_member.chapter_member import ChapterMember
            
            # Check if our new methods exist
            if hasattr(ChapterMember, 'validate_chapter_membership_tracking'):
                results["tests_run"].append(test_name)
                results["passed"] += 1
            else:
                results["tests_run"].append(test_name)
                results["failed"] += 1
                results["errors"].append(f"{test_name}: Validation method not found")
                
        except Exception as e:
            results["tests_run"].append(test_name)
            results["failed"] += 1
            results["errors"].append(f"{test_name}: Exception - {str(e)}")
    
    except Exception as e:
        results["errors"].append(f"Critical error in validation tests: {str(e)}")
    
    return results


@frappe.whitelist()
def test_api_endpoints():
    """Test that our updated API endpoints still work"""
    results = {
        "test_name": "API Endpoints",
        "tests_run": [],
        "passed": 0,
        "failed": 0,
        "errors": []
    }
    
    try:
        # Test 1: Chapter join API exists
        test_name = "Chapter join API availability"
        try:
            from verenigingen.api.chapter_join import join_chapter, get_chapter_join_context
            results["tests_run"].append(test_name)
            results["passed"] += 1
        except ImportError as e:
            results["tests_run"].append(test_name)
            results["failed"] += 1
            results["errors"].append(f"{test_name}: Import error - {str(e)}")
        
        # Test 2: Member management API exists
        test_name = "Member management API availability"
        try:
            from verenigingen.api.member_management import assign_member_to_chapter
            results["tests_run"].append(test_name)
            results["passed"] += 1
        except ImportError as e:
            results["tests_run"].append(test_name)
            results["failed"] += 1
            results["errors"].append(f"{test_name}: Import error - {str(e)}")
        
        # Test 3: Chapter context can be retrieved
        test_name = "Chapter context retrieval"
        try:
            context = get_chapter_join_context("Zeist")
            
            if context and context.get("success") is not False:
                results["tests_run"].append(test_name)
                results["passed"] += 1
            else:
                results["tests_run"].append(test_name)
                results["failed"] += 1
                results["errors"].append(f"{test_name}: Context retrieval failed - {context}")
                
        except Exception as e:
            results["tests_run"].append(test_name)
            results["failed"] += 1
            results["errors"].append(f"{test_name}: Exception - {str(e)}")
    
    except Exception as e:
        results["errors"].append(f"Critical error in API tests: {str(e)}")
    
    return results


@frappe.whitelist()
def run_all_regression_tests():
    """Run all regression tests"""
    all_results = {
        "summary": {
            "total_tests": 0,
            "total_passed": 0,
            "total_failed": 0,
            "success_rate": 0
        },
        "test_suites": []
    }
    
    test_functions = [
        test_existing_member_functionality,
        test_chapter_member_validation,
        test_api_endpoints
    ]
    
    for test_func in test_functions:
        try:
            result = test_func()
            all_results["test_suites"].append(result)
            
            all_results["summary"]["total_tests"] += len(result["tests_run"])
            all_results["summary"]["total_passed"] += result["passed"]
            all_results["summary"]["total_failed"] += result["failed"]
            
        except Exception as e:
            error_result = {
                "test_name": test_func.__name__,
                "tests_run": [],
                "passed": 0,
                "failed": 1,
                "errors": [f"Critical error: {str(e)}"]
            }
            all_results["test_suites"].append(error_result)
            all_results["summary"]["total_failed"] += 1
    
    # Calculate success rate
    total = all_results["summary"]["total_tests"]
    passed = all_results["summary"]["total_passed"]
    all_results["summary"]["success_rate"] = (passed / total * 100) if total > 0 else 0
    
    return all_results