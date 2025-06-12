"""
Chapter-based expense permissions system
Provides granular permission control for volunteer expenses based on chapter roles and amount thresholds
"""

import frappe
from frappe import _
from frappe.utils import flt

class ExpensePermissionManager:
    """Centralized expense permission management"""
    
    # Amount thresholds for different permission levels (in EUR)
    AMOUNT_THRESHOLDS = {
        "basic": 100.0,      # €0-€100: Any active Chapter Board Member
        "financial": 500.0,  # €100-€500: Board Members with Financial permission level
        "admin": float('inf') # €500+: Chapter Chair or Admin permission level
    }
    
    def __init__(self, expense_doc=None):
        self.expense = expense_doc
        self.user = frappe.session.user
        self.user_roles = frappe.get_roles(self.user)
    
    def can_approve_expense(self, expense_doc=None):
        """
        Enhanced permission checking with amount thresholds and role-based permissions
        
        Args:
            expense_doc: Volunteer Expense document (optional if set in __init__)
            
        Returns:
            bool: True if user can approve this expense
        """
        expense = expense_doc or self.expense
        if not expense:
            return False
        
        # System level permissions - can approve any expense
        if self._has_system_level_permission():
            return True
        
        # Get user's volunteer record
        user_volunteer = self._get_user_volunteer()
        if not user_volunteer:
            return False
        
        # Check organization-specific permissions
        if expense.organization_type == "Chapter" and expense.chapter:
            return self._can_approve_chapter_expense(expense, user_volunteer)
        elif expense.organization_type == "Team" and expense.team:
            return self._can_approve_team_expense(expense, user_volunteer)
        
        return False
    
    def get_required_permission_level(self, amount):
        """
        Determine required permission level based on expense amount
        
        Args:
            amount: Expense amount in EUR
            
        Returns:
            str: Required permission level ('basic', 'financial', 'admin')
        """
        amount = flt(amount)
        
        if amount <= self.AMOUNT_THRESHOLDS["basic"]:
            return "basic"
        elif amount <= self.AMOUNT_THRESHOLDS["financial"]:
            return "financial"
        else:
            return "admin"
    
    def get_chapter_approvers(self, chapter_name, required_permission_level="basic"):
        """
        Get list of users who can approve expenses for a specific chapter
        
        Args:
            chapter_name: Name of the chapter
            required_permission_level: Required permission level
            
        Returns:
            list: List of tuples (email, full_name, permission_level)
        """
        approvers = []
        
        # Get active board members for the chapter
        board_members = frappe.get_all("Chapter Board Member",
            filters={
                "parent": chapter_name,
                "is_active": 1
            },
            fields=["volunteer", "chapter_role"]
        )
        
        for board_member in board_members:
            try:
                # Get volunteer and member details
                volunteer = frappe.get_doc("Volunteer", board_member.volunteer)
                if not (hasattr(volunteer, 'member') and volunteer.member):
                    continue
                
                member = frappe.get_doc("Member", volunteer.member)
                if not member.email:
                    continue
                
                # Get chapter role permission level
                role_doc = frappe.get_doc("Chapter Role", board_member.chapter_role)
                permission_level = self._get_role_permission_level(role_doc)
                
                # Check if this board member can approve at the required level
                if self._can_approve_at_level(permission_level, required_permission_level):
                    approvers.append((
                        member.email,
                        member.full_name,
                        permission_level,
                        role_doc.role_name if hasattr(role_doc, 'role_name') else board_member.chapter_role
                    ))
                    
            except Exception as e:
                frappe.log_error(f"Error getting approver {board_member.volunteer}: {str(e)}")
                continue
        
        return approvers
    
    def get_expense_permission_query_conditions(self, user=None):
        """
        Get permission query conditions for expense list filtering
        
        Args:
            user: User email (optional, defaults to current user)
            
        Returns:
            str: SQL where condition for permission filtering
        """
        user = user or self.user
        
        # System level access
        if "System Manager" in frappe.get_roles(user) or "Verenigingen Manager" in frappe.get_roles(user):
            return ""  # No restrictions
        
        # Get user's volunteer record
        user_volunteer = frappe.db.get_value("Volunteer", {"user": user}, "name")
        if not user_volunteer:
            return "1=0"  # No access
        
        conditions = []
        
        # Can see own expenses
        conditions.append(f"`tabVolunteer Expense`.volunteer = '{user_volunteer}'")
        
        # Can see expenses from chapters where user is board member
        user_chapters = frappe.get_all("Chapter Board Member",
            filters={"volunteer": user_volunteer, "is_active": 1},
            pluck="parent",
            distinct=True
        )
        
        if user_chapters:
            chapter_list = "', '".join(user_chapters)
            conditions.append(f"""
                (`tabVolunteer Expense`.organization_type = 'Chapter' 
                 AND `tabVolunteer Expense`.chapter IN ('{chapter_list}'))
            """)
        
        # Can see expenses from teams where user is team lead
        user_teams = frappe.db.sql("""
            SELECT DISTINCT parent 
            FROM `tabTeam Member` 
            WHERE volunteer = %s AND status = 'Active' AND role_type = 'Team Leader'
        """, user_volunteer, pluck=True)
        
        if user_teams:
            team_list = "', '".join(user_teams)
            conditions.append(f"""
                (`tabVolunteer Expense`.organization_type = 'Team' 
                 AND `tabVolunteer Expense`.team IN ('{team_list}'))
            """)
        
        return f"({' OR '.join(conditions)})" if conditions else "1=0"
    
    def validate_approval_permission(self, expense_doc):
        """
        Validate that current user can approve the given expense
        Throws exception if not permitted
        
        Args:
            expense_doc: Volunteer Expense document
        """
        if not self.can_approve_expense(expense_doc):
            required_level = self.get_required_permission_level(expense_doc.amount)
            amount_text = f"€{expense_doc.amount:,.2f}"
            
            if expense_doc.organization_type == "Chapter":
                org_name = expense_doc.chapter
            else:
                org_name = expense_doc.team
            
            frappe.throw(_(
                "You do not have permission to approve this expense. "
                "Amount: {amount} requires {level} level approval for {org}."
            ).format(
                amount=amount_text,
                level=required_level.title(),
                org=org_name
            ))
    
    # Private helper methods
    
    def _has_system_level_permission(self):
        """Check if user has system-level approval permissions"""
        return any(role in self.user_roles for role in [
            "System Manager", 
            "Verenigingen Manager"
        ])
    
    def _get_user_volunteer(self):
        """Get current user's volunteer record"""
        return frappe.db.get_value("Volunteer", {"user": self.user}, "name")
    
    def _can_approve_chapter_expense(self, expense, user_volunteer):
        """Check if user can approve expense for specific chapter"""
        # Get user's board membership for this chapter
        board_membership = frappe.db.get_value("Chapter Board Member", {
            "volunteer": user_volunteer,
            "parent": expense.chapter,
            "is_active": 1
        }, ["chapter_role"], as_dict=True)
        
        if not board_membership:
            return False
        
        # Get role permission level
        role_doc = frappe.get_doc("Chapter Role", board_membership.chapter_role)
        user_permission_level = self._get_role_permission_level(role_doc)
        
        # Get required permission level for this expense amount
        required_level = self.get_required_permission_level(expense.amount)
        
        return self._can_approve_at_level(user_permission_level, required_level)
    
    def _can_approve_team_expense(self, expense, user_volunteer):
        """Check if user can approve expense for specific team"""
        # Check if user is team lead for this team
        is_team_lead = frappe.db.exists("Team Member", {
            "volunteer": user_volunteer,
            "parent": expense.team,
            "status": "Active",
            "role_type": "Team Leader"
        })
        
        # Team leads can approve up to financial level (€500)
        # For amounts > €500, need chapter board approval
        if is_team_lead:
            required_level = self.get_required_permission_level(expense.amount)
            # Team leads have 'financial' level permission
            return self._can_approve_at_level("financial", required_level)
        
        return False
    
    def _get_role_permission_level(self, role_doc):
        """
        Determine permission level from chapter role
        
        Args:
            role_doc: Chapter Role document
            
        Returns:
            str: Permission level ('basic', 'financial', 'admin')
        """
        # Check if role is chair (highest permission)
        if getattr(role_doc, 'is_chair', False):
            return "admin"
        
        # Check permission level field
        if hasattr(role_doc, 'permission_level'):
            level = role_doc.permission_level.lower()
            if level == "admin":
                return "admin"
            elif level == "financial":
                return "financial"
        
        # Default to basic permission
        return "basic"
    
    def _can_approve_at_level(self, user_level, required_level):
        """
        Check if user permission level is sufficient for required level
        
        Args:
            user_level: User's permission level
            required_level: Required permission level
            
        Returns:
            bool: True if user level is sufficient
        """
        level_hierarchy = {"basic": 1, "financial": 2, "admin": 3}
        
        user_rank = level_hierarchy.get(user_level, 0)
        required_rank = level_hierarchy.get(required_level, 999)
        
        return user_rank >= required_rank


# Convenience functions for use throughout the system

@frappe.whitelist()
def can_approve_expense(expense_name):
    """
    Check if current user can approve a specific expense
    
    Args:
        expense_name: Name of the Volunteer Expense document
        
    Returns:
        bool: True if user can approve
    """
    expense = frappe.get_doc("Volunteer Expense", expense_name)
    manager = ExpensePermissionManager()
    return manager.can_approve_expense(expense)

@frappe.whitelist()
def get_chapter_expense_approvers(chapter_name, amount=0):
    """
    Get list of users who can approve expenses for a chapter
    
    Args:
        chapter_name: Name of the chapter
        amount: Expense amount to determine required permission level
        
    Returns:
        list: List of approver details
    """
    manager = ExpensePermissionManager()
    required_level = manager.get_required_permission_level(amount)
    return manager.get_chapter_approvers(chapter_name, required_level)

def get_expense_permission_query_conditions(user=None):
    """
    Get permission query conditions for expense filtering
    Used by the doctype permission system
    
    Args:
        user: User email (optional)
        
    Returns:
        str: SQL where condition
    """
    manager = ExpensePermissionManager()
    return manager.get_expense_permission_query_conditions(user)