import frappe

def get_context(context):
    # Check permissions
    if not frappe.has_permission("E-Boekhouden Migration", "read"):
        frappe.throw("You don't have permission to access this page", frappe.PermissionError)
    
    context.no_cache = 1
    context.show_sidebar = False
    
    # Add page title
    context.title = "E-Boekhouden Account Mapping Review"
    
    return context