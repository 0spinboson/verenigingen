#!/usr/bin/env python3
import frappe
import json
from collections import Counter

def analyze_all_mutations():
    frappe.connect(site="dev.veganisme.net")
    
    print("=== Analyzing All Mutations in Database ===\n")
    
    # 1. Check E-Boekhouden Migration Document for stats
    print("1. Checking Migration Documents:")
    migrations = frappe.get_all("E-Boekhouden Migration", 
                               fields=["name", "status", "start_date", "end_date", "total_mutations_processed"],
                               order_by="creation desc",
                               limit=5)
    
    for mig in migrations:
        print(f"  - {mig.name}: {mig.status} | Total Processed: {mig.total_mutations_processed or 0}")
    
    # 2. Check what mutation types were attempted
    print("\n2. Checking Mutation Types from Error Logs:")
    mutation_types = frappe.db.sql("""
        SELECT 
            JSON_UNQUOTE(JSON_EXTRACT(error_details, '$.Soort')) as mutation_type,
            COUNT(*) as error_count
        FROM `tabE-Boekhouden Migration Error`
        WHERE error_details IS NOT NULL
        AND JSON_EXTRACT(error_details, '$.Soort') IS NOT NULL
        GROUP BY mutation_type
        ORDER BY error_count DESC
    """, as_dict=True)
    
    for mt in mutation_types:
        print(f"  - {mt.mutation_type}: {mt.error_count} errors")
    
    # 3. Check what's successfully imported
    print("\n3. Successfully Imported Records:")
    print(f"  - Sales Invoices (with eboekhouden_invoice_number): {frappe.db.count('Sales Invoice', {'eboekhouden_invoice_number': ['!=', '']})}")
    print(f"  - Purchase Invoices (with eboekhouden_invoice_number): {frappe.db.count('Purchase Invoice', {'eboekhouden_invoice_number': ['!=', '']})}")
    print(f"  - Payment Entries (with eboekhouden_mutation_nr): {frappe.db.count('Payment Entry', {'eboekhouden_mutation_nr': ['!=', '']})}")
    print(f"  - Payment Entries (with reference_no as number): {frappe.db.sql('SELECT COUNT(*) FROM `tabPayment Entry` WHERE reference_no REGEXP \"^[0-9]+$\"')[0][0]}")
    print(f"  - Journal Entries (with eboekhouden_mutation_nr): {frappe.db.count('Journal Entry', {'eboekhouden_mutation_nr': ['!=', '']})}")
    
    # 4. Check for specific mutation types in error details
    print("\n4. Searching for Specific Mutation Types in Error Details:")
    specific_types = ['GeldOntvangen', 'GeldUitgegeven', 'Memoriaal', 'FactuurVerstuurd', 'FactuurbetalingOntvangen']
    
    for mut_type in specific_types:
        count = frappe.db.sql("""
            SELECT COUNT(*)
            FROM `tabE-Boekhouden Migration Error`
            WHERE JSON_UNQUOTE(JSON_EXTRACT(error_details, '$.Soort')) = %s
        """, mut_type)[0][0]
        print(f"  - {mut_type}: {count} records in error logs")
    
    # 5. Sample some mutations to see what's in the data
    print("\n5. Sample Mutations from Error Logs (showing different types):")
    samples = frappe.db.sql("""
        SELECT DISTINCT 
            JSON_UNQUOTE(JSON_EXTRACT(error_details, '$.Soort')) as mutation_type,
            JSON_UNQUOTE(JSON_EXTRACT(error_details, '$.MutatieNr')) as mutation_nr,
            JSON_UNQUOTE(JSON_EXTRACT(error_details, '$.Omschrijving')) as description
        FROM `tabE-Boekhouden Migration Error`
        WHERE error_details IS NOT NULL
        GROUP BY mutation_type
        LIMIT 10
    """, as_dict=True)
    
    for sample in samples:
        desc = sample.description[:60] + "..." if sample.description and len(sample.description) > 60 else sample.description
        print(f"  - Type: {sample.mutation_type} | Mutation: {sample.mutation_nr} | Desc: {desc}")
    
    # 6. Check if we're actually fetching all mutation types
    print("\n6. Checking SOAP API Configuration:")
    settings = frappe.get_single("E-Boekhouden Settings")
    print(f"  - API Active: {settings.api_enabled}")
    print(f"  - Use SOAP: {getattr(settings, 'use_soap_api', 'N/A')}")
    
    frappe.db.close()

if __name__ == "__main__":
    analyze_all_mutations()