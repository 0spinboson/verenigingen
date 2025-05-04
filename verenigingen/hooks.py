# Add/update the following in your hooks.py file

# Scheduler Events
scheduler_events = {
    "daily": [
        # Process expired memberships
        "verenigingen.verenigingen.doctype.membership.scheduler.process_expired_memberships",
        # Send renewal reminders to members
        "verenigingen.verenigingen.doctype.membership.scheduler.send_renewal_reminders",
        # Process auto renewals for memberships
        "verenigingen.verenigingen.doctype.membership.scheduler.process_auto_renewals"
    ],
    "monthly": [
        # You can add monthly batch processing for direct debit here
    ]
}

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
    }
]

# Doc Events - will execute code when certain events happen
doc_events = {
    "Membership": {
        "on_update": "verenigingen.verenigingen.doctype.membership.membership.on_membership_update",
        "on_submit": "verenigingen.verenigingen.doctype.membership.membership.on_membership_submit",
        "on_cancel": "verenigingen.verenigingen.doctype.membership.membership.on_membership_cancel",
    },
    "Subscription": {
        "on_update": "verenigingen.verenigingen.doctype.membership.membership.update_membership_from_subscription",
    }
}

# Doctype JS - client scripts to be loaded with the form
doctype_js = {
    "Member": "public/js/member.js",
    "Membership": "public/js/membership.js",
    "Membership Type": "public/js/membership_type.js",
}

# Permission Handler
permission_query_conditions = {
    "Member": "verenigingen.permissions.get_member_permission_query",
    "Membership": "verenigingen.permissions.get_membership_permission_query",
}

# Define custom roles
role_permissions = [
    {
        "doctype": "Role",
        "role_name": "Membership Manager",
        "modules": ["Verenigingen"]
    },
    {
        "doctype": "Role",
        "role_name": "Membership User",
        "modules": ["Verenigingen"]
    },
    {
        "doctype": "Role",
        "role_name": "Member",
        "desk_access": 0
    }
]
