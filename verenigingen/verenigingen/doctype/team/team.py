# Copyright (c) 2025, Your Organization and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder import DocType

class Team(Document):
    def validate(self):
        self.validate_dates()
        self.validate_team_members()
        self.update_team_lead()
    
    def validate_dates(self):
        """Validate start and end dates"""
        if self.end_date and self.start_date and self.end_date < self.start_date:
            frappe.throw(_("End date cannot be before start date"))
    
    def validate_team_members(self):
        """Validate team members data"""
        # Check if there's at least one team leader
        has_leader = False
        for member in self.team_members:
            if member.role_type == "Team Leader" and member.is_active:
                has_leader = True
                break
                
        if not has_leader and self.status == "Active" and self.team_members:
            frappe.msgprint(_("Warning: Active team should have at least one active team leader"))
    
    def update_team_lead(self):
        """Auto-populate team_lead field from active Team Leader"""
        current_leader = None
        
        # Find the first active Team Leader
        for member in self.team_members or []:
            if member.role_type == "Team Leader" and member.is_active:
                # Get the user associated with this volunteer
                if member.volunteer:
                    volunteer_doc = frappe.get_doc("Volunteer", member.volunteer)
                    if volunteer_doc.member:
                        user = frappe.db.get_value("Member", volunteer_doc.member, "user")
                        if user:
                            current_leader = user
                            break
        
        # Update the team_lead field
        self.team_lead = current_leader
    
    def before_save(self):
        """Store document state before save for comparison"""
        if not self.is_new():
            self._doc_before_save = frappe.get_doc("Team", self.name)
    
    def before_insert(self):
        """Prepare for initial team creation"""
        pass
    
    def after_insert(self):
        """Handle team member assignments after team creation"""
        self.handle_team_member_changes()
    
    def on_update(self):
        """Update volunteer assignments when team is updated"""
        self.handle_team_member_changes()
    
    def handle_team_member_changes(self):
        """Handle team member changes and update assignment history"""
        if not hasattr(self, '_doc_before_save') or self._doc_before_save is None:
            # For new teams, add all active members to history
            for member in self.team_members or []:
                if member.is_active and member.volunteer:
                    self.add_team_assignment_history(
                        member.volunteer,
                        member.role,
                        member.from_date
                    )
            return

        # Get old team members - group by volunteer and from_date (not role)
        old_members_by_volunteer = {}
        for m in (self._doc_before_save.team_members or []):
            if m.volunteer:
                key = (m.volunteer, str(m.from_date))
                old_members_by_volunteer[key] = m
        
        # Check current team members - group by volunteer and from_date
        current_members_by_volunteer = {}
        for m in (self.team_members or []):
            if m.volunteer:
                key = (m.volunteer, str(m.from_date))
                current_members_by_volunteer[key] = m

        # Process each current member
        for key, member in current_members_by_volunteer.items():
            volunteer_id, from_date = key
            
            if key not in old_members_by_volunteer:
                # New member assignment
                if member.is_active:
                    self.add_team_assignment_history(
                        member.volunteer,
                        member.role,
                        member.from_date
                    )
            else:
                old_member = old_members_by_volunteer[key]
                
                # Check for role changes (same volunteer, same from_date, different role/role_type)
                role_changed = (old_member.role != member.role or 
                               old_member.role_type != member.role_type)
                
                if role_changed and old_member.is_active and member.is_active:
                    # Role changed - complete old assignment and create new one
                    change_date = frappe.utils.today()
                    self.complete_team_assignment_history(
                        old_member.volunteer,
                        old_member.role,
                        old_member.from_date,
                        change_date
                    )
                    # Start new assignment with new role using today's date
                    self.add_team_assignment_history(
                        member.volunteer,
                        member.role,
                        change_date  # Use change date, not original from_date
                    )
                
                # Check if member was reactivated
                elif not old_member.is_active and member.is_active:
                    self.add_team_assignment_history(
                        member.volunteer,
                        member.role,
                        member.from_date
                    )
                # Check if member was deactivated
                elif old_member.is_active and not member.is_active:
                    end_date = member.to_date or frappe.utils.today()
                    self.complete_team_assignment_history(
                        member.volunteer,
                        member.role,
                        member.from_date,
                        end_date
                    )

        # Find removed assignments
        for key, old_member in old_members_by_volunteer.items():
            if key not in current_members_by_volunteer and old_member.is_active:
                # Member was removed entirely
                end_date = frappe.utils.today()
                self.complete_team_assignment_history(
                    old_member.volunteer,
                    old_member.role,
                    old_member.from_date,
                    end_date
                )
    
    def add_team_assignment_history(self, volunteer_id: str, role: str, start_date: str):
        """Add active assignment to volunteer history when joining team"""
        from verenigingen.utils.assignment_history_manager import AssignmentHistoryManager
        
        # Get the team member to access role_type
        team_member = None
        for member in self.team_members:
            if member.volunteer == volunteer_id and str(member.from_date) == str(start_date):
                team_member = member
                break
        
        if not team_member:
            print(f"Could not find team member for volunteer {volunteer_id}")
            return
        
        # Use role_type as primary, append optional role name if provided
        role_description = team_member.role_type
        if role and role.strip():
            role_description = f"{team_member.role_type} - {role}"
        
        success = AssignmentHistoryManager.add_assignment_history(
            volunteer_id=volunteer_id,
            assignment_type="Team",
            reference_doctype="Team",
            reference_name=self.name,
            role=role_description,
            start_date=start_date
        )
        
        if success:
            print(f"Added team assignment history for volunteer {volunteer_id}: {role_description}")
        else:
            print(f"Error adding team assignment history for volunteer {volunteer_id}: {role_description}")
    
    def complete_team_assignment_history(self, volunteer_id: str, role: str, start_date: str, end_date: str):
        """Complete volunteer assignment history when leaving team"""
        from verenigingen.utils.assignment_history_manager import AssignmentHistoryManager
        
        # Get the team member to access role_type
        team_member = None
        for member in self.team_members:
            if member.volunteer == volunteer_id and str(member.from_date) == str(start_date):
                team_member = member
                break
        
        # If not in current members, check the old document
        if not team_member and hasattr(self, '_doc_before_save'):
            for member in self._doc_before_save.team_members or []:
                if member.volunteer == volunteer_id and str(member.from_date) == str(start_date):
                    team_member = member
                    break
        
        if not team_member:
            print(f"Could not find team member for volunteer {volunteer_id}")
            # Use role as-is if we can't find the member
            role_description = role
        else:
            # Use role_type as primary, append optional role name if provided
            role_description = team_member.role_type
            if role and role.strip():
                role_description = f"{team_member.role_type} - {role}"
        
        success = AssignmentHistoryManager.complete_assignment_history(
            volunteer_id=volunteer_id,
            assignment_type="Team",
            reference_doctype="Team",
            reference_name=self.name,
            role=role_description,
            start_date=start_date,
            end_date=end_date
        )
        
        if success:
            print(f"Completed team assignment history for volunteer {volunteer_id}: {role_description}")
        else:
            print(f"Error completing team assignment history for volunteer {volunteer_id}: {role_description}")

