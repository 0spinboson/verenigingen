import frappe

@frappe.whitelist()
def fix_sepa_workspace():
    """Fix SEPA Management workspace to work with current Frappe version"""
    
    try:
        # Get the workspace
        workspace = frappe.get_doc("Workspace", "SEPA Management")
        
        # Clear any problematic fields
        if hasattr(workspace, 'onboarding_list'):
            delattr(workspace, 'onboarding_list')
        
        # Ensure content is properly formatted
        if workspace.content:
            # Parse and rebuild content to ensure compatibility
            import json
            try:
                content_data = json.loads(workspace.content)
                # Remove any onboarding references
                if isinstance(content_data, list):
                    content_data = [item for item in content_data if item.get('type') != 'onboarding']
                workspace.content = json.dumps(content_data)
            except:
                # If content parsing fails, reset to minimal content
                workspace.content = '[]'
        
        # Clear module onboarding
        workspace.module_onboarding = None
        
        # Save without triggering validations
        workspace.flags.ignore_validate = True
        workspace.save(ignore_permissions=True)
        
        frappe.db.commit()
        frappe.clear_cache()
        
        return {"success": True, "message": "SEPA Management workspace fixed"}
        
    except Exception as e:
        frappe.log_error(str(e), "SEPA Workspace Fix Error")
        return {"success": False, "error": str(e)}