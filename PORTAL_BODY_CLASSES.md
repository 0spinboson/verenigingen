# Portal Page Body Classes for Brand Styling

## Overview
This document describes the implementation of dynamic body classes for portal pages to enable proper brand styling scope.

## Changes Made

### 1. Added Website Context Hook (`hooks.py`)
```python
# Website context update hook - adds body classes for brand styling
update_website_context = [
    "verenigingen.utils.portal_customization.add_brand_body_classes"
]
```

### 2. Created Body Class Function (`utils/portal_customization.py`)
Added `add_brand_body_classes()` function that:
- Adds `portal-page` class to all portal pages
- Adds `verenigingen-portal` class to verenigingen-specific pages
- Adds `member-portal` or `volunteer-portal` based on user roles
- Adds `brand-{name}` class based on active brand settings
- Adds `data-portal-page="true"` attribute for additional targeting

### 3. Updated Base Portal Template (`templates/base_portal.html`)
- Removed hardcoded `{% block body_class %}` since it's now set dynamically

## Body Classes Applied

### Base Classes
- `portal-page` - Applied to all portal pages

### Conditional Classes
- `verenigingen-portal` - Applied when path contains verenigingen portal pages
- `member-portal` - Applied when user has "Verenigingen Member" role
- `volunteer-portal` - Applied when user has "Volunteer" role
- `brand-{name}` - Applied based on active brand settings name (e.g., `brand-default-brand-settings`)

## CSS Targeting

The brand CSS in `brand_settings.py` uses these classes to scope styling:

```css
/* Portal-specific brand colors - only applied to portal pages */
body.portal-page .bg-red-600,
.verenigingen-portal .bg-red-600,
[data-portal-page] .bg-red-600 { 
    background-color: var(--brand-primary) !important; 
}
```

## Portal Pages Affected

The following paths are recognized as verenigingen portal pages:
- member_portal
- member_dashboard
- volunteer_portal
- my_addresses
- personal_details
- payment_dashboard
- chapter_dashboard
- my_teams
- team_members
- bank_details
- apply_for_membership
- donate
- contact_request
- chapter_join
- me

## Testing

Run the test script to verify body classes:
```bash
cd /home/frappe/frappe-bench
bench --site [sitename] run-python apps/verenigingen/test_body_classes.py
```

## Notes

1. The body classes are added via the `update_website_context` hook which runs for all web pages
2. The function gracefully handles missing brand settings
3. Multiple classes can be combined (e.g., `portal-page verenigingen-portal member-portal brand-default`)
4. The implementation ensures brand styling only affects portal pages, not the Frappe desk interface