# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version

app_name = "verenigingen"
app_title = "Verenigingen"
app_publisher = "Verenigingen"
app_description = "Association Management"
app_icon = "octicon octicon-organization"
app_color = "blue"
app_email = "info@verenigingen.org"
app_license = "AGPL-3"

# Required apps - Frappe will ensure these are installed before this app
required_apps = ["erpnext", "payments", "hrms"]

# Includes in <head>
# ------------------
on_app_init = ["verenigingen.setup.doctype_overrides.setup_subscription_override"]
app_include_css = [
    "/assets/verenigingen/css/verenigingen_custom.css",
    "/assets/verenigingen/css/volunteer_portal.css"
]
app_include_js = [
    # Removed termination_dashboard.js as it's a React component and causes import errors
    "/assets/verenigingen/js/member_portal_redirect.js"
]

# include js in doctype views
doctype_js = {
    "Member": "public/js/member.js",
    "Membership": "public/js/membership.js",
    "Membership Type": "public/js/membership_type.js",
    "Direct Debit Batch": "public/js/direct_debit_batch.js",
    "Membership Termination Request": "public/js/membership_termination_request.js",
}

# doctype_list_js = {
#     "Membership Termination Request": "public/js/membership_termination_request_list.js",
#     "Termination Appeals Process": "public/js/termination_appeals_process_list.js",
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
        "on_update": "verenigingen.verenigingen.doctype.member.member_utils.sync_member_counter_with_settings",
    },
    "Payment Entry": {
        "on_submit": "verenigingen.verenigingen.doctype.member.member_utils.update_member_payment_history",
        "on_cancel": "verenigingen.verenigingen.doctype.member.member_utils.update_member_payment_history",
        "on_trash": "verenigingen.verenigingen.doctype.member.member_utils.update_member_payment_history"
    },
    "Sales Invoice": {
        "before_validate": [
            "verenigingen.utils.apply_tax_exemption_from_source"
        ],
        "on_submit": "verenigingen.verenigingen.doctype.member.member_utils.update_member_payment_history_from_invoice",
        "on_update_after_submit": "verenigingen.verenigingen.doctype.member.member_utils.update_member_payment_history_from_invoice",
        "on_cancel": "verenigingen.verenigingen.doctype.member.member_utils.update_member_payment_history_from_invoice"
    },
    
    # Termination system events
    "Membership Termination Request": {
        "validate": "verenigingen.validations.validate_termination_request",
        "on_update_after_submit": "verenigingen.verenigingen.doctype.membership_termination_request.membership_termination_request.handle_status_change",
    },
    "Expulsion Report Entry": {
        "validate": "verenigingen.verenigingen.doctype.expulsion_report_entry.expulsion_report_entry.validate",
        "after_insert": "verenigingen.verenigingen.doctype.expulsion_report_entry.expulsion_report_entry.notify_governance_team",
        "before_save": "verenigingen.verenigingen.doctype.expulsion_report_entry.expulsion_report_entry.update_status_based_on_appeals",
    },
    "Member": {
        "before_save": "verenigingen.verenigingen.doctype.member.member_utils.update_termination_status_display",
        "after_save": "verenigingen.verenigingen.doctype.member.member.handle_fee_override_after_save"
    },
    
    # Donation history tracking
    "Donation": {
        "after_insert": "verenigingen.utils.donation_history_manager.on_donation_insert",
        "on_update": "verenigingen.utils.donation_history_manager.on_donation_update",
        "on_submit": "verenigingen.utils.donation_history_manager.on_donation_submit",
        "on_cancel": "verenigingen.utils.donation_history_manager.on_donation_cancel",
        "on_trash": "verenigingen.utils.donation_history_manager.on_donation_delete"
    },
}

