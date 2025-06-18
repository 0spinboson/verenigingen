# Chapter Membership History Manager - Centralized chapter membership tracking
import frappe
from frappe import _
from frappe.utils import today, now
from typing import Dict, Optional


class ChapterMembershipHistoryManager:
    """
    Centralized manager for chapter membership history tracking.
    
    Handles chapter membership history for both regular members and board members
    in a consistent way, similar to volunteer assignment history.
    """
    
    @staticmethod
    def add_membership_history(member_id: str, chapter_name: str, 
                              assignment_type: str, start_date: str,
                              reason: str = None) -> bool:
        """
        Add active membership to member history when starting a chapter relationship
        
        Args:
            member_id: Member ID
            chapter_name: Chapter name
            assignment_type: Type of assignment ("Member" or "Board Member")
            start_date: Start date of membership
            reason: Reason for assignment (optional)
            
        Returns:
            bool: Success status
        """
        try:
            member = frappe.get_doc("Member", member_id)

            # Check if this exact membership already exists as active
            for membership in member.chapter_membership_history or []:
                if (membership.chapter_name == chapter_name and 
                    membership.assignment_type == assignment_type and
                    membership.status == "Active" and
                    str(membership.start_date) == str(start_date)):
                    print(f"Membership already exists in history for member {member_id}")
                    return True  # This exact membership already exists

            # Add new active membership
            member.append("chapter_membership_history", {
                "chapter_name": chapter_name,
                "assignment_type": assignment_type,
                "start_date": start_date,
                "status": "Active",
                "reason": reason or f"Assigned to {chapter_name} as {assignment_type}"
            })

            member.save(ignore_permissions=True)

            print(f"Added membership history for member {member_id}: {assignment_type} at {chapter_name}")
            return True

        except Exception as e:
            print(f"Error adding membership history for member {member_id}: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    @staticmethod
    def complete_membership_history(member_id: str, chapter_name: str,
                                  assignment_type: str, start_date: str, 
                                  end_date: str, reason: str = None) -> bool:
        """
        Complete member chapter membership history when ending a relationship
        
        Args:
            member_id: Member ID
            chapter_name: Chapter name
            assignment_type: Type of assignment ("Member" or "Board Member")
            start_date: Start date of original membership
            end_date: End date of membership
            reason: Reason for ending (optional)
            
        Returns:
            bool: Success status
        """
        try:
            member = frappe.get_doc("Member", member_id)

            # Look for the specific membership that matches all criteria
            target_membership = None
            for membership in member.chapter_membership_history or []:
                if (membership.chapter_name == chapter_name and 
                    membership.assignment_type == assignment_type and
                    str(membership.start_date) == str(start_date) and
                    membership.status == "Active"):
                    target_membership = membership
                    break

            if target_membership:
                # Update the specific membership to completed
                target_membership.end_date = end_date
                target_membership.status = "Completed"
                if reason:
                    target_membership.reason = reason
                
                frappe.log_error(
                    f"Updated specific membership history for member {member_id}: {assignment_type} at {chapter_name}",
                    "Chapter Membership History Manager"
                )
            else:
                # If we can't find the exact membership, look for any active one
                fallback_membership = None
                for membership in member.chapter_membership_history or []:
                    if (membership.chapter_name == chapter_name and 
                        membership.assignment_type == assignment_type and
                        membership.status == "Active"):
                        fallback_membership = membership
                        break

                if fallback_membership:
                    fallback_membership.end_date = end_date
                    fallback_membership.status = "Completed"
                    if reason:
                        fallback_membership.reason = reason
                    
                    frappe.log_error(
                        f"Updated fallback membership history for member {member_id}: {assignment_type} at {chapter_name}",
                        "Chapter Membership History Manager"
                    )
                else:
                    # Create a new completed membership if nothing exists
                    member.append("chapter_membership_history", {
                        "chapter_name": chapter_name,
                        "assignment_type": assignment_type,
                        "start_date": start_date,
                        "end_date": end_date,
                        "status": "Completed",
                        "reason": reason or f"Left {chapter_name} as {assignment_type}"
                    })
                    
                    frappe.log_error(
                        f"Created new completed membership history for member {member_id}: {assignment_type} at {chapter_name}",
                        "Chapter Membership History Manager"
                    )

            member.save(ignore_permissions=True)
            return True

        except Exception as e:
            frappe.log_error(
                f"Error completing membership history for member {member_id}: {str(e)}",
                "Chapter Membership History Manager"
            )
            return False

    @staticmethod
    def get_active_memberships(member_id: str, assignment_type: str = None,
                             chapter_name: str = None) -> list:
        """
        Get active chapter memberships for a member
        
        Args:
            member_id: Member ID
            assignment_type: Filter by assignment type (optional)
            chapter_name: Filter by chapter name (optional)
            
        Returns:
            list: List of active memberships
        """
        try:
            member = frappe.get_doc("Member", member_id)
            active_memberships = []
            
            for membership in member.chapter_membership_history or []:
                if membership.status == "Active":
                    if assignment_type and membership.assignment_type != assignment_type:
                        continue
                    if chapter_name and membership.chapter_name != chapter_name:
                        continue
                    active_memberships.append(membership)
                    
            return active_memberships
            
        except Exception as e:
            frappe.log_error(
                f"Error getting active memberships for member {member_id}: {str(e)}",
                "Chapter Membership History Manager"
            )
            return []

    @staticmethod
    def remove_membership_history(member_id: str, chapter_name: str,
                                assignment_type: str, start_date: str) -> bool:
        """
        Remove membership history entry (for cases where membership is cancelled before completion)
        
        Args:
            member_id: Member ID
            chapter_name: Chapter name
            assignment_type: Type of assignment
            start_date: Start date of original membership
            
        Returns:
            bool: Success status
        """
        try:
            member = frappe.get_doc("Member", member_id)

            # Find and remove the specific membership
            membership_to_remove = None
            for membership in member.chapter_membership_history or []:
                if (membership.chapter_name == chapter_name and 
                    membership.assignment_type == assignment_type and
                    str(membership.start_date) == str(start_date) and
                    membership.status == "Active"):
                    membership_to_remove = membership
                    break

            if membership_to_remove:
                member.chapter_membership_history.remove(membership_to_remove)
                member.save(ignore_permissions=True)
                
                frappe.log_error(
                    f"Removed membership history for member {member_id}: {assignment_type} at {chapter_name}",
                    "Chapter Membership History Manager"
                )
                return True
            else:
                frappe.log_error(
                    f"Membership to remove not found for member {member_id}: {assignment_type} at {chapter_name}",
                    "Chapter Membership History Manager"
                )
                return False

        except Exception as e:
            frappe.log_error(
                f"Error removing membership history for member {member_id}: {str(e)}",
                "Chapter Membership History Manager"
            )
            return False

    @staticmethod
    def terminate_membership_history(member_id: str, chapter_name: str,
                                   assignment_type: str, end_date: str, 
                                   reason: str) -> bool:
        """
        Terminate membership history (different from completion - implies involuntary end)
        
        Args:
            member_id: Member ID
            chapter_name: Chapter name
            assignment_type: Type of assignment
            end_date: End date of membership
            reason: Reason for termination
            
        Returns:
            bool: Success status
        """
        try:
            member = frappe.get_doc("Member", member_id)

            # Find the active membership to terminate
            target_membership = None
            for membership in member.chapter_membership_history or []:
                if (membership.chapter_name == chapter_name and 
                    membership.assignment_type == assignment_type and
                    membership.status == "Active"):
                    target_membership = membership
                    break

            if target_membership:
                target_membership.end_date = end_date
                target_membership.status = "Terminated"
                target_membership.reason = reason
                
                member.save(ignore_permissions=True)
                
                frappe.log_error(
                    f"Terminated membership history for member {member_id}: {assignment_type} at {chapter_name}",
                    "Chapter Membership History Manager"
                )
                return True
            else:
                frappe.log_error(
                    f"No active membership found to terminate for member {member_id}: {assignment_type} at {chapter_name}",
                    "Chapter Membership History Manager"
                )
                return False

        except Exception as e:
            frappe.log_error(
                f"Error terminating membership history for member {member_id}: {str(e)}",
                "Chapter Membership History Manager"
            )
            return False

    @staticmethod
    def get_membership_history_summary(member_id: str) -> Dict:
        """
        Get summary of member's chapter membership history
        
        Args:
            member_id: Member ID
            
        Returns:
            Dict: Summary information
        """
        try:
            member = frappe.get_doc("Member", member_id)
            
            total_memberships = len(member.chapter_membership_history or [])
            active_memberships = len([m for m in member.chapter_membership_history or [] if m.status == "Active"])
            completed_memberships = len([m for m in member.chapter_membership_history or [] if m.status == "Completed"])
            terminated_memberships = len([m for m in member.chapter_membership_history or [] if m.status == "Terminated"])
            
            # Get chapters the member has been associated with
            chapters = list(set([m.chapter_name for m in member.chapter_membership_history or []]))
            
            return {
                "total_memberships": total_memberships,
                "active_memberships": active_memberships,
                "completed_memberships": completed_memberships,
                "terminated_memberships": terminated_memberships,
                "chapters_associated": chapters,
                "last_updated": now()
            }
            
        except Exception as e:
            frappe.log_error(
                f"Error getting membership history summary for member {member_id}: {str(e)}",
                "Chapter Membership History Manager"
            )
            return {
                "total_memberships": 0,
                "active_memberships": 0,
                "completed_memberships": 0,
                "terminated_memberships": 0,
                "chapters_associated": [],
                "error": str(e)
            }