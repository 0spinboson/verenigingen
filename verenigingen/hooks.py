app_name = "verenigingen"
app_title = "Verenigingen"
app_publisher = "Foppe de Haan"
app_description = "App that adds functionality needed to use it for our association"
app_email = "foppe@veganisme.org"
app_license = "agpl-3.0"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "verenigingen",
# 		"logo": "/assets/verenigingen/logo.png",
# 		"title": "Verenigingen",
# 		"route": "/verenigingen",
# 		"has_permission": "verenigingen.api.permission.has_app_permission"
# 	}
# ]

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
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "verenigingen/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "verenigingen.utils.jinja_methods",
# 	"filters": "verenigingen.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "verenigingen.install.before_install"
# after_install = "verenigingen.install.after_install"
after_install = "verenigingen.setup.setup_verenigingen"

# Uninstallation
# ------------

# before_uninstall = "verenigingen.uninstall.before_uninstall"
# after_uninstall = "verenigingen.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "verenigingen.utils.before_app_install"
# after_app_install = "verenigingen.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "verenigingen.utils.before_app_uninstall"
# after_app_uninstall = "verenigingen.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "verenigingen.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------
scheduler_events = {
	"daily": [
		"verenigingen.verenigingen.doctype.membership.membership.set_expired_status",
	],
}

# scheduler_events = {
# 	"all": [
# 		"verenigingen.tasks.all"
# 	],
# 	"daily": [
# 		"verenigingen.tasks.daily"
# 	],
# 	"hourly": [
# 		"verenigingen.tasks.hourly"
# 	],
# 	"weekly": [
# 		"verenigingen.tasks.weekly"
# 	],
# 	"monthly": [
# 		"verenigingen.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "verenigingen.install.before_tests"
before_tests = "verenigingen.verenigingen.utils.before_tests"
# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "verenigingen.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "verenigingen.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["verenigingen.utils.before_request"]
# after_request = ["verenigingen.utils.after_request"]

# Job Events
# ----------
# before_job = ["verenigingen.utils.before_job"]
# after_job = ["verenigingen.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"verenigingen.auth.validate"
# ]
global_search_doctypes = {
	"Verenigingen": [
		{'doctype': 'Volunteer', 'index': 1},
		{'doctype': 'Membership', 'index': 2},
		{'doctype': 'Member', 'index': 3},
		{'doctype': 'Donor', 'index': 4},
		{'doctype': 'Chapter', 'index': 5},
		{'doctype': 'Volunteer Type', 'index': 6},
		{'doctype': 'Donor Type', 'index': 7},
		{'doctype': 'Membership Type', 'index': 8}
	]
}
# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

