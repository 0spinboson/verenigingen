import frappe
from frappe import _


class ChapterMixin:
    """Mixin for chapter-related functionality"""
    
    def handle_chapter_assignment(self):
        """Handle automatic chapter assignment when primary_chapter changes"""
        if not self.primary_chapter or self.is_new():
            return
            
        if self.has_value_changed('primary_chapter'):
            old_chapter = self.get_doc_before_save().primary_chapter if self.get_doc_before_save() else None
            new_chapter = self.primary_chapter
            
            frappe.logger().info(f"Member {self.name} chapter changing from {old_chapter} to {new_chapter}")
            
            if old_chapter:
                try:
                    old_chapter_doc = frappe.get_doc("Chapter", old_chapter)
                    old_chapter_doc.remove_member(self.name, "Changed to different chapter")
                    frappe.logger().info(f"Removed {self.name} from old chapter {old_chapter}")
                except Exception as e:
                    frappe.logger().error(f"Error removing member from old chapter: {str(e)}")
            
            if new_chapter:
                try:
                    new_chapter_doc = frappe.get_doc("Chapter", new_chapter)
                    added = new_chapter_doc.add_member(self.name)
                    frappe.logger().info(f"Added {self.name} to new chapter {new_chapter}, result: {added}")
                except Exception as e:
                    frappe.logger().error(f"Error adding member to new chapter: {str(e)}")
    
    def get_chapters(self):
        """Get all chapters this member belongs to"""
        if not self._is_chapter_management_enabled():
            return []
            
        chapters = []
        
        if self.primary_chapter:
            chapters.append({
                "chapter": self.primary_chapter,
                "is_primary": 1
            })
        
        member_chapters = frappe.get_all(
            "Chapter Member", 
            filters={"user": self.user, "enabled": 1},
            fields=["parent as chapter"]
        )
        
        for mc in member_chapters:
            if mc.chapter != self.primary_chapter:
                chapters.append({
                    "chapter": mc.chapter,
                    "is_primary": 0
                })
        
        board_chapters = frappe.get_all(
            "Chapter Board Member",
            filters={"member": self.name, "is_active": 1},
            fields=["parent as chapter"]
        )
        
        for bc in board_chapters:
            if not any(c["chapter"] == bc.chapter for c in chapters):
                chapters.append({
                    "chapter": bc.chapter,
                    "is_primary": 0,
                    "is_board": 1
                })
        
        return chapters

    def is_board_member(self, chapter=None):
        """Check if member is a board member of any chapter or a specific chapter"""
        if not self._is_chapter_management_enabled():
            return False
            
        filters = {"member": self.name, "is_active": 1}
        
        if chapter:
            filters["parent"] = chapter
        
        return frappe.db.exists("Chapter Board Member", filters)
    
    def get_board_roles(self):
        """Get all board roles for this member"""
        if not self._is_chapter_management_enabled():
            return []
            
        board_roles = frappe.get_all(
            "Chapter Board Member",
            filters={"member": self.name, "is_active": 1},
            fields=["parent as chapter", "chapter_role as role"]
        )
        
        return board_roles
    
    def _is_chapter_management_enabled(self):
        """Check if chapter management is enabled"""
        try:
            return frappe.db.get_single_value("Verenigingen Settings", "enable_chapter_management") == 1
        except:
            return True