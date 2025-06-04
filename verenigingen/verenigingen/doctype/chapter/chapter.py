# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.website.website_generator import WebsiteGenerator
from frappe.utils import getdate, today, add_days, date_diff, now
import re
import json

# Import managers and validators
from .managers import (
    BoardManager, 
    MemberManager, 
    CommunicationManager, 
    VolunteerIntegrationManager
)
from .validators import ChapterValidator


class Chapter(WebsiteGenerator):
    """
    Chapter document with refactored manager pattern
    
    Core responsibilities:
    - Document lifecycle (validate, save, etc.)
    - Manager coordination
    - Public API compatibility
    
    Delegated responsibilities:
    - Board management -> BoardManager
    - Member management -> MemberManager  
    - Communications -> CommunicationManager
    - Volunteer integration -> VolunteerIntegrationManager
    - Validation -> ChapterValidator
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._managers = {}
        self._validator = None
    
    # ========================================================================
    # CORE DOCUMENT LIFECYCLE
    # ========================================================================
    
    def validate(self):
        """Main validation - delegates to ChapterValidator"""
        # Basic validations
        self._ensure_route()
        
        # Comprehensive validation using validator
        validation_result = self.validator.validate_before_save()
        if not validation_result.is_valid:
            # Log warnings but don't block save
            for warning in validation_result.warnings:
                frappe.msgprint(warning, indicator="orange", alert=True)
            
            # Throw errors that block save
            if validation_result.errors:
                frappe.throw(
                    _("Validation failed: {0}").format(", ".join(validation_result.errors))
                )
        
        # Handle board member changes (delegation to managers)
        self._handle_document_changes()
    
    def before_save(self):
        """Before save hook"""
        # Update chapter head based on board roles
        self.board_manager.handle_board_member_changes(self.get_doc_before_save())
        self.board_manager.handle_board_member_additions(self.get_doc_before_save())
    
    def after_save(self):
        """After save hook"""
        # Sync with volunteer system if needed
        if self.has_value_changed('board_members'):
            self.volunteer_integration_manager.sync_board_members_with_volunteer_system()
    
    def on_update(self):
        """On update hook"""
        self._clear_manager_caches()
    
    # ========================================================================
    # MANAGER PROPERTIES (Lazy Loading)
    # ========================================================================
    
    @property
    def board_manager(self) -> BoardManager:
        """Get board manager instance"""
        if 'board' not in self._managers:
            self._managers['board'] = BoardManager(self)
        return self._managers['board']
    
    @property  
    def member_manager(self) -> MemberManager:
        """Get member manager instance"""
        if 'member' not in self._managers:
            self._managers['member'] = MemberManager(self)
        return self._managers['member']
    
    @property
    def communication_manager(self) -> CommunicationManager:
        """Get communication manager instance"""
        if 'communication' not in self._managers:
            self._managers['communication'] = CommunicationManager(self)
        return self._managers['communication']
    
    @property
    def volunteer_integration_manager(self) -> VolunteerIntegrationManager:
        """Get volunteer integration manager instance"""
        if 'volunteer_integration' not in self._managers:
            self._managers['volunteer_integration'] = VolunteerIntegrationManager(self)
        return self._managers['volunteer_integration']
    
    @property
    def validator(self) -> ChapterValidator:
        """Get validator instance"""
        if self._validator is None:
            self._validator = ChapterValidator(self)
        return self._validator
    
    # ========================================================================
    # BOARD MANAGEMENT API (Delegated)
    # ========================================================================
    
    @frappe.whitelist()
    def add_board_member(self, volunteer, role, from_date=None, to_date=None):
        """Add a new board member - delegates to BoardManager"""
        return self.board_manager.add_board_member(volunteer, role, from_date, to_date)
    
    @frappe.whitelist()
    def remove_board_member(self, volunteer, end_date=None):
        """Remove a board member - delegates to BoardManager"""
        return self.board_manager.remove_board_member(volunteer, end_date)
    
    @frappe.whitelist()
    def transition_board_role(self, volunteer, new_role, transition_date=None):
        """Transition a board member's role - delegates to BoardManager"""
        return self.board_manager.transition_board_role(volunteer, new_role, transition_date)
    
    @frappe.whitelist()
    def bulk_remove_board_members(self, board_members):
        """Bulk remove board members - delegates to BoardManager"""
        return self.board_manager.bulk_remove_board_members(board_members)
    
    @frappe.whitelist()
    def bulk_deactivate_board_members(self, board_members):
        """Bulk deactivate board members - delegates to BoardManager"""
        return self.board_manager.bulk_deactivate_board_members(board_members)
    
    def get_board_members(self, include_inactive=False, role=None):
        """Get board members - delegates to BoardManager"""
        return self.board_manager.get_board_members(include_inactive, role)
    
    def is_board_member(self, member_name=None, user=None, volunteer_name=None):
        """Check if user is board member - delegates to BoardManager"""
        return self.board_manager.is_board_member(member_name, user, volunteer_name)
    
    def get_member_role(self, member_name=None, user=None, volunteer_name=None):
        """Get member's board role - delegates to BoardManager"""
        return self.board_manager.get_member_role(member_name, user, volunteer_name)
    
    def can_view_member_payments(self, member_name=None, user=None):
        """Check payment viewing permissions - delegates to BoardManager"""
        return self.board_manager.can_view_member_payments(member_name, user)
    
    def get_active_board_roles(self):
        """Get active board roles - delegates to BoardManager"""
        return self.board_manager.get_active_board_roles()
    
    # ========================================================================
    # MEMBER MANAGEMENT API (Delegated)
    # ========================================================================
    
    def add_member(self, member_id, introduction=None, website_url=None):
        """Add member to chapter - delegates to MemberManager"""
        result = self.member_manager.add_member(member_id, introduction, website_url)
        return result.get('success', False)
    
    def remove_member(self, member_id, leave_reason=None):
        """Remove member from chapter - delegates to MemberManager"""
        result = self.member_manager.remove_member(member_id, leave_reason)
        return result.get('success', False)
    
    def get_members(self, include_disabled=False):
        """Get chapter members - delegates to MemberManager"""
        return self.member_manager.get_members(include_disabled, with_details=True)
    
    @frappe.whitelist()
    def bulk_add_members(self, member_data_list):
        """Bulk add members - delegates to MemberManager"""
        return self.member_manager.bulk_add_members(member_data_list)
    
    # ========================================================================
    # COMMUNICATION API (Delegated) 
    # ========================================================================
    
    def notify_board_member_added(self, volunteer, role):
        """Notify board member added - delegates to CommunicationManager"""
        self.communication_manager.notify_board_member_added(volunteer, role)
    
    def notify_board_member_removed(self, volunteer):
        """Notify board member removed - delegates to CommunicationManager"""
        self.communication_manager.notify_board_member_removed(volunteer)
    
    @frappe.whitelist()
    def send_chapter_newsletter(self, subject, content, recipient_filter="all"):
        """Send newsletter - delegates to CommunicationManager"""
        return self.communication_manager.send_chapter_newsletter(subject, content, recipient_filter)
    
    def get_communication_history(self, limit=50):
        """Get communication history - delegates to CommunicationManager"""
        return self.communication_manager.get_communication_history(limit)
    
    # ========================================================================
    # VALIDATION API (Delegated)
    # ========================================================================
    
    def validate_postal_codes(self):
        """Validate postal codes"""
        if self.postal_codes:
            result = self.validator.postal_validator.validate_postal_codes(self.postal_codes)
            if not result.is_valid:
                frappe.throw(", ".join(result.errors))
    
    def matches_postal_code(self, postal_code):
        """Check if postal code matches chapter patterns"""
        return self.validator.validate_postal_code_match(postal_code)
    
    # ========================================================================
    # CORE CHAPTER FUNCTIONALITY (Kept in main class)
    # ========================================================================
    
    def update_chapter_head(self):
        """Update chapter_head based on board members with chair roles"""
        if not self.board_members:
            self.chapter_head = None
            return False
        
        chair_found = False
        
        # Find active board members with roles marked as chair
        for board_member in self.board_members:
            if not board_member.is_active or not board_member.chapter_role:
                continue
                
            try:
                # Get the role document
                role = frappe.get_doc("Chapter Role", board_member.chapter_role)
                
                # Check if this role is marked as chair
                if role.is_chair and role.is_active:
                    # Get the member ID from the volunteer
                    if board_member.volunteer:
                        member_id = frappe.db.get_value("Volunteer", board_member.volunteer, "member")
                        if member_id:
                            self.chapter_head = member_id
                            chair_found = True
                            break
            except frappe.DoesNotExistError:
                continue
        
        # If no chair found, clear chapter head
        if not chair_found:
            self.chapter_head = None
        
        return chair_found
    
    def get_context(self, context):
        """Get context for web view"""
        context.no_cache = True
        context.show_sidebar = True
        context.parents = [dict(label='View All Chapters',
            route='chapters', title='View Chapters')]
        
        # Get members for template
        context.members = self.get_members()
        
        # Get board members for template  
        context.board_members = self.get_board_members()
        
        # Check if current user is a board member
        context.is_board_member = self.is_board_member()
        context.board_role = self.get_member_role()
        
        # Add chapter head member details
        if self.chapter_head:
            try:
                context.chapter_head_member = frappe.get_doc("Member", self.chapter_head)
            except:
                context.chapter_head_member = None
        
        return context
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def _ensure_route(self):
        """Ensure route is set"""
        if not self.route:
            self.route = 'chapters/' + self.scrub(self.name)
    
    def _handle_document_changes(self):
        """Handle changes between document versions"""
        old_doc = self.get_doc_before_save()
        if old_doc:
            # Handle board member changes
            self.board_manager.handle_board_member_changes(old_doc)
            self.board_manager.handle_board_member_additions(old_doc)
    
    def _clear_manager_caches(self):
        """Clear all manager caches"""
        for manager in self._managers.values():
            if hasattr(manager, 'clear_cache'):
                manager.clear_cache()
    
    # ========================================================================
    # BACKWARD COMPATIBILITY METHODS
    # ========================================================================
    
    # Keep some key methods for backward compatibility
    def _add_to_members(self, member_id):
        """Backward compatibility - delegates to MemberManager"""
        return self.member_manager.add_member(member_id)
    
    # ========================================================================
    # DASHBOARD AND STATISTICS
    # ========================================================================
    
    def get_chapter_statistics(self):
        """Get comprehensive chapter statistics"""
        return {
            "board_stats": self.board_manager.get_summary(),
            "member_stats": self.member_manager.get_summary(), 
            "communication_stats": self.communication_manager.get_summary(),
            "volunteer_integration_stats": self.volunteer_integration_manager.get_summary(),
            "last_updated": now()
        }


# ============================================================================
# UTILITY FUNCTIONS (Unchanged from original)
# ============================================================================

def validate_chapter_access(doc, method=None):
    """Validate chapter access permissions"""
    if frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles():
        return
    
    settings = frappe.get_single("Verenigingen Settings")
    if not settings.get("national_board_chapter"):
        return
    
    if doc.name == settings.national_board_chapter:
        if ("Association Manager" in frappe.get_roles() and 
            "Association Manager" not in frappe.get_roles()):
            frappe.throw(_("Association Managers cannot edit the National Board chapter. Please contact an administrator."))

def get_list_context(context):
    """Get list context for chapter list view"""
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
        
    if "System Manager" in frappe.get_roles(user) or "Association Manager" in frappe.get_roles(user):
        return ""
        
    # Get chapters where user is a board member
    member = frappe.db.get_value("Member", {"user": user}, "name")
    if member:
        board_chapters = frappe.db.sql("""
            SELECT parent 
            FROM `tabChapter Board Member` 
            WHERE member = %s AND is_active = 1
        """, (member,), as_dict=True)
        
        if board_chapters:
            chapter_list = ["'" + chapter.parent + "'" for chapter in board_chapters]
            return f"`tabChapter`.name in ({', '.join(chapter_list)})"
    
    return "`tabChapter`.published = 1"

@frappe.whitelist()
def leave(title, member_id, leave_reason):
    """Leave a chapter"""
    chapter = frappe.get_doc("Chapter", title)
    return chapter.member_manager.remove_member(member_id, leave_reason)

@frappe.whitelist()
def get_board_memberships(member_name):
    """Get board memberships for a member"""
    board_memberships = frappe.db.sql("""
        SELECT cbm.parent, cbm.chapter_role 
        FROM `tabChapter Board Member` cbm
        WHERE cbm.member = %s AND cbm.is_active = 1
    """, (member_name,), as_dict=True)
    
    return board_memberships

@frappe.whitelist()
def remove_from_board(chapter_name, member_name, end_date=None):
    """Remove a member from the board"""
    chapter = frappe.get_doc("Chapter", chapter_name)
    return chapter.remove_board_member(member_name, end_date)

@frappe.whitelist()
def get_chapter_board_history(chapter_name):
    """Get complete board history for a chapter"""
    chapter = frappe.get_doc("Chapter", chapter_name)
    return chapter.get_board_members(include_inactive=True)

@frappe.whitelist()
def get_chapter_stats(chapter_name):
    """Get statistics for a chapter"""
    chapter = frappe.get_doc("Chapter", chapter_name)
    return chapter.get_chapter_statistics()

@frappe.whitelist()
def get_chapters_by_postal_code(postal_code):
    """Get chapters that match a postal code"""
    if not postal_code:
        return []
        
    chapters = frappe.get_all(
        "Chapter",
        filters={"published": 1},
        fields=["name", "region", "postal_codes", "introduction"]
    )
    
    matching_chapters = []
    
    for chapter in chapters:
        if not chapter.get("postal_codes"):
            continue
            
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
    
    result["all_chapters"] = frappe.get_all(
        "Chapter",
        filters={"published": 1},
        fields=["name", "region", "postal_codes", "introduction"]
    )
    
    if not (postal_code or state or city):
        return result
        
    if postal_code:
        result["matches_by_postal"] = get_chapters_by_postal_code(postal_code)
        if result["matches_by_postal"]:
            return result
    
    if state:
        for chapter in result["all_chapters"]:
            if chapter.get("region") and (
                state.lower() in chapter.get("region").lower() or
                chapter.get("region").lower() in state.lower()
            ):
                result["matches_by_region"].append(chapter)
    
    if city:
        for chapter in result["all_chapters"]:
            if (
                city.lower() in chapter.get("name").lower() or
                (chapter.get("region") and city.lower() in chapter.get("region").lower())
            ):
                if chapter not in result["matches_by_region"]:
                    result["matches_by_city"].append(chapter)
    
    return result

def is_chapter_management_enabled():
    """Check if chapter management is enabled in settings"""
    try:
        return frappe.db.get_single_value("Verenigingen Settings", "enable_chapter_management") == 1
    except:
        return True

@frappe.whitelist()
def assign_member_to_chapter(member, chapter, note=None):
    """Assign a member to a chapter"""
    if not member or not chapter:
        frappe.throw(_("Member and Chapter are required"))
        
    frappe.db.set_value("Member", member, "primary_chapter", chapter)
    
    chapter_doc = frappe.get_doc("Chapter", chapter)
    added = chapter_doc.add_member(member)
    
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
    """Web method for a member to join a chapter via portal"""
    if not frappe.db.exists("Member", member_name):
        frappe.throw(_("Invalid member"))
        
    member = frappe.get_doc("Member", member_name)
    
    user_email = frappe.session.user
    if user_email != "Administrator" and user_email != member.email:
        frappe.throw(_("You don't have permission to perform this action"))
    
    chapter = frappe.get_doc("Chapter", chapter_name)
    result = chapter.member_manager.add_member(member_name, introduction, website_url)
    
    if not member.primary_chapter:
        member.primary_chapter = chapter_name
        member.save(ignore_permissions=True)
    
    return {"success": result.get('success', False), "added": result.get('action') == 'added'}

@frappe.whitelist()
def leave_chapter(member_name, chapter_name, leave_reason=None):
    """Web method for a member to leave a chapter via portal"""
    if not frappe.db.exists("Member", member_name):
        frappe.throw(_("Invalid member"))
        
    member = frappe.get_doc("Member", member_name)
    
    user_email = frappe.session.user
    if user_email != "Administrator" and user_email != member.email:
        frappe.throw(_("You don't have permission to perform this action"))
    
    chapter = frappe.get_doc("Chapter", chapter_name)
    result = chapter.member_manager.remove_member(member_name, leave_reason)
    
    if member.primary_chapter == chapter_name:
        member.primary_chapter = None
        member.save(ignore_permissions=True)
    
    return {"success": result.get('success', False), "removed": result.get('action') in ['removed', 'disabled']}
