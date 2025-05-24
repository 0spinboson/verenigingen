# File: verenigingen/verenigingen/workflow_states.py
import frappe

def setup_termination_workflow():
    """Setup workflow states for the termination process"""
    
    print("   Starting workflow setup...")
    
    # First, let's check what roles actually exist
    print("   Checking existing roles...")
    existing_roles = frappe.get_all("Role", fields=["name"])
    role_names = [role.name for role in existing_roles]
    print(f"   Found {len(role_names)} existing roles: {', '.join(role_names[:10])}...")
    
    # Define the roles we need
    required_roles = ["System Manager", "Association Manager"]
    
    # Check which roles exist and which need to be created
    missing_roles = []
    existing_required = []
    
    for role in required_roles:
        if role in role_names:
            existing_required.append(role)
            print(f"   ✓ Role exists: {role}")
        else:
            missing_roles.append(role)
            print(f"   ✗ Role missing: {role}")
    
    # Create missing roles
    for role_name in missing_roles:
        if role_name != "System Manager":  # System Manager should already exist
            print(f"   Creating role: {role_name}")
            try:
                role_doc = frappe.get_doc({
                    "doctype": "Role",
                    "role_name": role_name,
                    "desk_access": 1,
                    "is_custom": 1
                })
                role_doc.insert(ignore_permissions=True)
                existing_required.append(role_name)
                print(f"   ✓ Created role: {role_name}")
            except Exception as e:
                print(f"   ✗ Failed to create role {role_name}: {str(e)}")
                continue
    
    # Commit role changes
    frappe.db.commit()
    print("   Committed role changes to database")
    
    # Verify we have at least one working role
    if not existing_required:
        print("   ✗ No valid roles available for workflow creation")
        return False
    
    # Use the first available role for workflow (prefer Association Manager, fallback to System Manager)
    primary_role = "Association Manager" if "Association Manager" in existing_required else existing_required[0]
    print(f"   Using primary role for workflow: {primary_role}")
    
    # Create simplified Membership Termination Request workflow
    workflow_name = "Membership Termination Workflow"
    if not frappe.db.exists("Workflow", workflow_name):
        print(f"   Creating workflow: {workflow_name}")
        
        try:
            # Create a minimal workflow that matches the document structure
            workflow = frappe.get_doc({
                "doctype": "Workflow",
                "workflow_name": workflow_name,
                "document_type": "Membership Termination Request",
                "is_active": 1,
                "send_email_alert": 0,  # Disable to avoid additional validation issues
                "workflow_state_field": "status",
                "states": [
                    {
                        "state": "Draft",
                        "doc_status": "0",
                        "allow_edit": primary_role,
                        "is_optional_state": 1
                    },
                    {
                        "state": "Pending Approval",
                        "doc_status": "0",
                        "allow_edit": primary_role
                    },
                    {
                        "state": "Approved", 
                        "doc_status": "0",
                        "allow_edit": primary_role
                    },
                    {
                        "state": "Executed",
                        "doc_status": "1",
                        "allow_edit": primary_role
                    }
                ],
                "transitions": [
                    {
                        "state": "Draft",
                        "action": "Submit for Approval",
                        "next_state": "Pending Approval",
                        "allowed": primary_role
                    },
                    {
                        "state": "Pending Approval",
                        "action": "Approve",
                        "next_state": "Approved",
                        "allowed": primary_role
                    },
                    {
                        "state": "Approved",
                        "action": "Execute",
                        "next_state": "Executed", 
                        "allowed": primary_role
                    }
                ]
            })
            
            # Insert with detailed error handling
            workflow.insert(ignore_permissions=True)
            print(f"   ✓ Successfully created workflow: {workflow_name}")
            
        except frappe.exceptions.LinkValidationError as e:
            print(f"   ✗ LinkValidationError creating workflow: {str(e)}")
            print("   Attempting to create minimal workflow...")
            
            # Try creating an even simpler workflow
            try:
                simple_workflow = frappe.get_doc({
                    "doctype": "Workflow",
                    "workflow_name": workflow_name + " Simple",
                    "document_type": "Membership Termination Request",
                    "is_active": 1,
                    "send_email_alert": 0,
                    "workflow_state_field": "status",
                    "states": [
                        {
                            "state": "Draft",
                            "doc_status": "0",
                            "allow_edit": "System Manager"
                        },
                        {
                            "state": "Executed",
                            "doc_status": "1", 
                            "allow_edit": "System Manager"
                        }
                    ],
                    "transitions": [
                        {
                            "state": "Draft",
                            "action": "Execute",
                            "next_state": "Executed",
                            "allowed": "System Manager"
                        }
                    ]
                })
                simple_workflow.insert(ignore_permissions=True)
                print(f"   ✓ Created simple workflow: {workflow_name} Simple")
            except Exception as e2:
                print(f"   ✗ Failed to create even simple workflow: {str(e2)}")
                return False
                
        except Exception as e:
            print(f"   ✗ Unexpected error creating workflow: {str(e)}")
            return False
    else:
        print(f"   ✓ Workflow already exists: {workflow_name}")
    
    return True

