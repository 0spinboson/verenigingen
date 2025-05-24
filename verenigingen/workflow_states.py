# File: verenigingen/workflow_states.py - CORRECTED VERSION
"""
Fixed Workflow States Setup with Proper Document Structure
"""

import frappe
from frappe import _

def setup_main_termination_workflow():
    """Create the main termination workflow with proper document structure"""
    
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
        roles_string = ",".join(available_roles)
        
        print(f"   Using primary role: {primary_role}")
        print(f"   Using roles string: {roles_string}")
        
        # Create the workflow document step by step
        workflow_doc = frappe.new_doc("Workflow")
        workflow_doc.workflow_name = workflow_name
        workflow_doc.document_type = "Membership Termination Request"
        workflow_doc.is_active = 1
        workflow_doc.send_email_alert = 1
        workflow_doc.workflow_state_field = "status"
        
        # Add states as child documents
        print("   Adding workflow states...")
        
        # State 1: Draft
        draft_state = workflow_doc.append("states", {})
        draft_state.state = "Draft"
        draft_state.doc_status = "0"
        draft_state.allow_edit = roles_string
        draft_state.is_optional_state = 1
        
        # State 2: Pending Approval
        pending_state = workflow_doc.append("states", {})
        pending_state.state = "Pending Approval"
        pending_state.doc_status = "0"
        pending_state.allow_edit = primary_role
        pending_state.message = "Awaiting secondary approval for disciplinary termination"
        
        # State 3: Approved
        approved_state = workflow_doc.append("states", {})
        approved_state.state = "Approved"
        approved_state.doc_status = "0"
        approved_state.allow_edit = roles_string
        approved_state.message = "Approved and ready for execution"
        
        # State 4: Rejected
        rejected_state = workflow_doc.append("states", {})
        rejected_state.state = "Rejected"
        rejected_state.doc_status = "0"
        rejected_state.allow_edit = primary_role
        rejected_state.message = "Termination request rejected"
        
        # State 5: Executed
        executed_state = workflow_doc.append("states", {})
        executed_state.state = "Executed"
        executed_state.doc_status = "1"
        executed_state.allow_edit = primary_role
        executed_state.message = "Termination has been executed"
        
        # Add transitions as child documents
        print("   Adding workflow transitions...")
        
        # Transition 1: Draft to Pending Approval
        trans1 = workflow_doc.append("transitions", {})
        trans1.state = "Draft"
        trans1.action = "Submit for Approval"
        trans1.next_state = "Pending Approval"
        trans1.allowed = roles_string
        trans1.condition = "doc.requires_secondary_approval == 1"
        
        # Transition 2: Draft to Approved (auto-approve)
        trans2 = workflow_doc.append("transitions", {})
        trans2.state = "Draft"
        trans2.action = "Auto Approve"
        trans2.next_state = "Approved"
        trans2.allowed = roles_string
        trans2.condition = "doc.requires_secondary_approval == 0"
        
        # Transition 3: Pending Approval to Approved
        trans3 = workflow_doc.append("transitions", {})
        trans3.state = "Pending Approval"
        trans3.action = "Approve"
        trans3.next_state = "Approved"
        trans3.allowed = primary_role
        
        # Transition 4: Pending Approval to Rejected
        trans4 = workflow_doc.append("transitions", {})
        trans4.state = "Pending Approval"
        trans4.action = "Reject"
        trans4.next_state = "Rejected"
        trans4.allowed = primary_role
        
        # Transition 5: Approved to Executed
        trans5 = workflow_doc.append("transitions", {})
        trans5.state = "Approved"
        trans5.action = "Execute"
        trans5.next_state = "Executed"
        trans5.allowed = roles_string
        
        print("   Saving workflow document...")
        workflow_doc.insert(ignore_permissions=True)
        frappe.db.commit()
        
        print(f"   ✅ Created workflow: {workflow_name}")
        return 1
        
    except Exception as e:
        print(f"   ❌ Failed to create workflow: {str(e)}")
        frappe.log_error(f"Failed to create termination workflow: {str(e)}", "Workflow Creation Error")
        import traceback
        traceback.print_exc()
        return 0

