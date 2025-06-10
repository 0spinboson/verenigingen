"""
Member management API endpoints
"""
import frappe
from frappe import _

@frappe.whitelist()
def assign_member_to_chapter(member_name, chapter_name):
    """Assign a member to a specific chapter"""
    try:
        # Validate inputs
        if not member_name or not chapter_name:
            return {
                "success": False,
                "error": "Member name and chapter name are required"
            }
        
        # Check if member exists
        if not frappe.db.exists("Member", member_name):
            return {
                "success": False,
                "error": f"Member {member_name} not found"
            }
        
        # Check if chapter exists
        if not frappe.db.exists("Chapter", chapter_name):
            return {
                "success": False,
                "error": f"Chapter {chapter_name} not found"
            }
        
        # Check permissions
        if not can_assign_member_to_chapter(member_name, chapter_name):
            return {
                "success": False,
                "error": "You don't have permission to assign members to this chapter"
            }
        
        # Get current chapter to check if change is needed
        old_chapter = frappe.db.get_value("Member", member_name, "primary_chapter")
        
        # Skip if already assigned to this chapter
        if old_chapter == chapter_name:
            return {
                "success": True,
                "message": f"Member {member_name} is already assigned to {chapter_name}",
                "old_chapter": old_chapter,
                "new_chapter": chapter_name
            }
        
        # Use direct database update to avoid document modification conflicts
        frappe.db.set_value("Member", member_name, {
            "primary_chapter": chapter_name,
            "chapter_change_reason": "Assigned via admin interface",
            "chapter_assigned_date": frappe.utils.now(),
            "chapter_assigned_by": frappe.session.user
        })
        
        # Add member to chapter's member roster
        add_member_to_chapter_roster(member_name, chapter_name, old_chapter)
        
        # Commit the transaction
        frappe.db.commit()
        
        # Log the change
        frappe.log_error(
            f"Member {member_name} chapter assignment changed from '{old_chapter}' to '{chapter_name}' by {frappe.session.user}",
            "Member Chapter Assignment"
        )
        
        return {
            "success": True,
            "message": f"Member {member_name} has been assigned to {chapter_name}",
            "old_chapter": old_chapter,
            "new_chapter": chapter_name
        }
        
    except Exception as e:
        frappe.log_error(f"Error assigning member to chapter: {str(e)}", "Member Assignment Error")
        return {
            "success": False,
            "error": f"Failed to assign member to chapter: {str(e)}"
        }

def can_assign_member_to_chapter(member_name, chapter_name):
    """Check if current user can assign a member to a specific chapter"""
    user = frappe.session.user
    
    # System managers and Association/Membership managers can assign anyone
    admin_roles = ["System Manager", "Verenigingen Manager", "Membership Manager"]
    if any(role in frappe.get_roles(user) for role in admin_roles):
        return True
    
    # Get user's member record
    user_member = frappe.db.get_value("Member", {"user": user}, "name")
    if not user_member:
        return False
    
    # Check if user has admin/membership permissions in the target chapter
    try:
        volunteer_records = frappe.get_all("Volunteer", filters={"member": user_member}, fields=["name"])
        
        for volunteer_record in volunteer_records:
            board_positions = frappe.get_all(
                "Chapter Board Member",
                filters={
                    "parent": chapter_name,
                    "volunteer": volunteer_record.name,
                    "is_active": 1
                },
                fields=["chapter_role"]
            )
            
            for position in board_positions:
                try:
                    role_doc = frappe.get_doc("Chapter Role", position.chapter_role)
                    if role_doc.permissions_level in ["Admin", "Membership"]:
                        return True
                except Exception:
                    continue
        
        # Check if user has national board access
        try:
            settings = frappe.get_single("Verenigingen Settings")
            if hasattr(settings, 'national_board_chapter') and settings.national_board_chapter:
                national_board_positions = frappe.get_all(
                    "Chapter Board Member",
                    filters={
                        "parent": settings.national_board_chapter,
                        "volunteer": [v.name for v in volunteer_records],
                        "is_active": 1
                    },
                    fields=["chapter_role"]
                )
                
                for position in national_board_positions:
                    try:
                        role_doc = frappe.get_doc("Chapter Role", position.chapter_role)
                        if role_doc.permissions_level in ["Admin", "Membership"]:
                            return True
                    except Exception:
                        continue
        except Exception:
            pass
            
    except Exception:
        pass
    
    return False

