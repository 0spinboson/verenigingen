# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.website.website_generator import WebsiteGenerator
from frappe.utils import getdate, today, add_days, date_diff, now
import re

class Chapter(WebsiteGenerator):
    def validate(self):
        # Keep existing validation code
        self.validate_board_members()
        self.validate_postal_codes()
        self.update_chapter_head()
        if not self.route:
            self.route = 'chapters/' + self.scrub(self.name)
    
    def validate_board_members(self):
        """Validate board members data"""
        # Get all roles that are marked as unique
        unique_roles = {}
        all_roles = frappe.get_all("Chapter Role", 
                                filters={"is_active": 1}, 
                                fields=["name", "is_unique"])
        
        for role in all_roles:
            if role.get("is_unique"):
                unique_roles[role.name] = True
        
        # Ensure each unique role occurs only once for active board members
        active_unique_roles = {}
        for member in self.board_members:
            if member.is_active:
                # Only enforce uniqueness for roles marked as unique
                if member.chapter_role in unique_roles:
                    if member.chapter_role in active_unique_roles:
                        frappe.throw(_("Unique role '{0}' is assigned to multiple active board members").format(member.chapter_role))
                    active_unique_roles[member.chapter_role] = member.volunteer
                
                # Check dates
                if member.to_date and getdate(member.from_date) > getdate(member.to_date):
                    frappe.throw(_("Board member {0} has start date after end date").format(member.volunteer_name))
                
                # Validate volunteer exists
                if not frappe.db.exists("Volunteer", member.volunteer):
                    frappe.throw(_("Volunteer {0} does not exist").format(member.volunteer))
    
    def validate_postal_codes(self):
        """Validate postal code patterns"""
        if not self.postal_codes:
            return
            
        # Split by commas and validate each pattern
        patterns = [p.strip() for p in self.postal_codes.split(',')]
        valid_patterns = []
        
        for pattern in patterns:
            # Check for range pattern (e.g. 1000-1099)
            if '-' in pattern:
                start, end = pattern.split('-', 1)
                if not (start.isdigit() and end.isdigit()):
                    frappe.msgprint(_("Invalid postal code range: {0}. Using numeric ranges only.").format(pattern))
                    continue
                valid_patterns.append(pattern)
            # Check for wildcard pattern (e.g. 10*)
            elif '*' in pattern:
                base = pattern.replace('*', '')
                if not base.isdigit():
                    frappe.msgprint(_("Invalid wildcard postal code: {0}. Base should be numeric.").format(pattern))
                    continue
                valid_patterns.append(pattern)
            # Simple postal code
            elif pattern.isdigit() or pattern.isalnum():
                valid_patterns.append(pattern)
            else:
                frappe.msgprint(_("Invalid postal code pattern: {0}. Skipping.").format(pattern))
        
        # Join valid patterns back together
        self.postal_codes = ', '.join(valid_patterns)

    def update_chapter_head(self):
        """Update chapter_head based on the board member with a chair role"""
        if not self.board_members:
            # If no board members, clear chapter head
            self.chapter_head = None
            return
        
        chair_found = False
        
        # First, find active board members with roles marked as chair
        for board_member in self.board_members:
            if not board_member.is_active or not board_member.chapter_role:
                continue
                
            try:
                # Get the role document
                role = frappe.get_doc("Chapter Role", board_member.chapter_role)
                
                # Check if this role is marked as chair
                if role.is_chair and role.is_active:
                    # Now we need to get the member ID from the volunteer
                    if board_member.volunteer:
                        member_id = frappe.db.get_value("Volunteer", board_member.volunteer, "member")
                        if member_id:
                            self.chapter_head = member_id
                            chair_found = True
                            break
            except frappe.DoesNotExistError:
                # Role might have been deleted
                continue
        
        # If no chair found, clear chapter head
        if not chair_found:
            self.chapter_head = None
        
        return chair_found

    def get_board_members(self, include_inactive=False, role=None):
        """Get list of board members, optionally filtered by role"""
        members = []
        for board_member in self.board_members:
            if (include_inactive or board_member.is_active) and (not role or board_member.chapter_role == role):
                # Get the member ID associated with this volunteer
                member_id = None
                if board_member.volunteer:
                    member_id = frappe.db.get_value("Volunteer", board_member.volunteer, "member")
                
                members.append({
                    "volunteer": board_member.volunteer,
                    "volunteer_name": board_member.volunteer_name,
                    "member": member_id,
                    "email": board_member.email,
                    "role": board_member.chapter_role,
                    "from_date": board_member.from_date,
                    "to_date": board_member.to_date,
                    "is_active": board_member.is_active
                })
        return members
    
    def is_board_member(self, member_name=None, user=None, volunteer_name=None):
        """Check if a member/user/volunteer is on the board of this chapter"""
        if not member_name and not user and not volunteer_name:
            user = frappe.session.user
            member_name = frappe.db.get_value("Member", {"user": user}, "name")
        
        # If we have a member but not a volunteer, try to find the associated volunteer
        if member_name and not volunteer_name:
            volunteer_name = frappe.db.get_value("Volunteer", {"member": member_name}, "name")
                
        if volunteer_name:
            # Check if this volunteer is on the board
            for board_member in self.board_members:
                if board_member.volunteer == volunteer_name and board_member.is_active:
                    return True
        
        # If we couldn't find by volunteer, and we have a member name, let's try to match board members by their member
        if member_name:
            # Get all volunteer IDs associated with this member
            volunteer_ids = [v.name for v in frappe.get_all("Volunteer", filters={"member": member_name})]
            
            # Check if any of these volunteers are on the board
            for board_member in self.board_members:
                if board_member.volunteer in volunteer_ids and board_member.is_active:
                    return True
                    
        return False
    
    def get_member_role(self, member_name=None, user=None, volunteer_name=None):
        """Get the board role of a member/user/volunteer"""
        if not member_name and not user and not volunteer_name:
            user = frappe.session.user
            member_name = frappe.db.get_value("Member", {"user": user}, "name")
        
        # If we have a member but not a volunteer, try to find the associated volunteer
        if member_name and not volunteer_name:
            volunteer_name = frappe.db.get_value("Volunteer", {"member": member_name}, "name")
                
        if volunteer_name:
            # Check if this volunteer is on the board
            for board_member in self.board_members:
                if board_member.volunteer == volunteer_name and board_member.is_active:
                    return board_member.chapter_role
        
        # If we couldn't find by volunteer, and we have a member name, let's try to match board members by their member
        if member_name:
            # Get all volunteer IDs associated with this member
            volunteer_ids = [v.name for v in frappe.get_all("Volunteer", filters={"member": member_name})]
            
            # Check if any of these volunteers are on the board
            for board_member in self.board_members:
                if board_member.volunteer in volunteer_ids and board_member.is_active:
                    return board_member.chapter_role
                    
        return None
    
    def can_view_member_payments(self, member_name=None, user=None):
        """Check if a board member can view payment information"""
        if not member_name and not user:
            user = frappe.session.user
            member_name = frappe.db.get_value("Member", {"user": user}, "name")
            
        if not member_name:
            return False
            
        # Get the role
        role = self.get_member_role(member_name)
        if not role:
            return False
            
        # Check if role has financial permissions
        try:
            role_doc = frappe.get_doc("Chapter Role", role)
            return role_doc.permissions_level in ["Financial", "Admin"]
        except:
            # If role doesn't exist or has no permissions level
            return False
    
    # Update the get_context method to use Member instead of User
    def get_context(self, context):
        context.no_cache = True
        context.show_sidebar = True
        context.parents = [dict(label='View All Chapters',
            route='chapters', title='View Chapters')]
        
        # Convert chapter members to use Member doctype
        chapter_members = []
        for member in self.members:
            if member.enabled:
                try:
                    member_doc = frappe.get_doc("Member", member.member)
                    chapter_members.append({
                        "name": member.member,
                        "full_name": member_doc.full_name,
                        "introduction": member.introduction,
                        "website_url": member.website_url,
                        "enabled": member.enabled
                    })
                except:
                    # Handle case where member might have been deleted
                    pass
        
        # Add members to context for template
        context.members = chapter_members
        
        # Add board members to context for template
        context.board_members = self.get_board_members()
        
        # Check if current user is a board member
        context.is_board_member = self.is_board_member()
        context.board_role = self.get_member_role()
        
        return context
    
    def matches_postal_code(self, postal_code):
        """Check if a postal code matches this chapter's postal code patterns"""
        if not self.postal_codes or not postal_code:
            return False
            
        postal_code = str(postal_code).strip().upper()
        patterns = [p.strip().upper() for p in self.postal_codes.split(',')]
        
        for pattern in patterns:
            # Check for range pattern (e.g. 1000-1099)
            if '-' in pattern:
                start, end = pattern.split('-', 1)
                if start.isdigit() and end.isdigit() and postal_code.isdigit():
                    if int(start) <= int(postal_code) <= int(end):
                        return True
            # Check for wildcard pattern (e.g. 10*)
            elif '*' in pattern:
                # Convert to regex pattern
                regex_pattern = pattern.replace('*', '.*')
                if re.match(f"^{regex_pattern}$", postal_code):
                    return True
            # Simple postal code
            elif postal_code == pattern:
                return True
        
        return False
        
    @frappe.whitelist()
    def add_board_member(self, member, role, from_date=None, to_date=None):
        """Add a new board member to this chapter"""
        if not from_date:
            from_date = today()
            
        # Check if member exists
        if not frappe.db.exists("Member", member):
            frappe.throw(_("Member {0} does not exist").format(member))
            
        # Get member details
        member_doc = frappe.get_doc("Member", member)
        
        # First deactivate any existing board member with the same role
        for board_member in self.board_members:
            if board_member.chapter_role == role and board_member.is_active:
                board_member.is_active = 0
                board_member.to_date = from_date
                
        # Add new board member
        self.append("board_members", {
            "member": member,
            "member_name": member_doc.full_name,
            "email": member_doc.email,
            "chapter_role": role,
            "from_date": from_date,
            "to_date": to_date,
            "is_active": 1
        })
        
        # Also add to chapter members if not already a member
        self._add_to_members(member)
        
        self.save()
        
        # Notify the member
        self.notify_board_member_added(member, role)
        
        return True

    # Helper method to add board member to members
    def _add_to_members(self, member_id):
        """Add a board member to chapter members if not already there"""
        # Check if already a member
        for member in self.members:
            if member.member == member_id:
                if not member.enabled:
                    # Re-enable if disabled
                    member.enabled = 1
                    member.leave_reason = None
                return
        
        # Not a member yet, add them
        member_doc = frappe.get_doc("Member", member_id)
        self.append("members", {
            "member": member_id,
            "member_name": member_doc.full_name,
            "enabled": 1
        })
    
    @frappe.whitelist()
    def remove_board_member(self, volunteer, end_date=None):
        """Remove a board member from this chapter"""
        if not end_date:
            end_date = today()
                
        # Find the active board membership
        found = False
        board_member_data = None
        for board_member in self.board_members:
            if board_member.volunteer == volunteer and board_member.is_active:
                board_member.is_active = 0
                board_member.to_date = end_date
                found = True
                
                # Store board member data for history update
                board_member_data = {
                    'volunteer': board_member.volunteer,
                    'chapter_role': board_member.chapter_role,
                    'from_date': board_member.from_date
                }
                break
                
        if not found:
            frappe.throw(_("Volunteer {0} is not an active board member").format(volunteer))
                
        self.save()
        
        # Update volunteer's assignment history using the standalone function
        if board_member_data:
            update_volunteer_assignment_history(
                board_member_data['volunteer'], 
                self.name, 
                board_member_data['chapter_role'], 
                board_member_data['from_date'], 
                end_date
            )
        
        # Notify the volunteer
        self.notify_board_member_removed(volunteer)
        
        return True
    
    def add_member(self, member_id, introduction=None, website_url=None):
        """Add a member to this chapter"""
        if not member_id:
            frappe.throw(_("Member ID is required"))
            
        # Check if member already exists in chapter
        for member in self.members:
            if member.member == member_id:
                # Already a member - just ensure enabled
                if not member.enabled:
                    member.enabled = 1
                    member.leave_reason = None
                    self.save()
                    return True
                return False
        
        # Get member details
        member_doc = frappe.get_doc("Member", member_id)
        
        # Add to members table
        self.append("members", {
            "member": member_id,
            "member_name": member_doc.full_name,
            "introduction": introduction,
            "website_url": website_url,
            "enabled": 1
        })
        
        self.save()
        return True
    
    def remove_member(self, member_id, leave_reason=None):
        """Remove or disable a member from this chapter"""
        if not member_id:
            frappe.throw(_("Member ID is required"))
            
        # Find the member in the table
        for i, member in enumerate(self.members):
            if member.member == member_id:
                if leave_reason:
                    # Disable with reason
                    member.enabled = 0
                    member.leave_reason = leave_reason
                    self.save()
                else:
                    # Remove completely
                    self.members.remove(member)
                    self.save()
                return True
        
        return False
    
    def get_members(self, include_disabled=False):
        """Get list of members with details"""
        members = []
        
        for member in self.members:
            if include_disabled or member.enabled:
                try:
                    member_doc = frappe.get_doc("Member", member.member)
                    members.append({
                        "id": member.member,
                        "name": member_doc.full_name,
                        "email": member_doc.email,
                        "enabled": member.enabled,
                        "introduction": member.introduction,
                        "website_url": member.website_url,
                        # Add other relevant fields
                    })
                except:
                    # Handle case where member might have been deleted
                    pass
                    
        return members
    
    @frappe.whitelist()
    def transition_board_role(self, member, new_role, transition_date=None):
        """Change a board member's role"""
        if not transition_date:
            transition_date = today()
            
        # Find the current role
        current_role = None
        for board_member in self.board_members:
            if board_member.member == member and board_member.is_active:
                current_role = board_member.chapter_role
                board_member.is_active = 0
                board_member.to_date = transition_date
                break
                
        if not current_role:
            frappe.throw(_("Member {0} is not an active board member").format(member))
            
        # Add new role
        return self.add_board_member(member, new_role, transition_date)
    
    def notify_board_member_added(self, member, role):
        """Send notification when a member is added to the board"""
        member_doc = frappe.get_doc("Member", member)
        
        if not member_doc.email:
            return
            
        # Get email template
        template = "board_member_added"
        if not frappe.db.exists("Email Template", template):
            return
            
        # Prepare context for email
        context = {
            "member": member_doc,
            "chapter": self,
            "role": role
        }
        
        # Send email
        try:
            frappe.sendmail(
                recipients=member_doc.email,
                subject=f"Board Role Assignment: {self.name}",
                template=template,
                args=context,
                header=[_("Board Role Assignment"), "green"]
            )
            frappe.logger().info(f"Board role notification sent to {member_doc.email}")
        except Exception as e:
            frappe.logger().error(f"Failed to send board role notification: {str(e)}")
    
    def notify_board_member_removed(self, member):
        """Send notification when a member is removed from the board"""
        member_doc = frappe.get_doc("Member", member)
        
        if not member_doc.email:
            return
            
        # Get email template
        template = "board_member_removed"
        if not frappe.db.exists("Email Template", template):
            return
            
        # Prepare context for email
        context = {
            "member": member_doc,
            "chapter": self
        }
        
        # Send email
        try:
            frappe.sendmail(
                recipients=member_doc.email,
                subject=f"Board Role Ended: {self.name}",
                template=template,
                args=context,
                header=[_("Board Role Ended"), "red"]
            )
            frappe.logger().info(f"Board removal notification sent to {member_doc.email}")
        except Exception as e:
            frappe.logger().error(f"Failed to send board removal notification: {str(e)}")
    
    def get_chapter_members(self):
        """Get all members of this chapter"""
        return frappe.get_all(
            "Member",
            filters={"primary_chapter": self.name},
            fields=["name", "full_name", "email", "status"]
        )
    
    def get_active_board_roles(self):
        """Get all active board roles"""
        roles = {}
        for member in self.board_members:
            if member.is_active:
                roles[member.chapter_role] = {
                    "member": member.member,
                    "member_name": member.member_name
                }
        return roles