def setup_email_templates():
    """Setup email templates for the termination system"""
    
    print("   Setting up email templates...")
    
    templates = [
        {
            "name": "Termination Approval Request",
            "subject": "Termination Approval Required - {{ doc.member_name }}",
            "response": """
            <p>Dear Reviewer,</p>
            
            <p>A termination request requires your approval:</p>
            
            <ul>
                <li><strong>Member:</strong> {{ doc.member_name }}</li>
                <li><strong>Type:</strong> {{ doc.termination_type }}</li>
                <li><strong>Date:</strong> {{ frappe.format_date(doc.request_date) }}</li>
            </ul>
            
            <p><strong>Reason:</strong> {{ doc.termination_reason }}</p>
            
            <p>Best regards,<br>System</p>
            """,
            "doctype": "Membership Termination Request"
        }
    ]
    
    created_count = 0
    for template_config in templates:
        template_name = template_config["name"]
        if not frappe.db.exists("Email Template", template_name):
            try:
                email_template = frappe.get_doc({
                    "doctype": "Email Template",
                    "name": template_name,
                    "subject": template_config["subject"],
                    "response": template_config["response"],
                    "reference_doctype": template_config["doctype"],
                    "enabled": 1
                })
                email_template.insert(ignore_permissions=True)
                print(f"   ✓ Created email template: {template_name}")
                created_count += 1
            except Exception as e:
                print(f"   ✗ Failed to create email template {template_name}: {str(e)}")
        else:
            print(f"   ✓ Email template already exists: {template_name}")
    
    print(f"   Email template setup complete. Created {created_count} new templates.")
    return True

def debug_workflow_requirements():
    """Debug function to check workflow requirements"""
    
    print("\n=== WORKFLOW DEBUG INFO ===")
    
    # Check roles
    print("1. Checking Roles:")
    roles = frappe.get_all("Role", fields=["name", "desk_access", "is_custom"])
    for role in roles:
        if "Manager" in role.name or "System" in role.name:
            print(f"   - {role.name} (desk_access: {role.desk_access}, custom: {role.is_custom})")
    
    # Check doctypes
    print("\n2. Checking DocTypes:")
    required_doctypes = ["Membership Termination Request", "Workflow", "Workflow State", "Workflow Transition"]
    for doctype in required_doctypes:
        exists = frappe.db.exists("DocType", doctype)
        print(f"   - {doctype}: {'✓' if exists else '✗'}")
    
    # Check existing workflows
    print("\n3. Existing Workflows:")
    workflows = frappe.get_all("Workflow", fields=["name", "document_type", "is_active"])
    for wf in workflows:
        print(f"   - {wf.name} ({wf.document_type}) - Active: {wf.is_active}")
    
    print("=== END DEBUG INFO ===\n")

# Add this function to be called during setup for debugging
def setup_with_debug():
    """Setup workflow with debug information"""
    debug_workflow_requirements()
    return setup_termination_workflow()
