# File: verenigingen/workflow_states.py - SIMPLE DIRECT APPROACH
"""
Simple Direct Workflow Creation using SQL and Manual Document Creation
"""

import frappe
from frappe import _
from verenigingen.simplified_workflow_setup import setup_workflows_simplified

# Replace the existing setup_with_debug() function with:
def setup_with_debug():
    """Setup workflows with simplified approach"""
    print("🔄 Setting up termination workflows using simplified approach...")
    return setup_workflows_simplified()


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
