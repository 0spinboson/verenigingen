"""
Workspace cleanup utility to find and fix broken links
"""

import frappe

@frappe.whitelist()
def check_workspace_links():
    """Check all workspace links for broken references"""
    
    try:
        workspace = frappe.get_doc('Workspace', 'Verenigingen')
        
        broken_links = []
        valid_links = []
        
        for i, link in enumerate(workspace.links):
            if link.type == "Link" and link.link_to:
                # Check if the target exists
                target_exists = False
                
                if link.link_type == "DocType":
                    target_exists = frappe.db.exists('DocType', link.link_to)
                elif link.link_type == "Report":
                    target_exists = frappe.db.exists('Report', link.link_to)
                elif link.link_type == "Page":
                    target_exists = frappe.db.exists('Page', link.link_to)
                
                link_info = {
                    "index": i,
                    "label": link.label,
                    "link_to": link.link_to,
                    "link_type": link.link_type,
                    "exists": target_exists
                }
                
                if target_exists:
                    valid_links.append(link_info)
                else:
                    broken_links.append(link_info)
        
        return {
            "success": True,
            "workspace": "Verenigingen",
            "total_links": len(workspace.links),
            "valid_links": valid_links,
            "broken_links": broken_links,
            "broken_count": len(broken_links)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# Governance Compliance Report was removed - function deleted


@frappe.whitelist()
def remove_broken_links():
    """Remove broken links from workspace"""
    
    try:
        workspace = frappe.get_doc('Workspace', 'Verenigingen')
        
        # Get broken links first
        check_result = check_workspace_links()
        if not check_result["success"]:
            return check_result
        
        broken_links = check_result["broken_links"]
        
        if not broken_links:
            return {
                "success": True,
                "message": "No broken links found",
                "removed_count": 0
            }
        
        # Remove broken links (in reverse order to maintain indices)
        removed_links = []
        
        for link_info in reversed(broken_links):
            removed_link = workspace.links.pop(link_info["index"])
            removed_links.append({
                "label": removed_link.label,
                "link_to": removed_link.link_to,
                "link_type": removed_link.link_type
            })
        
        workspace.save()
        frappe.db.commit()
        
        return {
            "success": True,
            "message": f"Removed {len(removed_links)} broken links from workspace",
            "removed_count": len(removed_links),
            "removed_links": removed_links
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def list_all_reports():
    """List all available reports to see what exists"""
    
    try:
        # Get all reports
        all_reports = frappe.get_all('Report', 
                                   fields=['name', 'report_name', 'report_type', 'module'],
                                   order_by='module, name')
        
        # Filter Verenigingen reports
        verenigingen_reports = [r for r in all_reports if r.module == 'Verenigingen']
        
        return {
            "success": True,
            "all_reports_count": len(all_reports),
            "verenigingen_reports": verenigingen_reports,
            "verenigingen_count": len(verenigingen_reports)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }