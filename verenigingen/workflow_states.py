# File: verenigingen/workflow_states.py
"""
Complete Workflow States and Email Template Setup for Termination System
"""

import frappe
from frappe import _

def setup_with_debug():
    """Setup workflows with debug information"""
    try:
        print("🔄 Setting up termination workflows...")
        
        # Run diagnostics first
        debug_workflow_requirements()
        
        # Create missing roles
        roles_created = create_missing_roles()
        
        # Setup main workflow
        workflow_created = setup_termination_workflow()
        
        # Setup appeals workflow
        appeals_workflow_created = setup_appeals_workflow()
        
        # Setup email templates
        templates_created = setup_email_templates()
        
        print(f"✅ Workflow setup completed - Roles: {roles_created}, Workflows: {workflow_created + appeals_workflow_created}, Templates: {templates_created}")
        return True
        
    except Exception as e:
        print(f"❌ Workflow setup failed: {str(e)}")
        frappe.log_error(f"Workflow setup error: {str(e)}", "Termination Workflow Setup")
        return False

def create_missing_roles():
    """Create required roles if they don't exist"""
    
    print("   🔐 Creating required roles...")
    
    required_roles = [
        {
            "role_name": "Association Manager",
            "desk_access": 1,
            "is_custom": 1
        },
        {
            "role_name": "Appeals Reviewer", 
            "desk_access": 1,
            "is_custom": 1
        },
        {
            "role_name": "Governance Auditor",
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
                print(f"   ✓ Created role: {role_name}")
                created_count += 1
            except Exception as e:
                print(f"   ❌ Failed to create role {role_name}: {str(e)}")
        else:
            print(f"   ✓ Role already exists: {role_name}")
    
    if created_count > 0:
        frappe.db.commit()
    
    return created_count

def setup_termination_workflow():
    """Create the main termination workflow"""
    
    workflow_name = "Membership Termination Workflow"
    
    # Check if workflow already exists
    if frappe.db.exists("Workflow", workflow_name):
        print(f"   ✓ Workflow '{workflow_name}' already exists")
        return 0
    
    print(f"   📋 Creating workflow: {workflow_name}")
    
    try:
        # Get available roles
        available_roles = get_available_roles()
        primary_role = available_roles[0] if available_roles else "System Manager"
        
        print(f"   Using roles: {', '.join(available_roles)}")
        
        # Create the workflow document
        workflow = frappe.get_doc({
            "doctype": "Workflow",
            "workflow_name": workflow_name,
            "document_type": "Membership Termination Request",
            "is_active": 1,
            "send_email_alert": 1,
            "workflow_state_field": "status",
            "states": [
                {
                    "state": "Draft",
                    "doc_status": "0",
                    "allow_edit": ",".join(available_roles),
                    "is_optional_state": 1
                },
                {
                    "state": "Pending Approval", 
                    "doc_status": "0",
                    "allow_edit": primary_role,
                    "message": "Awaiting secondary approval for disciplinary termination"
                },
                {
                    "state": "Approved",
                    "doc_status": "0", 
                    "allow_edit": ",".join(available_roles),
                    "message": "Approved and ready for execution"
                },
                {
                    "state": "Rejected",
                    "doc_status": "0",
                    "allow_edit": primary_role,
                    "message": "Termination request rejected"
                },
                {
                    "state": "Executed",
                    "doc_status": "1",
                    "allow_edit": primary_role,
                    "message": "Termination has been executed"
                }
            ],
            "transitions": [
                {
                    "state": "Draft",
                    "action": "Submit for Approval",
                    "next_state": "Pending Approval", 
                    "allowed": ",".join(available_roles),
                    "condition": "doc.requires_secondary_approval == 1"
                },
                {
                    "state": "Draft",
                    "action": "Auto Approve",
                    "next_state": "Approved",
                    "allowed": ",".join(available_roles),
                    "condition": "doc.requires_secondary_approval == 0"
                },
                {
                    "state": "Pending Approval",
                    "action": "Approve", 
                    "next_state": "Approved",
                    "allowed": primary_role
                },
                {
                    "state": "Pending Approval",
                    "action": "Reject",
                    "next_state": "Rejected", 
                    "allowed": primary_role
                },
                {
                    "state": "Approved",
                    "action": "Execute",
                    "next_state": "Executed",
                    "allowed": ",".join(available_roles)
                }
            ]
        })
        
        workflow.insert(ignore_permissions=True)
        frappe.db.commit()
        
        print(f"   ✓ Created workflow: {workflow_name}")
        return 1
        
    except Exception as e:
        print(f"   ❌ Failed to create workflow: {str(e)}")
        frappe.log_error(f"Failed to create termination workflow: {str(e)}", "Workflow Creation Error")
        return 0

def setup_appeals_workflow():
    """Create the appeals workflow"""
    
    workflow_name = "Termination Appeals Workflow"
    
    if frappe.db.exists("Workflow", workflow_name):
        print(f"   ✓ Appeals workflow '{workflow_name}' already exists")
        return 0
    
    print(f"   📋 Creating appeals workflow: {workflow_name}")
    
    try:
        available_roles = get_available_roles()
        primary_role = available_roles[0] if available_roles else "System Manager"
        
        workflow = frappe.get_doc({
            "doctype": "Workflow", 
            "workflow_name": workflow_name,
            "document_type": "Termination Appeals Process",
            "is_active": 1,
            "send_email_alert": 1,
            "workflow_state_field": "appeal_status",
            "states": [
                {
                    "state": "Draft",
                    "doc_status": "0",
                    "allow_edit": ",".join(available_roles + ["Member Portal User"]),
                    "is_optional_state": 1
                },
                {
                    "state": "Submitted",
                    "doc_status": "0", 
                    "allow_edit": primary_role,
                    "message": "Appeal submitted and awaiting review assignment"
                },
                {
                    "state": "Under Review",
                    "doc_status": "0",
                    "allow_edit": ",".join(available_roles),
                    "message": "Appeal is under active review"
                },
                {
                    "state": "Pending Decision",
                    "doc_status": "0",
                    "allow_edit": ",".join(available_roles), 
                    "message": "Review complete, decision pending"
                },
                {
                    "state": "Decided - Upheld",
                    "doc_status": "1",
                    "allow_edit": primary_role,
                    "message": "Appeal upheld - implementation required"
                },
                {
                    "state": "Decided - Rejected", 
                    "doc_status": "1",
                    "allow_edit": primary_role,
                    "message": "Appeal rejected - decision stands"
                },
                {
                    "state": "Decided - Partially Upheld",
                    "doc_status": "1", 
                    "allow_edit": primary_role,
                    "message": "Appeal partially upheld - partial implementation required"
                }
            ],
            "transitions": [
                {
                    "state": "Draft",
                    "action": "Submit Appeal",
                    "next_state": "Submitted",
                    "allowed": ",".join(available_roles + ["Member Portal User"])
                },
                {
                    "state": "Submitted", 
                    "action": "Start Review",
                    "next_state": "Under Review",
                    "allowed": ",".join(available_roles)
                },
                {
                    "state": "Under Review",
                    "action": "Complete Review", 
                    "next_state": "Pending Decision",
                    "allowed": ",".join(available_roles)
                },
                {
                    "state": "Pending Decision",
                    "action": "Uphold Appeal",
                    "next_state": "Decided - Upheld",
                    "allowed": ",".join(available_roles)
                },
                {
                    "state": "Pending Decision",
                    "action": "Reject Appeal", 
                    "next_state": "Decided - Rejected",
                    "allowed": ",".join(available_roles)
                },
                {
                    "state": "Pending Decision",
                    "action": "Partially Uphold",
                    "next_state": "Decided - Partially Upheld",
                    "allowed": ",".join(available_roles)
                }
            ]
        })
        
        workflow.insert(ignore_permissions=True)
        frappe.db.commit()
        
        print(f"   ✓ Created appeals workflow: {workflow_name}")
        return 1
        
    except Exception as e:
        print(f"   ❌ Failed to create appeals workflow: {str(e)}")
        frappe.log_error(f"Failed to create appeals workflow: {str(e)}", "Appeals Workflow Creation Error")
        return 0

def get_available_roles():
    """Get list of available roles for workflow"""
    
    preferred_roles = ["Association Manager", "System Manager"]
    available_roles = []
    
    for role in preferred_roles:
        if frappe.db.exists("Role", role):
            available_roles.append(role)
    
    return available_roles

def setup_email_templates():
    """Create email templates for the termination system"""
    
    print("   📧 Setting up email templates...")
    
    templates = [
        {
            "name": "Termination Approval Required",
            "subject": "🔍 Termination Approval Required - {{ doc.member_name }}",
            "use_html": 1,
            "response": get_approval_email_template()
        },
        {
            "name": "Appeal Acknowledgment",
            "subject": "Appeal Acknowledgment - {{ doc.name }}",
            "use_html": 1, 
            "response": get_appeal_acknowledgment_template()
        },
        {
            "name": "Appeal Decision Notification",
            "subject": "Appeal Decision - {{ doc.decision_outcome }} - {{ doc.name }}",
            "use_html": 1,
            "response": get_appeal_decision_template()
        },
        {
            "name": "Termination Execution Notice",
            "subject": "Membership Termination Executed - {{ doc.member_name }}",
            "use_html": 1,
            "response": get_execution_notice_template()
        }
    ]
    
    created_count = 0
    
    for template_data in templates:
        template_name = template_data["name"]
        
        if frappe.db.exists("Email Template", template_name):
            print(f"   ✓ Email template '{template_name}' already exists")
            continue
            
        try:
            template = frappe.get_doc({
                "doctype": "Email Template",
                "name": template_name,
                "subject": template_data["subject"],
                "use_html": template_data["use_html"],
                "response": template_data["response"]
            })
            
            template.insert(ignore_permissions=True)
            created_count += 1
            print(f"   ✓ Created email template: {template_name}")
            
        except Exception as e:
            print(f"   ❌ Failed to create email template '{template_name}': {str(e)}")
            frappe.log_error(f"Failed to create email template {template_name}: {str(e)}", "Email Template Creation Error")
    
    if created_count > 0:
        frappe.db.commit()
    
    return created_count

def get_approval_email_template():
    """Get the approval email template HTML"""
    return """
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <div style="background-color: #fff3cd; padding: 20px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #ffc107;">
        <h2 style="color: #856404; margin: 0;">🔍 Termination Approval Required</h2>
        <p style="color: #6c757d; margin: 5px 0 0 0;">{{ frappe.utils.format_date(frappe.utils.today(), "dd MMMM yyyy") }}</p>
    </div>
    
    <div style="padding: 20px;">
        <p>A disciplinary termination request requires your approval:</p>
        
        <div style="background-color: #f8d7da; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #dc3545;">
            <h3 style="margin-top: 0; color: #721c24;">Disciplinary Action</h3>
            <ul style="margin: 10px 0;">
                <li><strong>Member:</strong> {{ doc.member_name }}</li>
                <li><strong>Termination Type:</strong> {{ doc.termination_type }}</li>
                <li><strong>Requested by:</strong> {{ doc.requested_by }}</li>
                <li><strong>Request Date:</strong> {{ frappe.utils.format_date(doc.request_date, "dd MMMM yyyy") }}</li>
            </ul>
        </div>
        
        <div style="margin: 20px 0;">
            <h3>Termination Reason</h3>
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px;">
                {{ doc.termination_reason or 'Not specified' }}
            </div>
        </div>
        
        {% if doc.disciplinary_documentation %}
        <div style="margin: 20px 0;">
            <h3>Supporting Documentation</h3>
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; border-left: 3px solid #6c757d;">
                {{ doc.disciplinary_documentation | safe }}
            </div>
        </div>
        {% endif %}
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{{ frappe.utils.get_url() }}/app/membership-termination-request/{{ doc.name }}" 
               style="background-color: #007bff; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                Review Termination Request
            </a>
        </div>
        
        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e9ecef;">
            <p>Best regards,<br>
            <strong>Governance System</strong></p>
        </div>
    </div>
</div>
"""

def get_appeal_acknowledgment_template():
    """Get the appeal acknowledgment template HTML"""
    return """
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
        <h2 style="color: #2c3e50; margin: 0;">Appeal Acknowledgment</h2>
        <p style="color: #6c757d; margin: 5px 0 0 0;">{{ frappe.utils.format_date(frappe.utils.today(), "dd MMMM yyyy") }}</p>
    </div>
    
    <div style="padding: 20px;">
        <p>Dear {{ doc.appellant_name }},</p>
        
        <p>We acknowledge receipt of your appeal regarding the termination of member <strong>{{ doc.member_name }}</strong>.</p>
        
        <div style="background-color: #e3f2fd; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <h3 style="margin-top: 0; color: #1976d2;">Appeal Details</h3>
            <ul style="margin: 10px 0;">
                <li><strong>Appeal Reference:</strong> {{ doc.name }}</li>
                <li><strong>Appeal Date:</strong> {{ frappe.utils.format_date(doc.appeal_date, "dd MMMM yyyy") }}</li>
                <li><strong>Review Deadline:</strong> {{ frappe.utils.format_date(doc.review_deadline or frappe.utils.add_days(doc.appeal_date, 60), "dd MMMM yyyy") }}</li>
                <li><strong>Remedy Sought:</strong> {{ doc.remedy_sought }}</li>
            </ul>
        </div>
        
        <p>Your appeal will be reviewed according to our appeals process and you will be notified of the decision.</p>
        
        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e9ecef;">
            <p>Best regards,<br>
            <strong>Appeals Review Panel</strong></p>
        </div>
    </div>
</div>
"""

def get_appeal_decision_template():
    """Get the appeal decision template HTML"""
    return """
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <div style="background-color: {% if doc.decision_outcome == 'Upheld' %}#d4edda{% elif doc.decision_outcome == 'Partially Upheld' %}#fff3cd{% else %}#f8d7da{% endif %}; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
        <h2 style="color: {% if doc.decision_outcome == 'Upheld' %}#155724{% elif doc.decision_outcome == 'Partially Upheld' %}#856404{% else %}#721c24{% endif %}; margin: 0;">Appeal Decision: {{ doc.decision_outcome }}</h2>
        <p style="color: #6c757d; margin: 5px 0 0 0;">{{ frappe.utils.format_date(doc.decision_date, "dd MMMM yyyy") }}</p>
    </div>
    
    <div style="padding: 20px;">
        <p>Dear {{ doc.appellant_name }},</p>
        
        <p>A decision has been made regarding your appeal <strong>{{ doc.name }}</strong>:</p>
        
        <div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
            <h3 style="margin-top: 0;">Decision: {{ doc.decision_outcome }}</h3>
            {% if doc.decision_rationale %}
            <div style="margin-top: 15px;">
                {{ doc.decision_rationale | safe }}
            </div>
            {% endif %}
        </div>
        
        {% if doc.implementation_status == 'Pending' %}
        <div style="background-color: #d1ecf1; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <p style="margin: 0;"><strong>Implementation Required:</strong> Corrective actions will be processed and you will be notified when complete.</p>
        </div>
        {% endif %}
        
        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e9ecef;">
            <p>Best regards,<br>
            <strong>Appeals Review Panel</strong></p>
        </div>
    </div>
</div>
"""

def get_execution_notice_template():
    """Get the execution notice template HTML"""
    return """
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <div style="background-color: #f8d7da; padding: 20px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #dc3545;">
        <h2 style="color: #721c24; margin: 0;">Membership Termination Executed</h2>
        <p style="color: #6c757d; margin: 5px 0 0 0;">{{ frappe.utils.format_date(doc.execution_date, "dd MMMM yyyy") }}</p>
    </div>
    
    <div style="padding: 20px;">
        <p>This is to confirm that the membership termination for <strong>{{ doc.member_name }}</strong> has been executed.</p>
        
        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <h3 style="margin-top: 0;">Termination Details</h3>
            <ul style="margin: 10px 0;">
                <li><strong>Member:</strong> {{ doc.member_name }}</li>
                <li><strong>Termination Type:</strong> {{ doc.termination_type }}</li>
                <li><strong>Execution Date:</strong> {{ frappe.utils.format_date(doc.execution_date, "dd MMMM yyyy") }}</li>
                <li><strong>Request ID:</strong> {{ doc.name }}</li>
            </ul>
        </div>
        
        {% if doc.sepa_mandates_cancelled or doc.positions_ended %}
        <div style="background-color: #e3f2fd; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <h3 style="margin-top: 0; color: #1976d2;">System Updates Completed</h3>
            <ul style="margin: 10px 0;">
                {% if doc.sepa_mandates_cancelled %}
                <li>{{ doc.sepa_mandates_cancelled }} SEPA mandate(s) cancelled</li>
                {% endif %}
                {% if doc.positions_ended %}
                <li>{{ doc.positions_ended }} board position(s) ended</li>
                {% endif %}
                {% if doc.newsletters_updated %}
                <li>Newsletter subscriptions updated</li>
                {% endif %}
            </ul>
        </div>
        {% endif %}
        
        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e9ecef;">
            <p>Best regards,<br>
            <strong>Membership System</strong></p>
        </div>
    </div>
</div>
"""

def debug_workflow_requirements():
    """Debug function to check workflow requirements"""
    
    print("\n🔍 WORKFLOW DEBUG INFO")
    print("-" * 25)
    
    # Check roles
    print("1. Available Roles:")
    roles = frappe.get_all("Role", fields=["name", "desk_access", "is_custom"], limit=20)
    for role in roles:
        if any(word in role.name for word in ["Manager", "System", "Admin"]):
            print(f"   - {role.name} (desk: {role.desk_access}, custom: {role.is_custom})")
    
    # Check doctypes
    print("\n2. Required DocTypes:")
    required_doctypes = ["Membership Termination Request", "Termination Appeals Process", "Workflow"]
    for doctype in required_doctypes:
        exists = frappe.db.exists("DocType", doctype)
        print(f"   - {doctype}: {'✓' if exists else '❌'}")
    
    # Check existing workflows
    print("\n3. Existing Workflows:")
    workflows = frappe.get_all("Workflow", fields=["name", "document_type", "is_active"], limit=10)
    if workflows:
        for wf in workflows:
            print(f"   - {wf.name} ({wf.document_type}) - Active: {wf.is_active}")
    else:
        print("   - No workflows found")
    
    print("-" * 25)

# Backwards compatibility with existing setup
def setup_termination_workflow():
    """Wrapper for existing setup calls"""
    return setup_with_debug()
