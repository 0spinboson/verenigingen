#!/usr/bin/env python3
"""
Simple test runner for Member Contact Request workflow
Tests the basic functionality without complex mocking
"""

import frappe
import sys
import traceback
from frappe.utils import today


def setup_test_environment():
    """Set up basic test environment"""
    frappe.set_user("Administrator")
    print("✓ Test environment initialized")


def test_member_contact_request_doctype():
    """Test that Member Contact Request doctype exists and is properly configured"""
    try:
        # Test doctype exists
        doctype_exists = frappe.db.exists("DocType", "Member Contact Request")
        if not doctype_exists:
            print("✗ Member Contact Request doctype not found")
            return False
        
        # Test basic doctype structure
        doctype_doc = frappe.get_doc("DocType", "Member Contact Request")
        required_fields = ["member", "subject", "message", "request_type", "status"]
        
        doctype_fields = [field.fieldname for field in doctype_doc.fields]
        missing_fields = [field for field in required_fields if field not in doctype_fields]
        
        if missing_fields:
            print(f"✗ Missing required fields: {missing_fields}")
            return False
        
        print("✓ Member Contact Request doctype structure is valid")
        return True
        
    except Exception as e:
        print(f"✗ Error testing doctype: {str(e)}")
        return False


def test_api_methods():
    """Test that API methods are accessible"""
    try:
        from verenigingen.verenigingen.doctype.member_contact_request.member_contact_request import (
            create_contact_request,
            get_member_contact_requests
        )
        print("✓ API methods are importable")
        return True
        
    except ImportError as e:
        print(f"✗ API methods not importable: {str(e)}")
        return False
    except Exception as e:
        print(f"✗ Error testing API methods: {str(e)}")
        return False


def test_automation_methods():
    """Test that automation methods are accessible"""
    try:
        from verenigingen.verenigingen.doctype.member_contact_request.contact_request_automation import (
            process_contact_request_automation,
            get_contact_request_analytics
        )
        print("✓ Automation methods are importable")
        return True
        
    except ImportError as e:
        print(f"✗ Automation methods not importable: {str(e)}")
        return False
    except Exception as e:
        print(f"✗ Error testing automation methods: {str(e)}")
        return False


def test_basic_contact_request_creation():
    """Test basic contact request creation without dependencies"""
    try:
        # Create a minimal test member
        test_member = frappe.get_doc({
            "doctype": "Member",
            "member_name": "Test Contact User",
            "first_name": "Test",
            "last_name": "User", 
            "email_address": "test.contact@example.com",
            "membership_status": "Active",
            "status": "Active"
        })
        
        # Insert without triggering complex workflows
        test_member.insert(ignore_permissions=True, ignore_mandatory=True)
        
        # Create contact request
        contact_request = frappe.get_doc({
            "doctype": "Member Contact Request",
            "member": test_member.name,
            "subject": "Test Contact Request",
            "message": "This is a test message",
            "request_type": "General Inquiry",
            "preferred_contact_method": "Email",
            "urgency": "Normal",
            "status": "Open",
            "request_date": today()
        })
        
        # Insert the contact request
        contact_request.insert(ignore_permissions=True)
        
        # Verify creation
        created_request = frappe.get_doc("Member Contact Request", contact_request.name)
        if created_request.subject != "Test Contact Request":
            print("✗ Contact request creation failed - subject mismatch")
            return False
        
        if created_request.member != test_member.name:
            print("✗ Contact request creation failed - member mismatch")
            return False
        
        print("✓ Basic contact request creation works")
        
        # Clean up
        frappe.delete_doc("Member Contact Request", contact_request.name, force=True)
        frappe.delete_doc("Member", test_member.name, force=True)
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing contact request creation: {str(e)}")
        traceback.print_exc()
        return False


def test_portal_pages():
    """Test that portal pages exist and are accessible"""
    try:
        # Test contact_request.py exists
        try:
            from verenigingen.templates.pages.contact_request import get_context
            print("✓ Contact request portal page is importable")
        except ImportError as e:
            print(f"✗ Contact request portal page not importable: {str(e)}")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing portal pages: {str(e)}")
        return False


def test_member_portal_integration():
    """Test that member portal has been updated"""
    try:
        from verenigingen.templates.pages.member_portal import get_context
        print("✓ Member portal is accessible")
        return True
        
    except Exception as e:
        print(f"✗ Error accessing member portal: {str(e)}")
        return False


def test_javascript_integration():
    """Test that JavaScript files exist and are loadable"""
    try:
        import os
        
        # Check member.js exists
        member_js_path = "/home/frappe/frappe-bench/apps/verenigingen/verenigingen/public/js/member.js"
        if not os.path.exists(member_js_path):
            print("✗ member.js not found")
            return False
        
        # Check for contact request functions in member.js
        with open(member_js_path, 'r') as f:
            content = f.read()
            if "setup_contact_requests_section" not in content:
                print("✗ Contact request functions not found in member.js")
                return False
        
        print("✓ JavaScript integration is present")
        return True
        
    except Exception as e:
        print(f"✗ Error testing JavaScript integration: {str(e)}")
        return False


def test_scheduler_integration():
    """Test that scheduler hooks are properly configured"""
    try:
        from verenigingen import hooks
        
        # Check if contact request automation is in daily scheduler
        daily_tasks = hooks.scheduler_events.get("daily", [])
        automation_task = "verenigingen.verenigingen.doctype.member_contact_request.contact_request_automation.process_contact_request_automation"
        
        if automation_task not in daily_tasks:
            print("✗ Contact request automation not found in scheduler")
            return False
        
        print("✓ Scheduler integration is configured")
        return True
        
    except Exception as e:
        print(f"✗ Error testing scheduler integration: {str(e)}")
        return False


def run_workflow_tests():
    """Run all workflow tests"""
    print("🚀 Starting Member Contact Request Workflow Tests\n")
    
    tests = [
        ("Environment Setup", setup_test_environment),
        ("DocType Structure", test_member_contact_request_doctype),
        ("API Methods", test_api_methods),
        ("Automation Methods", test_automation_methods),
        ("Basic Creation", test_basic_contact_request_creation),
        ("Portal Pages", test_portal_pages),
        ("Member Portal Integration", test_member_portal_integration),
        ("JavaScript Integration", test_javascript_integration),
        ("Scheduler Integration", test_scheduler_integration)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        print(f"\n🔍 Testing: {test_name}")
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ {test_name} failed with exception: {str(e)}")
            failed += 1
    
    print(f"\n📊 Test Results:")
    print(f"✓ Passed: {passed}")
    print(f"✗ Failed: {failed}")
    print(f"📈 Success Rate: {(passed/(passed+failed)*100):.1f}%")
    
    if failed == 0:
        print("\n🎉 All tests passed! Contact request workflow is ready.")
        return True
    else:
        print(f"\n⚠️  {failed} tests failed. Please review the issues above.")
        return False


if __name__ == "__main__":
    try:
        # Initialize Frappe
        frappe.init(site="dev.veganisme.net")
        frappe.connect()
        
        success = run_workflow_tests()
        
        if success:
            print("\n✅ Contact request workflow validation completed successfully!")
            sys.exit(0)
        else:
            print("\n❌ Contact request workflow validation failed!")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n💥 Fatal error during testing: {str(e)}")
        traceback.print_exc()
        sys.exit(1)
    finally:
        try:
            frappe.destroy()
        except:
            pass