import frappe


def execute(filters=None):
	if not filters:
		filters = {}
	
	chapter = filters.get("chapter")
	if not chapter:
		frappe.throw("Chapter parameter is required")
	
	# Security check: Only allow board members to see their own chapter
	# or administrators to see any chapter
	if not (frappe.session.user == "Administrator" or 
	        "System Manager" in frappe.get_roles() or 
	        "Verenigingen Administrator" in frappe.get_roles()):
		
		# Check if user is a board member of this chapter
		user_email = frappe.session.user
		member = frappe.db.get_value("Member", {"user": user_email}, "name")
		
		if member:
			# Check via volunteer relationship
			volunteer = frappe.db.get_value("Volunteer", {"member": member}, "name")
			
			if volunteer:
				is_board_member = frappe.db.exists("Chapter Board Member", {
					"parent": chapter,
					"volunteer": volunteer,
					"is_active": 1
				})
				
				if not is_board_member:
					frappe.throw("You can only view members of chapters where you are a board member")
			else:
				frappe.throw("You must be registered as a volunteer to access this report")
		else:
			frappe.throw("You must be a member to access this report")
		
	columns = [
		{
			"fieldname": "member",
			"label": "Member",
			"fieldtype": "Link",
			"options": "Member",
			"width": 200
		},
		{
			"fieldname": "full_name", 
			"label": "Full Name",
			"fieldtype": "Data",
			"width": 200
		},
		{
			"fieldname": "email",
			"label": "Email", 
			"fieldtype": "Data",
			"width": 200
		},
		{
			"fieldname": "chapter_join_date",
			"label": "Join Date",
			"fieldtype": "Date",
			"width": 120
		},
		{
			"fieldname": "enabled",
			"label": "Active",
			"fieldtype": "Check",
			"width": 80
		},
		{
			"fieldname": "leave_reason",
			"label": "Leave Reason",
			"fieldtype": "Data", 
			"width": 150
		}
	]
	
	data = frappe.db.sql("""
		SELECT
			cm.member,
			m.full_name,
			m.email,
			cm.chapter_join_date,
			cm.enabled,
			cm.leave_reason
		FROM
			`tabChapter Member` cm
		INNER JOIN
			`tabMember` m ON cm.member = m.name
		WHERE
			cm.parent = %(chapter)s
			AND cm.enabled = 1
		ORDER BY
			cm.chapter_join_date DESC
	""", {"chapter": chapter}, as_dict=True)
	
	return columns, data