@frappe.whitelist()
def get_team_members(team):
    """Get team members with volunteer info"""
    if not team:
        return []
        
    team_doc = frappe.get_doc("Team", team)
    
    members = []
    for member in team_doc.team_members:
        if not member.volunteer:
            continue
            
        try:
            vol_doc = frappe.get_doc("Volunteer", member.volunteer)
            members.append({
                "volunteer": member.volunteer,
                "name": vol_doc.volunteer_name,
                "role": member.role,
                "role_type": member.role_type,
                "status": member.status,
                "from_date": member.from_date,
                "to_date": member.to_date,
                "skills": vol_doc.get_skills_by_category()
            })
        except:
            pass
            
    return members

@frappe.whitelist()
def sync_team_with_volunteers(team_name=None):
    """Sync all team members with volunteer system"""
    filters = {}
    if team_name:
        filters["name"] = team_name
        
    # Get all active teams
    teams = frappe.get_all("Team", filters=filters, fields=["name"])
    
    updated_count = 0
    
    for team in teams:
        try:
            team_doc = frappe.get_doc("Team", team.name)
            # Trigger volunteer assignment history updates by calling the handler
            team_doc.handle_team_member_changes()
            updated_count += 1
            print(f"Successfully synced team {team.name} with volunteers")
        except Exception as e:
            frappe.log_error(f"Failed to sync team {team.name}: {str(e)}")
            print(f"Error syncing team {team.name}: {str(e)}")
    
    return {"updated_count": updated_count}

