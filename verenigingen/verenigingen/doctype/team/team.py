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
    
    def before_insert(self):
        """Link volunteers to members before insert"""
        self.update_volunteer_assignments()
    
    def on_update(self):
        """Update volunteer assignments when team is updated"""
        self.update_volunteer_assignments()
    
    def update_volunteer_assignments(self):
        """Update volunteer assignments for all team members"""
        for member in self.team_members:
            # Skip if no volunteer is assigned
            if not member.volunteer:
                frappe.msgprint(_("Warning: Team member with role '{0}' has no volunteer assigned").format(member.role))
                continue
                
            # Process volunteer assignment
            if member.volunteer:
                # Get volunteer doc
                try:
                    vol_doc = frappe.get_doc("Volunteer", member.volunteer)
                    
                    # Ensure the volunteer has an assignments table
                    if not vol_doc.assignments:
                        vol_doc.append("assignments", {
                            "assignment_type": "Team",
                            "reference_doctype": "Team",
                            "reference_name": self.name,
                            "role": member.role,
                            "from_date": member.from_date,
                            "to_date": member.to_date if not member.is_active else None,
                            "is_active": member.is_active
                        })
                        vol_doc.save(ignore_permissions=True)
                        print(f"Added new assignment to volunteer {vol_doc.name} for team {self.name}")
                    else:
                        # Check if this assignment already exists
                        exists = False
                        for assignment in vol_doc.assignments:
                            if (assignment.reference_doctype == "Team" and 
                                assignment.reference_name == self.name and
                                assignment.role == member.role):
                                exists = True
                                # Update the assignment status
                                assignment.is_active = member.is_active
                                assignment.to_date = member.to_date if not member.is_active else None
                                vol_doc.save(ignore_permissions=True)
                                print(f"Updated existing assignment for volunteer {vol_doc.name} and team {self.name}")
                                break
                        
                        # If no matching assignment exists, add a new one
                        if not exists:
                            vol_doc.append("assignments", {
                                "assignment_type": "Team",
                                "reference_doctype": "Team",
                                "reference_name": self.name,
                                "role": member.role,
                                "from_date": member.from_date,
                                "to_date": member.to_date if not member.is_active else None,
                                "is_active": member.is_active
                            })
                            vol_doc.save(ignore_permissions=True)
                            print(f"Added new assignment to volunteer {vol_doc.name} for team {self.name}")
                    
                    # If the assignment changed status and was completed, add to history
                    if (not member.is_active or member.status != "Active") and member.to_date:
                        # Check if we need to add to assignment history
                        has_history = False
                        for entry in vol_doc.assignment_history:
                            if (entry.reference_doctype == "Team" and
                                entry.reference_name == self.name and
                                entry.role == member.role):
                                has_history = True
                                break
                                
                        if not has_history:
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
                            vol_doc.save(ignore_permissions=True)
                            print(f"Added assignment history entry for volunteer {vol_doc.name} and team {self.name}")
                        
                except Exception as e:
                    frappe.log_error(f"Failed to update volunteer assignment: {str(e)}")
                    print(f"Error updating volunteer assignment: {str(e)}")

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
            print(f"Successfully synced team {team.name} with volunteers")
        except Exception as e:
            frappe.log_error(f"Failed to sync team {team.name}: {str(e)}")
            print(f"Error syncing team {team.name}: {str(e)}")
    
    return {"updated_count": updated_count}