def validate_chapter_access(doc, method=None):
    """
    Validate whether the current user has permission to edit this chapter
    Specifically checks if Association Managers can edit the National Board chapter
    """
    if frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles():
        # Administrators and System Managers can edit any chapter
        return
    
    # Check if this is the National Board chapter
    settings = frappe.get_single("Verenigingen Settings")
    if not settings.get("national_board_chapter"):
        # No national board defined, so no special restrictions
        return
    
    if doc.name == settings.national_board_chapter:
        # This is the National Board chapter
        
        # Check if the user is an Association Manager but not a Verenigingen Manager
        if ("Association Manager" in frappe.get_roles() and 
            "Verenigingen Manager" not in frappe.get_roles()):
            frappe.throw(_("Association Managers cannot edit the National Board chapter. Please contact an administrator."))

def get_list_context(context):
    context.allow_guest = True
    context.no_cache = True
    context.show_sidebar = True
    context.title = 'All Chapters'
    context.no_breadcrumbs = True
    context.order_by = 'creation desc'

def get_chapter_permission_query_conditions(user=None):
    """Get permission query conditions for Chapters"""
    if not user:
        user = frappe.session.user
        
    if "System Manager" in frappe.get_roles(user) or "Verenigingen Manager" in frappe.get_roles(user):
        # Admins can see all chapters
        return ""
        
    # Get chapters where user is a board member
    member = frappe.db.get_value("Member", {"user": user}, "name")
    if member:
        # Get all chapters where this member is on the board
        board_chapters = frappe.db.sql("""
            SELECT parent 
            FROM `tabChapter Board Member` 
            WHERE member = %s AND is_active = 1
        """, (member,), as_dict=True)
        
        if board_chapters:
            chapter_list = ["'" + chapter.parent + "'" for chapter in board_chapters]
            return f"`tabChapter`.name in ({', '.join(chapter_list)})"
    
    # Default - show published chapters
    return "`tabChapter`.published = 1"

