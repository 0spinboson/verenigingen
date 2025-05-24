# File: verenigingen/verenigingen/workflow_diagnostics.py
"""
Diagnostic script to check workflow setup requirements
Run this before attempting to create workflows
"""

import frappe

def run_complete_diagnostics():
    """Run complete diagnostic check for workflow setup"""
    
    print("🔍 WORKFLOW SETUP DIAGNOSTICS")
    print("="*50)
    
    all_good = True
    
    # 1. Check required roles
    print("\n1. ROLE VERIFICATION")
    print("-" * 20)
    
    required_roles = ["System Manager", "Association Manager"]
    existing_roles = [r.name for r in frappe.get_all("Role", fields=["name"])]
    
    for role in required_roles:
        if role in existing_roles:
            print(f"   ✅ {role} - EXISTS")
        else:
            print(f"   ❌ {role} - MISSING")
            all_good = False
    
    print(f"\n   Total roles in system: {len(existing_roles)}")
    print(f"   Sample roles: {', '.join(existing_roles[:8])}...")
    
    # 2. Check required doctypes
    print("\n2. DOCTYPE VERIFICATION")
    print("-" * 22)
    
    required_doctypes = [
        "Membership Termination Request",
        "Workflow", 
        "Workflow State",
        "Workflow Transition",
        "Role"
    ]
    
    for doctype in required_doctypes:
        if frappe.db.exists("DocType", doctype):
            print(f"   ✅ {doctype}")
        else:
            print(f"   ❌ {doctype} - MISSING")
            all_good = False
    
    # 3. Check if Membership Termination Request has required fields
    print("\n3. DOCTYPE FIELD VERIFICATION")
    print("-" * 30)
    
    if frappe.db.exists("DocType", "Membership Termination Request"):
        meta = frappe.get_meta("Membership Termination Request")
        required_fields = ["status", "member", "termination_type", "requested_by"]
        
        for field in required_fields:
            if meta.has_field(field):
                print(f"   ✅ Membership Termination Request.{field}")
            else:
                print(f"   ❌ Membership Termination Request.{field} - MISSING")
                all_good = False
    else:
        print("   ❌ Cannot check fields - Membership Termination Request doctype missing")
        all_good = False
    
    # 4. Check existing workflows
    print("\n4. EXISTING WORKFLOWS")
    print("-" * 18)
    
    workflows = frappe.get_all("Workflow", fields=["name", "document_type", "is_active"])
    if workflows:
        for wf in workflows:
            print(f"   📋 {wf.name} -> {wf.document_type} (Active: {wf.is_active})")
    else:
        print("   📋 No existing workflows found")
    
    # 5. Test creating a minimal workflow (dry run)
    print("\n5. WORKFLOW CREATION TEST")
    print("-" * 25)
    
    try:
        # Create a test workflow document (but don't insert it)
        test_workflow = frappe.get_doc({
            "doctype": "Workflow",
            "workflow_name": "Test Workflow - DO NOT SAVE",
            "document_type": "Membership Termination Request",
            "is_active": 0,
            "workflow_state_field": "status",
            "states": [
                {
                    "state": "Draft",
                    "doc_status": "0",
                    "allow_edit": "System Manager"
                }
            ],
            "transitions": []
        })
        
        # Try to validate it without inserting
        test_workflow.validate()
        print("   ✅ Basic workflow validation passed")
        
    except Exception as e:
        print(f"   ❌ Workflow validation failed: {str(e)}")
        all_good = False
    
    # 6. Database permissions check
    print("\n6. PERMISSIONS CHECK")
    print("-" * 18)
    
    try:
        # Test if we can read/write basic doctypes
        test_read = frappe.get_all("Role", limit=1)
        print("   ✅ Can read Role doctype")
        
        # Test if we can create a role (dry run)
        if not frappe.db.exists("Role", "TEST_DIAGNOSTIC_ROLE"):
            test_role = frappe.get_doc({
                "doctype": "Role",
                "role_name": "TEST_DIAGNOSTIC_ROLE",
                "desk_access": 1,
                "is_custom": 1
            })
            # Don't actually insert, just validate
            test_role.validate()
            print("   ✅ Can create Role doctype (dry run)")
        else:
            print("   ✅ Can check Role existence")
            
    except Exception as e:
        print(f"   ❌ Permission issue: {str(e)}")
        all_good = False
    
    # 7. Summary
    print("\n" + "="*50)
    if all_good:
        print("🎉 ALL DIAGNOSTICS PASSED")
        print("   Your system should be ready for workflow setup!")
    else:
        print("⚠️  ISSUES FOUND")
        print("   Please resolve the issues marked with ❌ before proceeding")
    print("="*50)
    
    return all_good

def create_missing_roles():
    """Create any missing roles that are required"""
    
    print("\n🔧 CREATING MISSING ROLES")
    print("-" * 25)
    
    required_roles = [
        {
            "role_name": "Association Manager",
            "desk_access": 1,
            "is_custom": 1
        }
    ]
    
    created_count = 0
    
    for role_config in required_roles:
        role_name = role_config["role_name"]
        
        if not frappe.db.exists("Role", role_name):
            try:
                role_doc = frappe.get_doc({
                    "doctype": "Role",
                    **role_config
                })
                role_doc.insert(ignore_permissions=True)
                frappe.db.commit()
                print(f"   ✅ Created role: {role_name}")
                created_count += 1
            except Exception as e:
                print(f"   ❌ Failed to create role {role_name}: {str(e)}")
        else:
            print(f"   ✅ Role already exists: {role_name}")
    
    print(f"\n   Created {created_count} new roles")
    return created_count > 0

def fix_common_issues():
    """Attempt to fix common workflow setup issues"""
    
    print("\n🔧 ATTEMPTING TO FIX COMMON ISSUES")
    print("-" * 35)
    
    fixes_applied = 0
    
    # Fix 1: Create missing Association Manager role
    if not frappe.db.exists("Role", "Association Manager"):
        print("   🔧 Creating Association Manager role...")
        try:
            role = frappe.get_doc({
                "doctype": "Role",
                "role_name": "Association Manager",
                "desk_access": 1,
                "is_custom": 1
            })
            role.insert(ignore_permissions=True)
            frappe.db.commit()
            print("   ✅ Association Manager role created")
            fixes_applied += 1
        except Exception as e:
            print(f"   ❌ Failed to create Association Manager role: {str(e)}")
    
    print(f"\n   Applied {fixes_applied} fixes")
    return fixes_applied > 0

@frappe.whitelist()
def run_diagnostics():
    """API endpoint for running diagnostics"""
    return run_complete_diagnostics()

@frappe.whitelist() 
def run_fixes():
    """API endpoint for running fixes"""
    return fix_common_issues()

if __name__ == "__main__":
    run_complete_diagnostics()
