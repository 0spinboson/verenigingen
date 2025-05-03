# Copyright (c) 2023, Your Name and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    if not filters:
        filters = {}
        
    columns = get_columns()
    data = get_data(filters)
    
    return columns, data

def get_columns():
    return [
        {
            "label": "Team",
            "fieldname": "team",
            "fieldtype": "Link",
            "options": "Team",
            "width": 140
        },
        {
            "label": "Team Lead",
            "fieldname": "team_lead",
            "fieldtype": "Link",
            "options": "User",
            "width": 140
        },
        {
            "label": "User",
            "fieldname": "user",
            "fieldtype": "Link",
            "options": "User",
            "width": 140
        },
        {
            "label": "User Name",
            "fieldname": "user_full_name",
            "fieldtype": "Data",
            "width": 180
        },
        {
            "label": "Role",
            "fieldname": "role_name",
            "fieldtype": "Link",
            "options": "Team Role",
            "width": 120
        },
        {
            "label": "Permission Level",
            "fieldname": "permissions_level",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": "From Date",
            "fieldname": "from_date",
            "fieldtype": "Date",
            "width": 100
        },
        {
            "label": "To Date",
            "fieldname": "to_date",
            "fieldtype": "Date",
            "width": 100
        },
        {
            "label": "Active",
            "fieldname": "is_active",
            "fieldtype": "Check",
            "width": 70
        }
    ]

def get_data(filters):
    conditions = []
    values = {}
    
    if filters.get("team"):
        conditions.append("team.name = %(team)s")
        values["team"] = filters.get("team")
        
    if filters.get("user"):
        conditions.append("tmr.user = %(user)s")
        values["user"] = filters.get("user")
        
    if filters.get("role"):
        conditions.append("tmr.role = %(role)s")
        values["role"] = filters.get("role")
        
    if filters.get("active_only"):
        conditions.append("tmr.is_active = 1")
        
    if filters.get("department"):
        conditions.append("team.department = %(department)s")
        values["department"] = filters.get("department")
        
    if filters.get("from_date"):
        conditions.append("(tmr.to_date >= %(from_date)s OR tmr.to_date IS NULL)")
        values["from_date"] = filters.get("from_date")
        
    if filters.get("to_date"):
        conditions.append("tmr.from_date <= %(to_date)s")
        values["to_date"] = filters.get("to_date")
    
    if filters.get("permissions_level"):
        conditions.append("tr.permissions_level = %(permissions_level)s")
        values["permissions_level"] = filters.get("permissions_level")
    
    conditions_str = " AND ".join(conditions)
    if conditions_str:
        conditions_str = " AND " + conditions_str
        
    query = """
        SELECT
            team.name as team,
            team.team_lead,
            tmr.user,
            CONCAT(usr.first_name, ' ', IFNULL(usr.last_name, '')) as user_full_name,
            tmr.role,
            tr.role_name,
            tr.permissions_level,
            tmr.from_date,
            tmr.to_date,
            tmr.is_active
        FROM
            `tabTeam` team
        INNER JOIN
            `tabTeam Member Role` tmr ON tmr.parent = team.name
        LEFT JOIN
            `tabTeam Role` tr ON tmr.role = tr.name
        LEFT JOIN
            `tabUser` usr ON usr.name = tmr.user
        WHERE
            team.docstatus < 2
            {conditions}
        ORDER BY
            team.name, tmr.user
    """.format(conditions=conditions_str)
    
    return frappe.db.sql(query, values=values, as_dict=1)
