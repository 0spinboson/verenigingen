# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version

app_name = "verenigingen"
app_title = "Verenigingen"
app_publisher = "Foppe de Haan"
app_description = "Association Management"
app_icon = "octicon octicon-organization"
app_color = "blue"
app_email = "foppe@veganisme.org"
app_license = "AGPL-3"

# Includes in <head>
# ------------------
on_app_init = ["verenigingen.subscription_override.setup_subscription_override"]
app_include_css = "/assets/verenigingen/css/verenigingen_custom.css"
app_include_js = [
    "/assets/verenigingen/js/termination_dashboard.js"
]

# include js in doctype views
doctype_js = {
    "Member": "public/js/member.js",
    "Membership": "public/js/membership.js",
    "Membership Type": "public/js/membership_type.js",
    "Direct Debit Batch": "public/js/direct_debit_batch.js",
    "Membership Termination Request": "public/js/membership_termination_request.js",
    "Termination Appeals Process": "public/js/termination_appeals_process.js",
    "Expulsion Report Entry": "public/js/expulsion_report_entry.js"
}

# doctype_list_js = {
#     "Membership Termination Request": "public/js/membership_termination_request_list.js",
#     "Termination Appeals Process": "public/js/termination_appeals_process_list.js",
#     "Expulsion Report Entry": "public/js/expulsion_report_entry_list.js"
# }

# Document Events
# ---------------
doc_events = {
    # Core membership system events
    "Membership": {
        "on_submit": "verenigingen.verenigingen.doctype.membership.membership.on_submit",
        "on_cancel": "verenigingen.verenigingen.doctype.membership.membership.on_cancel"
    },
    "Subscription": {
        "on_update": [
            "verenigingen.verenigingen.doctype.membership.membership.update_membership_from_subscription",
        ]
    },
    "Chapter": {
        "validate": "verenigingen.verenigingen.doctype.chapter.chapter.validate_chapter_access",
    },
    "Verenigingen Settings": {
        "on_update": "verenigingen.utils.on_update_verenigingen_settings",
    },
    "Payment Entry": {
        "on_submit": "verenigingen.verenigingen.doctype.member.member.update_member_payment_history",
        "on_cancel": "verenigingen.verenigingen.doctype.member.member.update_member_payment_history",
        "on_trash": "verenigingen.verenigingen.doctype.member.member.update_member_payment_history"
    },
    "Sales Invoice": {
        "before_validate": [
            "verenigingen.utils.apply_tax_exemption_from_source"
        ],
        "on_submit": "verenigingen.verenigingen.doctype.member.member.update_member_payment_history_from_invoice",
        "on_update_after_submit": "verenigingen.verenigingen.doctype.member.member.update_member_payment_history_from_invoice",
        "on_cancel": "verenigingen.verenigingen.doctype.member.member.update_member_payment_history_from_invoice"
    },
    
    # Termination system events
    "Membership Termination Request": {
        "validate": "verenigingen.validations.validate_termination_request",
        "on_update_after_submit": "verenigingen.verenigingen.doctype.membership_termination_request.membership_termination_request.handle_status_change",
        "on_submit": "verenigingen.verenigingen.doctype.membership_termination_request.membership_termination_request.handle_status_change",
        "before_save": "verenigingen.verenigingen.doctype.membership_termination_request.membership_termination_request.before_save",
        "after_insert": "verenigingen.verenigingen.doctype.membership_termination_request.membership_termination_request.after_insert"
    },
    "Termination Appeals Process": {
        "validate": "verenigingen.validations.validate_appeal_filing",
        "before_save": "verenigingen.verenigingen.doctype.termination_appeals_process.termination_appeals_process.before_save",
        "after_insert": "verenigingen.verenigingen.doctype.termination_appeals_process.termination_appeals_process.after_insert",
        "on_update": "verenigingen.verenigingen.doctype.termination_appeals_process.termination_appeals_process.on_update"
    },
    "Expulsion Report Entry": {
        "validate": "verenigingen.verenigingen.doctype.expulsion_report_entry.expulsion_report_entry.validate",
        "before_save": "verenigingen.verenigingen.doctype.expulsion_report_entry.expulsion_report_entry.before_save",
        "after_insert": "verenigingen.verenigingen.doctype.expulsion_report_entry.expulsion_report_entry.after_insert"
    },
    "Member": {
        "before_save": "verenigingen.verenigingen.doctype.member.member.update_termination_status_display"
    },
    
    # Child table events (if needed)
    "Appeal Timeline Entry": {
        "validate": "verenigingen.verenigingen.doctype.appeal_timeline_entry.appeal_timeline_entry.validate"
    },
    "Appeal Communication Entry": {
        "validate": "verenigingen.verenigingen.doctype.appeal_communication_entry.appeal_communication_entry.validate"
    },
    "Termination Audit Entry": {
        "validate": "verenigingen.verenigingen.doctype.termination_audit_entry.termination_audit_entry.validate"
    }
}

