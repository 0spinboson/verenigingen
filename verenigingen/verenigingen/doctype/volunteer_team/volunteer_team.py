# Copyright (c) 2025, Your Organization and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class VolunteerTeam(Document):
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
            if member.role_type == "Team Leader" and member.status == "Active":
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
                continue
                
            # Get volunteer doc
            try:
                vol_doc = frappe.get_doc("Volunteer", member.volunteer)
                
                # Check if this assignment already exists
                exists = False
                for assignment in vol_doc.active_assignments:
                    if (assignment.assignment_type == "Team" and 
                        assignment.reference_doctype == "Volunteer Team" and
                        assignment.reference_name == self.name and
                        assignment.role == member.role):
                        exists = True
                        
                        # Update status if needed
                        if member.status != "Active" and assignment.status == "Active":
                            assignment.status = "Completed" if member.status == "Completed" else "Paused"
                            assignment.end_date = frappe.utils.today()
                            vol_doc.save()
                        break
                
                # If assignment doesn't exist and member is active, create it
                if not exists and member.status == "Active":
                    vol_doc.append("active_assignments", {
                        "assignment_type": "Team",
                        "reference_doctype": "Volunteer Team",
                        "reference_name": self.name,
                        "role": member.role,
                        "start_date": member.from_date or self.start_date or frappe.utils.today(),
                        "end_date": member.to_date,
                        "status": "Active"
                    })
                    
                    vol_doc.save()
                    
            except Exception as e:
                frappe.log_error(f"Failed to update volunteer assignment: {str(e)}")

@frappe.whitelist()
def get_team_members(team):
    """Get team members with volunteer info"""
    if not team:
        return []
        
    team_doc = frappe.get_doc("Volunteer Team", team)
    
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
