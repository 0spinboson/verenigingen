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

# include js in doctype views
doctype_js = {
    "Member": "public/js/member.js",
    "Membership": "public/js/membership.js",
    "Membership Type": "public/js/membership_type.js",
    "Direct Debit Batch": "public/js/direct_debit_batch.js",
}

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
        "on_submit": "verenigingen.verenigingen.doctype.membership_termination_request.membership_termination_request.handle_status_change"
    },
    "Termination Appeals Process": {
        "validate": "verenigingen.validations.validate_appeal_filing",
        "on_update": "verenigingen.verenigingen.doctype.termination_appeals_process.termination_appeals_process.on_update"
    },
    "Member": {
        "before_save": "verenigingen.verenigingen.doctype.member.member.update_termination_status_display"
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
        "verenigingen.utils.termination_utils.process_overdue_termination_requests"
    ],
    "weekly": [
        # Termination system
        "verenigingen.utils.termination_utils.generate_weekly_termination_report"
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
                "Termination Execution Notice"
            ]]
        ]
    },
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
    {
        "doctype": "Role",
        "filters": [
            ["name", "in", [
                "Association Manager",
                "Appeals Reviewer", 
                "Governance Auditor"
            ]]
        ]
    }
]
