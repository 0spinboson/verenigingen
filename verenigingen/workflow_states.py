# File: verenigingen/verenigingen/workflow_states.py
import frappe

def setup_termination_workflow():
    """Setup workflow states for the termination process"""
    
    # First ensure required roles exist and are committed to database
    print("   Ensuring required roles exist...")
    required_roles = [
        {
            "role_name": "Association Manager",
            "desk_access": 1,
            "is_custom": 1
        }
    ]
    
    for role_config in required_roles:
        role_name = role_config["role_name"]
        if not frappe.db.exists("Role", role_name):
            print(f"   Creating missing role: {role_name}")
            role_doc = frappe.get_doc({
                "doctype": "Role",
                **role_config
            })
            role_doc.insert()
            print(f"   ✓ Created role: {role_name}")
        else:
            print(f"   ✓ Role already exists: {role_name}")
    
    # Commit the roles to database before creating workflows
    frappe.db.commit()
    
    # Verify roles exist before proceeding
    missing_roles = []
    check_roles = ["System Manager", "Association Manager"]
    for role in check_roles:
        if not frappe.db.exists("Role", role):
            missing_roles.append(role)
    
    if missing_roles:
        frappe.throw(f"Required roles still missing after creation: {', '.join(missing_roles)}")
    
    print("   All required roles verified. Creating workflows...")
    
    # Create Membership Termination Request workflow
    if not frappe.db.exists("Workflow", "Membership Termination Workflow"):
        print("   Creating Membership Termination Workflow...")
        
        workflow = frappe.get_doc({
            "doctype": "Workflow",
            "workflow_name": "Membership Termination Workflow",
            "document_type": "Membership Termination Request",
            "is_active": 1,
            "send_email_alert": 1,
            "workflow_state_field": "status",  # Use the existing status field
            "states": [
                {
                    "state": "Draft",
                    "doc_status": "0",
                    "allow_edit": "System Manager,Association Manager"
                },
                {
                    "state": "Pending Approval",
                    "doc_status": "0", 
                    "allow_edit": "System Manager,Association Manager"
                },
                {
                    "state": "Approved",
                    "doc_status": "0",
                    "allow_edit": "System Manager,Association Manager"
                },
                {
                    "state": "Rejected",
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
                    "action": "Submit for Approval",
                    "next_state": "Pending Approval",
                    "allowed": "System Manager,Association Manager",
                    "condition": "doc.requires_secondary_approval == 1"
                },
                {
                    "state": "Draft",
                    "action": "Auto Approve", 
                    "next_state": "Approved",
                    "allowed": "System Manager,Association Manager",
                    "condition": "doc.requires_secondary_approval == 0"
                },
                {
                    "state": "Pending Approval",
                    "action": "Approve",
                    "next_state": "Approved",
                    "allowed": "System Manager,Association Manager"
                },
                {
                    "state": "Pending Approval",
                    "action": "Reject",
                    "next_state": "Rejected", 
                    "allowed": "System Manager,Association Manager"
                },
                {
                    "state": "Approved",
                    "action": "Execute",
                    "next_state": "Executed",
                    "allowed": "System Manager,Association Manager"
                }
            ]
        })
        
        try:
            workflow.insert()
            print("   ✓ Created Membership Termination Workflow")
        except Exception as e:
            print(f"   ✗ Failed to create Membership Termination Workflow: {str(e)}")
            raise
    else:
        print("   ✓ Membership Termination Workflow already exists")
    
    # Create Appeals Process workflow
    if not frappe.db.exists("Workflow", "Appeals Process Workflow"):
        print("   Creating Appeals Process Workflow...")
        
        appeals_workflow = frappe.get_doc({
            "doctype": "Workflow",
            "workflow_name": "Appeals Process Workflow",
            "document_type": "Termination Appeals Process",
            "is_active": 1,
            "send_email_alert": 1,
            "workflow_state_field": "appeal_status",  # Use the existing appeal_status field
            "states": [
                {
                    "state": "Draft",
                    "doc_status": "0",
                    "allow_edit": "ALL"
                },
                {
                    "state": "Submitted",
                    "doc_status": "0",
                    "allow_edit": "System Manager,Association Manager"
                },
                {
                    "state": "Under Review",
                    "doc_status": "0",
                    "allow_edit": "System Manager,Association Manager"
                },
                {
                    "state": "Decided - Upheld",
                    "doc_status": "1",
                    "allow_edit": "System Manager"
                },
                {
                    "state": "Decided - Rejected",
                    "doc_status": "1", 
                    "allow_edit": "System Manager"
                },
                {
                    "state": "Decided - Partially Upheld",
                    "doc_status": "1",
                    "allow_edit": "System Manager"
                }
            ],
            "transitions": [
                {
                    "state": "Draft",
                    "action": "Submit",
                    "next_state": "Submitted",
                    "allowed": "ALL"
                },
                {
                    "state": "Submitted",
                    "action": "Start Review",
                    "next_state": "Under Review",
                    "allowed": "System Manager,Association Manager"
                },
                {
                    "state": "Under Review",
                    "action": "Uphold Appeal",
                    "next_state": "Decided - Upheld",
                    "allowed": "System Manager,Association Manager"
                },
                {
                    "state": "Under Review",
                    "action": "Reject Appeal",
                    "next_state": "Decided - Rejected",
                    "allowed": "System Manager,Association Manager"
                },
                {
                    "state": "Under Review",
                    "action": "Partially Uphold",
                    "next_state": "Decided - Partially Upheld",
                    "allowed": "System Manager,Association Manager"
                }
            ]
        })
        
        try:
            appeals_workflow.insert()
            print("   ✓ Created Appeals Process Workflow")
        except Exception as e:
            print(f"   ✗ Failed to create Appeals Process Workflow: {str(e)}")
            # Don't raise here as this is less critical
            pass
    else:
        print("   ✓ Appeals Process Workflow already exists")

