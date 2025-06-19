#!/usr/bin/env python3

"""
Test script for Chapter Membership History functionality
"""

import frappe
from frappe.utils import today, add_days
from verenigingen.utils.chapter_membership_history_manager import ChapterMembershipHistoryManager

def test_chapter_membership_history():
    """Test the chapter membership history functionality"""
    print("Testing Chapter Membership History functionality...")
    
    try:
        # Get a test member
        test_member = frappe.get_all("Member", limit=1, fields=["name", "full_name"])
        if not test_member:
            print("No members found. Please create a member first.")
            return
        
        member_id = test_member[0].name
        member_name = test_member[0].full_name
        print(f"Testing with member: {member_name} ({member_id})")
        
        # Get a test chapter
        test_chapter = frappe.get_all("Chapter", limit=1, fields=["name"])
        if not test_chapter:
            print("No chapters found. Please create a chapter first.")
            return
        
        chapter_name = test_chapter[0].name
        print(f"Testing with chapter: {chapter_name}")
        
        # Test 1: Add membership history
        print("\n1. Testing add_membership_history...")
        result = ChapterMembershipHistoryManager.add_membership_history(
            member_id=member_id,
            chapter_name=chapter_name,
            assignment_type="Member",
            start_date=today(),
            reason="Test membership history"
        )
        print(f"Add membership result: {result}")
        
        # Test 2: Get active memberships
        print("\n2. Testing get_active_memberships...")
        active_memberships = ChapterMembershipHistoryManager.get_active_memberships(member_id)
        print(f"Active memberships count: {len(active_memberships)}")
        for membership in active_memberships:
            print(f"  - {membership.chapter_name} ({membership.assignment_type}) since {membership.start_date}")
        
        # Test 3: Get membership history summary
        print("\n3. Testing get_membership_history_summary...")
        summary = ChapterMembershipHistoryManager.get_membership_history_summary(member_id)
        print(f"Summary: {summary}")
        
        # Test 4: Complete membership history
        print("\n4. Testing complete_membership_history...")
        result = ChapterMembershipHistoryManager.complete_membership_history(
            member_id=member_id,
            chapter_name=chapter_name,
            assignment_type="Member",
            start_date=today(),
            end_date=add_days(today(), 1),
            reason="Test completion"
        )
        print(f"Complete membership result: {result}")
        
        # Test 5: Check final summary
        print("\n5. Final summary after completion...")
        final_summary = ChapterMembershipHistoryManager.get_membership_history_summary(member_id)
        print(f"Final summary: {final_summary}")
        
        print("\n✓ Chapter Membership History tests completed successfully!")
        
    except Exception as e:
        print(f"✗ Error during testing: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Connect to Frappe
    frappe.init(site="dev.veganisme.net")
    frappe.connect()
    
    test_chapter_membership_history()
    
    frappe.destroy()