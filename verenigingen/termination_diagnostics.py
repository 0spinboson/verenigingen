import frappe
from frappe import _

def run_pre_setup_diagnostics():
    """Run diagnostics BEFORE attempting workflow setup"""
    
    print("🔍 PRE-SETUP DIAGNOSTICS")
    print("=" * 30)
    
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
    
    # 2. Check required doctypes
    print("\n2. DOCTYPE VERIFICATION")
    print("-" * 22)
    
    required_doctypes = [
        "Membership Termination Request",
        "Termination Appeals Process",
        "Workflow", 
        "Workflow State",
        "Workflow Action Master",
        "Role"
    ]
    
    for doctype in required_doctypes:
        if frappe.db.exists("DocType", doctype):
            print(f"   ✅ {doctype}")
        else:
            print(f"   ❌ {doctype} - MISSING")
            all_good = False
    
    # 3. Check DOCTYPE fields
    print("\n3. REQUIRED FIELD VERIFICATION")
    print("-" * 30)
    
    # Check termination request fields
    if frappe.db.exists("DocType", "Membership Termination Request"):
        meta = frappe.get_meta("Membership Termination Request")
        required_fields = ["status", "member", "termination_type", "requested_by"]
        
        for field in required_fields:
            if meta.has_field(field):
                print(f"   ✅ Membership Termination Request.{field}")
            else:
                print(f"   ❌ Membership Termination Request.{field} - MISSING")
                all_good = False
                
    
    # 4. Test workflow creation capability
    print("\n4. WORKFLOW CREATION TEST")
    print("-" * 25)
    
    try:
        # Dry run - create workflow document but don't save
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
        
        test_workflow.validate()
        print("   ✅ Basic workflow validation passed")
        
    except Exception as e:
        print(f"   ❌ Workflow validation failed: {str(e)}")
        all_good = False
    
    print("\n" + "=" * 30)
    if all_good:
        print("🎉 PRE-SETUP DIAGNOSTICS PASSED")
        print("   System ready for workflow setup!")
    else:
        print("⚠️ PRE-SETUP ISSUES FOUND")
        print("   Fix issues before proceeding with setup")
    print("=" * 30)
    
    return all_good

def run_post_setup_diagnostics():
    """Run diagnostics AFTER workflow setup to verify everything works"""
    
    print("🔍 POST-SETUP DIAGNOSTICS")
    print("=" * 31)
    
    all_good = True
    
    # 1. Check workflows exist and are properly configured
    print("\n1. WORKFLOW VERIFICATION")
    print("-" * 23)
    
    required_workflows = [
        ("Membership Termination Workflow", "Membership Termination Request"),
        ("Termination Appeals Workflow", "Termination Appeals Process")
    ]
    
    for workflow_name, doctype in required_workflows:
        if frappe.db.exists("Workflow", workflow_name):
            try:
                workflow = frappe.get_doc("Workflow", workflow_name)
                print(f"   ✅ {workflow_name}")
                print(f"      - States: {len(workflow.states)}")
                print(f"      - Transitions: {len(workflow.transitions)}")
                print(f"      - Active: {workflow.is_active}")
                print(f"      - Target: {workflow.document_type}")
                
                if len(workflow.states) < 3:
                    print(f"      ⚠️ Too few states ({len(workflow.states)})")
                    all_good = False
                    
                if len(workflow.transitions) < 2:
                    print(f"      ⚠️ Too few transitions ({len(workflow.transitions)})")
                    all_good = False
                    
                if not workflow.is_active:
                    print(f"      ⚠️ Workflow is not active")
                    all_good = False
                    
            except Exception as e:
                print(f"   ❌ {workflow_name} - ERROR: {str(e)}")
                all_good = False
        else:
            print(f"   ❌ {workflow_name} - MISSING")
            all_good = False
    
    # 2. Check workflow masters
    print("\n2. WORKFLOW MASTERS")
    print("-" * 18)
    
    # Check custom workflow states
    custom_states = ["Executed"]
    for state in custom_states:
        if frappe.db.exists("Workflow State", state):
            print(f"   ✅ Workflow State: {state}")
        else:
            print(f"   ⚠️ Workflow State: {state} - MISSING")
    
    # Check custom workflow actions
    custom_actions = ["Execute"]
    for action in custom_actions:
        if frappe.db.exists("Workflow Action Master", action):
            print(f"   ✅ Workflow Action: {action}")
        else:
            print(f"   ⚠️ Workflow Action: {action} - MISSING")
    
    # 3. Check other required doctypes
    print("\n3. SUPPORTING DOCTYPES")
    print("-" * 22)
    
    supporting_doctypes = [
        "Expulsion Report Entry",
        "Appeal Timeline Entry", 
        "Appeal Communication Entry",
        "Termination Audit Entry"
    ]
    
    for doctype in supporting_doctypes:
        if frappe.db.exists("DocType", doctype):
            print(f"   ✅ {doctype}")
        else:
            print(f"   ❌ {doctype} - MISSING")
            all_good = False
    
    print("\n" + "=" * 31)
    if all_good:
        print("🎉 POST-SETUP DIAGNOSTICS PASSED")
        print("   Termination system is ready!")
    else:
        print("⚠️ POST-SETUP ISSUES FOUND")
        print("   Some components need attention")
    print("=" * 31)
    
    return all_good

