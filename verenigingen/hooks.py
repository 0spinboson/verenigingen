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
# Subscription handling - initialize override when app starts
on_app_init = ["verenigingen.subscription_override.setup_subscription_override"]
# include js, css files in header of desk.html
app_include_css = "/assets/verenigingen/css/verenigingen_custom.css"
# app_include_js = "/assets/verenigingen/js/verenigingen.js"

# include js, css files in header of web template
# web_include_css = "/assets/verenigingen/css/verenigingen.css"
# web_include_js = "/assets/verenigingen/js/verenigingen.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "verenigingen/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
    "Member": "public/js/member.js",
    "Membership": "public/js/membership.js",
    "Membership Type": "public/js/membership_type.js",
    "Direct Debit Batch": "public/js/direct_debit_batch.js",
}

# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# Enhanced hooks configuration that includes both original and termination system hooks
def get_doc_events():
    """Get all document events including termination system"""
    
    # Base doc events
    base_events = {
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
        }
    }
    
    # Add termination system events
    termination_events = get_termination_doc_events()
    
    # Merge the events
    for doctype, events in termination_events.items():
        if doctype in base_events:
            # Merge events for existing doctypes
            for event, handler in events.items():
                if event in base_events[doctype]:
                    # Convert to list if not already
                    if not isinstance(base_events[doctype][event], list):
                        base_events[doctype][event] = [base_events[doctype][event]]
                    if isinstance(handler, list):
                        base_events[doctype][event].extend(handler)
                    else:
                        base_events[doctype][event].append(handler)
                else:
                    base_events[doctype][event] = handler
        else:
            base_events[doctype] = events
    
    return base_events
def get_termination_doc_events():
    """Get document events for termination system"""
    return {
        "Membership Termination Request": {
            "validate": "verenigingen.validations.validate_termination_request",
            "on_update_after_submit": "verenigingen.verenigingen.doctype.membership_termination_request.membership_termination_request.handle_status_change",
            "on_submit": "verenigingen.verenigingen.doctype.membership_termination_request.membership_termination_request.handle_status_change"
        },
        "Termination Appeals Process": {
            "validate": "verenigingen.validations.validate_appeal_filing",
            # Remove this line - after_insert is a class method, not a module function
            # "after_insert": "verenigingen.verenigingen.doctype.termination_appeals_process.termination_appeals_process.after_insert",
            "on_update": "verenigingen.verenigingen.doctype.termination_appeals_process.termination_appeals_process.on_update"
        },
        "Member": {
            "before_save": "verenigingen.verenigingen.doctype.member.member.update_termination_status_display"
        }
    }

def get_scheduler_events():
    """Get all scheduler events including termination system"""
    
    base_events = {
        "daily": [
            "verenigingen.verenigingen.doctype.membership.scheduler.process_expired_memberships",
            "verenigingen.verenigingen.doctype.membership.scheduler.send_renewal_reminders",
            "verenigingen.verenigingen.doctype.membership.scheduler.process_auto_renewals",
            "verenigingen.subscription_handler.process_all_subscriptions",
            "verenigingen.verenigingen.doctype.membership.scheduler.notify_about_orphaned_records",
            "verenigingen.api.membership_application_review.send_overdue_notifications"
        ]
    }
    
    # Add termination system scheduler events
    termination_scheduler = {
        "daily": [
            "verenigingen.verenigingen.notification.overdue_appeal_reviews.send_overdue_appeal_notifications"
        ],
        "weekly": [
            "verenigingen.verenigingen.doctype.membership_termination_request.membership_termination_request.get_expulsion_governance_report"
        ]
    }
    
    # Merge scheduler events
    for frequency, handlers in termination_scheduler.items():
        if frequency in base_events:
            base_events[frequency].extend(handlers)
        else:
            base_events[frequency] = handlers
    
    return base_events

# Set the doc_events and scheduler_events
doc_events = get_doc_events()
scheduler_events = get_scheduler_events()

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
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

# before_install = "verenigingen.install.before_install"
after_install = "verenigingen.setup.execute_after_install"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "verenigingen.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
    "Member": "verenigingen.permissions.get_member_permission_query",
    "Membership": "verenigingen.permissions.get_membership_permission_query",
    "Chapter": "verenigingen.verenigingen.doctype.chapter.chapter.get_chapter_permission_query_conditions"
}

# has_permission = {
#	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

has_permission = {
    "Member": "verenigingen.permissions.has_member_permission",
    "Membership": "verenigingen.permissions.has_membership_permission",
}

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
#	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events
# (Now handled by get_doc_events() function above)

# Scheduled Tasks
# ---------------
# (Now handled by get_scheduler_events() function above)

# Testing
# -------

# before_tests = "verenigingen.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
#	"frappe.desk.doctype.event.event.get_events": "verenigingen.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
#	"Task": "verenigingen.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# User Data Protection
# --------------------

# user_data_fields = [
#	{
#		"doctype": "{doctype_1}",
#		"filter_by": "{filter_by}",
#		"redact_fields": ["{field_1}", "{field_2}"],
#		"partial": 1,
#	},
#	{
#		"doctype": "{doctype_2}",
#		"filter_by": "{filter_by}",
#		"partial": 1,
#	},
#	{
#		"doctype": "{doctype_3}",
#		"strict": False,
#	},
#	{
#		"doctype": "{doctype_4}"
#	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
#	"verenigingen.auth.validate"
# ]

# Fixtures - automatically export these doctypes when bench migrate
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
                "Membership Termination Workflow",  # Keep this
                "Termination Appeals Workflow"      # Keep this
                # Remove "Membership Workflow" if it's not related to termination
            ]]
        ]
    },
    {
        "doctype": "Workflow State",
        "filters": [
            ["workflow_state_name", "in", [
                "Executed"  # Only export custom states we create
            ]]
        ]
    },
    {
        "doctype": "Workflow Action Master", 
        "filters": [
            ["workflow_action_name", "in", [
                "Execute"  # Only export custom actions we create
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
workflow_action_handlers = {
    "Membership Termination Request": {
        "Execute": "verenigingen.verenigingen.doctype.membership_termination_request.membership_termination_request.on_workflow_action"
    }
}
