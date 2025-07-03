"""
Analyze why duplicate checking is marking 68% of transactions as "already exists"
"""

import frappe
import json
from collections import defaultdict

def analyze_duplicate_checking():
    """Analyze the duplicate checking logic and why so many are marked as already exists"""
    
    # Get company
    settings = frappe.get_single("E-Boekhouden Settings")
    company = settings.default_company
    
    if not company:
        print("No default company set")
        return
    
    print(f"Analyzing duplicate checking for company: {company}")
    print("=" * 60)
    
    # 1. Check Sales Invoices
    print("\n1. Sales Invoice Analysis:")
    print("-" * 40)
    
    # Get all sales invoices with eboekhouden_invoice_number
    si_with_eb = frappe.db.sql("""
        SELECT 
            COUNT(*) as count,
            COUNT(DISTINCT eboekhouden_invoice_number) as unique_eb_numbers,
            MIN(creation) as first_created,
            MAX(creation) as last_created
        FROM `tabSales Invoice`
        WHERE eboekhouden_invoice_number IS NOT NULL
        AND eboekhouden_invoice_number != ''
        AND company = %s
    """, company, as_dict=True)[0]
    
    print(f"Total Sales Invoices with E-Boekhouden number: {si_with_eb.count}")
    print(f"Unique E-Boekhouden invoice numbers: {si_with_eb.unique_eb_numbers}")
    
    if si_with_eb.count != si_with_eb.unique_eb_numbers:
        print(f"⚠️  DUPLICATES FOUND: {si_with_eb.count - si_with_eb.unique_eb_numbers} duplicate invoice numbers!")
        
        # Find duplicates
        duplicates = frappe.db.sql("""
            SELECT 
                eboekhouden_invoice_number,
                COUNT(*) as count,
                GROUP_CONCAT(name) as invoice_names
            FROM `tabSales Invoice`
            WHERE eboekhouden_invoice_number IS NOT NULL
            AND eboekhouden_invoice_number != ''
            AND company = %s
            GROUP BY eboekhouden_invoice_number
            HAVING count > 1
            LIMIT 10
        """, company, as_dict=True)
        
        print("\nSample duplicate invoice numbers:")
        for dup in duplicates:
            print(f"  - {dup.eboekhouden_invoice_number}: {dup.count} times ({dup.invoice_names})")
    
    # 2. Check Purchase Invoices
    print("\n2. Purchase Invoice Analysis:")
    print("-" * 40)
    
    pi_with_eb = frappe.db.sql("""
        SELECT 
            COUNT(*) as count,
            COUNT(DISTINCT eboekhouden_invoice_number) as unique_eb_numbers
        FROM `tabPurchase Invoice`
        WHERE eboekhouden_invoice_number IS NOT NULL
        AND eboekhouden_invoice_number != ''
        AND company = %s
    """, company, as_dict=True)[0]
    
    print(f"Total Purchase Invoices with E-Boekhouden number: {pi_with_eb.count}")
    print(f"Unique E-Boekhouden invoice numbers: {pi_with_eb.unique_eb_numbers}")
    
    # 3. Check Payment Entries
    print("\n3. Payment Entry Analysis:")
    print("-" * 40)
    
    # Check reference_no field
    pe_ref_no = frappe.db.sql("""
        SELECT 
            COUNT(*) as count,
            COUNT(DISTINCT reference_no) as unique_ref_numbers,
            SUM(CASE WHEN reference_no REGEXP '^[0-9]+$' THEN 1 ELSE 0 END) as numeric_refs
        FROM `tabPayment Entry`
        WHERE reference_no IS NOT NULL
        AND reference_no != ''
        AND company = %s
    """, company, as_dict=True)[0]
    
    print(f"Payment Entries with reference_no: {pe_ref_no.count}")
    print(f"Unique reference numbers: {pe_ref_no.unique_ref_numbers}")
    print(f"Numeric reference numbers (likely mutation IDs): {pe_ref_no.numeric_refs}")
    
    # Check eboekhouden_mutation_nr field if it exists
    if frappe.db.has_column("Payment Entry", "eboekhouden_mutation_nr"):
        pe_mut_nr = frappe.db.sql("""
            SELECT 
                COUNT(*) as count,
                COUNT(DISTINCT eboekhouden_mutation_nr) as unique_mut_numbers
            FROM `tabPayment Entry`
            WHERE eboekhouden_mutation_nr IS NOT NULL
            AND eboekhouden_mutation_nr != ''
            AND company = %s
        """, company, as_dict=True)[0]
        
        print(f"\nPayment Entries with eboekhouden_mutation_nr: {pe_mut_nr.count}")
        print(f"Unique mutation numbers: {pe_mut_nr.unique_mut_numbers}")
        
        # Check for overlaps between reference_no and eboekhouden_mutation_nr
        overlaps = frappe.db.sql("""
            SELECT COUNT(*) as count
            FROM `tabPayment Entry`
            WHERE reference_no = eboekhouden_mutation_nr
            AND reference_no IS NOT NULL
            AND company = %s
        """, company)[0][0]
        
        print(f"Entries where reference_no = eboekhouden_mutation_nr: {overlaps}")
    
    # 4. Check Journal Entries
    print("\n4. Journal Entry Analysis:")
    print("-" * 40)
    
    je_mut_nr = frappe.db.sql("""
        SELECT 
            COUNT(*) as count,
            COUNT(DISTINCT eboekhouden_mutation_nr) as unique_mut_numbers
        FROM `tabJournal Entry`
        WHERE eboekhouden_mutation_nr IS NOT NULL
        AND eboekhouden_mutation_nr != ''
        AND company = %s
    """, company, as_dict=True)[0]
    
    print(f"Journal Entries with mutation number: {je_mut_nr.count}")
    print(f"Unique mutation numbers: {je_mut_nr.unique_mut_numbers}")
    
    # 5. Check for cross-document duplicates
    print("\n5. Cross-Document Duplicate Check:")
    print("-" * 40)
    
    # Get all mutation numbers from different doctypes
    all_mutations = set()
    je_mutations = set()
    pe_mutations = set()
    
    # From Journal Entries
    je_muts = frappe.db.sql("""
        SELECT DISTINCT eboekhouden_mutation_nr
        FROM `tabJournal Entry`
        WHERE eboekhouden_mutation_nr IS NOT NULL
        AND eboekhouden_mutation_nr != ''
        AND company = %s
    """, company)
    for m in je_muts:
        je_mutations.add(str(m[0]))
        all_mutations.add(str(m[0]))
    
    # From Payment Entries (reference_no)
    pe_refs = frappe.db.sql("""
        SELECT DISTINCT reference_no
        FROM `tabPayment Entry`
        WHERE reference_no REGEXP '^[0-9]+$'
        AND reference_no != ''
        AND company = %s
    """, company)
    for m in pe_refs:
        pe_mutations.add(str(m[0]))
        all_mutations.add(str(m[0]))
    
    # From Payment Entries (eboekhouden_mutation_nr)
    if frappe.db.has_column("Payment Entry", "eboekhouden_mutation_nr"):
        pe_muts = frappe.db.sql("""
            SELECT DISTINCT eboekhouden_mutation_nr
            FROM `tabPayment Entry`
            WHERE eboekhouden_mutation_nr IS NOT NULL
            AND eboekhouden_mutation_nr != ''
            AND company = %s
        """, company)
        for m in pe_muts:
            pe_mutations.add(str(m[0]))
            all_mutations.add(str(m[0]))
    
    print(f"Total unique mutation numbers across all doctypes: {len(all_mutations)}")
    print(f"Mutation numbers in Journal Entries: {len(je_mutations)}")
    print(f"Mutation numbers in Payment Entries: {len(pe_mutations)}")
    print(f"Mutations in both JE and PE: {len(je_mutations.intersection(pe_mutations))}")
    
    # 6. Recent migration analysis
    print("\n6. Recent Migration Analysis:")
    print("-" * 40)
    
    # Get recent migrations
    recent_migrations = frappe.db.sql("""
        SELECT 
            name,
            creation,
            migration_status,
            total_records_processed,
            successful_imports,
            failed_imports,
            skipped_already_exists
        FROM `tabE-Boekhouden Migration`
        WHERE migration_status = 'Completed'
        ORDER BY creation DESC
        LIMIT 5
    """, as_dict=True)
    
    for mig in recent_migrations:
        print(f"\nMigration: {mig.name} ({mig.creation})")
        print(f"  Total processed: {mig.total_records_processed}")
        print(f"  Successful: {mig.successful_imports}")
        print(f"  Failed: {mig.failed_imports}")
        print(f"  Already exists: {mig.skipped_already_exists}")
        if mig.total_records_processed:
            pct = (mig.skipped_already_exists / mig.total_records_processed * 100) if mig.skipped_already_exists else 0
            print(f"  Already exists %: {pct:.1f}%")
    
    # 7. Check if documents were deleted but tracking fields remain
    print("\n7. Potential Issues:")
    print("-" * 40)
    
    # Check for cancelled documents that might still be blocking
    cancelled_si = frappe.db.sql("""
        SELECT COUNT(*) as count
        FROM `tabSales Invoice`
        WHERE docstatus = 2
        AND eboekhouden_invoice_number IS NOT NULL
        AND company = %s
    """, company)[0][0]
    
    print(f"Cancelled Sales Invoices with E-Boekhouden number: {cancelled_si}")
    
    cancelled_pi = frappe.db.sql("""
        SELECT COUNT(*) as count
        FROM `tabPurchase Invoice`
        WHERE docstatus = 2
        AND eboekhouden_invoice_number IS NOT NULL
        AND company = %s
    """, company)[0][0]
    
    print(f"Cancelled Purchase Invoices with E-Boekhouden number: {cancelled_pi}")
    
    # Check if the unique constraint is actually working
    print("\n8. Database Constraint Check:")
    print("-" * 40)
    
    # Check if unique constraint exists on custom fields
    constraints = frappe.db.sql("""
        SELECT 
            TABLE_NAME,
            COLUMN_NAME,
            CONSTRAINT_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = DATABASE()
        AND COLUMN_NAME IN ('eboekhouden_invoice_number', 'eboekhouden_mutation_nr')
        AND CONSTRAINT_NAME LIKE 'UNIQUE%'
    """, as_dict=True)
    
    if constraints:
        print("Unique constraints found:")
        for c in constraints:
            print(f"  - {c.TABLE_NAME}.{c.COLUMN_NAME} ({c.CONSTRAINT_NAME})")
    else:
        print("⚠️  No unique constraints found on E-Boekhouden tracking fields!")
        print("This could allow duplicates to be created!")

if __name__ == "__main__":
    frappe.init(site="dev.veganisme.net")
    frappe.connect()
    analyze_duplicate_checking()
    frappe.destroy()