@frappe.whitelist()
def fix_missing_assignment_history(team_name=None, volunteer_name=None):
    """Fix missing team assignment history for existing assignments"""
    
    try:
        from verenigingen.utils.assignment_history_manager import AssignmentHistoryManager
        
        if team_name and volunteer_name:
            # Fix specific team-volunteer assignment
            team = frappe.get_doc("Team", team_name)
            
            for member in team.team_members:
                if member.volunteer == volunteer_name and member.is_active:
                    print(f"Found active assignment: {member.volunteer} -> {member.role}")
                    
                    # Check if assignment history already exists
                    volunteer_doc = frappe.get_doc("Volunteer", volunteer_name)
                    has_assignment = False
                    
                    for assignment in volunteer_doc.assignment_history or []:
                        if (assignment.reference_doctype == "Team" and
                            assignment.reference_name == team_name and
                            assignment.role == member.role and
                            assignment.status == "Active"):
                            has_assignment = True
                            print(f"Assignment already exists in history")
                            break
                    
                    if not has_assignment:
                        success = AssignmentHistoryManager.add_assignment_history(
                            volunteer_id=volunteer_name,
                            assignment_type="Team",
                            reference_doctype="Team", 
                            reference_name=team_name,
                            role=member.role,
                            start_date=member.from_date
                        )
                        
                        if success:
                            print(f"✅ Successfully added assignment history for {volunteer_name}")
                            return {"success": True, "message": "Assignment history added successfully"}
                        else:
                            print(f"❌ Failed to add assignment history for {volunteer_name}")
                            return {"success": False, "error": "Failed to add assignment history"}
                    else:
                        return {"success": True, "message": "Assignment history already exists"}
        
        return {"success": False, "error": "No matching assignment found"}
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def debug_team_assignments():
    """Debug team assignments and volunteers"""
    
    result = {}
    
    # Get teams
    teams = frappe.get_all('Team', fields=['name', 'team_name'])
    result['teams'] = []
    for team in teams:
        team_doc = frappe.get_doc('Team', team.name)
        team_info = {
            'name': team.name,
            'team_name': team.team_name,
            'members': []
        }
        for member in team_doc.team_members:
            team_info['members'].append({
                'volunteer': member.volunteer,
                'volunteer_name': member.volunteer_name,
                'role': member.role,
                'is_active': member.is_active,
                'from_date': str(member.from_date) if member.from_date else None
            })
        result['teams'].append(team_info)
    
    # Get Foppe volunteers
    volunteers = frappe.get_all('Volunteer', filters={'volunteer_name': ['like', '%Foppe%']}, fields=['name', 'volunteer_name'])
    result['foppe_volunteers'] = []
    for vol in volunteers:
        volunteer_doc = frappe.get_doc('Volunteer', vol.name)
        vol_info = {
            'name': vol.name,
            'volunteer_name': vol.volunteer_name,
            'assignment_history': []
        }
        for assignment in volunteer_doc.assignment_history or []:
            vol_info['assignment_history'].append({
                'assignment_type': assignment.assignment_type,
                'reference_doctype': assignment.reference_doctype,
                'reference_name': assignment.reference_name,
                'role': assignment.role,
                'status': assignment.status,
                'start_date': str(assignment.start_date) if assignment.start_date else None,
                'end_date': str(assignment.end_date) if assignment.end_date else None
            })
        result['foppe_volunteers'].append(vol_info)
    
    return result

