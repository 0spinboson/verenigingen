import frappe
from frappe import _
from frappe.model.document import Document
from frappe.contacts.address_and_contact import load_address_and_contact
from frappe.utils import getdate, today, add_days, cint
from frappe.query_builder import DocType

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
            if assignment.end_date and assignment.start_date:
                start_date = getdate(assignment.start_date)
                end_date = getdate(assignment.end_date)
                if start_date > end_date:
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
        board_assignments = []
        
        # Query board memberships for this volunteer using Query Builder
        CBM = DocType('Chapter Board Member')
        Chapter = DocType('Chapter')
        
        board_memberships = (
            frappe.qb.from_(CBM)
            .join(Chapter).on(CBM.parent == Chapter.name)
            .select(
                CBM.name.as_('membership_id'),
                CBM.parent.as_('chapter'),
                CBM.chapter_role.as_('role'),
                CBM.from_date,
                CBM.to_date,
                CBM.is_active,
                Chapter.name.as_('chapter_name')
            )
            .where((CBM.volunteer == self.name) & (CBM.is_active == 1))
        ).run(as_dict=True)
        
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
        
        # Query team memberships for this volunteer using Query Builder
        TM = DocType('Team Member')
        Team = DocType('Team')
        
        team_memberships = (
            frappe.qb.from_(TM)
            .join(Team).on(TM.parent == Team.name)
            .select(
                TM.name.as_('membership_id'),
                TM.parent.as_('team'),
                TM.role,
                TM.role_type,
                TM.from_date,
                TM.to_date,
                TM.status,
                Team.name.as_('team_name'),
                Team.team_type
            )
            .where((TM.volunteer == self.name) & (TM.status == 'Active'))
        ).run(as_dict=True)
        
        for membership in team_memberships:
            team_assignments.append({
                "source_type": "Team",
                "source_doctype": "Team",
                "source_name": membership.team,
                "source_doctype_display": f"{membership.team_type or 'Team'}",
                "source_name_display": membership.team_name,
                "role": membership.role,
                "start_date": membership.from_date,
                "end_date": membership.to_date,
                "is_active": membership.status == "Active",
                "editable": False,
                "source_link": f"/app/team/{membership.team}"
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
        try:
            if not start_date:
                start_date = getdate(today())
            else:
                start_date = getdate(start_date)
                
            if end_date:
                end_date = getdate(end_date)
                if start_date > end_date:
                    frappe.throw(_("Start date cannot be after end date"))
                
            # Validate required fields
            if not activity_type:
                frappe.throw(_("Activity type is required"))
            if not role:
                frappe.throw(_("Role is required"))
                
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
            
        except frappe.ValidationError as e:
            frappe.throw(_("Failed to create activity: {0}").format(str(e)))
        except Exception as e:
            frappe.log_error(f"Error creating volunteer activity: {str(e)}")
            frappe.throw(_("An error occurred while creating the activity"))
    
    @frappe.whitelist()
    def end_activity(self, activity_name, end_date=None, notes=None):
        """End a volunteer activity"""
        try:
            if not end_date:
                end_date = getdate(today())
            else:
                end_date = getdate(end_date)
                
            if not activity_name:
                frappe.throw(_("Activity name is required"))
                
            activity = frappe.get_doc("Volunteer Activity", activity_name)
            
            # Validate that this activity belongs to this volunteer
            if activity.volunteer != self.name:
                frappe.throw(_("You can only end activities assigned to this volunteer"))
                
            activity.status = "Completed"
            activity.end_date = end_date
            
            if notes:
                activity.notes = notes
                
            activity.save()
            
            return True
            
        except frappe.DoesNotExistError:
            frappe.throw(_("Activity {0} not found").format(activity_name))
        except frappe.ValidationError as e:
            frappe.throw(_("Failed to end activity: {0}").format(str(e)))
        except Exception as e:
            frappe.log_error(f"Error ending volunteer activity: {str(e)}")
            frappe.throw(_("An error occurred while ending the activity"))
    
    def get_volunteer_history(self):
        """Get volunteer history in chronological order"""
        history = []
        
        # Get board assignment history using Query Builder and consistent volunteer identification
        CBM = DocType('Chapter Board Member')
        board_history = (
            frappe.qb.from_(CBM)
            .select(
                frappe.qb.terms.ValueWrapper('Board Position').as_('assignment_type'),
                CBM.chapter_role.as_('role'),
                CBM.parent.as_('reference'),
                CBM.from_date.as_('start_date'),
                CBM.to_date.as_('end_date'),
                CBM.is_active
            )
            .where(CBM.volunteer == self.name)
        ).run(as_dict=True)
        
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
        
        # Get team assignment history using Query Builder
        TM = DocType('Team Member')
        team_history = (
            frappe.qb.from_(TM)
            .select(
                frappe.qb.terms.ValueWrapper('Team').as_('assignment_type'),
                TM.role,
                TM.parent.as_('reference'),
                TM.from_date.as_('start_date'),
                TM.to_date.as_('end_date'),
                TM.status
            )
            .where(TM.volunteer == self.name)
        ).run(as_dict=True)
        
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
    try:
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
            existing_vol = frappe.get_doc("Volunteer", existing_volunteer)
            if existing_vol.status not in ["Inactive", "Cancelled"]:
                frappe.throw(_("Member {0} already has an active volunteer record: {1}")
                            .format(member_doc.full_name, existing_volunteer))
            else:
                # Reactivate existing inactive volunteer record
                existing_vol.status = "Active"
                existing_vol.save()
                frappe.msgprint(_("Reactivated existing volunteer record for {0}").format(member_doc.full_name))
                return existing_vol
        
        # Generate organization email based on full name
        domain = frappe.db.get_single_value("Verenigingen Settings", "organization_email_domain") or "example.org"
        name_for_email = member_doc.full_name.replace(" ", ".").lower() if member_doc.full_name else ""
        org_email = f"{name_for_email}@{domain}" if name_for_email else ""
        
        # Create new volunteer record
        volunteer = frappe.new_doc("Volunteer")
        volunteer.update({
            "volunteer_name": member_doc.full_name,
            "member": member_doc.name,
            "email": org_email,
            "personal_email": member_doc.email,
            "preferred_pronouns": getattr(member_doc, 'pronouns', ''),
            "status": "New",
            "start_date": getdate(today())
        })
        
        volunteer.insert(ignore_permissions=True)
        
        frappe.msgprint(_("Volunteer record created for {0}").format(member_doc.full_name))
        return volunteer
        
    except frappe.DoesNotExistError:
        frappe.throw(_("Member record not found"))
    except frappe.ValidationError as e:
        frappe.throw(_("Failed to create volunteer record: {0}").format(str(e)))
    except Exception as e:
        frappe.log_error(f"Error creating volunteer from member: {str(e)}")
        frappe.throw(_("An error occurred while creating the volunteer record"))

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

@frappe.whitelist()
def create_from_member(member=None, member_name=None):
    """Create volunteer from member - alias for create_volunteer_from_member"""
    # Handle both 'member' and 'member_name' parameters for compatibility
    target_member = member or member_name
    
    if not target_member:
        frappe.throw(_("Member is required"))
    
    return create_volunteer_from_member(target_member)
