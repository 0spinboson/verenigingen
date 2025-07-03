#!/usr/bin/env python3
"""
Test script to analyze Payment Entries for cleanup
"""

import frappe
import json

def analyze_payment_entries():
    """Analyze payment entries to see what cleanup methods would catch"""
    
    print("Analyzing Payment Entries for e-Boekhouden cleanup...")
    
    # Initialize Frappe
    frappe.init(site='dev.veganisme.net')
    frappe.connect()
    
    try:
        # Get company
        settings = frappe.get_single("E-Boekhouden Settings")
        company = settings.default_company
        
        print(f"Company: {company}")
        
        # Method 1: By eboekhouden_mutation_nr
        try:
            mutation_nr_entries = frappe.get_all("Payment Entry", filters=[
                ["company", "=", company],
                ["eboekhouden_mutation_nr", "is", "set"],
                ["eboekhouden_mutation_nr", "!=", ""],
                ["docstatus", "!=", 2]
            ])
            print(f"Method 1 (mutation_nr): Found {len(mutation_nr_entries)} entries")
        except Exception as e:
            print(f"Method 1 error: {str(e)}")
            mutation_nr_entries = []
        
        # Method 2: By numeric reference_no
        try:
            numeric_ref_entries = frappe.get_all("Payment Entry", filters=[
                ["company", "=", company],
                ["reference_no", "regexp", "^[0-9]+$"],
                ["docstatus", "!=", 2]
            ])
            print(f"Method 2 (numeric ref): Found {len(numeric_ref_entries)} entries")
        except Exception as e:
            print(f"Method 2 error: {str(e)}")
            numeric_ref_entries = []
        
        # Method 3: By remarks pattern
        try:
            remarks_entries = frappe.get_all("Payment Entry", filters=[
                ["company", "=", company],
                ["remarks", "like", "%Mutation Nr:%"],
                ["docstatus", "!=", 2]
            ])
            print(f"Method 3 (remarks): Found {len(remarks_entries)} entries")
        except Exception as e:
            print(f"Method 3 error: {str(e)}")
            remarks_entries = []
        
        # Method 4: By title pattern
        try:
            title_entries = frappe.get_all("Payment Entry", filters=[
                ["company", "=", company],
                ["title", "like", "%UNRECONCILED%"],
                ["docstatus", "!=", 2]
            ])
            print(f"Method 4 (title): Found {len(title_entries)} entries")
        except Exception as e:
            print(f"Method 4 error: {str(e)}")
            title_entries = []
        
        # Show sample entries for understanding
        print("\n=== Sample Payment Entries ===")
        sample_entries = frappe.get_all("Payment Entry", 
            filters={"company": company}, 
            fields=["name", "title", "reference_no", "remarks", "docstatus"],
            limit=3)
        
        for entry in sample_entries:
            print(f"Entry: {entry.name}")
            print(f"  Title: {entry.title}")
            print(f"  Reference: {entry.reference_no}")
            print(f"  Remarks: {entry.remarks[:100] if entry.remarks else 'None'}...")
            print(f"  Docstatus: {entry.docstatus}")
            print()
        
        print("✅ Analysis completed!")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        frappe.destroy()

if __name__ == "__main__":
    analyze_payment_entries()