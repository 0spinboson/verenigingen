import frappe
from frappe import _

# Jinja methods
def jinja_methods():
    """
    Methods available in jinja templates
    """
    return {
        "format_address": format_address,
        "get_membership_status": get_membership_status,
        "format_date_range": format_date_range
    }

# Jinja filters
def jinja_filters():
    """
    Filters available in jinja templates
    """
    return {
        "format_currency": format_currency,
        "status_color": status_color
    }

# Helper functions for jinja methods

def format_address(address_dict):
    """Format an address dictionary for display"""
    if not address_dict:
        return ""
        
    address_parts = []
    if address_dict.get("address_line1"):
        address_parts.append(address_dict.get("address_line1"))
    if address_dict.get("address_line2"):
        address_parts.append(address_dict.get("address_line2"))
        
    city_state = []
    if address_dict.get("city"):
        city_state.append(address_dict.get("city"))
    if address_dict.get("state"):
        city_state.append(address_dict.get("state"))
    if city_state:
        address_parts.append(", ".join(city_state))
        
    if address_dict.get("postal_code"):
        address_parts.append(address_dict.get("postal_code"))
    if address_dict.get("country"):
        address_parts.append(address_dict.get("country"))
        
    return "<br>".join(address_parts)

def get_membership_status(member_name):
    """Get the current membership status for a member"""
    if not member_name:
        return "Unknown"
        
    memberships = frappe.get_all(
        "Membership",
        filters={
            "member": member_name,
            "status": "Active",
            "docstatus": 1
        },
        fields=["status"],
        order_by="start_date desc",
        limit=1
    )
    
    if memberships:
        return memberships[0].status
    else:
        return "Inactive"

def format_date_range(start_date, end_date):
    """Format a date range for display"""
    if not start_date:
        return ""
        
    from frappe.utils import format_date
    
    if end_date:
        return f"{format_date(start_date)} - {format_date(end_date)}"
    else:
        return f"{format_date(start_date)} - Indefinite"

# Helper functions for jinja filters

def format_currency(value, currency="EUR"):
    """Format a number as currency"""
    from frappe.utils import fmt_money
    
    if not value:
        return fmt_money(0, currency=currency)
        
    return fmt_money(value, currency=currency)

def status_color(status):
    """Get color class for a status value"""
    status_colors = {
        "Active": "green",
        "Pending": "orange",
        "Expired": "red",
        "Cancelled": "grey",
        "Draft": "blue"
    }
    
    return status_colors.get(status, "grey")