def run_comprehensive_diagnostics():
    """Run both pre-setup and post-setup diagnostics"""
    
    print("🔍 COMPREHENSIVE TERMINATION SYSTEM DIAGNOSTICS")
    print("=" * 50)
    
    # Run pre-setup checks
    pre_setup_ok = run_pre_setup_diagnostics()
    
    print("\n")  # Spacing
    
    # Run post-setup checks
    post_setup_ok = run_post_setup_diagnostics()
    
    # Overall summary
    print("\n" + "=" * 50)
    print("📊 OVERALL SYSTEM STATUS")
    print("=" * 50)
    
    if pre_setup_ok and post_setup_ok:
        print("🎉 SYSTEM FULLY OPERATIONAL")
        print("   All components working correctly")
    elif pre_setup_ok:
        print("⚠️ SYSTEM PARTIALLY READY")  
        print("   Prerequisites OK, but setup incomplete or has issues")
    else:
        print("❌ SYSTEM NOT READY")
        print("   Prerequisites missing - setup will likely fail")
    
    print("=" * 50)
    
    return pre_setup_ok and post_setup_ok

def fix_common_issues():
    """Fix common setup issues"""
    
    print("🔧 FIXING COMMON ISSUES")
    print("=" * 25)
    
    fixes_applied = 0
    
    # Fix 1: Create Association Manager role
    if not frappe.db.exists("Role", "Association Manager"):
        print("🔧 Creating Association Manager role...")
        try:
            role = frappe.get_doc({
                "doctype": "Role",
                "role_name": "Association Manager",
                "desk_access": 1,
                "is_custom": 1
            })
            role.insert(ignore_permissions=True)
            print("   ✅ Association Manager role created")
            fixes_applied += 1
        except Exception as e:
            print(f"   ❌ Could not create role: {str(e)}")
    
    # Fix 2: Create custom workflow masters
    if not frappe.db.exists("Workflow State", "Executed"):
        print("🔧 Creating 'Executed' workflow state...")
        try:
            state = frappe.get_doc({
                "doctype": "Workflow State",
                "workflow_state_name": "Executed"
            })
            state.insert(ignore_permissions=True)
            print("   ✅ 'Executed' state created")
            fixes_applied += 1
        except Exception as e:
            print(f"   ❌ Could not create state: {str(e)}")
    
    if not frappe.db.exists("Workflow Action Master", "Execute"):
        print("🔧 Creating 'Execute' workflow action...")
        try:
            action = frappe.get_doc({
                "doctype": "Workflow Action Master",
                "workflow_action_name": "Execute"
            })
            action.insert(ignore_permissions=True)
            print("   ✅ 'Execute' action created")
            fixes_applied += 1
        except Exception as e:
            print(f"   ❌ Could not create action: {str(e)}")
    
    if fixes_applied > 0:
        frappe.db.commit()
        print(f"\n🔧 Applied {fixes_applied} fixes")
    else:
        print(f"\n✅ No fixes needed")
    
    return fixes_applied

