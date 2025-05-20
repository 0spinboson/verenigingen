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
        # Ensure each role occurs only once for active board members
        active_roles = {}
        for member in self.board_members:
            if member.is_active:
                if member.chapter_role in active_roles:
                    frappe.throw(_("Role '{0}' is assigned to multiple active board members").format(member.chapter_role))
                active_roles[member.chapter_role] = member.member
                
                # Check dates
                if member.to_date and getdate(member.from_date) > getdate(member.to_date):
                    frappe.throw(_("Board member {0} has start date after end date").format(member.member_name))
                
                # Validate member exists
                if not frappe.db.exists("Member", member.member):
                    frappe.throw(_("Member {0} does not exist").format(member.member))
    
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
                    self.chapter_head = board_member.member
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
        for member in self.board_members:
            if (include_inactive or member.is_active) and (not role or member.chapter_role == role):
                members.append({
                    "member": member.member,
                    "member_name": member.member_name,
                    "email": member.email,
                    "role": member.chapter_role,
                    "from_date": member.from_date,
                    "to_date": member.to_date,
                    "is_active": member.is_active
                })
        return members
    
    def is_board_member(self, member_name=None, user=None):
        """Check if a member/user is on the board of this chapter"""
        if not member_name and not user:
            user = frappe.session.user
            member_name = frappe.db.get_value("Member", {"user": user}, "name")
            
        if not member_name:
            return False
            
        for member in self.board_members:
            if member.member == member_name and member.is_active:
                return True
                
        return False
    
    def get_member_role(self, member_name=None, user=None):
        """Get the board role of a member/user"""
        if not member_name and not user:
            user = frappe.session.user
            member_name = frappe.db.get_value("Member", {"user": user}, "name")
            
        if not member_name:
            return None
            
        for member in self.board_members:
            if member.member == member_name and member.is_active:
                return member.chapter_role
                
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
    def remove_board_member(self, member, end_date=None):
        """Remove a board member from this chapter"""
        if not end_date:
            end_date = today()
            
        # Find the active board membership
        found = False
        for board_member in self.board_members:
            if board_member.member == member and board_member.is_active:
                board_member.is_active = 0
                board_member.to_date = end_date
                found = True
                break
                
        if not found:
            frappe.throw(_("Member {0} is not an active board member").format(member))
            
        self.save()
        
        # Notify the member
        self.notify_board_member_removed(member)
        
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