# Update leave function to use Member instead of User
@frappe.whitelist()
def leave(title, member_id, leave_reason):
    """Leave a chapter"""
    chapter = frappe.get_doc("Chapter", title)
    for member in chapter.members:
        if member.member == member_id:
            member.enabled = 0
            member.leave_reason = leave_reason
    chapter.save(ignore_permissions=1)
    frappe.db.commit()
    return "Thank you for Feedback"

@frappe.whitelist()
def get_board_memberships(member_name):
    """Get board memberships for a member with proper permission handling"""
    # Query directly using SQL to bypass permission checks
    board_memberships = frappe.db.sql("""
        SELECT cbm.parent, cbm.chapter_role 
        FROM `tabChapter Board Member` cbm
        WHERE cbm.member = %s AND cbm.is_active = 1
    """, (member_name,), as_dict=True)
    
    return board_memberships

@frappe.whitelist()
def remove_from_board(chapter_name, member_name, end_date=None):
    """Remove a member from the board (accessible via API)"""
    if not end_date:
        end_date = today()
        
    chapter = frappe.get_doc("Chapter", chapter_name)
    return chapter.remove_board_member(member_name, end_date)

@frappe.whitelist()
def get_chapter_board_history(chapter_name):
    """Get complete board history for a chapter"""
    chapter = frappe.get_doc("Chapter", chapter_name)
    
    # Get all board members including inactive ones
    board_history = chapter.get_board_members(include_inactive=True)
    
    # Sort by from_date
    board_history.sort(key=lambda x: x.get("from_date"), reverse=True)
    
    return board_history

