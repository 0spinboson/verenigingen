# File: verenigingen/workflow_states.py - SIMPLE DIRECT APPROACH
"""
Simple Direct Workflow Creation using SQL and Manual Document Creation
"""

import frappe
from frappe import _

def create_workflow_directly():
    """Create workflow using direct SQL approach to avoid document structure issues"""
    
    workflow_name = "Membership Termination Workflow"
    
    if frappe.db.exists("Workflow", workflow_name):
        print(f"   ✓ Workflow '{workflow_name}' already exists")
        return True
    
    print(f"   📋 Creating workflow directly: {workflow_name}")
    
    try:
        # Step 1: Create the main workflow record
        workflow_data = {
            'doctype': 'Workflow',
            'name': workflow_name,
            'workflow_name': workflow_name,
            'document_type': 'Membership Termination Request',
            'is_active': 1,
            'send_email_alert': 1,
            'workflow_state_field': 'status',
            'owner': frappe.session.user,
            'creation': frappe.utils.now(),
            'modified': frappe.utils.now(),
            'modified_by': frappe.session.user
        }
        
        # Insert main workflow record
        frappe.db.sql("""
            INSERT INTO `tabWorkflow` 
            (name, workflow_name, document_type, is_active, send_email_alert, workflow_state_field, 
             owner, creation, modified, modified_by, docstatus, idx)
            VALUES (%(name)s, %(workflow_name)s, %(document_type)s, %(is_active)s, %(send_email_alert)s, 
                   %(workflow_state_field)s, %(owner)s, %(creation)s, %(modified)s, %(modified_by)s, 0, 1)
        """, workflow_data)
        
        print("   ✓ Created main workflow record")
        
        # Step 2: Create workflow states
        states = [
            {'state': 'Draft', 'doc_status': '0', 'allow_edit': 'Association Manager', 'is_optional_state': 1},
            {'state': 'Pending Approval', 'doc_status': '0', 'allow_edit': 'Association Manager', 'message': 'Awaiting approval'},
            {'state': 'Approved', 'doc_status': '0', 'allow_edit': 'Association Manager', 'message': 'Approved for execution'},
            {'state': 'Rejected', 'doc_status': '0', 'allow_edit': 'Association Manager', 'message': 'Request rejected'},
            {'state': 'Executed', 'doc_status': '1', 'allow_edit': 'Association Manager', 'message': 'Termination executed'}
        ]
        
        for idx, state in enumerate(states, 1):
            state_name = frappe.generate_hash(length=10)
            frappe.db.sql("""
                INSERT INTO `tabWorkflow Document State`
                (name, parent, parenttype, parentfield, state, doc_status, allow_edit, message, is_optional_state, idx, 
                 owner, creation, modified, modified_by, docstatus)
                VALUES (%(name)s, %(parent)s, 'Workflow', 'states', %(state)s, %(doc_status)s, %(allow_edit)s, 
                       %(message)s, %(is_optional_state)s, %(idx)s, %(owner)s, %(creation)s, %(modified)s, %(modified_by)s, 0)
            """, {
                'name': state_name,
                'parent': workflow_name,
                'state': state['state'],
                'doc_status': state['doc_status'],
                'allow_edit': state['allow_edit'],
                'message': state.get('message', ''),
                'is_optional_state': state.get('is_optional_state', 0),
                'idx': idx,
                'owner': frappe.session.user,
                'creation': frappe.utils.now(),
                'modified': frappe.utils.now(),
                'modified_by': frappe.session.user
            })
        
        print("   ✓ Created workflow states")
        
        # Step 3: Create workflow transitions
        transitions = [
            {'state': 'Draft', 'action': 'Submit for Approval', 'next_state': 'Pending Approval', 'allowed': 'Association Manager'},
            {'state': 'Draft', 'action': 'Auto Approve', 'next_state': 'Approved', 'allowed': 'Association Manager'},
            {'state': 'Pending Approval', 'action': 'Approve', 'next_state': 'Approved', 'allowed': 'Association Manager'},
            {'state': 'Pending Approval', 'action': 'Reject', 'next_state': 'Rejected', 'allowed': 'Association Manager'},
            {'state': 'Approved', 'action': 'Execute', 'next_state': 'Executed', 'allowed': 'Association Manager'}
        ]
        
        for idx, transition in enumerate(transitions, 1):
            transition_name = frappe.generate_hash(length=10)
            frappe.db.sql("""
                INSERT INTO `tabWorkflow Transition`
                (name, parent, parenttype, parentfield, state, action, next_state, allowed, idx,
                 owner, creation, modified, modified_by, docstatus)
                VALUES (%(name)s, %(parent)s, 'Workflow', 'transitions', %(state)s, %(action)s, %(next_state)s, 
                       %(allowed)s, %(idx)s, %(owner)s, %(creation)s, %(modified)s, %(modified_by)s, 0)
            """, {
                'name': transition_name,
                'parent': workflow_name,
                'state': transition['state'],
                'action': transition['action'],
                'next_state': transition['next_state'],
                'allowed': transition['allowed'],
                'idx': idx,
                'owner': frappe.session.user,
                'creation': frappe.utils.now(),
                'modified': frappe.utils.now(),
                'modified_by': frappe.session.user
            })
        
        print("   ✓ Created workflow transitions")
        
        # Step 4: Commit the transaction
        frappe.db.commit()
        
        print(f"   ✅ Successfully created workflow: {workflow_name}")
        return True
        
    except Exception as e:
        print(f"   ❌ Failed to create workflow directly: {str(e)}")
        frappe.db.rollback()
        import traceback
        traceback.print_exc()
        return False

