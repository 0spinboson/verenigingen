import frappe
from frappe import _

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {
            "fieldname": "termination_request",
            "label": _("Termination Request"),
            "fieldtype": "Link",
            "options": "Membership Termination Request",
            "width": 180
        },
        {
            "fieldname": "member_name",
            "label": _("Member"),
            "fieldtype": "Data",
            "width": 200
        },
        {
            "fieldname": "chapter",
            "label": _("Chapter"),
            "fieldtype": "Link",
            "options": "Chapter",
            "width": 150
        },
        {
            "fieldname": "board_role",
            "label": _("Board Role"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "role_start_date",
            "label": _("Role Start"),
            "fieldtype": "Date",
            "width": 100
        },
        {
            "fieldname": "role_end_date",
            "label": _("Role End"),
            "fieldtype": "Date",
            "width": 100
        },
        {
            "fieldname": "termination_date",
            "label": _("Termination Date"),
            "fieldtype": "Date",
            "width": 120
        },
        {
            "fieldname": "termination_type",
            "label": _("Termination Type"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "auto_ended",
            "label": _("Auto Ended"),
            "fieldtype": "Check",
            "width": 100
        },
        {
            "fieldname": "volunteer_history_updated",
            "label": _("History Updated"),
            "fieldtype": "Check",
            "width": 120
        }
    ]

def get_data(filters):
    conditions = []
    values = {}
    
    if filters.get("from_date"):
        conditions.append("mtr.execution_date >= %(from_date)s")
        values["from_date"] = filters["from_date"]
        
    if filters.get("to_date"):
        conditions.append("mtr.execution_date <= %(to_date)s")
        values["to_date"] = filters["to_date"]
        
    if filters.get("chapter"):
        conditions.append("cbm.parent = %(chapter)s")
        values["chapter"] = filters["chapter"]
        
    if filters.get("termination_type"):
        conditions.append("mtr.termination_type = %(termination_type)s")
        values["termination_type"] = filters["termination_type"]

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    # Query to find board positions that were ended due to member termination
    query = f"""
        SELECT 
            mtr.name as termination_request,
            mtr.member_name,
            mtr.execution_date as termination_date,
            mtr.termination_type,
            cbm.parent as chapter,
            cbm.chapter_role as board_role,
            cbm.from_date as role_start_date,
            cbm.to_date as role_end_date,
            cbm.is_active,
            v.name as volunteer_id
        FROM `tabMembership Termination Request` mtr
        JOIN `tabMember` m ON mtr.member = m.name
        JOIN `tabVolunteer` v ON m.name = v.member
        JOIN `tabChapter Board Member` cbm ON v.name = cbm.volunteer
        {where_clause}
        AND mtr.status = 'Executed'
        AND mtr.end_board_positions = 1
        ORDER BY mtr.execution_date DESC, cbm.parent, cbm.chapter_role
    """
    
    results = frappe.db.sql(query, values, as_dict=True)
    
    data = []
    for row in results:
        # Check if the board position was automatically ended (role_end_date matches termination_date)
        auto_ended = (row.role_end_date == row.termination_date and not row.is_active)
        
        # Check if volunteer history was updated
        volunteer_history_updated = False
        if row.volunteer_id:
            # Check for completed assignment in volunteer history
            history_check = frappe.db.sql("""
                SELECT COUNT(*) as count
                FROM `tabVolunteer Assignment History` vah
                WHERE vah.parent = %s
                AND vah.reference_doctype = 'Chapter'
                AND vah.reference_name = %s
                AND vah.role = %s
                AND vah.status = 'Completed'
                AND vah.end_date = %s
            """, (row.volunteer_id, row.chapter, row.board_role, row.termination_date))
            
            volunteer_history_updated = history_check[0][0] > 0 if history_check else False
        
        data.append({
            "termination_request": row.termination_request,
            "member_name": row.member_name,
            "chapter": row.chapter,
            "board_role": row.board_role,
            "role_start_date": row.role_start_date,
            "role_end_date": row.role_end_date,
            "termination_date": row.termination_date,
            "termination_type": row.termination_type,
            "auto_ended": 1 if auto_ended else 0,
            "volunteer_history_updated": 1 if volunteer_history_updated else 0
        })
    
    return data
