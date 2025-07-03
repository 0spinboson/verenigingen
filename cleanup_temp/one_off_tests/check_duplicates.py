import frappe

@frappe.whitelist()
def check_duplicate_stats():
    """Check duplicate statistics in the database"""
    
    company = frappe.db.get_single_value("E-Boekhouden Settings", "default_company")
    
    results = {
        "company": company,
        "sales_invoices": {},
        "purchase_invoices": {},
        "payment_entries": {},
        "journal_entries": {},
        "recent_migrations": []
    }
    
    # Sales Invoices
    si_stats = frappe.db.sql("""
        SELECT 
            COUNT(*) as total_count,
            COUNT(DISTINCT eboekhouden_invoice_number) as unique_count
        FROM `tabSales Invoice`
        WHERE eboekhouden_invoice_number IS NOT NULL
        AND eboekhouden_invoice_number != ''
        AND company = %s
    """, company, as_dict=True)[0]
    
    results["sales_invoices"] = {
        "total": si_stats.total_count,
        "unique": si_stats.unique_count,
        "duplicates": si_stats.total_count - si_stats.unique_count
    }
    
    # Purchase Invoices
    pi_stats = frappe.db.sql("""
        SELECT 
            COUNT(*) as total_count,
            COUNT(DISTINCT eboekhouden_invoice_number) as unique_count
        FROM `tabPurchase Invoice`
        WHERE eboekhouden_invoice_number IS NOT NULL
        AND eboekhouden_invoice_number != ''
        AND company = %s
    """, company, as_dict=True)[0]
    
    results["purchase_invoices"] = {
        "total": pi_stats.total_count,
        "unique": pi_stats.unique_count,
        "duplicates": pi_stats.total_count - pi_stats.unique_count
    }
    
    # Payment Entries
    pe_stats = frappe.db.sql("""
        SELECT 
            COUNT(*) as total_count,
            COUNT(DISTINCT reference_no) as unique_count
        FROM `tabPayment Entry`
        WHERE reference_no REGEXP '^[0-9]+$'
        AND company = %s
    """, company, as_dict=True)[0]
    
    results["payment_entries"] = {
        "total": pe_stats.total_count,
        "unique": pe_stats.unique_count,
        "duplicates": pe_stats.total_count - pe_stats.unique_count
    }
    
    # Journal Entries
    je_stats = frappe.db.sql("""
        SELECT 
            COUNT(*) as total_count,
            COUNT(DISTINCT eboekhouden_mutation_nr) as unique_count
        FROM `tabJournal Entry`
        WHERE eboekhouden_mutation_nr IS NOT NULL
        AND eboekhouden_mutation_nr != ''
        AND company = %s
    """, company, as_dict=True)[0]
    
    results["journal_entries"] = {
        "total": je_stats.total_count,
        "unique": je_stats.unique_count,
        "duplicates": je_stats.total_count - je_stats.unique_count
    }
    
    # Recent migrations
    migrations = frappe.db.sql("""
        SELECT 
            name,
            creation,
            total_records_processed,
            successful_imports,
            failed_imports,
            skipped_already_exists
        FROM `tabE-Boekhouden Migration`
        WHERE migration_status = 'Completed'
        ORDER BY creation DESC
        LIMIT 5
    """, as_dict=True)
    
    for mig in migrations:
        if mig.total_records_processed:
            skip_pct = (mig.skipped_already_exists / mig.total_records_processed * 100) if mig.skipped_already_exists else 0
            results["recent_migrations"].append({
                "name": mig.name,
                "date": str(mig.creation),
                "total": mig.total_records_processed,
                "success": mig.successful_imports,
                "failed": mig.failed_imports,
                "already_exists": mig.skipped_already_exists,
                "already_exists_pct": round(skip_pct, 1)
            })
    
    # Check constraints
    constraints = frappe.db.sql("""
        SELECT 
            TABLE_NAME,
            COLUMN_NAME,
            CONSTRAINT_NAME,
            CONSTRAINT_TYPE
        FROM information_schema.TABLE_CONSTRAINTS tc
        JOIN information_schema.KEY_COLUMN_USAGE kcu
        ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
        WHERE tc.TABLE_SCHEMA = DATABASE()
        AND kcu.COLUMN_NAME IN ('eboekhouden_invoice_number', 'eboekhouden_mutation_nr')
    """, as_dict=True)
    
    results["constraints"] = constraints
    
    # Check for cancelled documents
    results["cancelled_docs"] = {
        "sales_invoices": frappe.db.count("Sales Invoice", {
            "docstatus": 2,
            "eboekhouden_invoice_number": ["!=", ""],
            "company": company
        }),
        "purchase_invoices": frappe.db.count("Purchase Invoice", {
            "docstatus": 2,
            "eboekhouden_invoice_number": ["!=", ""],
            "company": company
        })
    }
    
    return results