@frappe.whitelist()
def test_team_member_removal():
    """Test that removing a team member properly updates assignment history"""
    
    print("=== Testing Team Member Removal ===")
    
    try:
        # Create a test team with a member
        test_team = frappe.get_doc({
            "doctype": "Team",
            "team_name": f"Removal Test Team {frappe.utils.random_string(5)}",
            "status": "Active",
            "team_type": "Project Team",
            "start_date": frappe.utils.today()
        })
        test_team.insert()
        
        # Get Foppe de Haan as our test volunteer
        volunteer_name = "Foppe de  Haan"  # Note the double space
        
        # Add him to the team
        test_team.append("team_members", {
            "volunteer": volunteer_name,
            "volunteer_name": volunteer_name,
            "role": "Test Removal Role",
            "role_type": "Team Member",
            "from_date": frappe.utils.today(),
            "is_active": 1,
            "status": "Active"
        })
        
        print(f"1. Adding {volunteer_name} to team {test_team.name}")
        test_team.save()
        
        # Check if assignment history was created
        volunteer_doc = frappe.get_doc("Volunteer", volunteer_name)
        active_assignment = None
        for assignment in volunteer_doc.assignment_history or []:
            if (assignment.reference_name == test_team.name and 
                assignment.status == "Active"):
                active_assignment = assignment
                break
        
        if active_assignment:
            print(f"✅ Active assignment created: {active_assignment.role}")
        else:
            print("❌ No active assignment found")
            return {"success": False, "error": "No active assignment created"}
        
        # Now test removal by deactivating the member
        print(f"2. Deactivating {volunteer_name} from team")
        team_member = test_team.team_members[0]
        team_member.is_active = 0
        team_member.to_date = frappe.utils.today()
        team_member.status = "Completed"
        
        test_team.save()
        
        # Check if assignment history was completed
        volunteer_doc.reload()
        completed_assignment = None
        for assignment in volunteer_doc.assignment_history or []:
            if (assignment.reference_name == test_team.name and 
                assignment.status == "Completed"):
                completed_assignment = assignment
                break
        
        if completed_assignment:
            print(f"✅ Assignment completed with end date: {completed_assignment.end_date}")
            
            # Now test complete removal
            print(f"3. Completely removing {volunteer_name} from team")
            test_team.team_members = []  # Remove all members
            test_team.save()
            
            # Check that assignment history is still completed (not removed)
            volunteer_doc.reload()
            still_completed = None
            for assignment in volunteer_doc.assignment_history or []:
                if (assignment.reference_name == test_team.name and 
                    assignment.status == "Completed"):
                    still_completed = assignment
                    break
            
            if still_completed:
                print(f"✅ Assignment history preserved after complete removal")
            else:
                print("❌ Assignment history lost after complete removal")
        else:
            print("❌ Assignment was not completed")
            return {"success": False, "error": "Assignment not completed"}
        
        # Clean up - remove assignment history and delete team
        print("4. Cleaning up test data")
        volunteer_doc.reload()
        assignments_to_remove = []
        for assignment in volunteer_doc.assignment_history or []:
            if assignment.reference_name == test_team.name:
                assignments_to_remove.append(assignment)
        
        for assignment in assignments_to_remove:
            volunteer_doc.assignment_history.remove(assignment)
        
        if assignments_to_remove:
            volunteer_doc.save()
        
        try:
            frappe.delete_doc("Team", test_team.name)
        except:
            pass  # Ignore deletion errors for testing
        
        print("✅ Test completed successfully!")
        return {"success": True, "message": "Team member removal test passed"}
        
    except Exception as e:
        print(f"❌ Error during test: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

def get_team_permission_query_conditions(user=None):
    """Get permission query conditions for Teams"""
    try:
        if not user:
            user = frappe.session.user
            
        if "System Manager" in frappe.get_roles(user) or "Verenigingen Administrator" in frappe.get_roles(user):
            return ""
            
        # Get member record for the user
        member = frappe.db.get_value("Member", {"user": user}, "name")
        if not member:
            return "`tabTeam`.name = ''"  # No access if not a member
            
        # Get volunteer record for the member
        volunteer = frappe.db.get_value("Volunteer", {"member": member}, "name")
        if not volunteer:
            return "`tabTeam`.name = ''"  # No access if not a volunteer
            
        # Get teams where user is a team member using Query Builder
        TM = DocType('Team Member')
        team_memberships = (
            frappe.qb.from_(TM)
            .select(TM.parent)
            .where((TM.volunteer == volunteer) & (TM.is_active == 1))
        ).run(as_dict=True)
        
        if team_memberships:
            team_list = ["'" + team.parent + "'" for team in team_memberships]
            return f"`tabTeam`.name in ({', '.join(team_list)})"
        
        return "`tabTeam`.name = ''"  # No access if not part of any teams
        
    except Exception as e:
        frappe.log_error(f"Error in team permission query: {str(e)}")
        return "`tabTeam`.name = ''"  # Default to no access on error
