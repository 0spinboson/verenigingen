# Utility to populate chapter membership history for existing members
import frappe
from frappe import _
from frappe.utils import today
from verenigingen.utils.chapter_membership_history_manager import ChapterMembershipHistoryManager


@frappe.whitelist()
def populate_existing_member_chapter_history():
    """
    Populate chapter membership history for existing members who have current chapter memberships
    but no history records yet.
    
    This is a one-time migration utility.
    """
    try:
        # Get all current chapter members
        chapter_members = frappe.get_all(
            "Chapter Member",
            filters={"enabled": 1},
            fields=["member", "parent", "chapter_join_date"]
        )
        
        processed_count = 0
        error_count = 0
        
        for chapter_member in chapter_members:
            try:
                member_id = chapter_member.member
                chapter_name = chapter_member.parent
                start_date = chapter_member.chapter_join_date or today()
                
                # Check if member already has history for this chapter
                member_doc = frappe.get_doc("Member", member_id)
                existing_history = [
                    h for h in (member_doc.chapter_membership_history or [])
                    if h.chapter_name == chapter_name and h.assignment_type == "Member" and h.status == "Active"
                ]
                
                if not existing_history:
                    # Add membership history
                    success = ChapterMembershipHistoryManager.add_membership_history(
                        member_id=member_id,
                        chapter_name=chapter_name,
                        assignment_type="Member",
                        start_date=start_date,
                        reason=f"Migrated existing membership to {chapter_name}"
                    )
                    
                    if success:
                        processed_count += 1
                        print(f"Added history for member {member_id} in chapter {chapter_name}")
                    else:
                        error_count += 1
                        print(f"Failed to add history for member {member_id} in chapter {chapter_name}")
                else:
                    print(f"History already exists for member {member_id} in chapter {chapter_name}")
                    
            except Exception as e:
                error_count += 1
                print(f"Error processing member {chapter_member.member}: {str(e)}")
        
        # Also populate board member history
        board_members = frappe.get_all(
            "Chapter Board Member",
            filters={"is_active": 1},
            fields=["volunteer", "parent", "chapter_role", "from_date"]
        )
        
        for board_member in board_members:
            try:
                volunteer_id = board_member.volunteer
                chapter_name = board_member.parent
                start_date = board_member.from_date or today()
                
                # Get the associated member
                volunteer_doc = frappe.get_doc("Volunteer", volunteer_id)
                if not volunteer_doc.member:
                    continue
                
                member_id = volunteer_doc.member
                
                # Check if member already has board history for this chapter
                member_doc = frappe.get_doc("Member", member_id)
                existing_history = [
                    h for h in (member_doc.chapter_membership_history or [])
                    if h.chapter_name == chapter_name and h.assignment_type == "Board Member" and h.status == "Active"
                ]
                
                if not existing_history:
                    # Add board membership history
                    success = ChapterMembershipHistoryManager.add_membership_history(
                        member_id=member_id,
                        chapter_name=chapter_name,
                        assignment_type="Board Member",
                        start_date=start_date,
                        reason=f"Migrated existing {board_member.chapter_role} position in {chapter_name}"
                    )
                    
                    if success:
                        processed_count += 1
                        print(f"Added board history for member {member_id} in chapter {chapter_name}")
                    else:
                        error_count += 1
                        print(f"Failed to add board history for member {member_id} in chapter {chapter_name}")
                        
            except Exception as e:
                error_count += 1
                print(f"Error processing board member {board_member.volunteer}: {str(e)}")
        
        return {
            "success": True,
            "processed_count": processed_count,
            "error_count": error_count,
            "message": f"Processed {processed_count} records with {error_count} errors"
        }
        
    except Exception as e:
        frappe.log_error(f"Error in populate_existing_member_chapter_history: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def get_member_chapter_history_summary(member_id):
    """
    Get a summary of a member's chapter membership history
    """
    try:
        return ChapterMembershipHistoryManager.get_membership_history_summary(member_id)
    except Exception as e:
        frappe.log_error(f"Error getting chapter history summary for {member_id}: {str(e)}")
        return {"error": str(e)}