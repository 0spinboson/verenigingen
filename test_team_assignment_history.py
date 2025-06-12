#!/usr/bin/env python3
"""
Test script for team assignment history functionality
"""

import frappe
from frappe.utils import today, add_days

def test_team_assignment_history():
    """Test that team assignments are properly tracked in volunteer history"""
    
    print("Testing team assignment history functionality...")
    
    # Connect to frappe
    frappe.connect()
    
    try:
        # Get an existing volunteer for testing
        volunteers = frappe.get_all("Volunteer", limit=1)
        if not volunteers:
            print("No volunteers found for testing")
            return
        
        volunteer_id = volunteers[0].name
        volunteer_doc = frappe.get_doc("Volunteer", volunteer_id)
        print(f"Testing with volunteer: {volunteer_doc.volunteer_name} ({volunteer_id})")
        
        # Check initial assignment history count
        initial_history_count = len(volunteer_doc.assignment_history or [])
        print(f"Initial assignment history count: {initial_history_count}")
        
        # Create a test team
        team = frappe.new_doc("Team")
        team.team_name = f"Test Team {frappe.utils.random_string(5)}"
        team.status = "Active"
        team.team_type = "Project Team"
        team.start_date = today()
        
        # Add the volunteer as a team member
        team.append("team_members", {
            "volunteer": volunteer_id,
            "volunteer_name": volunteer_doc.volunteer_name,
            "role": "Test Role",
            "role_type": "Team Member",
            "from_date": today(),
            "is_active": 1,
            "status": "Active"
        })
        
        print(f"Creating team: {team.team_name}")
        team.save()
        
        # Reload volunteer and check assignment history
        volunteer_doc.reload()
        new_history_count = len(volunteer_doc.assignment_history or [])
        print(f"Assignment history count after team creation: {new_history_count}")
        
        if new_history_count > initial_history_count:
            print("✅ SUCCESS: Assignment history was added when volunteer was assigned to team")
            
            # Find the new assignment
            for assignment in volunteer_doc.assignment_history:
                if (assignment.reference_doctype == "Team" and 
                    assignment.reference_name == team.name and
                    assignment.status == "Active"):
                    print(f"   Assignment details: {assignment.assignment_type} - {assignment.role}")
                    print(f"   Reference: {assignment.reference_doctype} {assignment.reference_name}")
                    print(f"   Status: {assignment.status}")
                    print(f"   Start Date: {assignment.start_date}")
                    break
        else:
            print("❌ FAILURE: No assignment history was added")
            return
        
        # Test deactivating the team member
        print("\nTesting team member deactivation...")
        team_member = team.team_members[0]
        team_member.is_active = 0
        team_member.to_date = today()
        team_member.status = "Completed"
        team.save()
        
        # Reload volunteer and check assignment history
        volunteer_doc.reload()
        
        # Check if assignment was completed
        assignment_completed = False
        for assignment in volunteer_doc.assignment_history:
            if (assignment.reference_doctype == "Team" and 
                assignment.reference_name == team.name and
                assignment.status == "Completed"):
                assignment_completed = True
                print(f"✅ SUCCESS: Assignment was marked as completed")
                print(f"   End Date: {assignment.end_date}")
                break
        
        if not assignment_completed:
            print("❌ FAILURE: Assignment was not marked as completed")
        
        # Clean up - delete the test team
        print(f"\nCleaning up test team: {team.name}")
        frappe.delete_doc("Team", team.name)
        
        print("\nTest completed successfully!")
        
    except Exception as e:
        print(f"❌ ERROR during testing: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        frappe.destroy()

if __name__ == "__main__":
    test_team_assignment_history()