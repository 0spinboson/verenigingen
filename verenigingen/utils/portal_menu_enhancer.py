"""
Portal menu enhancer to add submenu items
"""

import frappe

@frappe.whitelist()
def debug_portal_settings():
    """Debug portal settings to see what menu items are available"""
    try:
        portal_settings = frappe.get_single("Portal Settings")
        
        menu_items = []
        for idx, item in enumerate(portal_settings.menu):
            menu_items.append({
                "idx": idx + 1,
                "title": item.title,
                "route": item.route,
                "enabled": item.enabled,
                "role": getattr(item, 'role', None),
                "reference_doctype": getattr(item, 'reference_doctype', None)
            })
        
        return {
            "success": True,
            "total_items": len(portal_settings.menu),
            "menu_items": menu_items
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_enhanced_portal_menu_items():
    """Get portal menu items with submenus for member portal"""
    
    # Start with custom member-specific items that may not be in Portal Settings
    enhanced_menu = []
    
    # Add Member Portal (custom item)
    enhanced_menu.append({
        "title": "Member Portal",
        "route": "/member_portal",
        "reference_doctype": None,
        "role": None,
        "target": None,
        "submenu": [
            {
                "title": "Dashboard Overview",
                "description": "View your membership status and key information",
                "icon": "fa fa-dashboard"
            },
            {
                "title": "Personal Information", 
                "description": "Update your contact details and preferences",
                "icon": "fa fa-user"
            },
            {
                "title": "Membership Details",
                "description": "View membership type, fees, and renewal dates", 
                "icon": "fa fa-id-card"
            },
            {
                "title": "Payment History",
                "description": "Review your payment records and invoices",
                "icon": "fa fa-credit-card"
            },
            {
                "title": "Chapter Information",
                "description": "View your chapter membership and activities",
                "icon": "fa fa-users"
            }
        ]
    })
    
    # Check if user is a volunteer and add Volunteer Portal
    user_roles = frappe.get_roles(frappe.session.user)
    if "Volunteer" in user_roles or frappe.db.exists("Volunteer", {"member": frappe.db.get_value("Member", {"email": frappe.session.user})}):
        enhanced_menu.append({
            "title": "Volunteer Portal",
            "route": "/volunteer/dashboard",
            "reference_doctype": None,
            "role": "Volunteer",
            "target": None,
            "submenu": [
                {
                    "title": "Volunteer Activities",
                    "description": "View your current and past volunteer assignments",
                    "icon": "fa fa-hands-helping"
                },
                {
                    "title": "Expense Claims",
                    "description": "Submit and track your volunteer expense claims",
                    "icon": "fa fa-receipt"
                },
                {
                    "title": "Team Information", 
                    "description": "View your team assignments and contacts",
                    "icon": "fa fa-sitemap"
                },
                {
                    "title": "Activity History",
                    "description": "Review your volunteer contribution history",
                    "icon": "fa fa-history"
                }
            ]
        })
    
    # Add Contact Us (custom item)
    enhanced_menu.append({
        "title": "Contact Us",
        "route": "/contact_request",
        "reference_doctype": None,
        "role": None,
        "target": None,
        "submenu": [
            {
                "title": "General Inquiry",
                "description": "Ask questions about our organization",
                "icon": "fa fa-question-circle"
            },
            {
                "title": "Membership Support",
                "description": "Get help with your membership",
                "icon": "fa fa-id-card"
            },
            {
                "title": "Technical Support",
                "description": "Report website or portal issues",
                "icon": "fa fa-cog"
            }
        ]
    })
    
    # Now add relevant items from Portal Settings
    member_relevant_items = [
        "Issues & Support", "Addresses"
    ]
    
    portal_settings = frappe.get_single("Portal Settings")
    
    for item in portal_settings.menu:
        if not item.enabled:
            continue
            
        # Skip items that are not relevant for members
        if item.title not in member_relevant_items:
            continue
            
        menu_item = {
            "title": item.title,
            "route": item.route,
            "reference_doctype": item.reference_doctype,
            "role": item.role,
            "target": getattr(item, 'target', None)
        }
        
        # Add submenu for Issues & Support
        if item.title in ["Issues", "Issues & Support"]:
            menu_item["submenu"] = [
                {
                    "title": "Report an Issue",
                    "description": "Submit a new issue or support request",
                    "icon": "fa fa-plus-circle"
                },
                {
                    "title": "My Support Tickets",
                    "description": "View your submitted issues and their status",
                    "icon": "fa fa-list"
                },
                {
                    "title": "Contact Support",
                    "description": "Get help with your membership or account",
                    "icon": "fa fa-envelope"
                }
            ]
            
        # Add submenu for Addresses
        elif item.title == "Addresses":
            menu_item["submenu"] = [
                {
                    "title": "My Addresses",
                    "description": "View and manage your saved addresses",
                    "icon": "fa fa-map-marker"
                },
                {
                    "title": "Update Address",
                    "description": "Change your primary mailing address",
                    "icon": "fa fa-edit"
                }
            ]
        
        enhanced_menu.append(menu_item)
    
    return enhanced_menu

@frappe.whitelist()
def get_user_portal_menu():
    """Get portal menu items for current user with submenus"""
    try:
        user = frappe.session.user
        user_roles = frappe.get_roles(user)
        
        enhanced_menu = get_enhanced_portal_menu_items()
        
        # Filter menu items based on user roles
        filtered_menu = []
        for item in enhanced_menu:
            # Check role requirements
            if item.get("role") and item["role"] not in user_roles:
                continue
            
            filtered_menu.append(item)
        
        return {
            "success": True,
            "user": user,
            "user_roles": user_roles,
            "menu_items": filtered_menu
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def generate_portal_menu_html():
    """Generate HTML for enhanced portal menu"""
    try:
        menu_data = get_user_portal_menu()
        if not menu_data["success"]:
            return menu_data
        
        menu_items = menu_data["menu_items"]
        
        html_parts = []
        html_parts.append('<div class="portal-menu-enhanced">')
        
        for item in menu_items:
            # Main menu item
            html_parts.append(f'''
                <div class="portal-menu-item">
                    <div class="main-menu-item">
                        <a href="{item['route']}" class="menu-link">
                            <h4>{item['title']}</h4>
                        </a>
                    </div>
            ''')
            
            # Submenu items if they exist
            if item.get("submenu"):
                html_parts.append('<div class="submenu-items">')
                for submenu in item["submenu"]:
                    icon = submenu.get("icon", "fa fa-circle")
                    html_parts.append(f'''
                        <div class="submenu-item">
                            <i class="{icon}"></i>
                            <div class="submenu-content">
                                <strong>{submenu['title']}</strong>
                                <p class="text-muted">{submenu['description']}</p>
                            </div>
                        </div>
                    ''')
                html_parts.append('</div>')
            
            html_parts.append('</div>')
        
        html_parts.append('</div>')
        
        # Add CSS
        css = '''
        <style>
        .portal-menu-enhanced {
            margin: 20px 0;
        }
        .portal-menu-item {
            margin-bottom: 30px;
            border: 1px solid #e7e7e7;
            border-radius: 5px;
            overflow: hidden;
        }
        .main-menu-item {
            background-color: #f8f9fa;
            padding: 15px 20px;
            border-bottom: 1px solid #e7e7e7;
        }
        .main-menu-item a {
            text-decoration: none;
            color: #333;
        }
        .main-menu-item h4 {
            margin: 0;
            color: #2c3e50;
        }
        .submenu-items {
            padding: 10px 0;
        }
        .submenu-item {
            display: flex;
            align-items: flex-start;
            padding: 10px 20px;
            border-bottom: 1px solid #f0f0f0;
        }
        .submenu-item:last-child {
            border-bottom: none;
        }
        .submenu-item i {
            margin-right: 15px;
            margin-top: 3px;
            color: #6c757d;
            min-width: 16px;
        }
        .submenu-content {
            flex: 1;
        }
        .submenu-content strong {
            display: block;
            color: #495057;
            margin-bottom: 3px;
        }
        .submenu-content p {
            margin: 0;
            font-size: 13px;
            line-height: 1.4;
        }
        .main-menu-item:hover {
            background-color: #e9ecef;
        }
        .submenu-item:hover {
            background-color: #f8f9fa;
        }
        </style>
        '''
        
        return {
            "success": True,
            "html": css + ''.join(html_parts)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def add_enhanced_sidebar_to_context(context):
    """Add enhanced sidebar items to any portal page context"""
    try:
        menu_data = get_user_portal_menu()
        if menu_data["success"]:
            context.sidebar_items = menu_data["menu_items"]
            context.show_sidebar = True
            context.parent_template = "templates/base_portal.html"
        else:
            context.sidebar_items = []
            context.show_sidebar = False
        
        return {"success": True}
        
    except Exception as e:
        frappe.log_error(f"Error adding enhanced sidebar to context: {str(e)}")
        return {"success": False, "error": str(e)}