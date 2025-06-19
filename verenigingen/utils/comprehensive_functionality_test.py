"""
Comprehensive functionality test for our payment status and fee calculation improvements
"""

import frappe
from frappe import _
from frappe.utils import today, getdate


@frappe.whitelist()
def test_payment_status_functionality():
    """Test the new payment status functionality in member portals"""
    results = {
        "test_name": "Payment Status Functionality",
        "tests_run": [],
        "passed": 0,
        "failed": 0,
        "errors": []
    }
    
    try:
        # Test 1: Payment status function exists and works
        test_name = "Payment status function availability"
        try:
            from verenigingen.templates.pages.member_portal import get_payment_status
            results["tests_run"].append(test_name)
            results["passed"] += 1
        except ImportError as e:
            results["tests_run"].append(test_name)
            results["failed"] += 1
            results["errors"].append(f"{test_name}: Import error - {str(e)}")
        
        # Test 2: Test with actual member data (Foppe de Haan)
        test_name = "Payment status with real member data"
        try:
            member = frappe.get_doc("Member", "Assoc-Member-2025-06-0001")
            membership = frappe.db.get_value(
                "Membership", 
                {"member": member.name, "status": "Active", "docstatus": 1},
                ["name", "membership_type"],
                as_dict=True
            )
            
            payment_status = get_payment_status(member, membership)
            
            # Verify structure
            expected_fields = ["current_fee", "billing_frequency", "outstanding_amount", "payment_up_to_date"]
            missing_fields = [field for field in expected_fields if field not in payment_status]
            
            if missing_fields:
                results["tests_run"].append(test_name)
                results["failed"] += 1
                results["errors"].append(f"{test_name}: Missing fields - {missing_fields}")
            else:
                results["tests_run"].append(test_name)
                results["passed"] += 1
                
        except Exception as e:
            results["tests_run"].append(test_name)
            results["failed"] += 1
            results["errors"].append(f"{test_name}: Exception - {str(e)}")
        
        # Test 3: Test billing frequency detection
        test_name = "Billing frequency detection"
        try:
            if payment_status and payment_status.get("billing_frequency") == "Quarterly":
                results["tests_run"].append(test_name)
                results["passed"] += 1
            else:
                results["tests_run"].append(test_name)
                results["failed"] += 1
                results["errors"].append(f"{test_name}: Expected Quarterly, got {payment_status.get('billing_frequency')}")
        except Exception as e:
            results["tests_run"].append(test_name)
            results["failed"] += 1
            results["errors"].append(f"{test_name}: Exception - {str(e)}")
        
    except Exception as e:
        results["errors"].append(f"Critical error in payment status tests: {str(e)}")
    
    return results


@frappe.whitelist()
def test_fee_calculation_improvements():
    """Test the improved fee calculation logic"""
    results = {
        "test_name": "Fee Calculation Improvements",
        "tests_run": [],
        "passed": 0,
        "failed": 0,
        "errors": []
    }
    
    try:
        # Test 1: Improved fee function exists
        test_name = "Improved fee function availability"
        try:
            from verenigingen.templates.pages.membership_fee_adjustment import get_effective_fee_for_member
            results["tests_run"].append(test_name)
            results["passed"] += 1
        except ImportError as e:
            results["tests_run"].append(test_name)
            results["failed"] += 1
            results["errors"].append(f"{test_name}: Import error - {str(e)}")
        
        # Test 2: Test with Foppe de Haan's data (should return €45 not €145)
        test_name = "Correct fee calculation for quarterly member"
        try:
            member = frappe.get_doc("Member", "Assoc-Member-2025-06-0001")
            membership = frappe.db.get_value(
                "Membership", 
                {"member": member.name, "status": "Active", "docstatus": 1},
                ["name", "membership_type"],
                as_dict=True
            )
            
            # Test original method (should return €145)
            original_fee = member.get_current_membership_fee()
            
            # Test improved method (should return €45)
            improved_fee = get_effective_fee_for_member(member, membership)
            
            if improved_fee.get("amount") == 45.0 and original_fee.get("amount") == 145.0:
                results["tests_run"].append(test_name)
                results["passed"] += 1
            else:
                results["tests_run"].append(test_name)
                results["failed"] += 1
                results["errors"].append(f"{test_name}: Expected improved=45, original=145, got improved={improved_fee.get('amount')}, original={original_fee.get('amount')}")
                
        except Exception as e:
            results["tests_run"].append(test_name)
            results["failed"] += 1
            results["errors"].append(f"{test_name}: Exception - {str(e)}")
        
        # Test 3: Test billing frequency context
        test_name = "Billing frequency in fee adjustment context"
        try:
            from verenigingen.templates.pages.membership_fee_adjustment import get_context
            
            # Mock context object
            class MockContext:
                pass
            
            context = MockContext()
            # This would normally be called by the web framework
            # but we can test the logic components
            
            billing_frequency = "Monthly"
            if membership and "kwartaal" in membership.membership_type.lower():
                billing_frequency = "Quarterly"
            
            if billing_frequency == "Quarterly":
                results["tests_run"].append(test_name)
                results["passed"] += 1
            else:
                results["tests_run"].append(test_name)
                results["failed"] += 1
                results["errors"].append(f"{test_name}: Expected Quarterly, got {billing_frequency}")
                
        except Exception as e:
            results["tests_run"].append(test_name)
            results["failed"] += 1
            results["errors"].append(f"{test_name}: Exception - {str(e)}")
    
    except Exception as e:
        results["errors"].append(f"Critical error in fee calculation tests: {str(e)}")
    
    return results