def setup_appeals_workflow():
    """Create the appeals workflow with proper document structure"""
    
    workflow_name = "Termination Appeals Workflow"
    
    if frappe.db.exists("Workflow", workflow_name):
        print(f"   ✓ Appeals workflow '{workflow_name}' already exists")
        return 0
    
    print(f"   📋 Creating appeals workflow: {workflow_name}")
    
    try:
        available_roles = get_available_roles()
        primary_role = available_roles[0] if available_roles else "System Manager"
        roles_string = ",".join(available_roles)
        member_roles_string = ",".join(available_roles + ["Member Portal User"])
        
        # Create the workflow document
        workflow_doc = frappe.new_doc("Workflow")
        workflow_doc.workflow_name = workflow_name
        workflow_doc.document_type = "Termination Appeals Process"
        workflow_doc.is_active = 1
        workflow_doc.send_email_alert = 1
        workflow_doc.workflow_state_field = "appeal_status"
        
        # Add states
        print("   Adding appeals workflow states...")
        
        # State 1: Draft
        draft_state = workflow_doc.append("states", {})
        draft_state.state = "Draft"
        draft_state.doc_status = "0"
        draft_state.allow_edit = member_roles_string
        draft_state.is_optional_state = 1
        
        # State 2: Submitted
        submitted_state = workflow_doc.append("states", {})
        submitted_state.state = "Submitted"
        submitted_state.doc_status = "0"
        submitted_state.allow_edit = primary_role
        submitted_state.message = "Appeal submitted and awaiting review assignment"
        
        # State 3: Under Review
        review_state = workflow_doc.append("states", {})
        review_state.state = "Under Review"
        review_state.doc_status = "0"
        review_state.allow_edit = roles_string
        review_state.message = "Appeal is under active review"
        
        # State 4: Pending Decision
        pending_state = workflow_doc.append("states", {})
        pending_state.state = "Pending Decision"
        pending_state.doc_status = "0"
        pending_state.allow_edit = roles_string
        pending_state.message = "Review complete, decision pending"
        
        # State 5: Decided - Upheld
        upheld_state = workflow_doc.append("states", {})
        upheld_state.state = "Decided - Upheld"
        upheld_state.doc_status = "1"
        upheld_state.allow_edit = primary_role
        upheld_state.message = "Appeal upheld - implementation required"
        
        # State 6: Decided - Rejected
        rejected_state = workflow_doc.append("states", {})
        rejected_state.state = "Decided - Rejected"
        rejected_state.doc_status = "1"
        rejected_state.allow_edit = primary_role
        rejected_state.message = "Appeal rejected - decision stands"
        
        # State 7: Decided - Partially Upheld
        partial_state = workflow_doc.append("states", {})
        partial_state.state = "Decided - Partially Upheld"
        partial_state.doc_status = "1"
        partial_state.allow_edit = primary_role
        partial_state.message = "Appeal partially upheld - partial implementation required"
        
        # Add transitions
        print("   Adding appeals workflow transitions...")
        
        # Transition 1: Draft to Submitted
        trans1 = workflow_doc.append("transitions", {})
        trans1.state = "Draft"
        trans1.action = "Submit Appeal"
        trans1.next_state = "Submitted"
        trans1.allowed = member_roles_string
        
        # Transition 2: Submitted to Under Review
        trans2 = workflow_doc.append("transitions", {})
        trans2.state = "Submitted"
        trans2.action = "Start Review"
        trans2.next_state = "Under Review"
        trans2.allowed = roles_string
        
        # Transition 3: Under Review to Pending Decision
        trans3 = workflow_doc.append("transitions", {})
        trans3.state = "Under Review"
        trans3.action = "Complete Review"
        trans3.next_state = "Pending Decision"
        trans3.allowed = roles_string
        
        # Transition 4: Pending Decision to Upheld
        trans4 = workflow_doc.append("transitions", {})
        trans4.state = "Pending Decision"
        trans4.action = "Uphold Appeal"
        trans4.next_state = "Decided - Upheld"
        trans4.allowed = roles_string
        
        # Transition 5: Pending Decision to Rejected
        trans5 = workflow_doc.append("transitions", {})
        trans5.state = "Pending Decision"
        trans5.action = "Reject Appeal"
        trans5.next_state = "Decided - Rejected"
        trans5.allowed = roles_string
        
        # Transition 6: Pending Decision to Partially Upheld
        trans6 = workflow_doc.append("transitions", {})
        trans6.state = "Pending Decision"
        trans6.action = "Partially Uphold"
        trans6.next_state = "Decided - Partially Upheld"
        trans6.allowed = roles_string
        
        print("   Saving appeals workflow document...")
        workflow_doc.insert(ignore_permissions=True)
        frappe.db.commit()
        
        print(f"   ✅ Created appeals workflow: {workflow_name}")
        return 1
        
    except Exception as e:
        print(f"   ❌ Failed to create appeals workflow: {str(e)}")
        frappe.log_error(f"Failed to create appeals workflow: {str(e)}", "Appeals Workflow Creation Error")
        import traceback
        traceback.print_exc()
        return 0

