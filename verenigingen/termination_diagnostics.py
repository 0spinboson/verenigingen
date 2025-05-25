# File: verenigingen/termination_diagnostics.py
"""
Minimal diagnostic and troubleshooting tools for termination system
Keep only the useful parts from setup_termination_system_cli.py
"""

import frappe
from frappe import _

def run_diagnostics():
    """Run comprehensive diagnostics - KEEP THIS"""
    
    print("🔍 TERMINATION SYSTEM DIAGNOSTICS")
    print("=" * 40)
    
    all_good = True
    
    # 1. Check required doctypes
    print("\n1. DOCTYPE CHECK")
    print("-" * 15)
    
    required_doctypes = [
        "Membership Termination Request",
        "Termination Appeals Process", 
        "Expulsion Report Entry",
        "Appeal Timeline Entry",
        "Appeal Communication Entry",
        "Termination Audit Entry"
    ]
    
    for doctype in required_doctypes:
        if frappe.db.exists("DocType", doctype):
            print(f"   ✅ {doctype}")
        else:
            print(f"   ❌ {doctype} - MISSING")
            all_good = False
    
    # 2. Check roles
    print("\n2. ROLE CHECK")
    print("-" * 12)
    
    required_roles = ["System Manager", "Association Manager"]
    
    for role in required_roles:
        if frappe.db.exists("Role", role):
            print(f"   ✅ {role}")
        else:
            print(f"   ❌ {role} - MISSING")
            all_good = False
    
    # 3. Check workflows
    print("\n3. WORKFLOW CHECK")
    print("-" * 15)
    
    workflows = ["Membership Termination Workflow", "Termination Appeals Workflow"]
    workflow_count = 0
    
    for workflow in workflows:
        if frappe.db.exists("Workflow", workflow):
            workflow_count += 1
            print(f"   ✅ {workflow}")
            
            # Check workflow details
            wf_doc = frappe.get_doc("Workflow", workflow)
            print(f"      - States: {len(wf_doc.states)}")
            print(f"      - Transitions: {len(wf_doc.transitions)}")
            print(f"      - Active: {wf_doc.is_active}")
        else:
            print(f"   ❌ {workflow} - MISSING")
            all_good = False
    
    # 4. Check workflow masters
    print("\n4. WORKFLOW MASTERS CHECK")
    print("-" * 23)
    
    # Check custom workflow states
    if frappe.db.exists("Workflow State", "Executed"):
        print("   ✅ Custom 'Executed' state exists")
    else:
        print("   ⚠️ Custom 'Executed' state missing")
    
    # Check custom workflow actions  
    if frappe.db.exists("Workflow Action Master", "Execute"):
        print("   ✅ Custom 'Execute' action exists")
    else:
        print("   ⚠️ Custom 'Execute' action missing")
    
    # 5. Summary
    print("\n" + "=" * 40)
    if all_good:
        print("✅ ALL DIAGNOSTICS PASSED")
    else:
        print("⚠️ SOME ISSUES FOUND")
        print("   Please review the items marked with ❌")
    print("=" * 40)
    
    return all_good

def verify_workflow_functionality():
    """Verify workflows are working properly - KEEP THIS"""
    
    print("🔍 Verifying workflow functionality...")
    
    issues = []
    
    # Test termination workflow
    try:
        if frappe.db.exists("Workflow", "Membership Termination Workflow"):
            workflow = frappe.get_doc("Workflow", "Membership Termination Workflow")
            
            # Check basic structure
            if len(workflow.states) < 3:
                issues.append("Termination workflow has too few states")
            if len(workflow.transitions) < 3:
                issues.append("Termination workflow has too few transitions")
            if not workflow.is_active:
                issues.append("Termination workflow is not active")
                
            print(f"   ✅ Termination workflow: {len(workflow.states)} states, {len(workflow.transitions)} transitions")
        else:
            issues.append("Termination workflow missing")
    except Exception as e:
        issues.append(f"Error checking termination workflow: {str(e)}")
    
    # Test appeals workflow
    try:
        if frappe.db.exists("Workflow", "Termination Appeals Workflow"):
            workflow = frappe.get_doc("Workflow", "Termination Appeals Workflow")
            print(f"   ✅ Appeals workflow: {len(workflow.states)} states, {len(workflow.transitions)} transitions")
        else:
            issues.append("Appeals workflow missing")
    except Exception as e:
        issues.append(f"Error checking appeals workflow: {str(e)}")
    
    if issues:
        print("   ❌ Issues found:")
        for issue in issues:
            print(f"      - {issue}")
        return False
    else:
        print("   ✅ All workflows verified")
        return True