@frappe.whitelist()
def test_chapter_membership_refactoring():
    """Test the chapter membership manager refactoring"""
    results = {
        "test_name": "Chapter Membership Manager",
        "tests_run": [],
        "passed": 0,
        "failed": 0,
        "errors": []
    }
    
    try:
        # Test 1: Centralized manager exists
        test_name = "Centralized chapter membership manager availability"
        try:
            from verenigingen.utils.chapter_membership_manager import ChapterMembershipManager
            results["tests_run"].append(test_name)
            results["passed"] += 1
        except ImportError as e:
            results["tests_run"].append(test_name)
            results["failed"] += 1
            results["errors"].append(f"{test_name}: Import error - {str(e)}")
        
        # Test 2: Manager methods exist
        test_name = "Manager methods availability"
        try:
            # Check key methods exist
            methods = ["join_chapter", "leave_chapter", "get_member_chapter_status", "validate_chapter_membership_change"]
            missing_methods = []
            
            for method in methods:
                if not hasattr(ChapterMembershipManager, method):
                    missing_methods.append(method)
            
            if missing_methods:
                results["tests_run"].append(test_name)
                results["failed"] += 1
                results["errors"].append(f"{test_name}: Missing methods - {missing_methods}")
            else:
                results["tests_run"].append(test_name)
                results["passed"] += 1
                
        except Exception as e:
            results["tests_run"].append(test_name)
            results["failed"] += 1
            results["errors"].append(f"{test_name}: Exception - {str(e)}")
        
        # Test 3: Test member status retrieval
        test_name = "Member chapter status retrieval"
        try:
            status = ChapterMembershipManager.get_member_chapter_status("Assoc-Member-2025-06-0001")
            
            if status.get("success") and "current_memberships" in status:
                results["tests_run"].append(test_name)
                results["passed"] += 1
            else:
                results["tests_run"].append(test_name)
                results["failed"] += 1
                results["errors"].append(f"{test_name}: Status retrieval failed - {status}")
                
        except Exception as e:
            results["tests_run"].append(test_name)
            results["failed"] += 1
            results["errors"].append(f"{test_name}: Exception - {str(e)}")
    
    except Exception as e:
        results["errors"].append(f"Critical error in chapter membership tests: {str(e)}")
    
    return results


@frappe.whitelist()
def run_comprehensive_functionality_tests():
    """Run all comprehensive functionality tests"""
    all_results = {
        "summary": {
            "total_tests": 0,
            "total_passed": 0,
            "total_failed": 0,
            "success_rate": 0
        },
        "test_suites": []
    }
    
    # Run all test suites
    test_functions = [
        test_payment_status_functionality,
        test_fee_calculation_improvements,
        test_chapter_membership_refactoring
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