def get_available_roles():
    """Get list of available roles for workflow"""
    
    preferred_roles = ["Association Manager", "System Manager"]
    available_roles = []
    
    for role in preferred_roles:
        if frappe.db.exists("Role", role):
            available_roles.append(role)
    
    return available_roles

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
        try:
            frappe.db.commit()
        except Exception as e:
            print(f"   ⚠️ Role commit warning: {str(e)}")
    
    return created_count

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
        try:
            frappe.db.commit()
        except Exception as e:
            print(f"   ⚠️ Template commit warning: {str(e)}")
    
    return created_count

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

def setup_with_debug():
    """Setup workflows with debug information"""
    try:
        print("🔄 Setting up termination workflows...")
        
        # Run diagnostics first
        debug_workflow_requirements()
        
        # Create missing roles
        roles_created = create_missing_roles()
        
        # Setup main workflow
        workflow_created = setup_main_termination_workflow()
        
        # Setup appeals workflow
        appeals_workflow_created = setup_appeals_workflow()
        
        # Setup email templates
        templates_created = setup_email_templates()
        
        print(f"✅ Workflow setup completed - Roles: {roles_created}, Workflows: {workflow_created + appeals_workflow_created}, Templates: {templates_created}")
        return True
        
    except Exception as e:
        print(f"❌ Workflow setup failed: {str(e)}")
        frappe.log_error(f"Workflow setup error: {str(e)}", "Termination Workflow Setup")
        import traceback
        traceback.print_exc()
        return False

def safe_setup_termination_system():
    """Safe setup with database transaction handling"""
    
    print("🔄 Starting SAFE termination system setup...")
    
    try:
        # Step 1: Check database connection
        frappe.db.sql("SELECT 1")
        print("   ✓ Database connection OK")
        
        # Step 2: Setup roles first (small transaction)
        print("   🔐 Setting up roles...")
        roles_created = create_missing_roles()
        
        # Step 3: Setup main workflow
        print("   📋 Setting up main workflow...")
        main_workflow_created = setup_main_termination_workflow()
        
        # Step 4: Setup appeals workflow  
        print("   📋 Setting up appeals workflow...")
        appeals_workflow_created = setup_appeals_workflow()
        
        # Step 5: Setup email templates
        print("   📧 Setting up email templates...")
        templates_created = setup_email_templates()
        
        # Final commit
        frappe.db.commit()
        
        print(f"✅ SAFE setup completed successfully!")
        print(f"   - Roles created: {roles_created}")
        print(f"   - Workflows created: {main_workflow_created + appeals_workflow_created}")
        print(f"   - Email templates created: {templates_created}")
        
        return True
        
    except Exception as e:
        print(f"❌ SAFE setup failed: {str(e)}")
        try:
            frappe.db.rollback()
            print("   🔄 Database rolled back")
        except:
            pass
        
        import traceback
        traceback.print_exc()
        return False

