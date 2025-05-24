#!/usr/bin/env python3
# File: verenigingen/setup_termination_system_cli.py
"""
Command-line setup script for the Termination System
Run this script to setup or troubleshoot the termination system

Usage:
    bench execute verenigingen.setup_termination_system_cli.run_setup
    bench execute verenigingen.setup_termination_system_cli.run_diagnostics
    bench execute verenigingen.setup_termination_system_cli.run_full_setup
"""

import frappe
from frappe import _

def run_setup():
    """Run the termination system setup"""
    
    print("🚀 TERMINATION SYSTEM SETUP")
    print("=" * 40)
    
    try:
        # Step 1: Run diagnostics first
        print("\n📋 Step 1: Running diagnostics...")
        diagnostic_result = run_diagnostics_internal()
        
        if not diagnostic_result:
            print("⚠️ Diagnostics found issues, but continuing with setup...")
        
        # Step 2: Setup termination system
        print("\n📋 Step 2: Setting up termination system...")
        from verenigingen.setup import setup_termination_system_integration
        setup_termination_system()
        
        # Step 3: Verify setup
        print("\n📋 Step 3: Verifying setup...")
        verify_setup()
        
        print("\n🎉 TERMINATION SYSTEM SETUP COMPLETED!")
        
    except Exception as e:
        print(f"\n❌ SETUP FAILED: {str(e)}")
        import traceback
        traceback.print_exc()

def run_diagnostics():
    """Run comprehensive diagnostics"""
    
    print("🔍 TERMINATION SYSTEM DIAGNOSTICS")
    print("=" * 40)
    
    return run_diagnostics_internal()

def run_diagnostics_internal():
    """Internal diagnostics function"""
    
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
    
    # 3. Check settings
    print("\n3. SETTINGS CHECK")
    print("-" * 15)
    
    if frappe.db.exists("Verenigingen Settings", "Verenigingen Settings"):
        print("   ✅ Verenigingen Settings exists")
        
        settings = frappe.get_single("Verenigingen Settings")
        if hasattr(settings, 'enable_termination_system'):
            if settings.enable_termination_system:
                print("   ✅ Termination system enabled")
            else:
                print("   ⚠️ Termination system disabled")
        else:
            print("   ⚠️ Termination system field missing")
    else:
        print("   ❌ Verenigingen Settings missing")
        all_good = False
    
    # 4. Check workflows
    print("\n4. WORKFLOW CHECK")
    print("-" * 15)
    
    workflows = frappe.get_all("Workflow", fields=["name", "document_type", "is_active"])
    termination_workflows = [w for w in workflows if "Termination" in w.name or "Appeal" in w.name]
    
    if termination_workflows:
        for wf in termination_workflows:
            status = "✅" if wf.is_active else "⚠️"
            print(f"   {status} {wf.name} ({wf.document_type})")
    else:
        print("   ⚠️ No termination workflows found")
    
    # 5. Check email templates
    print("\n5. EMAIL TEMPLATE CHECK")
    print("-" * 20)
    
    template_names = [
        "Termination Approval Required",
        "Appeal Acknowledgment",
        "Appeal Decision Notification"
    ]
    
    for template in template_names:
        if frappe.db.exists("Email Template", template):
            print(f"   ✅ {template}")
        else:
            print(f"   ⚠️ {template} - MISSING")
    
    # 6. Summary
    print("\n" + "=" * 40)
    if all_good:
        print("✅ ALL DIAGNOSTICS PASSED")
    else:
        print("⚠️ SOME ISSUES FOUND")
        print("   Please review the items marked with ❌")
    print("=" * 40)
    
    return all_good

def run_full_setup():
    """Run full enhanced setup"""
    
    print("🚀 FULL VERENIGINGEN SETUP")
    print("=" * 30)
    
    try:
        from verenigingen.setup import execute_after_install_with_termination
        execute_after_install_with_termination()
        
        print("\n🎉 FULL SETUP COMPLETED!")
        
    except Exception as e:
        print(f"\n❌ FULL SETUP FAILED: {str(e)}")
        import traceback
        traceback.print_exc()

