"""
Summary of E-Boekhouden Migration Updates
========================================

This file documents the changes made to use mutation ID ranges instead of date ranges.

Changes Made:
1. Added get_highest_mutation_number() method to EBoekhoudenSOAPAPI class
   - Determines the highest mutation number in E-Boekhouden
   - Uses a combination of date-based queries and mutation range queries

2. Updated migrate_using_soap() in eboekhouden_soap_migration.py
   - Now uses mutation ID ranges instead of date ranges
   - Processes mutations in batches of 500 (1-500, 501-1000, etc.)
   - Ensures ALL mutations are captured, not just recent ones
   - Supports resuming from a specific mutation number

3. Added duplicate prevention
   - get_processed_mutation_numbers() - tracks already processed mutations
   - is_mutation_processed() - checks if a mutation was already imported
   - Prevents duplicate imports when re-running migration

4. Added resume capability
   - get_last_processed_mutation_number() - finds the highest processed mutation
   - resume_migration() - allows resuming from where migration left off
   - Useful for handling interruptions or failures

5. Created test functions in test_mutation_range_migration.py
   - test_get_highest_mutation_number() - verifies highest mutation detection
   - test_mutation_range_retrieval() - tests batch retrieval
   - test_batch_migration() - tests small batch processing

Usage:
------
# Normal migration (processes all mutations from 1 to highest)
from verenigingen.utils.eboekhouden_soap_migration import migrate_using_soap
result = migrate_using_soap(migration_doc, settings)

# Resume migration from where it left off
from verenigingen.utils.eboekhouden_soap_migration import resume_migration
result = resume_migration(migration_doc_name)

# Test the highest mutation number detection
frappe.enqueue_doc(
    "E-Boekhouden Migration",
    migration_doc_name,
    "test_get_highest_mutation_number",
    queue="long"
)

Benefits:
---------
1. Ensures ALL mutations are captured, not limited by date ranges
2. Handles the 500 record API limit by processing in batches
3. Can resume from interruptions
4. Prevents duplicate imports
5. Provides progress updates during migration
6. More reliable than date-based filtering

Notes:
------
- The SOAP API already supported mutation_nr_from and mutation_nr_to parameters
- Each mutation has a MutatieNr field for tracking
- Batch size is configurable but defaulted to 500
- Progress is reported via frappe.publish_realtime()
"""

import frappe
from frappe import _

@frappe.whitelist()
def get_migration_status():
    """Get current migration status"""
    settings = frappe.get_single("E-Boekhouden Settings")
    company = settings.default_company
    
    if not company:
        return {"error": "No default company set"}
    
    from verenigingen.utils.eboekhouden_soap_migration import (
        get_last_processed_mutation_number,
        get_processed_mutation_numbers
    )
    from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    
    # Get highest mutation number
    api = EBoekhoudenSOAPAPI(settings)
    highest_result = api.get_highest_mutation_number()
    
    if not highest_result["success"]:
        highest = "Unknown"
    else:
        highest = highest_result["highest_mutation_number"]
    
    # Get last processed
    last_processed = get_last_processed_mutation_number(company)
    
    # Get count of processed
    processed_count = len(get_processed_mutation_numbers(company))
    
    return {
        "highest_mutation_number": highest,
        "last_processed_mutation": last_processed,
        "processed_count": processed_count,
        "remaining": highest - last_processed if isinstance(highest, int) and last_processed else "Unknown",
        "progress_percentage": round((last_processed / highest) * 100, 2) if isinstance(highest, int) and highest > 0 else 0
    }

if __name__ == "__main__":
    print(get_migration_status())
