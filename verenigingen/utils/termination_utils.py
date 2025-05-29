import frappe
from frappe import _
from frappe.utils import today, getdate

@frappe.whitelist()
def validate_termination_readiness(member_name):
    """
    Validate if a member is ready for termination and return impact assessment
    """
    try:
        member = frappe.get_doc("Member", member_name)
        
        readiness = {
            "ready": True,
            "warnings": [],
            "blockers": [],
            "impact": {
                "active_memberships": 0,
                "sepa_mandates": 0,
                "board_positions": 0,
                "outstanding_invoices": 0,
                "active_subscriptions": 0
            }
        }
        
        # Check active memberships
        active_memberships = frappe.db.count("Membership", {
            "member": member_name,
            "status": ["in", ["Active", "Pending"]],
            "docstatus": 1
        })
        readiness["impact"]["active_memberships"] = active_memberships
        
        if active_memberships > 1:
            readiness["warnings"].append(f"Member has {active_memberships} active memberships")
        
        # Check SEPA mandates
        active_mandates = frappe.db.count("SEPA Mandate", {
            "member": member_name,
            "status": "Active",
            "is_active": 1
        })
        readiness["impact"]["sepa_mandates"] = active_mandates
        
        # Check board positions
        volunteer_records = frappe.get_all("Volunteer", filters={"member": member_name}, fields=["name"])
        board_positions = 0
        for volunteer in volunteer_records:
            board_positions += frappe.db.count("Chapter Board Member", {
                "volunteer": volunteer.name,
                "is_active": 1
            })
        readiness["impact"]["board_positions"] = board_positions
        
        if board_positions > 0:
            readiness["warnings"].append(f"Member holds {board_positions} board position(s)")
        
        # Check outstanding invoices and subscriptions
        if member.customer:
            outstanding_invoices = frappe.db.count("Sales Invoice", {
                "customer": member.customer,
                "docstatus": 1,
                "status": ["in", ["Unpaid", "Overdue", "Partially Paid"]]
            })
            readiness["impact"]["outstanding_invoices"] = outstanding_invoices
            
            active_subscriptions = frappe.db.count("Subscription", {
                "party_type": "Customer",
                "party": member.customer,
                "status": ["in", ["Active", "Past Due"]]
            })
            readiness["impact"]["active_subscriptions"] = active_subscriptions
            
            if outstanding_invoices > 5:
                readiness["warnings"].append(f"Member has {outstanding_invoices} outstanding invoices")
        
        # Check for existing termination requests
        existing_requests = frappe.db.count("Membership Termination Request", {
            "member": member_name,
            "status": ["in", ["Draft", "Pending", "Approved"]]
        })
        
        if existing_requests > 0:
            readiness["ready"] = False
            readiness["blockers"].append("Member already has pending termination request(s)")
        
        return readiness
        
    except Exception as e:
        return {"ready": False, "error": str(e)}

@frappe.whitelist()
def get_termination_impact_summary(member_name):
    """
    Get a summary of what will be affected by member termination
    """
    try:
        readiness = validate_termination_readiness(member_name)
        impact = readiness.get("impact", {})
        
        summary = {
            "member_name": frappe.db.get_value("Member", member_name, "full_name"),
            "total_items_affected": sum(impact.values()),
            "categories": []
        }
        
        if impact.get("active_memberships", 0) > 0:
            summary["categories"].append({
                "category": "Memberships",
                "count": impact["active_memberships"],
                "action": "Will be cancelled"
            })
        
        if impact.get("sepa_mandates", 0) > 0:
            summary["categories"].append({
                "category": "SEPA Mandates", 
                "count": impact["sepa_mandates"],
                "action": "Will be cancelled"
            })
        
        if impact.get("board_positions", 0) > 0:
            summary["categories"].append({
                "category": "Board Positions",
                "count": impact["board_positions"],
                "action": "Will be ended"
            })
        
        if impact.get("outstanding_invoices", 0) > 0:
            summary["categories"].append({
                "category": "Outstanding Invoices",
                "count": impact["outstanding_invoices"],
                "action": "Will be annotated"
            })
        
        if impact.get("active_subscriptions", 0) > 0:
            summary["categories"].append({
                "category": "Active Subscriptions",
                "count": impact["active_subscriptions"],
                "action": "Will be cancelled"
            })
        
        summary["warnings"] = readiness.get("warnings", [])
        summary["blockers"] = readiness.get("blockers", [])
        summary["ready_for_termination"] = readiness.get("ready", False)
        
        return summary
        
    except Exception as e:
        return {"error": str(e)}
