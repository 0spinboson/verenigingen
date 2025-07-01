import frappe

# Initialize Frappe
frappe.init(site="dev.veganisme.net")
frappe.connect()

# Check recent migrations
migrations = frappe.db.sql("""
    SELECT name, migration_status, docstatus, current_operation, 
           progress_percentage, error_log, start_time, end_time
    FROM `tabE-Boekhouden Migration`
    ORDER BY creation DESC
    LIMIT 5
""", as_dict=True)

print("Recent E-Boekhouden Migrations:")
print("-" * 80)
for m in migrations:
    print(f"Name: {m.name}")
    print(f"Status: {m.migration_status}")
    print(f"DocStatus: {m.docstatus}")
    print(f"Operation: {m.current_operation}")
    print(f"Progress: {m.progress_percentage}%")
    if m.error_log:
        print(f"Error: {m.error_log[:100]}...")
    print("-" * 80)

# Check if there's a stuck migration
stuck = frappe.db.sql("""
    SELECT name, start_time
    FROM `tabE-Boekhouden Migration`
    WHERE migration_status = 'In Progress'
    AND docstatus = 0
""", as_dict=True)

if stuck:
    print("\nWARNING: Found stuck migrations:")
    for s in stuck:
        print(f"- {s.name} (started: {s.start_time})")
else:
    print("\nNo stuck migrations found.")

frappe.db.commit()
frappe.destroy()