@frappe.whitelist()
def get_chapter_stats(chapter_name):
    """Get statistics for a chapter"""
    chapter = frappe.get_doc("Chapter", chapter_name)
    
    # Get count of members
    member_count = frappe.db.count("Member", {"primary_chapter": chapter_name})
    
    # Get active board members count
    board_count = 0
    for member in chapter.board_members:
        if member.is_active:
            board_count += 1
    
    # Get recent memberships
    recent_memberships = frappe.get_all(
        "Membership",
        filters={
            "docstatus": 1,
            "member": ["in", frappe.db.get_all("Member", {"primary_chapter": chapter_name}, pluck="name")],
            "start_date": [">=", add_days(today(), -30)]  # Last 30 days
        },
        fields=["name", "member", "start_date", "status"],
        limit=5
    )
    
    return {
        "member_count": member_count,
        "board_count": board_count,
        "recent_memberships": recent_memberships,
        "last_updated": now()
    }

@frappe.whitelist()
def get_chapters_by_postal_code(postal_code):
    """Get chapters that match a postal code"""
    if not postal_code:
        return []
        
    postal_code = str(postal_code).strip().upper()
    
    # Get all published chapters
    chapters = frappe.get_all(
        "Chapter",
        filters={"published": 1},
        fields=["name", "region", "postal_codes", "introduction"]
    )
    
    matching_chapters = []
    
    for chapter in chapters:
        if not chapter.get("postal_codes"):
            continue
            
        # Create chapter object to use the matching method
        chapter_doc = frappe.get_doc("Chapter", chapter.name)
        if chapter_doc.matches_postal_code(postal_code):
            matching_chapters.append(chapter)
    
    return matching_chapters

