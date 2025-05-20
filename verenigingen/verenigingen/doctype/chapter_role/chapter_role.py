# verenigingen/verenigingen/doctype/chapter_role/chapter_role.py
from frappe.model.document import Document

class ChapterRole(Document):
    def validate(self):
        # Keep existing validation code
        self.validate_board_members()
        self.validate_postal_codes()
        
        # Update chapter head based on chair role
        self.update_chapter_head()
        
        if not self.route:
            self.route = 'chapters/' + self.scrub(self.name)
    
    def update_chapter_head(self):
        """Update chapter_head based on the board member with a chair role"""
        if not self.board_members:
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
                if role.is_chair:
                    self.chapter_head = board_member.member
                    chair_found = True
                    break
            except frappe.DoesNotExistError:
                # Role might have been deleted
                continue
        
        # If no chair role found, try to find a role with "Chair" in the name
        if not chair_found:
            for board_member in self.board_members:
                if not board_member.is_active or not board_member.chapter_role:
                    continue
                    
                # Check if role name contains "Chair"
                if "chair" in board_member.chapter_role.lower():
                    self.chapter_head = board_member.member
                    chair_found = True
                    break
    
    def get_context(self, context):
        # Keep existing code
        context.no_cache = True
        context.show_sidebar = True
        context.parents = [dict(label='View All Chapters',
            route='chapters', title='View Chapters')]
        
        # Add board members to context for template
        context.board_members = self.get_board_members()
        
        # Get chapter head details for template
        if self.chapter_head:
            try:
                context.chapter_head_member = frappe.get_doc("Member", self.chapter_head)
            except frappe.DoesNotExistError:
                context.chapter_head_member = None
        else:
            context.chapter_head_member = None
            
        # Check if current user is a board member
        context.is_board_member = self.is_board_member()
        context.board_role = self.get_member_role()
        
        return context
