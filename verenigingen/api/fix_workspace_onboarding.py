"""
Fix Workspace Onboarding Visibility
"""

import frappe

@frappe.whitelist()
def add_onboarding_to_workspace():
    """Add Module Onboarding link to Verenigingen workspace"""
    
    try:
        # Get the Verenigingen workspace
        workspace = frappe.get_doc('Workspace', 'Verenigingen')
        
        # Check if onboarding link already exists
        onboarding_exists = False
        for link in workspace.links:
            if link.link_to == 'Module Onboarding' or 'onboarding' in (link.label or "").lower():
                onboarding_exists = True
                break
        
        if not onboarding_exists:
            # Add onboarding section at the top
            workspace.append('links', {
                'label': 'Getting Started',
                'type': 'Card Break',
                'hidden': 0,
                'link_count': 1
            })
            
            workspace.append('links', {
                'label': 'Association Setup Guide',
                'type': 'Link',
                'link_type': 'DocType',
                'link_to': 'Module Onboarding',
                'dependencies': '',
                'hidden': 0,
                'is_query_report': 0,
                'onboard': 1  # This makes it show as onboarding
            })
            
            # Also add a shortcut
            workspace.append('shortcuts', {
                'label': 'Setup Guide',
                'type': 'DocType',
                'link_to': 'Module Onboarding',
                'color': 'Blue'
            })
            
            workspace.save()
            frappe.db.commit()
            
            return {
                "success": True,
                "message": "Onboarding link added to Verenigingen workspace",
                "onboarding_url": "/app/module-onboarding/Verenigingen"
            }
        else:
            return {
                "success": True,
                "message": "Onboarding link already exists in workspace"
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def create_onboarding_shortcut():
    """Create a direct shortcut to Verenigingen onboarding"""
    
    try:
        # Get the workspace
        workspace = frappe.get_doc('Workspace', 'Verenigingen')
        
        # Add a prominent onboarding shortcut if it doesn't exist
        onboarding_shortcut_exists = False
        for shortcut in workspace.shortcuts:
            if 'setup' in (shortcut.label or "").lower() or 'onboard' in (shortcut.label or "").lower():
                onboarding_shortcut_exists = True
                break
        
        if not onboarding_shortcut_exists:
            # Add as first shortcut
            workspace.shortcuts.insert(0, {
                'label': '🚀 Setup Guide',
                'type': 'DocType', 
                'link_to': 'Module Onboarding',
                'color': 'Green'
            })
            
            workspace.save()
            frappe.db.commit()
            
            return {
                "success": True,
                "message": "Setup Guide shortcut added to workspace"
            }
        else:
            return {
                "success": True,
                "message": "Setup shortcut already exists"
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def check_onboarding_status():
    """Check the status of Verenigingen onboarding"""
    
    try:
        # Get the onboarding document
        onboarding = frappe.get_doc('Module Onboarding', 'Verenigingen')
        
        # Get onboarding steps
        steps = frappe.get_all('Onboarding Step',
                              filters={'parent': 'Verenigingen'},
                              fields=['title', 'action', 'is_complete', 'intro_video_url', 'description'],
                              order_by='idx')
        
        return {
            "success": True,
            "onboarding": {
                "name": onboarding.name,
                "title": onboarding.title,
                "is_complete": onboarding.is_complete,
                "subtitle": getattr(onboarding, 'subtitle', ''),
                "success_message": getattr(onboarding, 'success_message', ''),
                "steps_count": len(steps),
                "completed_steps": len([s for s in steps if s.is_complete])
            },
            "steps": steps,
            "direct_url": f"/app/module-onboarding/{onboarding.name}"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }