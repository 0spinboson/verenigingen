import frappe
from frappe import _

def create_workflow_state_masters():
    """Create workflow state masters if they don't exist"""
    
    print("   🏗️ Creating workflow state masters...")
    
    # Standard states that should already exist in Frappe
    standard_states = ["Draft", "Pending", "Approved", "Rejected", "Cancelled"]
    
    # Custom states we need for termination workflow
    custom_states = ["Executed"]
    
    created_count = 0
    
    for state in custom_states:
        if not frappe.db.exists("Workflow State", state):
            try:
                state_doc = frappe.get_doc({
                    "doctype": "Workflow State",
                    "workflow_state_name": state
                })
                state_doc.insert(ignore_permissions=True)
                created_count += 1
                print(f"      ✓ Created workflow state: {state}")
            except Exception as e:
                print(f"      ⚠️ Could not create state {state}: {str(e)}")
        else:
            print(f"      ✓ State already exists: {state}")
    
    return created_count

def create_workflow_action_masters():
    """Create workflow action masters if they don't exist"""
    
    print("   ⚡ Creating workflow action masters...")
    
    # Standard actions that should already exist
    standard_actions = ["Submit", "Approve", "Reject", "Cancel"]
    
    # Custom actions we need
    custom_actions = ["Execute"]
    
    created_count = 0
    
    for action in custom_actions:
        if not frappe.db.exists("Workflow Action Master", action):
            try:
                action_doc = frappe.get_doc({
                    "doctype": "Workflow Action Master",
                    "workflow_action_name": action
                })
                action_doc.insert(ignore_permissions=True)
                created_count += 1
                print(f"      ✓ Created workflow action: {action}")
            except Exception as e:
                print(f"      ⚠️ Could not create action {action}: {str(e)}")
        else:
            print(f"      ✓ Action already exists: {action}")
    
    return created_count

