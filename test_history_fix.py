#!/usr/bin/env python3

import frappe
from verenigingen.utils.chapter_membership_history_manager import ChapterMembershipHistoryManager

@frappe.whitelist()
def test_chapter_membership_history():
    """Test function to check chapter membership history implementation"""
    
    member_id = "Assoc-Member-2025-06-0136"
    
    try:
        # Get the member
        member = frappe.get_doc("Member", member_id)
        
        print(f"Testing member: {member_id}")
        print(f"Member name: {member.full_name}")
        print(f"Current chapter display: {getattr(member, 'current_chapter_display', 'None')}")
        
        # Check current chapter membership history
        history_count = len(member.chapter_membership_history) if member.chapter_membership_history else 0
        print(f"Current history entries: {history_count}")
        
        if member.chapter_membership_history:
            for i, history in enumerate(member.chapter_membership_history):
                print(f"  {i+1}. Chapter: {history.chapter_name}")
                print(f"      Type: {history.assignment_type}")
                print(f"      Status: {history.status}")
                print(f"      Start Date: {history.start_date}")
                print(f"      Reason: {history.reason}")
                print()
        
        # Test creating a new pending membership history
        test_result = ChapterMembershipHistoryManager.add_membership_history(
            member_id=member_id,
            chapter_name="Rotterdam",
            assignment_type="Member", 
            start_date=frappe.utils.today(),
            status="Pending",
            reason="Test - Applied for membership in Rotterdam chapter"
        )
        
        print(f"Test add history result: {test_result}")
        
        # Check history after adding
        member.reload()
        new_history_count = len(member.chapter_membership_history) if member.chapter_membership_history else 0
        print(f"History entries after test: {new_history_count}")
        
        return {
            "success": True,
            "member_id": member_id,
            "initial_history_count": history_count,
            "final_history_count": new_history_count,
            "test_add_result": test_result
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }

if __name__ == "__main__":
    frappe.init(site='dev.veganisme.net')
    frappe.connect()
    result = test_chapter_membership_history()
    print("Test completed:", result)