@frappe.whitelist()
def suggest_chapter_for_member(member_name, postal_code=None, state=None, city=None):
    """Suggest appropriate chapters for a member based on location data"""
    if not is_chapter_management_enabled():
        return {"all_chapters": [], "disabled": True}
        
    result = {
        "matches_by_postal": [],
        "matches_by_region": [],
        "matches_by_city": [],
        "all_chapters": []
    }
    
    # Get all published chapters for baseline
    result["all_chapters"] = frappe.get_all(
        "Chapter",
        filters={"published": 1},
        fields=["name", "region", "postal_codes", "introduction"]
    )
    
    # If no location data, just return all chapters
    if not (postal_code or state or city):
        return result
        
    # First priority: Match by postal code
    if postal_code:
        result["matches_by_postal"] = get_chapters_by_postal_code(postal_code)
        
        # If we have postal matches, that's the most specific, so return early
        if result["matches_by_postal"]:
            return result
    
    # Second priority: Match by region/state
    if state:
        for chapter in result["all_chapters"]:
            if chapter.get("region") and (
                state.lower() in chapter.get("region").lower() or
                chapter.get("region").lower() in state.lower()
            ):
                result["matches_by_region"].append(chapter)
    
    # Third priority: Match by city
    if city:
        for chapter in result["all_chapters"]:
            if (
                city.lower() in chapter.get("name").lower() or
                (chapter.get("region") and city.lower() in chapter.get("region").lower())
            ):
                # Don't add duplicates already in region matches
                if chapter not in result["matches_by_region"]:
                    result["matches_by_city"].append(chapter)
    
    return result