def create_simple_workflow_using_dict():
    """Alternative: Create workflow using simplified dictionary approach"""
    
    workflow_name = "Membership Termination Workflow"
    
    if frappe.db.exists("Workflow", workflow_name):
        print(f"   ✓ Workflow '{workflow_name}' already exists")
        return True
    
    print(f"   📋 Creating simple workflow: {workflow_name}")
    
    try:
        # Create workflow with minimal complexity
        workflow_doc = frappe.get_doc({
            "doctype": "Workflow",
            "workflow_name": workflow_name,
            "document_type": "Membership Termination Request",
            "is_active": 1,
            "workflow_state_field": "status",
            "states": [
                {
                    "doctype": "Workflow Document State",
                    "state": "Draft",
                    "doc_status": "0",
                    "allow_edit": "Association Manager"
                },
                {
                    "doctype": "Workflow Document State", 
                    "state": "Approved",
                    "doc_status": "0",
                    "allow_edit": "Association Manager"
                },
                {
                    "doctype": "Workflow Document State",
                    "state": "Executed", 
                    "doc_status": "1",
                    "allow_edit": "Association Manager"
                }
            ],
            "transitions": [
                {
                    "doctype": "Workflow Transition",
                    "state": "Draft",
                    "action": "Approve",
                    "next_state": "Approved",
                    "allowed": "Association Manager"
                },
                {
                    "doctype": "Workflow Transition",
                    "state": "Approved", 
                    "action": "Execute",
                    "next_state": "Executed",
                    "allowed": "Association Manager"
                }
            ]
        })
        
        workflow_doc.insert(ignore_permissions=True)
        frappe.db.commit()
        
        print(f"   ✅ Successfully created simple workflow: {workflow_name}")
        return True
        
    except Exception as e:
        print(f"   ❌ Failed to create simple workflow: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def create_workflow_via_api():
    """Create workflow using Frappe's API approach"""
    
    workflow_name = "Membership Termination Workflow"
    
    if frappe.db.exists("Workflow", workflow_name):
        print(f"   ✓ Workflow '{workflow_name}' already exists")
        return True
    
    print(f"   📋 Creating workflow via API: {workflow_name}")
    
    try:
        # Use frappe.client.insert equivalent
        workflow_dict = {
            "doctype": "Workflow",
            "workflow_name": workflow_name,
            "document_type": "Membership Termination Request", 
            "is_active": 1,
            "workflow_state_field": "status"
        }
        
        # Create the main document first
        workflow_doc = frappe.new_doc("Workflow")
        workflow_doc.update(workflow_dict)
        
        # Add states one by one
        workflow_doc.append("states", {
            "state": "Draft",
            "doc_status": "0", 
            "allow_edit": "Association Manager"
        })
        
        workflow_doc.append("states", {
            "state": "Approved",
            "doc_status": "0",
            "allow_edit": "Association Manager"
        })
        
        workflow_doc.append("states", {
            "state": "Executed",
            "doc_status": "1",
            "allow_edit": "Association Manager"
        })
        
        # Add transitions one by one
        workflow_doc.append("transitions", {
            "state": "Draft",
            "action": "Approve", 
            "next_state": "Approved",
            "allowed": "Association Manager"
        })
        
        workflow_doc.append("transitions", {
            "state": "Approved",
            "action": "Execute",
            "next_state": "Executed", 
            "allowed": "Association Manager"
        })
        
        # Save the document
        workflow_doc.save(ignore_permissions=True)
        frappe.db.commit()
        
        print(f"   ✅ Successfully created workflow via API: {workflow_name}")
        return True
        
    except Exception as e:
        print(f"   ❌ Failed to create workflow via API: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def setup_workflows_with_fallback():
    """Try multiple approaches to create workflows"""
    
    print("🔄 Setting up workflows with fallback approaches...")
    
    # Approach 1: Direct SQL
    print("\n   Approach 1: Direct SQL creation")
    if create_workflow_directly():
        return True
    
    # Approach 2: Simple dictionary
    print("\n   Approach 2: Simple dictionary approach")  
    if create_simple_workflow_using_dict():
        return True
    
    # Approach 3: API approach
    print("\n   Approach 3: API approach")
    if create_workflow_via_api():
        return True
    
    print("\n   ❌ All approaches failed")
    return False

def manual_workflow_creation_instructions():
    """Provide manual instructions for workflow creation"""
    
    print("\n" + "="*60)
    print("MANUAL WORKFLOW CREATION INSTRUCTIONS")
    print("="*60)
    
    print("\nSince automated workflow creation is failing, please create the workflow manually:")
    print("\n1. Go to: Setup → Workflow → Workflow")
    print("2. Click 'New'")
    print("3. Fill in the following details:")
    
    print("\n📋 WORKFLOW DETAILS:")
    print("   - Workflow Name: Membership Termination Workflow")
    print("   - Document Type: Membership Termination Request") 
    print("   - Is Active: ✓")
    print("   - Workflow State Field: status")
    
    print("\n📋 STATES:")
    print("   State 1:")
    print("     - State: Draft")
    print("     - Doc Status: 0 (Draft)")
    print("     - Allow Edit: Association Manager")
    print("     - Is Optional State: ✓")
    
    print("   State 2:")
    print("     - State: Approved") 
    print("     - Doc Status: 0 (Draft)")
    print("     - Allow Edit: Association Manager")
    
    print("   State 3:")
    print("     - State: Executed")
    print("     - Doc Status: 1 (Submitted)")
    print("     - Allow Edit: Association Manager")
    
    print("\n📋 TRANSITIONS:")
    print("   Transition 1:")
    print("     - State: Draft")
    print("     - Action: Approve")
    print("     - Next State: Approved")
    print("     - Allowed: Association Manager")
    
    print("   Transition 2:")
    print("     - State: Approved")
    print("     - Action: Execute") 
    print("     - Next State: Executed")
    print("     - Allowed: Association Manager")
    
    print("\n4. Save the workflow")
    print("5. The workflow should now be active")
    
    print("\n" + "="*60)

# Updated main setup function
def setup_with_debug():
    """Setup workflows with debug information and fallback approaches"""
    
    try:
        print("🔄 Setting up termination workflows...")
        
        # Run diagnostics
        debug_workflow_requirements()
        
        # Create missing roles
        roles_created = create_missing_roles()
        
        # Try workflow creation with fallback approaches
        workflow_success = setup_workflows_with_fallback()
        
        if not workflow_success:
            print("\n⚠️ Automated workflow creation failed")
            manual_workflow_creation_instructions()
            
        # Setup email templates (this usually works)
        templates_created = setup_email_templates()
        
        if workflow_success:
            print(f"✅ Workflow setup completed - Roles: {roles_created}, Workflows: 1, Templates: {templates_created}")
        else:
            print(f"⚠️ Partial setup completed - Roles: {roles_created}, Workflows: MANUAL, Templates: {templates_created}")
            
        return workflow_success
        
    except Exception as e:
        print(f"❌ Workflow setup failed: {str(e)}")
        frappe.log_error(f"Workflow setup error: {str(e)}", "Termination Workflow Setup")
        import traceback
        traceback.print_exc()
        return False

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

def create_missing_roles():
    """Create required roles if they don't exist"""
    
    print("   🔐 Creating required roles...")
    
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
    """Create basic email templates"""
    
    print("   📧 Setting up email templates...")
    
    templates = [
        {
            "name": "Termination Approval Required",  
            "subject": "Termination Approval Required - {{ doc.member_name }}",
            "use_html": 1,
            "response": "<p>A termination request requires your approval for member: {{ doc.member_name }}</p>"
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
    
    if created_count > 0:
        try:
            frappe.db.commit()
        except Exception as e:
            print(f"   ⚠️ Template commit warning: {str(e)}")
    
    return created_count

# Entry points
def setup_termination_workflow():
    """Main entry point for workflow setup"""
    return setup_with_debug()

@frappe.whitelist()
def run_safe_setup():
    """API endpoint for safe setup"""
    return setup_with_debug()
