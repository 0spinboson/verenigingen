import frappe
from frappe import _
from frappe.utils import cint

# Store the original function
original_make_test_records = frappe.test_runner.make_test_records

def patched_make_test_records(doctype, verbose=False, force=False, commit=False):
    """Patched version that skips certain doctypes"""
    skip_doctypes = [
        "Warehouse", 
        "Account", 
        "Company",
        # Add other problematic doctypes here
    ]
    
    if doctype in skip_doctypes:
        print(f"Skipping test record creation for {doctype}")
        return
        
    return original_make_test_records(doctype, verbose, force, commit)

# Apply the patch
frappe.test_runner.make_test_records = patched_make_test_records