# Email template functions (keeping them short for space)
def get_approval_email_template():
    return """
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <div style="background-color: #fff3cd; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
        <h2 style="color: #856404; margin: 0;">🔍 Termination Approval Required</h2>
    </div>
    <div style="padding: 20px;">
        <p>A disciplinary termination request requires your approval:</p>
        <div style="background-color: #f8d7da; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <h3 style="margin-top: 0; color: #721c24;">Disciplinary Action</h3>
            <ul>
                <li><strong>Member:</strong> {{ doc.member_name }}</li>
                <li><strong>Type:</strong> {{ doc.termination_type }}</li>
                <li><strong>Requested by:</strong> {{ doc.requested_by }}</li>
            </ul>
        </div>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{{ frappe.utils.get_url() }}/app/membership-termination-request/{{ doc.name }}" 
               style="background-color: #007bff; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px;">
                Review Request
            </a>
        </div>
    </div>
</div>
"""

def get_appeal_acknowledgment_template():
    return """
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
        <h2 style="color: #2c3e50; margin: 0;">Appeal Acknowledgment</h2>
    </div>
    <div style="padding: 20px;">
        <p>Dear {{ doc.appellant_name }},</p>
        <p>We acknowledge receipt of your appeal regarding <strong>{{ doc.member_name }}</strong>.</p>
        <div style="background-color: #e3f2fd; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <h3 style="margin-top: 0; color: #1976d2;">Appeal Details</h3>
            <ul>
                <li><strong>Reference:</strong> {{ doc.name }}</li>
                <li><strong>Appeal Date:</strong> {{ frappe.utils.format_date(doc.appeal_date) }}</li>
                <li><strong>Remedy Sought:</strong> {{ doc.remedy_sought }}</li>
            </ul>
        </div>
        <p>Your appeal will be reviewed and you will be notified of the decision.</p>
    </div>
</div>
"""

def get_appeal_decision_template():
    return """
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
        <h2 style="color: #2c3e50; margin: 0;">Appeal Decision: {{ doc.decision_outcome }}</h2>
    </div>
    <div style="padding: 20px;">
        <p>Dear {{ doc.appellant_name }},</p>
        <p>A decision has been made regarding your appeal <strong>{{ doc.name }}</strong>:</p>
        <div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
            <h3>Decision: {{ doc.decision_outcome }}</h3>
            {% if doc.decision_rationale %}
            <div>{{ doc.decision_rationale | safe }}</div>
            {% endif %}
        </div>
    </div>
</div>
"""

def get_execution_notice_template():
    return """
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <div style="background-color: #f8d7da; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
        <h2 style="color: #721c24; margin: 0;">Membership Termination Executed</h2>
    </div>
    <div style="padding: 20px;">
        <p>The membership termination for <strong>{{ doc.member_name }}</strong> has been executed.</p>
        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <h3>Termination Details</h3>
            <ul>
                <li><strong>Member:</strong> {{ doc.member_name }}</li>
                <li><strong>Type:</strong> {{ doc.termination_type }}</li>
                <li><strong>Date:</strong> {{ frappe.utils.format_date(doc.execution_date) }}</li>
            </ul>
        </div>
    </div>
</div>
"""

# Entry point
def setup_termination_workflow():
    """Main entry point for workflow setup"""
    return setup_with_debug()

@frappe.whitelist()
def run_safe_setup():
    """API endpoint for safe setup"""
    return safe_setup_termination_system()
