# File: verenigingen/verenigingen/setup_termination_system.py
"""
Setup utility for the Enhanced Membership Termination System
Run this script after deployment to initialize all components
"""

import frappe
from frappe import _
import json

def setup_complete_termination_system():
    """Complete setup of the termination system"""
    
    print("🚀 Starting Enhanced Membership Termination System Setup...")
    
    try:
        # Step 1: Create standard roles first (needed for workflows)
        print("🔐 Step 1: Setting up roles and permissions...")
        setup_roles_and_permissions()
        print("✅ Roles and permissions configured")
        
        # Step 3: Setup workflows (now that roles exist)
        print("⚙️ Step 3: Setting up workflows...")
        from verenigingen.verenigingen.workflow_states import setup_termination_workflow
        setup_termination_workflow()
        print("✅ Workflows created successfully")
        
        # Step 4: Setup email templates
        print("📧 Step 4: Setting up email templates...")
        from verenigingen.verenigingen.workflow_states import setup_email_templates
        setup_email_templates()
        print("✅ Email templates created successfully")
        
        # Step 5: Setup system settings
        print("⚙️ Step 5: Configuring system settings...")
        setup_system_settings()
        print("✅ System settings configured")
        
        # Step 6: Create sample data (if requested)
        create_sample = input("Create sample data for testing? (y/N): ").lower() == 'y'
        if create_sample:
            print("🧪 Step 6: Creating sample test data...")
            create_sample_data()
            print("✅ Sample data created")
        else:
            print("⏭️ Step 6: Skipped sample data creation")
        
        # Step 7: Validate system
        print("🔍 Step 7: Validating system setup...")
        validation_results = validate_system_setup()
        
        if validation_results["success"]:
            print("✅ System validation passed")
        else:
            print("⚠️ System validation found issues:")
            for issue in validation_results["issues"]:
                print(f"   - {issue}")
        
        # Step 8: Generate setup report
        print("📊 Step 8: Generating setup report...")
        generate_setup_report(validation_results)
        
        print("\n🎉 Enhanced Membership Termination System setup completed!")
        print("\n📋 Next Steps:")
        print("1. Review the setup report for any issues")
        print("2. Test the system with sample data")
        print("3. Configure user permissions as needed")
        print("4. Setup scheduled jobs for notifications")
        print("5. Train users on the new system")
        
        frappe.db.commit()
        
    except Exception as e:
        frappe.db.rollback()
        print(f"❌ Setup failed: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

def setup_roles_and_permissions():
    """Setup roles and permissions for the termination system"""
    
    # Define role permissions (simplified to use existing roles)
    role_permissions = {
        "Association Manager": {
            "description": "Can manage all aspects of membership terminations and appeals",
            "doctypes": {
                "Membership Termination Request": ["read", "write", "create", "delete", "submit", "cancel"],
                "Termination Appeals Process": ["read", "write", "create", "delete", "submit"],
                "Expulsion Report Entry": ["read", "write", "create", "delete"]
            }
        },
        "Appeals Reviewer": {
            "description": "Can review and decide on termination appeals",
            "doctypes": {
                "Termination Appeals Process": ["read", "write", "create", "submit"],
                "Membership Termination Request": ["read"],
                "Expulsion Report Entry": ["read"]
            }
        },
        "Governance Auditor": {
            "description": "Can access all termination and appeals data for compliance",
            "doctypes": {
                "Membership Termination Request": ["read", "export", "report"],
                "Termination Appeals Process": ["read", "export", "report"],
                "Expulsion Report Entry": ["read", "export", "report"]
            }
        }
    }
    
    # Create roles if they don't exist
    for role_name, role_config in role_permissions.items():
        if not frappe.db.exists("Role", role_name):
            role = frappe.get_doc({
                "doctype": "Role",
                "role_name": role_name,
                "desk_access": 1,
                "is_custom": 1
            })
            role.insert()
            print(f"   Created role: {role_name}")
        
        # Set up permissions for each doctype
        for doctype, permissions in role_config["doctypes"].items():
            # Remove existing permissions first
            existing_perms = frappe.get_all("DocPerm", {
                "parent": doctype,
                "role": role_name
            })
            for perm in existing_perms:
                frappe.delete_doc("DocPerm", perm.name, ignore_permissions=True)
            
            # Create new permission
            perm_doc = frappe.get_doc({
                "doctype": "DocPerm",
                "parent": doctype,
                "parenttype": "DocType",
                "parentfield": "permissions",
                "role": role_name,
                "read": 1 if "read" in permissions else 0,
                "write": 1 if "write" in permissions else 0,
                "create": 1 if "create" in permissions else 0,
                "delete": 1 if "delete" in permissions else 0,
                "submit": 1 if "submit" in permissions else 0,
                "cancel": 1 if "cancel" in permissions else 0,
                "export": 1 if "export" in permissions else 0,
                "report": 1 if "report" in permissions else 0
            })
            perm_doc.insert(ignore_permissions=True)

def setup_system_settings():
    """Setup system-wide settings for the termination system"""
    
    # Create Verenigingen Settings if it doesn't exist
    if not frappe.db.exists("Verenigingen Settings"):
        settings = frappe.get_doc({
            "doctype": "Verenigingen Settings",
            "docstatus": 0
        })
        settings.insert()
    
    # Update settings with termination system configuration
    settings = frappe.get_single("Verenigingen Settings")
    
    # Set default values if not already configured
    default_settings = {
        "enable_termination_system": 1,
        "appeal_deadline_days": 30,
        "appeal_review_days": 60,
        "require_secondary_approval": 1,
        "auto_cancel_sepa_mandates": 1,
        "auto_end_board_positions": 1,
        "send_termination_notifications": 1,
        "termination_grace_period_days": 30
    }
    
    updated = False
    for setting, value in default_settings.items():
        if not hasattr(settings, setting) or not getattr(settings, setting):
            setattr(settings, setting, value)
            updated = True
    
    if updated:
        settings.save()
        print("   Updated system settings with termination defaults")

def create_sample_data():
    """Create sample data for testing the termination system"""
    
    # Create sample members for testing
    sample_members = [
        {
            "first_name": "John",
            "last_name": "TestMember",
            "email": "john.test@example.com",
            "status": "Active"
        },
        {
            "first_name": "Jane", 
            "last_name": "BoardMember",
            "email": "jane.board@example.com", 
            "status": "Active"
        },
        {
            "first_name": "Bob",
            "last_name": "ExpiredMember",
            "email": "bob.expired@example.com",
            "status": "Expired"
        }
    ]
    
    created_members = []
    for member_data in sample_members:
        # Check if member already exists
        existing = frappe.db.exists("Member", {"email": member_data["email"]})
        if not existing:
            member = frappe.get_doc({
                "doctype": "Member",
                "full_name": f"{member_data['first_name']} {member_data['last_name']}",
                **member_data
            })
            member.insert()
            created_members.append(member.name)
            print(f"   Created sample member: {member_data['first_name']} {member_data['last_name']}")
    
    # Create a sample termination request
    if created_members:
        sample_termination = frappe.get_doc({
            "doctype": "Membership Termination Request",
            "member": created_members[0],
            "termination_type": "Voluntary",
            "termination_reason": "Sample termination for testing purposes",
            "requested_by": frappe.session.user,
            "status": "Draft"
        })
        sample_termination.insert()
        print(f"   Created sample termination request: {sample_termination.name}")

def validate_system_setup():
    """Validate that the termination system is set up correctly"""
    
    validation_results = {
        "success": True,
        "issues": []
    }
    
    # Check that all required doctypes exist
    required_doctypes = [
        "Membership Termination Request",
        "Termination Appeals Process", 
        "Expulsion Report Entry",
        "Appeal Timeline Entry",
        "Appeal Communication Entry",
        "Termination Audit Entry"
    ]
    
    for doctype in required_doctypes:
        if not frappe.db.exists("DocType", doctype):
            validation_results["success"] = False
            validation_results["issues"].append(f"Missing DocType: {doctype}")
    
    # Check that workflows exist
    required_workflows = [
        "Membership Termination Workflow",
        "Appeals Process Workflow" 
    ]
    
    for workflow in required_workflows:
        if not frappe.db.exists("Workflow", workflow):
            validation_results["issues"].append(f"Missing Workflow: {workflow}")
    
    # Check that roles exist
    required_roles = [
        "Association Manager",
        "Appeals Reviewer", 
        "Governance Auditor"
    ]
    
    for role in required_roles:
        if not frappe.db.exists("Role", role):
            validation_results["issues"].append(f"Missing Role: {role}")
    
    # Check system settings
    try:
        settings = frappe.get_single("Verenigingen Settings")
        if not hasattr(settings, 'enable_termination_system') or not settings.enable_termination_system:
            validation_results["issues"].append("Termination system not enabled in settings")
    except:
        validation_results["issues"].append("Verenigingen Settings not configured")
    
    # Check that reports exist
    required_reports = [
        "Termination Compliance Report",
        "Appeals Analysis Report",
        "Board Position Termination Impact"
    ]
    
    for report in required_reports:
        if not frappe.db.exists("Report", report):
            validation_results["issues"].append(f"Missing Report: {report}")
    
    if validation_results["issues"]:
        validation_results["success"] = False
    
    return validation_results

def generate_setup_report(validation_results):
    """Generate a comprehensive setup report"""
    
    report = {
        "setup_date": frappe.utils.now(),
        "setup_by": frappe.session.user,
        "validation_results": validation_results,
        "system_stats": get_system_stats()
    }
    
    # Save report as a JSON file
    report_json = json.dumps(report, indent=2, default=str)
    
    # Create a System Setup Report document if the doctype exists
    try:
        setup_report = frappe.get_doc({
            "doctype": "System Setup Report",
            "report_name": "Termination System Setup",
            "setup_date": report["setup_date"],
            "setup_by": report["setup_by"],
            "validation_success": validation_results["success"],
            "report_data": report_json
        })
        setup_report.insert()
        print(f"   Setup report saved: {setup_report.name}")
    except:
        # If doctype doesn't exist, just print the report
        print("   Setup Report:")
        print(f"   - Setup Date: {report['setup_date']}")
        print(f"   - Setup By: {report['setup_by']}")
        print(f"   - Validation Success: {validation_results['success']}")
        print(f"   - Total Issues: {len(validation_results['issues'])}")

def get_system_stats():
    """Get current system statistics"""
    
    stats = {}
    
    try:
        stats["total_members"] = frappe.db.count("Member")
        stats["total_termination_requests"] = frappe.db.count("Membership Termination Request")
        stats["total_appeals"] = frappe.db.count("Termination Appeals Process") 
        stats["total_expulsions"] = frappe.db.count("Expulsion Report Entry")
    except:
        stats["error"] = "Could not retrieve system statistics"
    
    return stats

@frappe.whitelist()
def run_termination_system_setup():
    """API endpoint to run the setup"""
    try:
        setup_complete_termination_system()
        return {"success": True, "message": "Termination system setup completed successfully"}
    except Exception as e:
        return {"success": False, "message": str(e)}

if __name__ == "__main__":
    # Run the setup when script is executed directly
    setup_complete_termination_system()