def is_chapter_management_enabled():
    """Check if chapter management is enabled in settings"""
    try:
        return frappe.db.get_single_value("Verenigingen Settings", "enable_chapter_management") == 1
    except:
        # Default to enabled if setting doesn't exist
        return True

# New server-side methods for Chapter.py

@frappe.whitelist()
def assign_member_to_chapter(member, chapter, note=None):
    """
    Assign a member to a chapter - both setting primary_chapter and adding to chapter's members
    """
    if not member or not chapter:
        frappe.throw(_("Member and Chapter are required"))
        
    # Update member's primary chapter
    frappe.db.set_value("Member", member, "primary_chapter", chapter)
    
    # Add member to chapter's members list
    chapter_doc = frappe.get_doc("Chapter", chapter)
    added = chapter_doc.add_member(member)
    
    # Log the change if a note was provided
    if note:
        frappe.get_doc({
            "doctype": "Comment",
            "comment_type": "Info",
            "reference_doctype": "Member",
            "reference_name": member,
            "content": _("Changed chapter to {0}. Note: {1}").format(chapter, note)
        }).insert(ignore_permissions=True)
    
    return {"success": True, "added_to_members": added}

@frappe.whitelist()
def join_chapter(member_name, chapter_name, introduction=None, website_url=None):
    """
    Web method for a member to join a chapter via portal
    """
    # First verify if the member exists
    if not frappe.db.exists("Member", member_name):
        frappe.throw(_("Invalid member"))
        
    # Get member's email to verify permission
    member = frappe.get_doc("Member", member_name)
    
    # Check if user email matches member email for permission
    user_email = frappe.session.user
    if user_email != "Administrator" and user_email != member.email:
        frappe.throw(_("You don't have permission to perform this action"))
    
    # Add member to chapter
    chapter = frappe.get_doc("Chapter", chapter_name)
    added = chapter.add_member(member_name, introduction, website_url)
    
    # If this is the first chapter for the member, set as primary chapter
    if not member.primary_chapter:
        member.primary_chapter = chapter_name
        member.save(ignore_permissions=True)
    
    return {"success": True, "added": added}

