# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version

app_name = "verenigingen"
app_title = "Verenigingen"
app_publisher = "Your Name"
app_description = "Association Management"
app_icon = "octicon octicon-organization"
app_color = "blue"
app_email = "your-email@example.com"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/verenigingen/css/verenigingen.css"
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

doc_events = {
    "Membership": {
        "on_update": "verenigingen.verenigingen.doctype.membership.membership.on_membership_update",
        "on_submit": "verenigingen.verenigingen.doctype.membership.membership.on_membership_submit",
        "on_cancel": "verenigingen.verenigingen.doctype.membership.membership.on_membership_cancel",
    },
    "Subscription": {
        "on_update": "verenigingen.verenigingen.doctype.membership.membership.update_membership_from_subscription",
    },
    "Chapter": {
        "validate": "verenigingen.verenigingen.doctype.chapter.chapter.validate_chapter_access",
    },
    "Verenigingen Settings": {
        "on_update": "verenigingen.verenigingen.doctype.tax_exemption_handler.on_update_verenigingen_settings",
    },
    "Payment Entry": {
        "on_submit": "verenigingen.verenigingen.doctype.member.member.update_member_payment_history",
        "on_cancel": "verenigingen.verenigingen.doctype.member.member.update_member_payment_history",
        "on_trash": "verenigingen.verenigingen.doctype.member.member.update_member_payment_history"
    }
}

# Scheduled Tasks
# ---------------

scheduler_events = {
    "daily": [
        "verenigingen.verenigingen.doctype.membership.scheduler.process_expired_memberships",
        "verenigingen.verenigingen.doctype.membership.scheduler.send_renewal_reminders",
        "verenigingen.verenigingen.doctype.membership.scheduler.process_auto_renewals"
    ]
}

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
        "doctype": "Workflow",
        "filters": [
            ["name", "=", "Membership Workflow"]
        ]
    },
    {
        "doctype": "Role",
        "filters": [
            ["name", "=", "Association Manager"]
        ]
    },
    {
        "doctype": "Role",
        "filters": [
            ["name", "=", "Assocation Member"]
        ]
    }
]
