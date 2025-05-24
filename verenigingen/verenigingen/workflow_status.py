# File: verenigingen/verenigingen/workflow_states.py
import frappe

def setup_termination_workflow():
    """Setup workflow states for the termination process"""
    
    # Create Membership Termination Request workflow
    if not frappe.db.exists("Workflow", "Membership Termination Workflow"):
        workflow = frappe.get_doc({
            "doctype": "Workflow",
            "workflow_name": "Membership Termination Workflow",
            "document_type": "Membership Termination Request",
            "is_active": 1,
            "send_email_alert": 1,
            "workflow_state_field": "workflow_state",
            "states": [
                {
                    "state": "Draft",
                    "doc_status": "0",
                    "allow_edit": "System Manager,Association Manager,Association Manager",
                    "is_optional_state": 1
                },
                {
                    "state": "Pending Approval",
                    "doc_status": "0",
                    "allow_edit": "System Manager,Association Manager",
                    "message": "Awaiting secondary approval for disciplinary termination"
                },
                {
                    "state": "Approved",
                    "doc_status": "0",
                    "allow_edit": "System Manager,Association Manager,Association Manager",
                    "message": "Approved and ready for execution"
                },
                {
                    "state": "Rejected",
                    "doc_status": "0",
                    "allow_edit": "System Manager",
                    "message": "Termination request rejected"
                },
                {
                    "state": "Executed",
                    "doc_status": "1",
                    "allow_edit": "System Manager",
                    "message": "Termination has been executed"
                }
            ],
            "transitions": [
                {
                    "state": "Draft",
                    "action": "Submit for Approval",
                    "next_state": "Pending Approval",
                    "allowed": "System Manager,Association Manager,Association Manager",
                    "condition": "doc.requires_secondary_approval == 1"
                },
                {
                    "state": "Draft", 
                    "action": "Auto Approve",
                    "next_state": "Approved",
                    "allowed": "ALL",
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
                    "allowed": "System Manager,Association Manager,Association Manager"
                }
            ]
        })
        workflow.insert()
        print("Created Membership Termination Workflow")
    
    # Create Appeals Process workflow
    if not frappe.db.exists("Workflow", "Appeals Process Workflow"):
        appeals_workflow = frappe.get_doc({
            "doctype": "Workflow",
            "workflow_name": "Appeals Process Workflow",
            "document_type": "Termination Appeals Process",
            "is_active": 1,  
            "send_email_alert": 1,
            "workflow_state_field": "workflow_state",
            "states": [
                {
                    "state": "Draft",
                    "doc_status": "0",
                    "allow_edit": "ALL",
                    "is_optional_state": 1
                },
                {
                    "state": "Submitted",
                    "doc_status": "0",
                    "allow_edit": "System Manager,Association Manager",
                    "message": "Appeal submitted for review"
                },
                {
                    "state": "Under Review",
                    "doc_status": "0",
                    "allow_edit": "System Manager,Association Manager,Association Manager",
                    "message": "Appeal is being reviewed"
                },
                {
                    "state": "Decided",
                    "doc_status": "1",
                    "allow_edit": "System Manager",
                    "message": "Appeal decision has been made"
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
                    "allowed": "System Manager,Association Manager,Association Manager"
                },
                {
                    "state": "Under Review",
                    "action": "Make Decision",
                    "next_state": "Decided",
                    "allowed": "System Manager,Association Manager,Association Manager"
                }
            ]
        })
        appeals_workflow.insert()
        print("Created Appeals Process Workflow")

def setup_email_templates():
    """Setup email templates for the termination system"""
    
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
            
            <p>Your appeal will be reviewed within {{ date_diff(doc.review_deadline, doc.appeal_date) }} days.</p>
            
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
    
    for template_config in templates:
        if not frappe.db.exists("Email Template", template_config["name"]):
            email_template = frappe.get_doc({
                "doctype": "Email Template",
                "name": template_config["name"],
                "subject": template_config["subject"],
                "response": template_config["response"],
                "reference_doctype": template_config["doctype"],
                "enabled": 1
            })
            email_template.insert()
            print(f"Created email template: {template_config['name']}")
