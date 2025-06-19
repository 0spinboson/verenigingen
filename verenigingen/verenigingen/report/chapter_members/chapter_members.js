frappe.query_reports["Chapter Members"] = {
	"filters": [
		{
			"fieldname": "chapter",
			"label": __("Chapter"),
			"fieldtype": "Link",
			"options": "Chapter",
			"reqd": 1
		}
	]
};