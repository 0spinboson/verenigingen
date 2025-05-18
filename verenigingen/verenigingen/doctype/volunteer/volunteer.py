import frappe
from frappe import _
from frappe.model.document import Document
from frappe.contacts.address_and_contact import load_address_and_contact
from frappe.utils import getdate, today, add_days, cint

class Volunteer(Document):
    def onload(self):
        """Load address and contacts in `__onload`"""
        load_address_and_contact(self)
        
        # Load aggregated assignments
        self.load_aggregated_assignments()
    
    def load_aggregated_assignments(self):
        """Load aggregated assignments from all sources"""
        self.get("__onload").aggregated_assignments = self.get_aggregated_assignments()
    
    def validate(self):
        """Validate volunteer data"""
        self.validate_required_fields()
        self.validate_dates()
        
    def validate_required_fields(self):
        """Check if required fields are filled"""
        if not self.start_date:
            self.start_date = today()
            
    def validate_dates(self):
        """Validate date fields in child tables"""
        for assignment in self.assignment_history:
            if assignment.end_date and getdate(assignment.start_date) > getdate(assignment.end_date):
                frappe.throw(_("Assignment start date cannot be after end date for {0}").format(assignment.role))
        
    def before_save(self):
        """Actions before saving volunteer record"""
        # Update volunteer status based on assignments
        self.update_status()
        
    def update_status(self):
        """Update volunteer status based on assignments"""
        if not self.status or self.status == "New":
            # If this is a new volunteer record
            assignments = self.get_aggregated_assignments()
            if assignments:
                self.status = "Active"
            else:
                self.status = "New"
    
    @frappe.whitelist()
    def get_aggregated_assignments(self):
        """Get aggregated assignments from all sources"""
        assignments = []
        
        # 1. Get board assignments
        board_assignments = self.get_board_assignments()
        assignments.extend(board_assignments)
        
        # 2. Get team assignments
        team_assignments = self.get_team_assignments()
        assignments.extend(team_assignments)
        
        # 3. Get activity assignments
        activity_assignments = self.get_activity_assignments()
        assignments.extend(activity_assignments)
        
        return assignments
    
    def get_board_assignments(self):
        """Get board assignments from Chapter Board Member"""
        if not self.member:
            return []
            
        board_assignments = []
        
        # Query board memberships for this member
        board_memberships = frappe.db.sql("""
            SELECT cbm.name as membership_id, cbm.parent as chapter, cbm.chapter_role as role, 
                   cbm.from_date, cbm.to_date, cbm.is_active,
                   c.name as chapter_name
            FROM `tabChapter Board Member` cbm
            JOIN `tabChapter` c ON cbm.parent = c.name
            WHERE cbm.member = %s AND cbm.is_active = 1
        """, (self.member,), as_dict=True)
        
        for membership in board_memberships:
            board_assignments.append({
                "source_type": "Board Position",
                "source_doctype": "Chapter",
                "source_name": membership.chapter,
                "source_doctype_display": "Chapter",
                "source_name_display": membership.chapter_name,
                "role": membership.role,
                "start_date": membership.from_date,
                "end_date": membership.to_date,
                "is_active": membership.is_active,
                "editable": False,
                "source_link": f"/app/chapter/{membership.chapter}"
            })
            
        return board_assignments
    
    def get_team_assignments(self):
        """Get team assignments from Team Member"""
        team_assignments = []
        
        # Query team memberships for this volunteer
        team_memberships = frappe.db.sql("""
            SELECT tm.name as membership_id, tm.parent as team, tm.role, 
                   tm.role_type, tm.from_date, tm.to_date, tm.status,
                   t.name as team_name, t.team_type
            FROM `tabVolunteer Team Member` tm
            JOIN `tabVolunteer Team` t ON tm.parent = t.name
            WHERE tm.volunteer = %s AND tm.status = 'Active'
        """, (self.name,), as_dict=True)
        
        for membership in team_memberships:
            team_assignments.append({
                "source_type": "Team",
                "source_doctype": "Volunteer Team",
                "source_name": membership.team,
                "source_doctype_display": f"{membership.team_type or 'Team'}",
                "source_name_display": membership.team_name,
                "role": membership.role,
                "start_date": membership.from_date,
                "end_date": membership.to_date,
                "is_active": membership.status == "Active",
                "editable": False,
                "source_link": f"/app/volunteer-team/{membership.team}"
            })
            
        return team_assignments
    
    def get_activity_assignments(self):
        """Get assignments from Volunteer Activity"""
        activity_assignments = []
        
        # Query activities for this volunteer
        activities = frappe.get_all(
            "Volunteer Activity",
            filters={
                "volunteer": self.name,
                "status": "Active"
            },
            fields=["name", "activity_type", "role", "description", "status", 
                    "start_date", "end_date", "reference_doctype", "reference_name",
                    "estimated_hours", "actual_hours", "notes"]
        )
        
        for activity in activities:
            ref_display = ""
            ref_link = ""
            
            if activity.reference_doctype and activity.reference_name:
                ref_display = f"{activity.reference_doctype}: {activity.reference_name}"
                ref_link = f"/app/{frappe.scrub(activity.reference_doctype)}/{activity.reference_name}"
                
            activity_assignments.append({
                "source_type": "Activity",
                "source_doctype": "Volunteer Activity",
                "source_name": activity.name,
                "source_doctype_display": activity.activity_type,
                "source_name_display": activity.description or activity.role,
                "role": activity.role,
                "start_date": activity.start_date,
                "end_date": activity.end_date,
                "is_active": activity.status == "Active",
                "editable": True,
                "source_link": f"/app/volunteer-activity/{activity.name}",
                "reference_display": ref_display,
                "reference_link": ref_link
            })
            
        return activity_assignments
    
    @frappe.whitelist()
    def add_activity(self, activity_type, role, description=None, start_date=None, end_date=None,
                    reference_doctype=None, reference_name=None, estimated_hours=None, notes=None):
        """Add a new volunteer activity"""
        if not start_date:
            start_date = today()
            
        activity = frappe.get_doc({
            "doctype": "Volunteer Activity",
            "volunteer": self.name,
            "activity_type": activity_type,
            "role": role,
            "description": description,
            "start_date": start_date,
            "end_date": end_date,
            "status": "Active",
            "reference_doctype": reference_doctype,
            "reference_name": reference_name,
            "estimated_hours": estimated_hours,
            "notes": notes
        })
        
        activity.insert()
        
        return activity.name
    
    @frappe.whitelist()
    def end_activity(self, activity_name, end_date=None, notes=None):
        """End a volunteer activity"""
        if not end_date:
            end_date = today()
            
        activity = frappe.get_doc("Volunteer Activity", activity_name)
        activity.status = "Completed"
        activity.end_date = end_date
        
        if notes:
            activity.notes = notes
            
        activity.save()
        
        return True
    
    def get_volunteer_history(self):
        """Get volunteer history in chronological order"""
        history = []
        
        # Get board assignment history
        if self.member:
            board_history = frappe.db.sql("""
                SELECT 'Board Position' as assignment_type, cbm.chapter_role as role, 
                       cbm.parent as reference, cbm.from_date as start_date, 
                       cbm.to_date as end_date, cbm.is_active
                FROM `tabChapter Board Member` cbm
                WHERE cbm.member = %s
            """, (self.member,), as_dict=True)
            
            for item in board_history:
                history.append({
                    "assignment_type": item.assignment_type,
                    "role": item.role,
                    "reference": item.reference,
                    "start_date": item.start_date,
                    "end_date": item.end_date,
                    "is_active": item.is_active,
                    "status": "Active" if item.is_active else "Completed"
                })
        
        # Get team assignment history
        team_history = frappe.db.sql("""
            SELECT 'Team' as assignment_type, tm.role, 
                   tm.parent as reference, tm.from_date as start_date, 
                   tm.to_date as end_date, tm.status
            FROM `tabVolunteer Team Member` tm
            WHERE tm.volunteer = %s
        """, (self.name,), as_dict=True)
        
        for item in team_history:
            history.append({
                "assignment_type": item.assignment_type,
                "role": item.role,
                "reference": item.reference,
                "start_date": item.start_date,
                "end_date": item.end_date,
                "is_active": item.status == "Active",
                "status": item.status
            })
        
        # Get activity history
        activity_history = frappe.get_all(
            "Volunteer Activity",
            filters={"volunteer": self.name},
            fields=["activity_type as assignment_type", "role", "description as reference",
                    "start_date", "end_date", "status", "name"]
        )
        
        for item in activity_history:
            history.append({
                "assignment_type": item.assignment_type,
                "role": item.role,
                "reference": item.reference or item.name,
                "start_date": item.start_date,
                "end_date": item.end_date,
                "is_active": item.status == "Active",
                "status": item.status
            })
        
        # Add assignment history from the child table (for historical records)
        for item in self.assignment_history:
            history.append({
                "assignment_type": item.assignment_type,
                "role": item.role,
                "reference": f"{item.reference_doctype}: {item.reference_name}" if item.reference_doctype else "",
                "start_date": item.start_date,
                "end_date": item.end_date,
                "is_active": False,
                "status": item.status
            })
        
        # Sort by start date (newest first)
        history.sort(key=lambda x: getdate(x.get("start_date")), reverse=True)
        
        return history
    
    @frappe.whitelist()
    def get_skills_by_category(self):
        """Get volunteer skills grouped by category"""
        skills_by_category = {}
        
        for skill in self.skills_and_qualifications:
            category = skill.skill_category
            if category not in skills_by_category:
                skills_by_category[category] = []
            
            skills_by_category[category].append({
                "skill": skill.volunteer_skill,
                "level": skill.proficiency_level,
                "experience": skill.experience_years
            })
            
        return skills_by_category
    
