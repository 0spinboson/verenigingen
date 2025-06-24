"""
Test utilities for Chapter Membership History implementation
"""
import frappe
from frappe.utils import today
from verenigingen.utils.chapter_membership_history_manager import ChapterMembershipHistoryManager

@frappe.whitelist()
def test_chapter_membership_history_for_member(member_id):
    """Test function to check chapter membership history for a specific member"""
    
    try:
        # Get the member
        member = frappe.get_doc("Member", member_id)
        
        result = {
            "member_id": member_id,
            "member_name": getattr(member, 'full_name', ''),
            "current_chapter_display": getattr(member, 'current_chapter_display', ''),
            "history_entries": []
        }
        
        # Check current chapter membership history
        if member.chapter_membership_history:
            for history in member.chapter_membership_history:
                result["history_entries"].append({
                    "chapter_name": history.chapter_name,
                    "assignment_type": history.assignment_type,
                    "status": history.status,
                    "start_date": str(history.start_date),
                    "end_date": str(history.end_date) if hasattr(history, 'end_date') and history.end_date else None,
                    "reason": history.reason
                })
        
        result["total_history_entries"] = len(result["history_entries"])
        result["success"] = True
        
        frappe.logger().info(f"Chapter membership history check for {member_id}: {result['total_history_entries']} entries")
        
        return result
        
    except Exception as e:
        frappe.log_error(f"Error checking chapter membership history for {member_id}: {str(e)}", "Chapter History Test")
        return {
            "success": False,
            "error": str(e),
            "member_id": member_id
        }

@frappe.whitelist()
def create_test_pending_membership(member_id, chapter_name):
    """Create a test pending membership to verify history tracking"""
    
    try:
        # Test creating a pending membership history
        result = ChapterMembershipHistoryManager.add_membership_history(
            member_id=member_id,
            chapter_name=chapter_name,
            assignment_type="Member",
            start_date=today(),
            status="Pending",
            reason=f"Test - Applied for membership in {chapter_name} chapter"
        )
        
        frappe.logger().info(f"Created test pending membership for {member_id} in {chapter_name}: {result}")
        
        return {
            "success": True,
            "member_id": member_id,
            "chapter_name": chapter_name,
            "history_created": result
        }
        
    except Exception as e:
        frappe.log_error(f"Error creating test pending membership for {member_id}: {str(e)}", "Chapter History Test")
        return {
            "success": False,
            "error": str(e),
            "member_id": member_id,
            "chapter_name": chapter_name
        }