@frappe.whitelist()
def leave_chapter(member_name, chapter_name, leave_reason=None):
    """
    Web method for a member to leave a chapter via portal
    """
    # First verify if the member exists
    if not frappe.db.exists("Member", member_name):
        frappe.throw(_("Invalid member"))
        
    # Get member's email to verify permission
    member = frappe.get_doc("Member", member_name)
    
    # Check if user email matches member email for permission
    user_email = frappe.session.user
    if user_email != "Administrator" and user_email != member.email:
        frappe.throw(_("You don't have permission to perform this action"))
    
    # Remove member from chapter
    chapter = frappe.get_doc("Chapter", chapter_name)
    removed = chapter.remove_member(member_name, leave_reason)
    
    # If this was the primary chapter for the member, clear it
    if member.primary_chapter == chapter_name:
        member.primary_chapter = None
        member.save(ignore_permissions=True)
    
    return {"success": True, "removed": removed}

# Add this to chapter.py

@frappe.whitelist()
def get_volunteers_for_chapter(doctype, txt, searchfield, start, page_len, filters):
    """Get volunteers that have members in this chapter"""
    chapter = filters.get('chapter')
    
    # Get members that belong to this chapter
    members = frappe.db.sql("""
        SELECT member
        FROM `tabChapter Member`
        WHERE parent = %s AND enabled = 1
    """, (chapter,), as_dict=True)
    
    member_ids = [m.member for m in members]
    
    if not member_ids:
        return []
    
    # Find volunteers related to these members
    volunteers = frappe.db.sql("""
        SELECT name, volunteer_name, email
        FROM `tabVolunteer`
        WHERE member IN (%s) AND status = 'Active'
        AND (volunteer_name LIKE %s OR email LIKE %s)
        ORDER BY volunteer_name
        LIMIT %s, %s
    """ % (", ".join(["%s"] * len(member_ids)), "%s", "%s", "%s", "%s"),
        tuple(member_ids) + ("%" + txt + "%", "%" + txt + "%", start, page_len), as_dict=True)
    
    return [(v.name, v.volunteer_name, v.email) for v in volunteers]

