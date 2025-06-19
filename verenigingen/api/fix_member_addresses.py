"""
Fix member address linking issues
"""

import frappe

@frappe.whitelist()
def fix_member_address_links():
    """Fix missing Dynamic Link entries for member addresses"""
    try:
        # Find all members with primary_address but missing Dynamic Links
        members_with_addresses = frappe.get_all("Member", 
                                               filters={"primary_address": ["!=", ""]},
                                               fields=["name", "primary_address"])
        
        fixed_count = 0
        errors = []
        
        for member in members_with_addresses:
            try:
                # Check if Dynamic Link already exists
                existing_link = frappe.get_all("Dynamic Link", {
                    "parent": member.primary_address,
                    "parenttype": "Address",
                    "link_doctype": "Member",
                    "link_name": member.name
                })
                
                if not existing_link:
                    # Get the address document
                    address_doc = frappe.get_doc("Address", member.primary_address)
                    
                    # Add the Dynamic Link
                    address_doc.append("links", {
                        "link_doctype": "Member",
                        "link_name": member.name
                    })
                    
                    # Save without running validation/hooks to avoid recursion
                    address_doc.save(ignore_permissions=True)
                    fixed_count += 1
                    
            except Exception as e:
                errors.append(f"Error fixing {member.name}: {str(e)}")
        
        frappe.db.commit()
        
        return {
            "success": True,
            "members_checked": len(members_with_addresses),
            "links_fixed": fixed_count,
            "errors": errors
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def check_member_address_status(member_name):
    """Check address linking status for a specific member"""
    try:
        member = frappe.get_doc("Member", member_name)
        
        result = {
            "member_name": member.name,
            "primary_address": member.primary_address,
            "addresses": []
        }
        
        if member.primary_address:
            # Check if address exists
            try:
                address_doc = frappe.get_doc("Address", member.primary_address)
                
                # Check Dynamic Links
                dynamic_links = frappe.get_all("Dynamic Link", {
                    "parent": member.primary_address,
                    "parenttype": "Address"
                }, ["link_doctype", "link_name"])
                
                result["addresses"].append({
                    "name": address_doc.name,
                    "address_title": address_doc.address_title,
                    "exists": True,
                    "dynamic_links": dynamic_links,
                    "has_member_link": any(link.link_doctype == "Member" and link.link_name == member.name 
                                         for link in dynamic_links)
                })
                
            except frappe.DoesNotExistError:
                result["addresses"].append({
                    "name": member.primary_address,
                    "exists": False,
                    "error": "Address document not found"
                })
        
        return {
            "success": True,
            "data": result
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }