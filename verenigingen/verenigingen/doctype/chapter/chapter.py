# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.website.website_generator import WebsiteGenerator
from frappe.utils import getdate

class Chapter(WebsiteGenerator):
    # Keep existing code
    
    def validate(self):
        # Keep existing validation code if present
        self.validate_board_members()
        
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
    
    def get_board_members(self, include_inactive=False):
        """Get list of board members"""
        members = []
        for member in self.board_members:
            if include_inactive or member.is_active:
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
        role_doc = frappe.get_doc("Chapter Role", role)
        return role_doc.permissions_level in ["Financial", "Admin"]
    
    def get_context(self, context):
        context.no_cache = True
        context.show_sidebar = True
        context.parents = [dict(label='View All Chapters',
            route='chapters', title='View Chapters')]
        
        # Add board members to context for template
        context.board_members = self.get_board_members()
        
        # Check if current user is a board member
        context.is_board_member = self.is_board_member()
        context.board_role = self.get_member_role()
        
        return context


def get_list_context(context):
	context.allow_guest = True
	context.no_cache = True
	context.show_sidebar = True
	context.title = 'All Chapters'
	context.no_breadcrumbs = True
	context.order_by = 'creation desc'


@frappe.whitelist()
def leave(title, user_id, leave_reason):
	chapter = frappe.get_doc("Chapter", title)
	for member in chapter.members:
		if member.user == user_id:
			member.enabled = 0
			member.leave_reason = leave_reason
	chapter.save(ignore_permissions=1)
	frappe.db.commit()
	return "Thank you for Feedback"
