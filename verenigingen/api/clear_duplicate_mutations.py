import frappe
from frappe import _

@frappe.whitelist()
def clear_may_2025_mutations():
    """Clear May 2025 journal entries to allow re-import"""
    
    # Get all journal entries from May 2025 with E-Boekhouden mutation numbers
    may_journals = frappe.get_all("Journal Entry",
        filters={
            "eboekhouden_mutation_nr": ["!=", ""],
            "posting_date": ["between", ["2025-05-01", "2025-05-31"]],
            "docstatus": 1  # Only submitted docs
        },
        fields=["name", "eboekhouden_mutation_nr"])
    
    count = 0
    errors = []
    
    for journal in may_journals:
        try:
            # Cancel and delete the journal entry
            je = frappe.get_doc("Journal Entry", journal.name)
            if je.docstatus == 1:
                je.cancel()
            je.delete()
            count += 1
        except Exception as e:
            errors.append(f"{journal.name}: {str(e)}")
    
    frappe.db.commit()
    
    return {
        "success": True,
        "cleared": count,
        "errors": errors,
        "message": f"Cleared {count} journal entries from May 2025"
    }

@frappe.whitelist()
def clear_and_reimport():
    """Clear May 2025 data and reimport"""
    
    # First clear the duplicates
    clear_result = clear_may_2025_mutations()
    
    if not clear_result["success"]:
        return clear_result
    
    # Then run the migration
    from verenigingen.api.fix_cost_center_and_run import run_soap_migration_for_may
    
    return run_soap_migration_for_may()