def setup_email_templates():
    """Setup email templates for the termination system"""
    
    print("   Setting up email templates...")
    
    templates = [
        {
            "name": "Termination Approval Request",
            "subject": "Termination Approval Required - {{ doc.member_name }}",
            "response": """
            <p>Dear {{ frappe.get_value("User", doc.secondary_approver, "full_name") }},</p>
            
            <p>A disciplinary termination request requires your approval:</p>
            
            <ul>
                <li><strong>Member:</strong> {{ doc.member_name }}</li>
                <li><strong>Type:</strong> {{ doc.termination_type }}</li>
                <li><strong>Requested by:</strong> {{ doc.requested_by }}</li>
                <li><strong>Date:</strong> {{ frappe.format_date(doc.request_date) }}</li>
            </ul>
            
            <p><strong>Reason:</strong> {{ doc.termination_reason }}</p>
            
            <p><a href="{{ frappe.utils.get_url() }}/app/membership-termination-request/{{ doc.name }}">Review Request</a></p>
            
            <p>Best regards,<br>Governance System</p>
            """,
            "doctype": "Membership Termination Request"
        },
        {
            "name": "Appeal Acknowledgment",
            "subject": "Appeal Acknowledgment - {{ doc.name }}",
            "response": """
            <p>Dear {{ doc.appellant_name }},</p>
            
            <p>We acknowledge receipt of your appeal regarding {{ doc.member_name }}:</p>
            
            <ul>
                <li><strong>Appeal Reference:</strong> {{ doc.name }}</li>
                <li><strong>Date:</strong> {{ frappe.format_date(doc.appeal_date) }}</li>
                <li><strong>Type:</strong> {{ doc.appeal_type }}</li>
            </ul>
            
            <p>Your appeal will be reviewed within the statutory timeframe.</p>
            
            <p>Best regards,<br>Appeals Review Panel</p>
            """,
            "doctype": "Termination Appeals Process"
        },
        {
            "name": "Appeal Decision",
            "subject": "Appeal Decision - {{ doc.decision_outcome }} - {{ doc.name }}",
            "response": """
            <p>Dear {{ doc.appellant_name }},</p>
            
            <p>A decision has been made on your appeal:</p>
            
            <ul>
                <li><strong>Decision:</strong> {{ doc.decision_outcome }}</li>
                <li><strong>Date:</strong> {{ frappe.format_date(doc.decision_date) }}</li>
                <li><strong>Decided by:</strong> {{ doc.decided_by }}</li>
            </ul>
            
            {% if doc.decision_rationale %}
            <p><strong>Rationale:</strong></p>
            <p>{{ doc.decision_rationale }}</p>
            {% endif %}
            
            <p>Best regards,<br>Appeals Review Panel</p>
            """,
            "doctype": "Termination Appeals Process"
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
                email_template.insert()
                print(f"   ✓ Created email template: {template_name}")
                created_count += 1
            except Exception as e:
                print(f"   ✗ Failed to create email template {template_name}: {str(e)}")
        else:
            print(f"   ✓ Email template already exists: {template_name}")
    
    print(f"   Email template setup complete. Created {created_count} new templates.")
