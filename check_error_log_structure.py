import frappe

# Get Error Log fields
fields = frappe.get_meta("Error Log").get_fieldnames()
print("Error Log fields:", fields)

# Check a sample error log
error = frappe.db.sql("""
    SELECT * FROM `tabError Log` 
    ORDER BY creation DESC 
    LIMIT 1
""", as_dict=True)

if error:
    print("\nSample Error Log columns:", list(error[0].keys()))