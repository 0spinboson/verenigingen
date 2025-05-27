
// Report configuration
frappe.query_reports["Membership Conversion Analysis"] = {
    "filters": [
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -3)
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today()
        },
        {
            "fieldname": "group_by",
            "label": __("Group By"),
            "fieldtype": "Select",
            "options": ["Day", "Week", "Month", "Quarter"],
            "default": "Month"
        },
        {
            "fieldname": "chapter",
            "label": __("Chapter"),
            "fieldtype": "Link",
            "options": "Chapter"
        },
        {
            "fieldname": "membership_type",
            "label": __("Membership Type"),
            "fieldtype": "Link",
            "options": "Membership Type"
        }
    ]
};
