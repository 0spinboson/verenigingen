// Report configuration
frappe.query_reports["Pending Membership Applications"] = {
    "filters": [
        {
            "fieldname": "chapter",
            "label": __("Chapter"),
            "fieldtype": "Link",
            "options": "Chapter"
        },
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -1)
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today()
        },
        {
            "fieldname": "membership_type",
            "label": __("Membership Type"),
            "fieldtype": "Link",
            "options": "Membership Type"
        },
        {
            "fieldname": "overdue_only",
            "label": __("Overdue Only (>14 days)"),
            "fieldtype": "Check",
            "default": 0
        }
    ],
    
    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        
        if (column.fieldname == "days_pending") {
            if (value > 14) {
                value = `<span style="color: red; font-weight: bold">${value}</span>`;
            } else if (value > 7) {
                value = `<span style="color: orange">${value}</span>`;
            }
        }
        
        return value;
    },
    
    onload: function(report) {
        // Add custom button to export overdue applications
        report.page.add_inner_button(__("Email Overdue List"), function() {
            frappe.call({
                method: "verenigingen.api.membership_application_review.send_overdue_notifications",
                callback: function(r) {
                    if (r.message) {
                        frappe.msgprint(__("Notifications sent to {0} chapters", [r.message.notified_chapters]));
                    }
                }
            });
        });
        
        // Add button to bulk approve
        report.page.add_inner_button(__("Bulk Actions"), function() {
            show_bulk_actions_dialog(report);
        });
    }
};

function show_bulk_actions_dialog(report) {
    // Get selected rows or all visible rows
    let data = report.data || [];
    
    if (data.length === 0) {
        frappe.msgprint(__("No applications to process"));
        return;
    }
    
    let d = new frappe.ui.Dialog({
        title: __("Bulk Actions"),
        fields: [
            {
                fieldname: "action",
                label: __("Action"),
                fieldtype: "Select",
                options: ["Approve Selected", "Send Reminders"],
                reqd: 1
            },
            {
                fieldname: "membership_type",
                label: __("Default Membership Type"),
                fieldtype: "Link",
                options: "Membership Type",
                depends_on: "eval:doc.action=='Approve Selected'",
                description: __("Used if application doesn't specify a type")
            }
        ],
        primary_action_label: __("Execute"),
        primary_action: function(values) {
            // Implementation would go here
            frappe.msgprint(__("Bulk action executed"));
            d.hide();
        }
    });
    
    d.show();
}