def cleanup_broken_workflows():
    """Clean up broken workflows"""
    
    print("🧹 CLEANING UP BROKEN WORKFLOWS")
    print("=" * 35)
    
    workflows_to_clean = [
        "Membership Termination Workflow",
        "Termination Appeals Workflow"
    ]
    
    cleaned_count = 0
    
    for workflow_name in workflows_to_clean:
        if frappe.db.exists("Workflow", workflow_name):
            print(f"🗑️ Removing: {workflow_name}")
            try:
                frappe.delete_doc("Workflow", workflow_name, force=True)
                print(f"   ✅ Removed {workflow_name}")
                cleaned_count += 1
            except Exception as e:
                print(f"   ❌ Could not remove {workflow_name}: {str(e)}")
    
    if cleaned_count > 0:
        frappe.db.commit()
        print(f"\n🧹 Cleaned up {cleaned_count} workflows")
    else:
        print(f"\n✅ No workflows to clean up")
    
    return cleaned_count

def run_complete_setup():
    """Run complete setup with diagnostics"""
    
    print("🚀 COMPLETE TERMINATION SYSTEM SETUP")
    print("=" * 40)
    
    try:
        # Step 1: Pre-setup diagnostics
        print("\n📋 Step 1: Pre-setup validation...")
        if not run_pre_setup_diagnostics():
            print("❌ Pre-setup validation failed - fixing issues...")
            fix_common_issues()
        
        # Step 2: Run simplified workflow setup
        print("\n📋 Step 2: Setting up workflows...")
        from verenigingen.simplified_workflow_setup import setup_workflows_simplified
        setup_success = setup_workflows_simplified()
        
        if not setup_success:
            print("⚠️ Workflow setup had issues")
        
        # Step 3: Post-setup verification
        print("\n📋 Step 3: Post-setup verification...")
        run_post_setup_diagnostics()
        
        # Step 4: Final comprehensive check
        print("\n📋 Step 4: Final system check...")
        system_ok = run_comprehensive_diagnostics()
        
        if system_ok:
            print("\n🎉 COMPLETE SETUP SUCCESSFUL!")
        else:
            print("\n⚠️ Setup completed with some issues")
        
        return system_ok
        
    except Exception as e:
        print(f"\n❌ SETUP FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

# API endpoints
@frappe.whitelist()
def api_run_diagnostics():
    """API endpoint for comprehensive diagnostics"""
    try:
        result = run_comprehensive_diagnostics()
        return {"success": True, "system_ok": result}
    except Exception as e:
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def api_pre_setup_check():
    """API endpoint for pre-setup validation"""
    try:
        result = run_pre_setup_diagnostics()
        return {"success": True, "ready_for_setup": result}
    except Exception as e:
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def api_post_setup_check():
    """API endpoint for post-setup verification"""
    try:
        result = run_post_setup_diagnostics()
        return {"success": True, "setup_successful": result}
    except Exception as e:
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def api_fix_issues():
    """API endpoint to fix common issues"""
    try:
        fixes = fix_common_issues()
        return {"success": True, "fixes_applied": fixes}
    except Exception as e:
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def api_cleanup_workflows():
    """API endpoint to cleanup broken workflows"""
    try:
        cleaned = cleanup_broken_workflows()
        return {"success": True, "workflows_cleaned": cleaned}
    except Exception as e:
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def api_complete_setup():
    """API endpoint for complete setup"""
    try:
        result = run_complete_setup()
        return {"success": True, "setup_successful": result}
    except Exception as e:
        return {"success": False, "message": str(e)}

# Main execution
if __name__ == "__main__":
    run_comprehensive_diagnostics()
