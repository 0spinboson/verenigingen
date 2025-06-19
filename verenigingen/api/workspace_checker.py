"""
Workspace and Onboarding Checker
"""

import frappe
import os

@frappe.whitelist()
def check_workspace_and_onboarding():
    """Check workspace configuration and onboarding setup"""
    
    result = {
        "workspaces": [],
        "verenigingen_workspace": None,
        "onboarding_info": {},
        "onboarding_files": [],
        "issues": []
    }
    
    try:
        # Check available workspaces
        workspaces = frappe.get_all('Workspace', fields=['name', 'title', 'module'])
        result["workspaces"] = workspaces
        
        # Look for Verenigingen workspace
        verenigingen_workspace = None
        for ws in workspaces:
            if 'verenigingen' in ws.name.lower() or 'verenigingen' in (ws.title or "").lower():
                verenigingen_workspace = ws
                break
        
        if verenigingen_workspace:
            # Get detailed workspace info
            workspace_doc = frappe.get_doc('Workspace', verenigingen_workspace.name)
            result["verenigingen_workspace"] = {
                "name": workspace_doc.name,
                "title": workspace_doc.title,
                "module": workspace_doc.module,
                "public": workspace_doc.public,
                "links_count": len(workspace_doc.links),
                "shortcuts_count": len(workspace_doc.shortcuts),
                "links": [{"label": link.label, "link_to": link.link_to, "type": link.type} 
                         for link in workspace_doc.links if link.type == "Link"],
                "shortcuts": [{"label": shortcut.label, "link_to": shortcut.link_to, "type": shortcut.type}
                             for shortcut in workspace_doc.shortcuts]
            }
        else:
            result["issues"].append("No Verenigingen workspace found")
        
        # Check onboarding doctypes
        onboarding_doctypes = ['Module Onboarding', 'Onboarding Permission', 'Onboarding Step']
        
        for doctype in onboarding_doctypes:
            if frappe.db.exists('DocType', doctype):
                count = frappe.db.count(doctype)
                result["onboarding_info"][doctype] = {"exists": True, "count": count}
                
                if doctype == 'Module Onboarding':
                    # Check for Verenigingen-specific onboarding
                    verenigingen_onboarding = frappe.get_all(doctype, 
                        filters={'module': 'Verenigingen'}, 
                        fields=['name', 'title', 'is_complete'])
                    
                    result["onboarding_info"][doctype]["verenigingen_records"] = verenigingen_onboarding
                    
                    if not verenigingen_onboarding:
                        result["issues"].append("No Verenigingen Module Onboarding found")
            else:
                result["onboarding_info"][doctype] = {"exists": False, "count": 0}
                result["issues"].append(f"{doctype} doctype not found")
        
        # Check for onboarding files
        app_path = frappe.get_app_path('verenigingen')
        onboarding_path = os.path.join(app_path, 'onboarding')
        
        if os.path.exists(onboarding_path):
            files = os.listdir(onboarding_path)
            result["onboarding_files"] = files
        else:
            result["issues"].append("No onboarding directory found in app")
            
        return result
        
    except Exception as e:
        result["error"] = str(e)
        return result


@frappe.whitelist() 
def list_workspace_contents():
    """List all workspace contents to see what's available"""
    
    workspaces = frappe.get_all('Workspace', fields=['name', 'title', 'module'])
    result = []
    
    for ws_info in workspaces:
        try:
            ws_doc = frappe.get_doc('Workspace', ws_info.name)
            
            workspace_data = {
                "name": ws_doc.name,
                "title": ws_doc.title, 
                "module": ws_doc.module,
                "public": ws_doc.public,
                "links": [],
                "shortcuts": []
            }
            
            # Get links
            for link in ws_doc.links:
                if link.type == "Link":
                    workspace_data["links"].append({
                        "label": link.label,
                        "link_to": link.link_to,
                        "link_type": link.link_type
                    })
            
            # Get shortcuts
            for shortcut in ws_doc.shortcuts:
                workspace_data["shortcuts"].append({
                    "label": shortcut.label,
                    "link_to": shortcut.link_to,
                    "type": shortcut.type
                })
            
            result.append(workspace_data)
            
        except Exception as e:
            result.append({
                "name": ws_info.name,
                "error": str(e)
            })
    
    return result


@frappe.whitelist()
def check_onboarding_access():
    """Check how to access onboarding features"""
    
    result = {
        "ways_to_access": [],
        "available_onboarding": [],
        "issues": []
    }
    
    # Check if Module Onboarding exists
    if frappe.db.exists('DocType', 'Module Onboarding'):
        all_onboarding = frappe.get_all('Module Onboarding', 
                                       fields=['name', 'title', 'module', 'is_complete'])
        result["available_onboarding"] = all_onboarding
        
        # Check if Verenigingen onboarding exists
        verenigingen_onboarding = [ob for ob in all_onboarding if ob.module == 'Verenigingen']
        
        if verenigingen_onboarding:
            result["ways_to_access"].append({
                "method": "Direct URL",
                "url": f"/app/module-onboarding",
                "description": "Go directly to Module Onboarding list"
            })
            
            for ob in verenigingen_onboarding:
                result["ways_to_access"].append({
                    "method": "Direct Onboarding",
                    "url": f"/app/module-onboarding/{ob.name}",
                    "description": f"Access {ob.title} directly"
                })
        else:
            result["issues"].append("No Verenigingen Module Onboarding found")
    
    # Check workspace access
    verenigingen_workspaces = frappe.get_all('Workspace', 
                                           filters=[
                                               ['name', 'like', '%verenigingen%']
                                           ],
                                           fields=['name', 'title'])
    
    if verenigingen_workspaces:
        for ws in verenigingen_workspaces:
            result["ways_to_access"].append({
                "method": "Workspace",
                "url": f"/app/{ws.name}",
                "description": f"Access via {ws.title} workspace"
            })
    
    # Check if onboarding should be in workspace
    if frappe.db.exists('DocType', 'Module Onboarding'):
        result["ways_to_access"].append({
            "method": "Search",
            "url": "/app/List/Module%20Onboarding",
            "description": "Search for 'Module Onboarding' in the search bar"
        })
    
    return result