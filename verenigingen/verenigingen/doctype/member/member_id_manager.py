"""
Member ID Counter Management
verenigingen/verenigingen/doctype/member/member_id_manager.py
"""

import frappe
from frappe import _
from frappe.utils import cint
from frappe.model.document import Document

class MemberIDManager:
    """Manages member ID counter with atomic operations"""
    
    @staticmethod
    def get_next_member_id():
        """
        Get the next available member ID with atomic increment
        Returns: int - the next member ID to use
        """
        # Use Redis-based counter for thread safety
        counter_key = "member_id_counter"
        
        # Try to get current counter value
        current_counter = frappe.cache().get(counter_key)
        
        if current_counter is None:
            # Initialize counter from database or settings
            current_counter = MemberIDManager._initialize_counter()
            frappe.cache().set(counter_key, current_counter)
        
        # Atomic increment
        next_id = frappe.cache().incr(counter_key)
        
        # Also update the display field in a Member document for UI purposes
        MemberIDManager._update_display_counter(next_id)
        
        return next_id
    
    @staticmethod
    def _initialize_counter():
        """Initialize the counter from existing data or settings"""
        
        # Check if there's an existing counter in any Member document
        existing_counter = frappe.db.sql("""
            SELECT MAX(next_member_id) as max_counter
            FROM `tabMember`
            WHERE next_member_id IS NOT NULL
        """, as_dict=True)
        
        if existing_counter and existing_counter[0].max_counter:
            return cint(existing_counter[0].max_counter)
        
        # Check highest existing member_id (extract numeric part)
        highest_member = frappe.db.sql("""
            SELECT member_id
            FROM `tabMember`
            WHERE member_id IS NOT NULL
            AND member_id REGEXP '^[0-9]+$'
            ORDER BY CAST(member_id AS UNSIGNED) DESC
            LIMIT 1
        """, as_dict=True)
        
        if highest_member and highest_member[0].member_id:
            return cint(highest_member[0].member_id) + 1
        
        # Fall back to settings
        settings = frappe.get_single("Verenigingen Settings")
        return cint(settings.member_id_start) or 1000
    
    @staticmethod
    def _update_display_counter(next_id):
        """Update the display counter in a Member document for UI"""
        try:
            # Find a system Member document to store the counter, or create one
            system_member = frappe.db.get_value(
                "Member", 
                {"name": "MEMBER-COUNTER-SYSTEM"}, 
                "name"
            )
            
            if not system_member:
                # Create a system member document for counter storage
                counter_doc = frappe.get_doc({
                    "doctype": "Member",
                    "name": "MEMBER-COUNTER-SYSTEM",
                    "first_name": "System",
                    "last_name": "Counter",
                    "email": "system@counter.internal",
                    "status": "System",
                    "next_member_id": next_id + 1  # Next available
                })
                counter_doc.insert(ignore_permissions=True, ignore_mandatory=True)
            else:
                # Update existing counter document
                frappe.db.set_value("Member", system_member, "next_member_id", next_id + 1)
                
        except Exception as e:
            # Don't fail the main process if counter display update fails
            frappe.log_error(f"Failed to update display counter: {str(e)}", "Member ID Counter")
    
    @staticmethod
    def reset_counter(new_value):
        """
        Reset the counter to a specific value
        Args:
            new_value (int): New counter value to set
        """
        if not frappe.has_permission("Member", "write"):
            frappe.throw(_("Insufficient permissions to reset member ID counter"))
        
        # Validate new value
        settings = frappe.get_single("Verenigingen Settings")
        min_value = cint(settings.member_id_start) or 1000
        
        if new_value < min_value:
            frappe.throw(_("Counter value cannot be less than the configured minimum: {0}").format(min_value))
        
        # Check if new value conflicts with existing member IDs
        existing_conflict = frappe.db.sql("""
            SELECT member_id
            FROM `tabMember`
            WHERE member_id IS NOT NULL
            AND CAST(member_id AS UNSIGNED) >= %s
            ORDER BY CAST(member_id AS UNSIGNED) ASC
            LIMIT 1
        """, (new_value,), as_dict=True)
        
        if existing_conflict:
            frappe.msgprint(
                _("Warning: Counter reset to {0}, but member ID {1} already exists. "
                  "This may cause conflicts.").format(new_value, existing_conflict[0].member_id),
                indicator="orange"
            )
        
        # Reset the cache counter
        counter_key = "member_id_counter"
        frappe.cache().set(counter_key, new_value)
        
        # Update display counter
        MemberIDManager._update_display_counter(new_value)
        
        frappe.msgprint(_("Member ID counter reset to {0}").format(new_value), indicator="green")
    
    @staticmethod
    def sync_counter_with_settings():
        """
        Sync counter with Verenigingen Settings if settings value is higher
        This is called when Verenigingen Settings is updated
        """
        settings = frappe.get_single("Verenigingen Settings")
        settings_start = cint(settings.member_id_start) or 1000
        
        counter_key = "member_id_counter"
        current_counter = frappe.cache().get(counter_key)
        
        if current_counter is None:
            current_counter = MemberIDManager._initialize_counter()
        
        # If settings value is higher, update counter
        if settings_start > current_counter:
            frappe.cache().set(counter_key, settings_start)
            MemberIDManager._update_display_counter(settings_start)
            
            frappe.msgprint(
                _("Member ID counter updated to {0} based on Verenigingen Settings").format(settings_start),
                indicator="blue"
            )