def create_termination_workflow_simple():
    """Create termination workflow using standard Frappe patterns"""
    
    workflow_name = "Membership Termination Workflow"
    
    if frappe.db.exists("Workflow", workflow_name):
        print(f"   ✓ Workflow '{workflow_name}' already exists")
        return True
    
    print(f"   📋 Creating simplified workflow: {workflow_name}")
    
    try:
        # Create workflow document
        workflow_doc = frappe.new_doc("Workflow")
        workflow_doc.workflow_name = workflow_name
        workflow_doc.document_type = "Membership Termination Request"
        workflow_doc.is_active = 1
        workflow_doc.workflow_state_field = "status"
        workflow_doc.send_email_alert = 0
        
        # Add states using standard Frappe pattern
        # State 1: Draft (initial state)
        workflow_doc.append("states", {
            "state": "Draft",
            "doc_status": "0",
            "allow_edit": "System Manager,Association Manager",
            "is_optional_state": 1
        })
        
        # State 2: Pending (for approval workflow)
        workflow_doc.append("states", {
            "state": "Pending",
            "doc_status": "0", 
            "allow_edit": "System Manager,Association Manager"
        })
        
        # State 3: Approved (ready for execution)
        workflow_doc.append("states", {
            "state": "Approved",
            "doc_status": "0",
            "allow_edit": "System Manager,Association Manager"
        })
        
        # State 4: Rejected 
        workflow_doc.append("states", {
            "state": "Rejected",
            "doc_status": "0",
            "allow_edit": "System Manager,Association Manager"
        })
        
        # State 5: Executed (final state)
        workflow_doc.append("states", {
            "state": "Executed",
            "doc_status": "1",
            "allow_edit": "System Manager"
        })
        
        # Add transitions using standard actions
        # Draft -> Pending (Submit)
        workflow_doc.append("transitions", {
            "state": "Draft",
            "action": "Submit",
            "next_state": "Pending",
            "allowed": "System Manager,Association Manager"
        })
        
        # Pending -> Approved (Approve)
        workflow_doc.append("transitions", {
            "state": "Pending", 
            "action": "Approve",
            "next_state": "Approved",
            "allowed": "System Manager,Association Manager"
        })
        
        # Pending -> Rejected (Reject)
        workflow_doc.append("transitions", {
            "state": "Pending",
            "action": "Reject", 
            "next_state": "Rejected",
            "allowed": "System Manager,Association Manager"
        })
        
        # Approved -> Executed (Execute)
        workflow_doc.append("transitions", {
            "state": "Approved",
            "action": "Execute",
            "next_state": "Executed",
            "allowed": "System Manager,Association Manager"
        })
        
        # Draft -> Approved (direct approval for non-disciplinary)
        workflow_doc.append("transitions", {
            "state": "Draft",
            "action": "Approve",
            "next_state": "Approved", 
            "allowed": "System Manager,Association Manager"
        })
        
        # Save the workflow
        workflow_doc.insert(ignore_permissions=True)
        
        print(f"   ✅ Successfully created workflow: {workflow_name}")
        return True
        
    except Exception as e:
        print(f"   ❌ Failed to create workflow: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def create_appeals_workflow_simple():
    """Create appeals workflow using standard patterns"""
    
    workflow_name = "Termination Appeals Workflow"
    
    if frappe.db.exists("Workflow", workflow_name):
        print(f"   ✓ Appeals workflow already exists")
        return True
    
    print(f"   📋 Creating appeals workflow: {workflow_name}")
    
    try:
        workflow_doc = frappe.new_doc("Workflow")
        workflow_doc.workflow_name = workflow_name
        workflow_doc.document_type = "Termination Appeals Process"
        workflow_doc.is_active = 1
        workflow_doc.workflow_state_field = "appeal_status"
        workflow_doc.send_email_alert = 0
        
        # Appeals states
        workflow_doc.append("states", {
            "state": "Draft",
            "doc_status": "0",
            "allow_edit": "All",
            "is_optional_state": 1
        })
        
        workflow_doc.append("states", {
            "state": "Pending",
            "doc_status": "0",
            "allow_edit": "System Manager,Association Manager"
        })
        
        workflow_doc.append("states", {
            "state": "Approved",  # Appeal upheld
            "doc_status": "1",
            "allow_edit": "System Manager"
        })
        
        workflow_doc.append("states", {
            "state": "Rejected",  # Appeal rejected
            "doc_status": "1", 
            "allow_edit": "System Manager"
        })
        
        # Appeals transitions
        workflow_doc.append("transitions", {
            "state": "Draft",
            "action": "Submit",
            "next_state": "Pending",
            "allowed": "All"
        })
        
        workflow_doc.append("transitions", {
            "state": "Pending",
            "action": "Approve", 
            "next_state": "Approved",
            "allowed": "System Manager,Association Manager"
        })
        
        workflow_doc.append("transitions", {
            "state": "Pending",
            "action": "Reject",
            "next_state": "Rejected",
            "allowed": "System Manager,Association Manager"
        })
        
        workflow_doc.insert(ignore_permissions=True)
        
        print(f"   ✅ Successfully created appeals workflow")
        return True
        
    except Exception as e:
        print(f"   ❌ Failed to create appeals workflow: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def validate_prerequisites():
    """Validate prerequisites for workflow creation"""
    
    print("   🔍 Validating prerequisites...")
    
    issues = []
    
    # Check target doctypes
    required_doctypes = [
        "Membership Termination Request",
        "Termination Appeals Process"
    ]
    
    for doctype in required_doctypes:
        if not frappe.db.exists("DocType", doctype):
            issues.append(f"Missing DocType: {doctype}")
        else:
            # Check workflow state field exists
            try:
                meta = frappe.get_meta(doctype)
                if doctype == "Membership Termination Request":
                    if not meta.has_field("status"):
                        issues.append(f"{doctype} missing 'status' field")
                elif doctype == "Termination Appeals Process":
                    if not meta.has_field("appeal_status"):
                        issues.append(f"{doctype} missing 'appeal_status' field")
            except Exception as e:
                issues.append(f"Cannot validate {doctype}: {str(e)}")
    
    # Check required roles
    required_roles = ["System Manager", "Association Manager"]
    for role in required_roles:
        if not frappe.db.exists("Role", role):
            issues.append(f"Missing Role: {role}")
    
    if issues:
        print("   ❌ Prerequisites validation failed:")
        for issue in issues:
            print(f"      - {issue}")
        return False
    
    print("   ✅ All prerequisites validated")
    return True

def setup_workflows_simplified():
    """Main function to setup workflows using simplified approach"""
    
    print("🔄 Setting up workflows using simplified Frappe patterns...")
    
    # Step 1: Validate prerequisites
    if not validate_prerequisites():
        return False
    
    success_count = 0
    
    # Step 2: Create workflow masters if needed
    try:
        states_created = create_workflow_state_masters()
        actions_created = create_workflow_action_masters()
        
        if states_created > 0 or actions_created > 0:
            frappe.db.commit()
            print(f"   ✅ Created {states_created} states and {actions_created} actions")
    except Exception as e:
        print(f"   ⚠️ Warning creating masters: {str(e)}")
    
    # Step 3: Create termination workflow
    if create_termination_workflow_simple():
        success_count += 1
    
    # Step 4: Create appeals workflow
    if create_appeals_workflow_simple():
        success_count += 1
    
    # Step 5: Commit all changes
    try:
        frappe.db.commit()
        print(f"   ✅ Successfully committed {success_count} workflows")
        return success_count > 0
    except Exception as e:
        print(f"   ❌ Commit failed: {str(e)}")
        frappe.db.rollback()
        return False

def test_workflow_functionality():
    """Test that workflows are working properly"""
    
    print("🧪 Testing workflow functionality...")
    
    # Test termination workflow
    try:
        if frappe.db.exists("Workflow", "Membership Termination Workflow"):
            workflow = frappe.get_doc("Workflow", "Membership Termination Workflow")
            print(f"   ✓ Termination workflow has {len(workflow.states)} states and {len(workflow.transitions)} transitions")
        else:
            print("   ❌ Termination workflow not found")
    except Exception as e:
        print(f"   ❌ Error testing termination workflow: {str(e)}")
    
    # Test appeals workflow
    try:
        if frappe.db.exists("Workflow", "Termination Appeals Workflow"):
            workflow = frappe.get_doc("Workflow", "Termination Appeals Workflow")
            print(f"   ✓ Appeals workflow has {len(workflow.states)} states and {len(workflow.transitions)} transitions")
        else:
            print("   ❌ Appeals workflow not found")
    except Exception as e:
        print(f"   ❌ Error testing appeals workflow: {str(e)}")

# API endpoints
@frappe.whitelist()
def setup_production_workflows():
    """API endpoint for production workflow setup"""
    result = setup_workflows_simplified()
    if result:
        test_workflow_functionality()
    return result

@frappe.whitelist()
def test_workflows():
    """API endpoint for testing workflows"""
    test_workflow_functionality()
    return True

# Integration with existing setup
def replace_workflow_setup():
    """Function to replace the existing workflow setup in workflow_states.py"""
    return setup_workflows_simplified()

# Main execution for testing
if __name__ == "__main__":
    setup_workflows_simplified()
    test_workflow_functionality()