def verify_setup():
    """Verify the setup was successful"""
    
    print("🔍 Verifying setup...")
    
    # Check workflows
    workflows = ["Membership Termination Workflow", "Termination Appeals Workflow"]
    workflow_count = 0
    
    for workflow in workflows:
        if frappe.db.exists("Workflow", workflow):
            workflow_count += 1
            print(f"   ✅ {workflow} exists")
        else:
            print(f"   ❌ {workflow} missing")
    
    # Check email templates
    templates = ["Termination Approval Required", "Appeal Acknowledgment"]
    template_count = 0
    
    for template in templates:
        if frappe.db.exists("Email Template", template):
            template_count += 1
            print(f"   ✅ {template} exists")
        else:
            print(f"   ❌ {template} missing")
    
    # Check roles
    if frappe.db.exists("Role", "Association Manager"):
        print("   ✅ Association Manager role exists")
    else:
        print("   ❌ Association Manager role missing")
    
    # Check settings
    try:
        settings = frappe.get_single("Verenigingen Settings")
        if hasattr(settings, 'enable_termination_system') and settings.enable_termination_system:
            print("   ✅ Termination system enabled in settings")
        else:
            print("   ⚠️ Termination system not enabled in settings")
    except:
        print("   ❌ Could not check settings")
    
    print(f"\n📊 Setup Summary:")
    print(f"   - Workflows: {workflow_count}/2")
    print(f"   - Email Templates: {template_count}/2")
    print(f"   - Roles: {'✅' if frappe.db.exists('Role', 'Association Manager') else '❌'}")

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
            frappe.db.commit()
            print("   ✅ Association Manager role created")
            fixes_applied += 1
        except Exception as e:
            print(f"   ❌ Could not create role: {str(e)}")
    
    # Fix 2: Enable termination system in settings
    try:
        settings = frappe.get_single("Verenigingen Settings")
        if hasattr(settings, 'enable_termination_system'):
            if not settings.enable_termination_system:
                settings.enable_termination_system = 1
                settings.save(ignore_permissions=True)
                frappe.db.commit()
                print("   ✅ Enabled termination system in settings")
                fixes_applied += 1
        else:
            print("   ⚠️ Termination system field not found in settings")
    except Exception as e:
        print(f"   ⚠️ Could not update settings: {str(e)}")
    
    print(f"\n🔧 Applied {fixes_applied} fixes")

def reset_workflows():
    """Reset/recreate workflows"""
    
    print("🔄 RESETTING WORKFLOWS")
    print("=" * 20)
    
    workflows_to_reset = [
        "Membership Termination Workflow",
        "Termination Appeals Workflow"
    ]
    
    for workflow_name in workflows_to_reset:
        if frappe.db.exists("Workflow", workflow_name):
            print(f"🗑️ Removing existing workflow: {workflow_name}")
            try:
                frappe.delete_doc("Workflow", workflow_name, force=True)
                print(f"   ✅ Removed {workflow_name}")
            except Exception as e:
                print(f"   ❌ Could not remove {workflow_name}: {str(e)}")
    
    frappe.db.commit()
    
    print("🔄 Recreating workflows...")
    try:
        from verenigingen.workflow_states import setup_with_debug
        success = setup_with_debug()
        if success:
            print("   ✅ Workflows recreated successfully")
        else:
            print("   ⚠️ Workflow recreation had issues")
    except Exception as e:
        print(f"   ❌ Could not recreate workflows: {str(e)}")

# API endpoints that can be called from the web interface
@frappe.whitelist()
def api_run_setup():
    """API endpoint to run setup"""
    try:
        run_setup()
        return {"success": True, "message": "Setup completed successfully"}
    except Exception as e:
        return {"success": False, "message": str(e)}

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
        fix_common_issues()
        return {"success": True, "message": "Common issues fixed"}
    except Exception as e:
        return {"success": False, "message": str(e)}

# Main execution
if __name__ == "__main__":
    run_setup()