# Integration functions to be called from other doctypes

@frappe.whitelist()
def create_volunteer_from_member(member_doc):
    """Create or update volunteer record from member"""
    if not member_doc:
        return None
        
    if isinstance(member_doc, str):
        member_doc = frappe.get_doc("Member", member_doc)
        
    if not member_doc.email:
        frappe.msgprint(_("Member does not have an email address. Cannot create volunteer record."))
        return None
        
    # Check if volunteer record already exists
    existing_volunteer = frappe.db.exists("Volunteer", {"member": member_doc.name})
    
    if existing_volunteer:
        return frappe.get_doc("Volunteer", existing_volunteer)
    
    # Generate organization email based on full name
    domain = frappe.db.get_single_value("Verenigingen Settings", "organization_email_domain") or "example.org"
    name_for_email = member_doc.full_name.replace(" ", ".").lower()
    org_email = f"{name_for_email}@{domain}"
    
    # Create new volunteer record
    volunteer = frappe.new_doc("Volunteer")
    volunteer.update({
        "volunteer_name": member_doc.full_name,
        "member": member_doc.name,
        "email": org_email,
        "personal_email": member_doc.email,
        "preferred_pronouns": member_doc.pronouns,
        "status": "New",
        "start_date": today()
    })
    
    volunteer.insert(ignore_permissions=True)
    
    frappe.msgprint(_("Volunteer record created for {0}").format(member_doc.full_name))
    return volunteer

@frappe.whitelist()
def sync_chapter_board_members():
    """Sync all chapter board members with volunteer system"""
    # Get all active chapter board members
    board_members = frappe.db.sql("""
        SELECT 
            cbm.name, cbm.parent as chapter, cbm.member, cbm.chapter_role, 
            cbm.from_date, cbm.to_date, cbm.is_active
        FROM `tabChapter Board Member` cbm
        WHERE cbm.is_active = 1
    """, as_dict=True)
    
    updated_count = 0
    
    for board_member in board_members:
        # Get or create volunteer record
        volunteer = None
        member_doc = frappe.get_doc("Member", board_member.member)
        
        # Find volunteer by member link
        existing_volunteer = frappe.db.exists("Volunteer", {"member": board_member.member})
        
        if existing_volunteer:
            volunteer = frappe.get_doc("Volunteer", existing_volunteer)
        else:
            # Create new volunteer from member
            volunteer = create_volunteer_from_member(member_doc)
            
        if volunteer:
            updated_count += 1
    
    return {"updated_count": updated_count}
