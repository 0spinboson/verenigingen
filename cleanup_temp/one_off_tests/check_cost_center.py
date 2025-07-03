#!/usr/bin/env python
import frappe

# Initialize frappe
frappe.init(site="erp.rockwellsecurity.nl")
frappe.connect()

# Search for cost centers with "maanden - NVV"
cost_centers = frappe.db.get_all("Cost Center",
    filters={"cost_center_name": ["like", "%maanden - NVV%"]},
    fields=["name", "cost_center_name", "is_group", "parent_cost_center", "company"],
    order_by="cost_center_name"
)

print(f"Found {len(cost_centers)} cost centers with 'maanden - NVV':")
for cc in cost_centers:
    print(f"\n- Name: {cc.name}")
    print(f"  Cost Center Name: {cc.cost_center_name}")
    print(f"  Is Group: {cc.is_group}")
    print(f"  Parent: {cc.parent_cost_center}")
    print(f"  Company: {cc.company}")

# Check if "12 maanden - NVV" specifically exists
specific_cc = frappe.db.get_all("Cost Center",
    filters={"cost_center_name": "12 maanden - NVV"},
    fields=["name", "is_group", "parent_cost_center", "company"]
)

if specific_cc:
    print(f"\n\nSpecific '12 maanden - NVV' cost center found:")
    for cc in specific_cc:
        print(f"- Name: {cc.name}")
        print(f"  Is Group: {cc.is_group}")
        print(f"  Parent: {cc.parent_cost_center}")
        print(f"  Company: {cc.company}")
else:
    print("\n\n'12 maanden - NVV' cost center not found")

# Check the default cost center being used in migrations
settings = frappe.get_single("E-Boekhouden Settings")
company = settings.default_company

if company:
    print(f"\n\nDefault company: {company}")
    
    # Check for Main cost center
    main_cc = frappe.db.get_value("Cost Center", {
        "company": company,
        "cost_center_name": "Main",
        "is_group": 0
    }, "name")
    
    print(f"Main cost center: {main_cc}")

frappe.db.close()