#!/usr/bin/env python
import frappe
from collections import Counter

@frappe.whitelist()
def analyze_mutation_distribution():
    """Analyze the distribution of mutation types in the database"""
    try:
        # Get the latest migration document
        migration_doc = frappe.get_last_doc("E-Boekhouden Migration")
        migration_id = migration_doc.name
        
        # Query all mutation types from error logs
        mutation_types = frappe.db.sql("""
            SELECT 
                JSON_UNQUOTE(JSON_EXTRACT(error_details, '$.Soort')) as mutation_type,
                COUNT(*) as count
            FROM `tabE-Boekhouden Migration Error`
            WHERE parent = %s
            AND error_details IS NOT NULL
            AND JSON_EXTRACT(error_details, '$.Soort') IS NOT NULL
            GROUP BY mutation_type
            ORDER BY count DESC
        """, migration_id, as_dict=True)
        
        print("\n=== Mutation Types in Error Logs ===")
        for mt in mutation_types:
            print(f"{mt.mutation_type}: {mt.count}")
        
        # Also check what's been successfully processed
        print("\n=== Successfully Processed Records ===")
        
        # Sales Invoices
        si_count = frappe.db.count("Sales Invoice", {"eboekhouden_invoice_number": ["!=", ""]})
        print(f"Sales Invoices with eboekhouden_invoice_number: {si_count}")
        
        # Purchase Invoices
        pi_count = frappe.db.count("Purchase Invoice", {"eboekhouden_invoice_number": ["!=", ""]})
        print(f"Purchase Invoices with eboekhouden_invoice_number: {pi_count}")
        
        # Payment Entries
        pe_count = frappe.db.count("Payment Entry", {"eboekhouden_mutation_nr": ["!=", ""]})
        print(f"Payment Entries with eboekhouden_mutation_nr: {pe_count}")
        
        # Journal Entries
        je_count = frappe.db.count("Journal Entry", {"eboekhouden_mutation_nr": ["!=", ""]})
        print(f"Journal Entries with eboekhouden_mutation_nr: {je_count}")
        
        # Check for unrecognized mutation types
        print("\n=== Checking for Unknown Mutation Types ===")
        unknown_types = frappe.db.sql("""
            SELECT DISTINCT
                JSON_UNQUOTE(JSON_EXTRACT(error_details, '$.Soort')) as mutation_type
            FROM `tabE-Boekhouden Migration Error`
            WHERE parent = %s
            AND error_details IS NOT NULL
            AND JSON_EXTRACT(error_details, '$.Soort') IS NOT NULL
            AND JSON_UNQUOTE(JSON_EXTRACT(error_details, '$.Soort')) NOT IN (
                'FactuurVerstuurd', 'FactuurOntvangen', 
                'FactuurbetalingOntvangen', 'FactuurbetalingVerstuurd',
                'GeldOntvangen', 'GeldUitgegeven', 'Memoriaal'
            )
        """, migration_id, as_dict=True)
        
        if unknown_types:
            print("Found unknown mutation types:")
            for ut in unknown_types:
                print(f"  - {ut.mutation_type}")
        else:
            print("No unknown mutation types found")
            
        return True
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    frappe.connect(site="dev.veganisme.net")
    analyze_mutation_distribution()