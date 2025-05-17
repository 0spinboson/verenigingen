import frappe
from frappe import _
from frappe.model.document import Document
from frappe.contacts.address_and_contact import load_address_and_contact
from frappe.utils import getdate, today, add_days, cint

class Volunteer(Document):
    def onload(self):
        """Load address and contacts in `__onload`"""
        load_address_and_contact(self)
    
    def validate(self):
        """Validate volunteer data"""
        self.validate_required_fields()
        self.validate_dates()
        self.validate_assignments()
        
    def validate_required_fields(self):
        """Check if required fields are filled"""
        if not self.start_date:
            self.start_date = today()
            
    def validate_dates(self):
        """Validate date fields"""
        for assignment in self.active_assignments:
            if assignment.end_date and getdate(assignment.start_date) > getdate(assignment.end_date):
                frappe.throw(_("Assignment start date cannot be after end date for {0}").format(assignment.role))
                
    def validate_assignments(self):
        """Validate assignment data"""
        # Check if assignments are properly categorized as active or historical
        for assignment in self.active_assignments:
            if assignment.status == "Completed" or assignment.end_date and getdate(assignment.end_date) < getdate(today()):
                # Move to assignment history
                self.append("assignment_history", {
                    "assignment_type": assignment.assignment_type,
                    "reference_doctype": assignment.reference_doctype,
                    "reference_name": assignment.reference_name,
                    "role": assignment.role,
                    "start_date": assignment.start_date,
                    "end_date": assignment.end_date or today(),
                    "status": "Completed" if assignment.status != "Cancelled" else assignment.status,
                    "estimated_hours": assignment.estimated_hours,
                    "actual_hours": assignment.actual_hours,
                    "accomplishments": assignment.accomplishments,
                    "notes": assignment.notes
                })
                # Mark for removal from active assignments
                assignment.remove = True
        
        # Remove assignments that have been moved to history
        self.active_assignments = [a for a in self.active_assignments if not hasattr(a, 'remove') or not a.remove]
    
    def before_save(self):
        """Actions before saving volunteer record"""
        # Update volunteer status based on assignments
        self.update_status()
        
    def update_status(self):
        """Update volunteer status based on assignments"""
        if not self.status or self.status == "New":
            # If this is a new volunteer record
            if self.active_assignments:
                self.status = "Active"
            else:
                self.status = "New"
    
    @frappe.whitelist()
    def add_board_assignment(self, chapter, role, start_date=None, end_date=None, status="Active"):
        """Add a board position assignment"""
        if not start_date:
            start_date = today()
            
        # Check if this assignment already exists
        for assignment in self.active_assignments:
            if (assignment.assignment_type == "Board Position" and 
                assignment.reference_doctype == "Chapter" and
                assignment.reference_name == chapter and
                assignment.role == role and
                assignment.status == "Active"):
                frappe.msgprint(_("This board assignment already exists"))
                return
        
        # Add new board assignment
        self.append("active_assignments", {
            "assignment_type": "Board Position",
            "reference_doctype": "Chapter",
            "reference_name": chapter,
            "role": role,
            "start_date": start_date,
            "end_date": end_date,
            "status": status
        })
        
        self.save()
        return True
    
    @frappe.whitelist()
    def add_team_assignment(self, team, role, start_date=None, end_date=None, status="Active"):
        """Add a team/committee assignment"""
        if not start_date:
            start_date = today()
            
        # Add new team assignment
        self.append("active_assignments", {
            "assignment_type": "Team",
            "reference_doctype": "Volunteer Team",  # This would be a new doctype we'd create
            "reference_name": team,
            "role": role,
            "start_date": start_date,
            "end_date": end_date,
            "status": status
        })
        
        self.save()
        return True
    
    @frappe.whitelist()
    def end_assignment(self, assignment_idx, end_date=None, notes=None):
        """End an active assignment and move to history"""
        if not end_date:
            end_date = today()
            
        try:
            assignment = self.active_assignments[cint(assignment_idx) - 1]
            assignment.status = "Completed"
            assignment.end_date = end_date
            if notes:
                assignment.notes = notes
                
            self.save()
            return True
        except:
            frappe.msgprint(_("Assignment not found"))
            return False
    
    def get_volunteer_history(self):
        """Get volunteer history in chronological order"""
        history = []
        
        # Add active assignments
        for assignment in self.active_assignments:
            history.append({
                "assignment_type": assignment.assignment_type,
                "role": assignment.role,
                "reference": assignment.reference_name,
                "start_date": assignment.start_date,
                "end_date": assignment.end_date,
                "status": assignment.status,
                "is_active": True
            })
            
        # Add historical assignments
        for assignment in self.assignment_history:
            history.append({
                "assignment_type": assignment.assignment_type,
                "role": assignment.role,
                "reference": assignment.reference_name,
                "start_date": assignment.start_date,
                "end_date": assignment.end_date,
                "status": assignment.status,
                "is_active": False
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

def create_volunteer_from_member(member_doc):
    """Create or update volunteer record from member"""
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
def add_board_member_assignment(volunteer, chapter, role, start_date=None, end_date=None):
    """Add board member assignment from Chapter Board Member"""
    if not volunteer:
        frappe.throw(_("Volunteer is required"))
        
    vol_doc = frappe.get_doc("Volunteer", volunteer)
    return vol_doc.add_board_assignment(chapter, role, start_date, end_date)

@frappe.whitelist()
def sync_chapter_board_members():
    """Sync all chapter board members with volunteer assignments"""
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
            # Check if assignment already exists
            exists = False
            for assignment in volunteer.active_assignments:
                if (assignment.assignment_type == "Board Position" and 
                    assignment.reference_doctype == "Chapter" and
                    assignment.reference_name == board_member.chapter and
                    assignment.role == board_member.chapter_role):
                    exists = True
                    break
                    
            if not exists:
                # Add board assignment
                volunteer.add_board_assignment(
                    board_member.chapter, 
                    board_member.chapter_role,
                    board_member.from_date,
                    board_member.to_date
                )
                updated_count += 1
    
    return {"updated_count": updated_count}
