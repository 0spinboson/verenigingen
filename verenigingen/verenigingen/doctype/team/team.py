# Copyright (c) 2025, Your Organization and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

class Team(Document):
    def validate(self):
        self.validate_dates()
        self.validate_team_members()
    
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
    
    def on_update(self):
        """Update volunteer assignments when team is updated"""
        self.update_volunteer_assignments()
    
    def update_volunteer_assignments(self):
        """Update volunteer assignments for all team members"""
        for member in self.team_members:
            if not member.volunteer:
                # If no volunteer is specified but member is, try to find a volunteer
                if member.member:
                    volunteer = frappe.db.get_value("Volunteer", {"member": member.member}, "name")
                    if volunteer:
                        member.volunteer = volunteer
                        member.volunteer_name = frappe.db.get_value("Volunteer", volunteer, "volunteer_name")
                else:
                    continue
                
            # Now proceed if we have a volunteer
            if member.volunteer:
                # Get volunteer doc
                try:
                    vol_doc = frappe.get_doc("Volunteer", member.volunteer)
                    
                    # Check if this assignment already exists in aggregated assignments
                    assignments = vol_doc.get_aggregated_assignments()
                    exists = False
                    
                    for assignment in assignments:
                        if (assignment["source_type"] == "Team" and 
                            assignment["source_doctype"] == "Team" and
                            assignment["source_name"] == self.name and
                            assignment["role"] == member.role):
                            exists = True
                            
                            # Status is tracked in the Team Member record
                            # No need to update anything else here
                            break
                    
                    # If the assignment changed status and was completed, add to history
                    if (not member.is_active or member.status != "Active") and member.to_date:
                        # Check if we need to add to assignment history
                        # This only happens if status changed from active to something else
                        if not frappe.db.exists("Volunteer Assignment", {
                            "parent": vol_doc.name,
                            "assignment_type": "Team",
                            "reference_doctype": "Team",
                            "reference_name": self.name,
                            "role": member.role,
                            "status": member.status
                        }):
                            # Add to assignment history
                            vol_doc.append("assignment_history", {
                                "assignment_type": "Team",
                                "reference_doctype": "Team",
                                "reference_name": self.name,
                                "role": member.role,
                                "start_date": member.from_date,
                                "end_date": member.to_date or frappe.utils.today(),
                                "status": "Completed" if member.status != "Cancelled" else member.status
                            })
                            vol_doc.save()
                        
                except Exception as e:
                    frappe.log_error(f"Failed to update volunteer assignment: {str(e)}")

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
            team_doc.update_volunteer_assignments()
            updated_count += 1
        except Exception as e:
            frappe.log_error(f"Failed to sync team {team.name}: {str(e)}")
    
    return {"updated_count": updated_count}
