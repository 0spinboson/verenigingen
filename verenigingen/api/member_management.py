"""
Member management API endpoints
"""
import frappe
from frappe import _

@frappe.whitelist()
def assign_member_to_chapter(member_name, chapter_name):
    """Assign a member to a specific chapter using centralized manager"""
    try:
        # Validate inputs
        if not member_name or not chapter_name:
            return {
                "success": False,
                "error": "Member name and chapter name are required"
            }
        
        # Check permissions
        if not can_assign_member_to_chapter(member_name, chapter_name):
            return {
                "success": False,
                "error": "You don't have permission to assign members to this chapter"
            }
        
        # Use centralized chapter membership manager for proper history tracking
        from verenigingen.utils.chapter_membership_manager import ChapterMembershipManager
        
        result = ChapterMembershipManager.assign_member_to_chapter(
            member_id=member_name,
            chapter_name=chapter_name,
            reason="Assigned via admin interface",
            assigned_by=frappe.session.user
        )
        
        # Adapt result format for backward compatibility
        if result.get('success'):
            return {
                "success": True,
                "message": f"Member {member_name} has been assigned to {chapter_name}",
                "new_chapter": chapter_name
            }
        else:
            return result
        
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
    admin_roles = ["System Manager", "Verenigingen Administrator", "Membership Manager"]
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
        
        # Get members who are not in any Chapter Member records
        members_with_chapters = frappe.get_all(
            "Chapter Member",
            filters={"enabled": 1},
            fields=["member"],
            distinct=True
        )
        
        excluded_members = [m.member for m in members_with_chapters]
        
        # Get members without chapter
        member_filters = {}
        if excluded_members:
            member_filters["name"] = ["not in", excluded_members]
            
        members = frappe.get_all(
            "Member",
            filters=member_filters,
            fields=[
                "name", "full_name", "email", "status", "creation"
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
    admin_roles = ["System Manager", "Verenigingen Administrator", "Membership Manager"]
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

def add_member_to_chapter_roster(member_name, new_chapter):
    """Add member to chapter's member roster using centralized manager"""
    try:
        if new_chapter:
            # Use centralized chapter membership manager for proper history tracking
            from verenigingen.utils.chapter_membership_manager import ChapterMembershipManager
            
            result = ChapterMembershipManager.assign_member_to_chapter(
                member_id=member_name,
                chapter_name=new_chapter,
                reason="Administrative assignment",
                assigned_by=frappe.session.user
            )
            
            if not result.get('success'):
                frappe.log_error(f"Failed to add member {member_name} to chapter {new_chapter}: {result.get('error')}", "Chapter Roster Update Error")
        
    except Exception as e:
        frappe.log_error(f"Error updating chapter roster: {str(e)}", "Chapter Roster Update Error")