# Scheduled Tasks
# ---------------
scheduler_events = {
    "daily": [
        # Member financial history refresh - runs once daily
        "verenigingen.verenigingen.doctype.member.scheduler.refresh_all_member_financial_histories",
        # Membership duration updates - runs once daily
        "verenigingen.verenigingen.doctype.member.scheduler.update_all_membership_durations",
        # Core membership system
        "verenigingen.verenigingen.doctype.membership.scheduler.process_expired_memberships",
        "verenigingen.verenigingen.doctype.membership.scheduler.send_renewal_reminders",
        "verenigingen.verenigingen.doctype.membership.scheduler.process_auto_renewals",
        "verenigingen.utils.subscription_processing.process_all_subscriptions",
        "verenigingen.verenigingen.doctype.membership.scheduler.notify_about_orphaned_records",
        "verenigingen.api.membership_application_review.send_overdue_notifications",
        
        # Amendment system processing
        "verenigingen.verenigingen.doctype.membership_amendment_request.membership_amendment_request.process_pending_amendments",
        
        # Termination system maintenance
        "verenigingen.utils.termination_utils.process_overdue_termination_requests",
        "verenigingen.utils.termination_utils.audit_termination_compliance",
        
        # SEPA mandate synchronization
        "verenigingen.verenigingen.doctype.member.mixins.sepa_mixin.check_sepa_mandate_discrepancies",
        
        # Contact request automation
        "verenigingen.verenigingen.doctype.member_contact_request.contact_request_automation.process_contact_request_automation",
        
        # Board member role cleanup
        "verenigingen.utils.board_member_role_cleanup.cleanup_expired_board_member_roles",
    ],
    "weekly": [
        # Termination reports and reviews
        "verenigingen.utils.termination_utils.generate_weekly_termination_report",
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

# Installation and Migration Hooks
# ---------------------------------
after_migrate = [
    "verenigingen.verenigingen.doctype.brand_settings.brand_settings.create_default_brand_settings"
]

# Portal Configuration
# --------------------
# Custom portal menu items for association members (overrides ERPNext defaults)
standard_portal_menu_items = [
    {"title": "Member Portal", "route": "/member_portal", "reference_doctype": "", "role": "Verenigingen Member"},
    {"title": "Volunteer Portal", "route": "/volunteer_portal", "reference_doctype": "", "role": "Volunteer"}
]

# Override functions removed - only affecting website/portal, not desk

# Portal context processors
website_context = {
    "get_member_context": "verenigingen.utils.portal_customization.get_member_context"
}

# Installation
# ------------
after_install = [
    "verenigingen.setup.execute_after_install"
]

# Permissions
# -----------
permission_query_conditions = {
    "Member": "verenigingen.permissions.get_member_permission_query",
    "Membership": "verenigingen.permissions.get_membership_permission_query",
    "Chapter": "verenigingen.verenigingen.doctype.chapter.chapter.get_chapter_permission_query_conditions",
    "Chapter Member": "verenigingen.permissions.get_chapter_member_permission_query",
    "Team": "verenigingen.verenigingen.doctype.team.team.get_team_permission_query_conditions",
    "Team Member": "verenigingen.permissions.get_team_member_permission_query",
    "Membership Termination Request": "verenigingen.permissions.get_termination_permission_query",
    "Volunteer": "verenigingen.permissions.get_volunteer_permission_query",
    "Address": "verenigingen.permissions.get_address_permission_query"
}

has_permission = {
    "Member": "verenigingen.permissions.has_member_permission",
    "Membership": "verenigingen.permissions.has_membership_permission", 
    "Address": "verenigingen.permissions.has_address_permission",
}

# Workflow Action Handlers
# -------------------------
workflow_action_handlers = {
    "Membership Termination Workflow": {
        "Approve": "verenigingen.verenigingen.doctype.membership_termination_request.membership_termination_request.on_workflow_action",
        "Execute": "verenigingen.verenigingen.doctype.membership_termination_request.membership_termination_request.on_workflow_action",
        "Reject": "verenigingen.verenigingen.doctype.membership_termination_request.membership_termination_request.on_workflow_action"
    }
}

# Domain setting removed - was hiding desk modules

# Fixtures
# --------
fixtures = [
    # Donation Types
    {
        "doctype": "Donation Type",
        "filters": [
            ["name", "in", [
                "General",
                "Monthly", 
                "One-time",
                "Campaign",
                "Emergency Relief",
                "Membership Support"
            ]]
        ]
    },
    
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
                "expense_approval_request",
                "expense_approved", 
                "expense_rejected",
                "donation_confirmation",
                "donation_payment_confirmation",
                "anbi_tax_receipt",
                "termination_overdue_notification",
                "member_contact_request_received"
            ]]
        ]
    },
    {
        "doctype": "Email Template",
        "filters": [
            ["name", "in", [
                "Termination Approval Required",
                "Termination Execution Notice"
            ]]
        ]
    },
    
    # Workflows
    {
        "doctype": "Workflow",
        "filters": [
            ["name", "in", [
                "Membership Termination Workflow"
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
                "Verenigingen Administrator",
                "Governance Auditor", 
                "Chapter Board Member",
                "Verenigingen Member"
            ]]
        ]
    },
    
    # Reports
    {
        "doctype": "Report",
        "filters": [
            ["name", "in", [
                "Termination Audit Report",
                "Termination Compliance Report"
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

# Session hooks for member portal redirects
on_session_creation = "verenigingen.auth_hooks.on_session_creation"
on_logout = "verenigingen.auth_hooks.on_logout"

# Optional: Request hooks to enforce member portal access
# before_request = "verenigingen.auth_hooks.before_request"

# Custom auth validation (if needed)
# auth_hooks = [
#     "verenigingen.auth_hooks.validate_auth_via_api"
# ]

# Automatically update python controller files
# override_whitelisted_methods = {
#	"frappe.desk.query_report.export_query": "verenigingen.verenigingen.report.termination_audit_report.termination_audit_report.export_audit_report"
# }

# Whitelisted API Methods
# ----------------------
# These methods are automatically whitelisted due to @frappe.whitelist() decorators
# Listed here for documentation purposes:
#
# Termination API:
# - verenigingen.verenigingen.doctype.membership_termination_request.membership_termination_request.get_termination_impact_preview
# - verenigingen.verenigingen.doctype.membership_termination_request.membership_termination_request.execute_safe_member_termination  
# - verenigingen.verenigingen.doctype.membership_termination_request.membership_termination_request.get_member_termination_status
# - verenigingen.verenigingen.doctype.membership_termination_request.membership_termination_request.get_member_termination_history
#
# Permission API:
# - verenigingen.permissions.can_terminate_member_api
# - verenigingen.permissions.can_access_termination_functions_api
#
# Expulsion Report API:
# - verenigingen.verenigingen.doctype.expulsion_report_entry.expulsion_report_entry.get_expulsion_statistics
# - verenigingen.verenigingen.doctype.expulsion_report_entry.expulsion_report_entry.generate_expulsion_governance_report
# - verenigingen.verenigingen.doctype.expulsion_report_entry.expulsion_report_entry.reverse_expulsion_entry
# - verenigingen.verenigingen.doctype.expulsion_report_entry.expulsion_report_entry.get_member_expulsion_history

# Each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
#	"Member": "verenigingen.verenigingen.dashboard.member_dashboard.get_dashboard_data"
# }

# Exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# DocType Class Overrides
# -----------------------
# Override core ERPNext doctypes with custom functionality

# override_doctype_class = {
#	"Payment Entry": "verenigingen.overrides.payment_entry.PaymentEntry"
# }
# Note: Payment Entry override removed - now using standard Sales Invoice flow for donations

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