# Helper method to add board member to members - update this in chapter.py
def _add_to_members(self, member_id):
    """Add a board member to chapter members if not already there"""
    # Check if already a member
    already_member = False
    for member in self.members:
        if member.member == member_id:
            already_member = True
            # If disabled, re-enable
            if not member.enabled:
                member.enabled = 1
                member.leave_reason = None
            break
    
    # Not a member yet, add them
    if not already_member:
        member_doc = frappe.get_doc("Member", member_id)
        self.append("members", {
            "member": member_id,
            "member_name": member_doc.full_name,
            "enabled": 1
        })
        return True
    
    return False

@frappe.whitelist()
def add_board_member(self, volunteer, role, from_date=None, to_date=None):
    """Add a new board member to this chapter"""
    if not from_date:
        from_date = today()
    
    # Check if volunteer exists
    if not frappe.db.exists("Volunteer", volunteer):
        frappe.throw(_("Volunteer {0} does not exist").format(volunteer))
    
    # Get volunteer details
    volunteer_doc = frappe.get_doc("Volunteer", volunteer)
    
    # Check if volunteer has a member
    if not volunteer_doc.member:
        frappe.throw(_("Volunteer {0} does not have an associated member").format(volunteer_doc.volunteer_name))
    
    # Get member details
    member_id = volunteer_doc.member
    member_doc = frappe.get_doc("Member", member_id)
    
    # First deactivate any existing board member with the same role
    for board_member in self.board_members:
        if board_member.chapter_role == role and board_member.is_active:
            board_member.is_active = 0
            board_member.to_date = from_date
    
    # Add new board member
    self.append("board_members", {
        "volunteer": volunteer,
        "volunteer_name": volunteer_doc.volunteer_name,
        "email": volunteer_doc.email,
        "chapter_role": role,
        "from_date": from_date,
        "to_date": to_date,
        "is_active": 1
    })
    
    # Also add to chapter members if not already a member
    self._add_to_members(member_id)
    
    self.save()
    
    # Notify the volunteer
    self.notify_board_member_added(volunteer, role)
    
    return True
# Add this to chapter.py at the bottom, outside the Chapter class

@frappe.whitelist()
def update_volunteer_assignment_history(volunteer_id, chapter_name, role, start_date, end_date=None):
    """Update volunteer's assignment history when removed from board (standalone version)"""
    if not end_date:
        end_date = today()
        
    try:
        volunteer = frappe.get_doc("Volunteer", volunteer_id)
        
        # Check if we already have this assignment in history
        for assignment in volunteer.assignment_history:
            if (assignment.reference_doctype == "Chapter" and 
                assignment.reference_name == chapter_name and
                assignment.role == role and
                getdate(assignment.start_date) == getdate(start_date)):
                
                # Already in history, just update end date and status
                assignment.end_date = end_date
                assignment.status = "Completed"
                volunteer.save(ignore_permissions=True)
                return True
        
        # Not found in history, add new entry
        volunteer.append("assignment_history", {
            "assignment_type": "Board Position",
            "reference_doctype": "Chapter",
            "reference_name": chapter_name,
            "role": role,
            "start_date": start_date,
            "end_date": end_date,
            "status": "Completed"
        })
        
        volunteer.save(ignore_permissions=True)
        frappe.db.commit()
        return True
        
    except Exception as e:
        frappe.log_error(f"Error updating volunteer assignment history: {str(e)}", 
                       "Volunteer Assignment Error")
        return False