# Hook function to be called from Member.before_insert
def generate_member_id(doc):
    """
    Generate member ID for new Member documents
    Args:
        doc: Member document
    """
    if not doc.member_id:
        # Skip system counter document
        if doc.name == "MEMBER-COUNTER-SYSTEM":
            return
            
        next_id = MemberIDManager.get_next_member_id()
        doc.member_id = str(next_id)
        
        # Log the assignment
        frappe.logger().info(f"Assigned member ID {next_id} to {doc.full_name}")

# Validation to prevent manual member_id changes that could break sequence
def validate_member_id_change(doc, method=None):
    """
    Validate member ID changes to prevent sequence conflicts
    """
    if doc.get("__islocal"):
        return  # New document, OK
    
    if doc.name == "MEMBER-COUNTER-SYSTEM":
        return  # System document, OK
    
    # Check if member_id was changed
    if doc.has_value_changed("member_id"):
        old_id = doc.get_db_value("member_id")
        new_id = doc.member_id
        
        # Only allow changes by System Managers
        if not frappe.has_permission("System Manager"):
            frappe.throw(_("Only System Managers can change member IDs"))
        
        # Validate new ID is not in use
        if new_id and frappe.db.exists("Member", {"member_id": new_id, "name": ["!=", doc.name]}):
            frappe.throw(_("Member ID {0} is already in use").format(new_id))
        
        # Log the change
        frappe.logger().info(f"Member ID changed from {old_id} to {new_id} for {doc.name} by {frappe.session.user}")

# Function to get counter statistics for dashboard
@frappe.whitelist()
def get_member_id_statistics():
    """Get statistics about member ID usage"""
    if not frappe.has_permission("Member", "read"):
        frappe.throw(_("Insufficient permissions"))
    
    stats = {}
    
    # Current counter value
    counter_key = "member_id_counter" 
    current_counter = frappe.cache().get(counter_key)
    if current_counter is None:
        current_counter = MemberIDManager._initialize_counter()
    
    stats["next_id"] = current_counter + 1
    stats["current_counter"] = current_counter
    
    # Highest assigned ID
    highest = frappe.db.sql("""
        SELECT MAX(CAST(member_id AS UNSIGNED)) as highest
        FROM `tabMember`
        WHERE member_id IS NOT NULL
        AND member_id REGEXP '^[0-9]+$'
        AND name != 'MEMBER-COUNTER-SYSTEM'
    """, as_dict=True)
    
    stats["highest_assigned"] = highest[0].highest if highest and highest[0].highest else 0
    
    # Total members with numeric IDs
    total = frappe.db.sql("""
        SELECT COUNT(*) as total
        FROM `tabMember`
        WHERE member_id IS NOT NULL
        AND member_id REGEXP '^[0-9]+$'
        AND name != 'MEMBER-COUNTER-SYSTEM'
    """, as_dict=True)
    
    stats["total_with_numeric_ids"] = total[0].total if total else 0
    
    # Gap analysis
    if stats["highest_assigned"] > 0:
        gaps = frappe.db.sql("""
            SELECT member_id
            FROM `tabMember`
            WHERE member_id IS NOT NULL
            AND member_id REGEXP '^[0-9]+$'
            AND name != 'MEMBER-COUNTER-SYSTEM'
            ORDER BY CAST(member_id AS UNSIGNED)
        """, as_dict=True)
        
        used_ids = [int(g.member_id) for g in gaps]
        all_ids = set(range(min(used_ids), max(used_ids) + 1))
        gaps_found = all_ids - set(used_ids)
        stats["gaps"] = sorted(list(gaps_found))[:10]  # Show first 10 gaps
        stats["gap_count"] = len(gaps_found)
    else:
        stats["gaps"] = []
        stats["gap_count"] = 0
    
    return stats
