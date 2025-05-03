# Copyright (c) 2023, Verenigingen and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {
            "label": _("Team"),
            "fieldname": "team",
            "fieldtype": "Link",
            "options": "Team",
            "width": 140
        },
        {
            "label": _("Team Lead"),
            "fieldname": "team_lead",
            "fieldtype": "Link",
            "options": "User",
            "width": 140
        },
        {
            "label": _("User"),
            "fieldname": "user",
            "fieldtype": "Link",
            "options": "User",
            "width": 140
        },
        {
            "label": _("User Name"),
            "fieldname": "user_full_name",
            "fieldtype": "Data",
            "width": 180
        },
        {
            "label": _("Role"),
            "fieldname": "team_role",
            "fieldtype": "Link",
            "options": "Team Role",
            "width": 120
        },
        {
            "label": _("Permission Level"),
            "fieldname": "permissions_level",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("From Date"),
            "fieldname": "from_date",
            "fieldtype": "Date",
            "width": 100
        },
        {
            "label": _("To Date"),
            "fieldname": "to_date",
            "fieldtype": "Date",
            "width": 100
        },
        {
            "label": _("Active"),
            "fieldname": "is_active",
            "fieldtype": "Check",
            "width": 70
        }
    ]

def get_data(filters):
    # Start by defining conditions based on filters
    conditions = []
    values = {}
    
    # Apply active only filter
    if filters.get("active_only"):
        conditions.append("tmr.is_active = 1")
    
    # Convert conditions to SQL WHERE clause
    conditions_str = " AND ".join(conditions) if conditions else "1=1"
    
    try:
        # Build and execute the query
        query = """
            SELECT 
                t.name as team,
                t.team_lead,
                tmr.user,
                usr.full_name as user_full_name,
                tmr.team_role,
                tr.permissions_level,
                tmr.from_date,
                tmr.to_date,
                tmr.is_active
            FROM 
                `tabTeam` t
            LEFT JOIN 
                `tabTeam Member Role` tmr ON tmr.parent = t.name
            LEFT JOIN 
                `tabUser` usr ON usr.name = tmr.user
            LEFT JOIN 
                `tabTeam Role` tr ON tr.name = tmr.team_role
            WHERE 
                {conditions}
            ORDER BY 
                t.name, tmr.user
        """.format(conditions=conditions_str)
        
        # Execute the query
        results = frappe.db.sql(query, values=values, as_dict=1)
        return results
        
    except Exception as e:
        # More controlled error logging that won't exceed field limits
        error_msg = str(e)
        if len(error_msg) > 100:
            error_msg = error_msg[:100] + "..."
        frappe.log_error(f"Error in users_by_team report: {error_msg}", "Report Error")
        return []

def get_formatted_data(data):
    # Format data for display if needed
    return data