@frappe.whitelist()
def get_members_without_chapter():
    """Get list of members without chapter assignment"""
    try:
        # Check permissions
        if not can_view_members_without_chapter():
            return {
                "success": False,
                "error": "You don't have permission to view this data"
            }
        
        # Get members without chapter
        members = frappe.get_all(
            "Member",
            filters={
                "primary_chapter": ["in", ["", None]]
            },
            fields=[
                "name", "full_name", "email", "city", "postal_code", 
                "country", "status", "creation"
            ],
            order_by="creation desc"
        )
        
        return {
            "success": True,
            "members": members,
            "count": len(members)
        }
        
    except Exception as e:
        frappe.log_error(f"Error getting members without chapter: {str(e)}", "Members Without Chapter Error")
        return {
            "success": False,
            "error": f"Failed to get members: {str(e)}"
        }

def can_view_members_without_chapter():
    """Check if current user can view members without chapter"""
    user = frappe.session.user
    
    # System managers and Association/Membership managers can view
    admin_roles = ["System Manager", "Verenigingen Manager", "Membership Manager"]
    if any(role in frappe.get_roles(user) for role in admin_roles):
        return True
    
    # Chapter board members with admin/membership permissions can view
    user_member = frappe.db.get_value("Member", {"user": user}, "name")
    if not user_member:
        return False
    
    try:
        volunteer_records = frappe.get_all("Volunteer", filters={"member": user_member}, fields=["name"])
        
        for volunteer_record in volunteer_records:
            board_positions = frappe.get_all(
                "Chapter Board Member",
                filters={
                    "volunteer": volunteer_record.name,
                    "is_active": 1
                },
                fields=["chapter_role"]
            )
            
            for position in board_positions:
                try:
                    role_doc = frappe.get_doc("Chapter Role", position.chapter_role)
                    if role_doc.permissions_level in ["Admin", "Membership"]:
                        return True
                except Exception:
                    continue
    except Exception:
        pass
    
    return False

@frappe.whitelist()
def bulk_assign_members_to_chapters(assignments):
    """Bulk assign multiple members to chapters
    
    Args:
        assignments: List of dicts with member_name and chapter_name
    """
    try:
        if not assignments:
            return {
                "success": False,
                "error": "No assignments provided"
            }
        
        results = []
        success_count = 0
        error_count = 0
        
        for assignment in assignments:
            member_name = assignment.get("member_name")
            chapter_name = assignment.get("chapter_name")
            
            result = assign_member_to_chapter(member_name, chapter_name)
            results.append({
                "member_name": member_name,
                "chapter_name": chapter_name,
                "result": result
            })
            
            if result.get("success"):
                success_count += 1
            else:
                error_count += 1
        
        return {
            "success": True,
            "message": f"Processed {len(assignments)} assignments: {success_count} successful, {error_count} failed",
            "results": results,
            "success_count": success_count,
            "error_count": error_count
        }
        
    except Exception as e:
        frappe.log_error(f"Error in bulk assignment: {str(e)}", "Bulk Assignment Error")
        return {
            "success": False,
            "error": f"Failed to process bulk assignments: {str(e)}"
        }

def add_member_to_chapter_roster(member_name, new_chapter, old_chapter=None):
    """Add member to chapter's member roster and remove from old chapter if needed"""
    try:
        # Remove from old chapter roster if exists
        if old_chapter and old_chapter != new_chapter:
            old_chapter_doc = frappe.get_doc("Chapter", old_chapter)
            # Find and remove member from old chapter
            for i, member_row in enumerate(old_chapter_doc.members):
                if member_row.member == member_name:
                    old_chapter_doc.members.pop(i)
                    break
            old_chapter_doc.save()
        
        # Add to new chapter roster
        if new_chapter:
            # Check if member already exists in roster
            existing_member = frappe.db.exists("Chapter Member", {
                "parent": new_chapter,
                "member": member_name
            })
            
            if not existing_member:
                # Get member's full name for the roster
                member_full_name = frappe.db.get_value("Member", member_name, "full_name")
                
                # Add member to chapter roster
                new_chapter_doc = frappe.get_doc("Chapter", new_chapter)
                new_chapter_doc.append("members", {
                    "member": member_name,
                    "member_name": member_full_name,
                    "enabled": 1
                })
                new_chapter_doc.save()
            else:
                # Member already exists, just ensure they're enabled
                frappe.db.set_value("Chapter Member", existing_member, "enabled", 1)
        
    except Exception as e:
        frappe.log_error(f"Error updating chapter roster: {str(e)}", "Chapter Roster Update Error")