# ===== File: verenigingen/api/suspension_api.py =====
import frappe
from frappe import _
from frappe.utils import today


@frappe.whitelist()
def suspend_member(member_name, suspension_reason, suspend_user=True, suspend_teams=True):
    """
    Suspend a member with specified options
    """
    # Check permissions first
    from verenigingen.permissions import can_terminate_member

    if not can_terminate_member(member_name):
        frappe.throw(_("You don't have permission to suspend this member"))

    from verenigingen.utils.termination_integration import suspend_member_safe

    # Convert string booleans to actual booleans
    suspend_user = frappe.utils.cint(suspend_user)
    suspend_teams = frappe.utils.cint(suspend_teams)

    results = suspend_member_safe(
        member_name=member_name,
        suspension_reason=suspension_reason,
        suspension_date=today(),
        suspend_user=suspend_user,
        suspend_teams=suspend_teams,
    )

    if results.get("success"):
        frappe.msgprint(
            _("Member suspended successfully. Actions taken: {0}").format(
                ", ".join(results.get("actions_taken", []))
            ),
            indicator="orange",
        )
    else:
        frappe.throw(_("Failed to suspend member: {0}").format(results.get("error", "Unknown error")))

    return results


@frappe.whitelist()
def unsuspend_member(member_name, unsuspension_reason):
    """
    Unsuspend a member
    """
    # Check permissions first
    from verenigingen.permissions import can_terminate_member

    if not can_terminate_member(member_name):
        frappe.throw(_("You don't have permission to unsuspend this member"))

    from verenigingen.utils.termination_integration import unsuspend_member_safe

    results = unsuspend_member_safe(member_name=member_name, unsuspension_reason=unsuspension_reason)

    if results.get("success"):
        frappe.msgprint(
            _("Member unsuspended successfully. Actions taken: {0}").format(
                ", ".join(results.get("actions_taken", []))
            ),
            indicator="green",
        )
    else:
        frappe.throw(_("Failed to unsuspend member: {0}").format(results.get("error", "Unknown error")))

    return results


@frappe.whitelist()
def get_suspension_status(member_name):
    """
    Get suspension status for a member
    """
    from verenigingen.utils.termination_integration import get_member_suspension_status

    return get_member_suspension_status(member_name)


@frappe.whitelist()
def can_suspend_member(member_name):
    """
    Check if current user can suspend/unsuspend a member
    """
    # Import the function using frappe's import system to handle any import issues
    try:
        # Use frappe.get_attr to import the function
        can_terminate_member = frappe.get_attr("verenigingen.permissions.can_terminate_member")
        # For suspension, we use the same permission logic as termination
        # since suspension is essentially a temporary termination
        return can_terminate_member(member_name)
    except Exception as e:
        frappe.log_error(f"Import error in can_suspend_member: {e}", "Suspension API Import Error")
        # Fallback to basic permission check
        return _can_suspend_member_fallback(member_name)


def _can_suspend_member_fallback(member_name):
    """
    Fallback permission check for suspension if import fails
    """
    user = frappe.session.user

    # System managers and Association managers always can
    admin_roles = ["System Manager", "Verenigingen Administrator"]
    user_roles = frappe.get_roles(user)
    if any(role in user_roles for role in admin_roles):
        return True

    # Get the member being suspended
    try:
        member_doc = frappe.get_doc("Member", member_name)
    except Exception:
        return False

    # Get the user making the request as a member
    requesting_member = frappe.db.get_value("Member", {"user": user}, "name")
    if not requesting_member:
        return False

    # Check if user is a board member of the member's chapter
    if member_doc.current_chapter_display:
        try:
            chapter_doc = frappe.get_doc("Chapter", member_doc.current_chapter_display)
            # Simple check - if the function exists on the chapter
            if hasattr(chapter_doc, "user_has_board_access"):
                return chapter_doc.user_has_board_access(requesting_member)
        except Exception:
            pass

    return False


@frappe.whitelist()
def get_suspension_preview(member_name):
    """
    Preview what would be affected by suspension
    """
    try:
        member = frappe.get_doc("Member", member_name)

        # Get user account info
        user_email = frappe.db.get_value("Member", member_name, "user")
        has_user_account = bool(user_email and frappe.db.exists("User", user_email))

        # Get team memberships
        active_teams = 0
        team_details = []
        if user_email:
            teams = frappe.get_all(
                "Team Member", filters={"user": user_email, "docstatus": 1}, fields=["parent", "role"]
            )
            active_teams = len(teams)
            team_details = [{"team": t.parent, "role": t.role} for t in teams]

        # Get active memberships
        active_memberships = frappe.get_all(
            "Membership",
            filters={"member": member_name, "status": "Active", "docstatus": 1},
            fields=["name", "membership_type"],
        )

        return {
            "member_status": member.status,
            "has_user_account": has_user_account,
            "active_teams": active_teams,
            "team_details": team_details,
            "active_memberships": len(active_memberships),
            "membership_details": active_memberships,
            "can_suspend": member.status != "Suspended",
            "is_currently_suspended": member.status == "Suspended",
        }

    except Exception as e:
        frappe.logger().error(f"Failed to get suspension preview for {member_name}: {str(e)}")
        return {"error": str(e), "can_suspend": False}


@frappe.whitelist()
def bulk_suspend_members(member_list, suspension_reason, suspend_user=True, suspend_teams=True):
    """
    Suspend multiple members at once
    """
    if isinstance(member_list, str):
        import json

        member_list = json.loads(member_list)

    results = {"success": 0, "failed": 0, "details": []}

    for member_name in member_list:
        try:
            # Check permissions for each member
            from verenigingen.permissions import can_terminate_member

            if not can_terminate_member(member_name):
                results["failed"] += 1
                results["details"].append(
                    {
                        "member": member_name,
                        "status": "failed",
                        "error": "No permission to suspend this member",
                    }
                )
                continue

            # Suspend the member
            from verenigingen.utils.termination_integration import suspend_member_safe

            suspend_result = suspend_member_safe(
                member_name=member_name,
                suspension_reason=suspension_reason,
                suspend_user=frappe.utils.cint(suspend_user),
                suspend_teams=frappe.utils.cint(suspend_teams),
            )

            if suspend_result.get("success"):
                results["success"] += 1
                results["details"].append(
                    {
                        "member": member_name,
                        "status": "success",
                        "actions": suspend_result.get("actions_taken", []),
                    }
                )
            else:
                results["failed"] += 1
                results["details"].append(
                    {
                        "member": member_name,
                        "status": "failed",
                        "error": suspend_result.get("error", "Unknown error"),
                    }
                )

        except Exception as e:
            results["failed"] += 1
            results["details"].append({"member": member_name, "status": "failed", "error": str(e)})

    # Show summary message
    if results["success"] > 0:
        frappe.msgprint(
            _("Bulk suspension completed: {0} successful, {1} failed").format(
                results["success"], results["failed"]
            ),
            indicator="blue",
        )
    else:
        frappe.msgprint(_("Bulk suspension failed: No members were suspended"), indicator="red")


@frappe.whitelist()
def test_bank_details_debug():
    """Test function to debug bank details issue"""
    return {
        "status": "working_from_api_file",
        "user": frappe.session.user,
        "form_data": dict(frappe.local.form_dict) if hasattr(frappe.local, "form_dict") else {},
    }