# Scheduled Tasks
# ---------------
scheduler_events = {
    "daily": [
        # Core membership system
        "verenigingen.verenigingen.doctype.membership.scheduler.process_expired_memberships",
        "verenigingen.verenigingen.doctype.membership.scheduler.send_renewal_reminders",
        "verenigingen.verenigingen.doctype.membership.scheduler.process_auto_renewals",
        "verenigingen.subscription_handler.process_all_subscriptions",
        "verenigingen.verenigingen.doctype.membership.scheduler.notify_about_orphaned_records",
        "verenigingen.api.membership_application_review.send_overdue_notifications",
        
        # Termination system
        "verenigingen.verenigingen.notification.overdue_appeal_reviews.send_overdue_appeal_notifications",
        "verenigingen.utils.termination_utils.process_overdue_termination_requests"
    ],
    "weekly": [
        # Termination system
        "verenigingen.utils.termination_utils.generate_weekly_termination_report",
        "verenigingen.verenigingen.doctype.membership_termination_request.membership_termination_request.generate_governance_compliance_report"
    ]
}

# Jinja
# -----
jinja = {
    "methods": [
        "verenigingen.utils.jinja_methods"
    ],
    "filters": [
        "verenigingen.utils.jinja_filters"
    ]
}

# Installation
# ------------
after_install = "verenigingen.setup.execute_after_install"
# after_migrate = "verenigingen.verenigingen.notification.overdue_appeal_reviews.create_custom_fields"

# Permissions
# -----------
permission_query_conditions = {
    "Member": "verenigingen.permissions.get_member_permission_query",
    "Membership": "verenigingen.permissions.get_membership_permission_query",
    "Chapter": "verenigingen.verenigingen.doctype.chapter.chapter.get_chapter_permission_query_conditions"
}

has_permission = {
    "Member": "verenigingen.permissions.has_member_permission",
    "Membership": "verenigingen.permissions.has_membership_permission",
}

# Workflow Action Handlers
# -------------------------
workflow_action_handlers = {
    "Membership Termination Request": {
        "Execute": "verenigingen.verenigingen.doctype.membership_termination_request.membership_termination_request.on_workflow_action"
    }
}

# Fixtures
# --------
fixtures = [
    # Email Templates
    {
        "doctype": "Email Template", 
        "filters": [
            ["name", "like", "membership_%"]
        ]
    },
    {
        "doctype": "Email Template",
        "filters": [
            ["name", "in", [
                "Termination Approval Required",
                "Appeal Acknowledgment", 
                "Appeal Decision Notification",
                "Termination Execution Notice",
                "termination_approval_request",
                "appeal_acknowledgment",
                "appeal_decision_notification"
            ]]
        ]
    },
    
    # Workflows
    {
        "doctype": "Workflow",
        "filters": [
            ["name", "in", [
                "Membership Termination Workflow",
                "Termination Appeals Workflow"
            ]]
        ]
    },
    {
        "doctype": "Workflow State",
        "filters": [
            ["workflow_state_name", "in", [
                "Executed"
            ]]
        ]
    },
    {
        "doctype": "Workflow Action Master", 
        "filters": [
            ["workflow_action_name", "in", [
                "Execute"
            ]]
        ]
    },
    
    # Roles
    {
        "doctype": "Role",
        "filters": [
            ["name", "in", [
                "Association Manager",
                "Appeals Reviewer", 
                "Governance Auditor",
                "Chapter Board Member",
                "Member Portal User"
            ]]
        ]
    },
    
    # Reports
    {
        "doctype": "Report",
        "filters": [
            ["name", "in", [
                "Termination Audit Report",
                "Appeals Analysis Report",
                "Termination Compliance Report",
                "Board Position Termination Impact",
                "Expulsion Governance Report",
                "Governance Compliance Report"
            ]]
        ]
    },
    
    # Custom Fields (if you want to export them)
    {
        "doctype": "Custom Field",
        "filters": [
            ["dt", "in", ["Membership Termination Request", "Sales Invoice", "Membership", "Donation"]],
            ["fieldname", "like", "btw_%"]
        ]
    }
]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
#	"verenigingen.auth.validate"
# ]

# Automatically update python controller files
# override_whitelisted_methods = {
#	"frappe.desk.query_report.export_query": "verenigingen.verenigingen.report.termination_audit_report.termination_audit_report.export_audit_report"
# }

# Each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
#	"Member": "verenigingen.verenigingen.dashboard.member_dashboard.get_dashboard_data"
# }

# Exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# User Data Protection
# --------------------

# user_data_fields = [
#	{
#		"doctype": "Member",
#		"filter_by": "user",
#		"redact_fields": ["full_name", "email"],
#		"partial": 1,
#	}
# ]

# Additional termination-specific configurations
termination_config = {
    "appeal_deadline_days": 30,
    "review_deadline_days": 60,
    "governance_notification_roles": ["Association Manager", "System Manager"],
    "enable_automatic_execution": True,
    "require_documentation_for_disciplinary": True
}