def cleanup_broken_workflows():
    """Clean up broken workflows - KEEP THIS for troubleshooting"""
    
    print("🧹 Cleaning up broken workflows...")
    
    workflows_to_clean = [
        "Membership Termination Workflow",
        "Termination Appeals Workflow"
    ]
    
    for workflow_name in workflows_to_clean:
        if frappe.db.exists("Workflow", workflow_name):
            print(f"🗑️ Removing existing workflow: {workflow_name}")
            try:
                frappe.delete_doc("Workflow", workflow_name, force=True)
                print(f"   ✅ Removed {workflow_name}")
            except Exception as e:
                print(f"   ❌ Could not remove {workflow_name}: {str(e)}")
    
    frappe.db.commit()
    print("🧹 Cleanup completed")

def fix_common_workflow_issues():
    """Fix common workflow setup issues - KEEP THIS"""
    
    print("🔧 FIXING COMMON WORKFLOW ISSUES")
    print("=" * 35)
    
    fixes_applied = 0
    
    # Fix 1: Create Association Manager role if missing
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
            frappe.db.commit()
            print("   ✅ Association Manager role created")
            fixes_applied += 1
        except Exception as e:
            print(f"   ❌ Could not create role: {str(e)}")
    
    # Fix 2: Create custom workflow masters if missing
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
    return fixes_applied

def run_complete_setup():
    """Run complete setup using simplified approach - UPDATED"""
    
    print("🚀 RUNNING COMPLETE TERMINATION SYSTEM SETUP")
    print("=" * 50)
    
    try:
        # Step 1: Run diagnostics
        print("\n📋 Step 1: Running diagnostics...")
        run_diagnostics()
        
        # Step 2: Fix common issues
        print("\n📋 Step 2: Fixing common issues...")
        fix_common_workflow_issues()
        
        # Step 3: Setup workflows using simplified approach
        print("\n📋 Step 3: Setting up workflows...")
        from verenigingen.simplified_workflow_setup import setup_workflows_simplified
        setup_workflows_simplified()
        
        # Step 4: Verify setup
        print("\n📋 Step 4: Verifying setup...")
        verify_workflow_functionality()
        
        print("\n🎉 COMPLETE SETUP FINISHED!")
        
    except Exception as e:
        print(f"\n❌ SETUP FAILED: {str(e)}")
        import traceback
        traceback.print_exc()

# API endpoints that can be called from the web interface
@frappe.whitelist()
def api_run_diagnostics():
    """API endpoint to run diagnostics"""
    try:
        result = run_diagnostics()
        return {"success": True, "diagnostics_passed": result}
    except Exception as e:
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def api_fix_issues():
    """API endpoint to fix common issues"""
    try:
        fixes = fix_common_workflow_issues()
        return {"success": True, "fixes_applied": fixes}
    except Exception as e:
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def api_cleanup_workflows():
    """API endpoint to cleanup broken workflows"""
    try:
        cleanup_broken_workflows()
        return {"success": True, "message": "Workflows cleaned up"}
    except Exception as e:
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def api_complete_setup():
    """API endpoint for complete setup"""
    try:
        run_complete_setup()
        return {"success": True, "message": "Complete setup finished"}
    except Exception as e:
        return {"success": False, "message": str(e)}

# Main execution
if __name__ == "__main__":
    run_complete_setup()
