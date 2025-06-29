"""
Investigate why duplicate payments were created for mutation 7281
"""

import frappe
import json

@frappe.whitelist()
def investigate_duplicates():
    """Check why mutation 7281 created duplicate payments"""
    
    result = {
        "invoice_info": {},
        "payment_entries": [],
        "mutation_data": []
    }
    
    # 1. Get the invoice details
    invoice_name = frappe.db.get_value("Purchase Invoice", 
        {"eboekhouden_invoice_number": "8008125556501050"}, 
        "name")
    
    if invoice_name:
        invoice = frappe.get_doc("Purchase Invoice", invoice_name)
        result["invoice_info"] = {
            "name": invoice.name,
            "eboekhouden_invoice_number": invoice.eboekhouden_invoice_number,
            "grand_total": invoice.grand_total,
            "outstanding_amount": invoice.outstanding_amount,
            "creation": str(invoice.creation),
            "eboekhouden_mutation_nr": frappe.db.get_value("Purchase Invoice", invoice.name, "eboekhouden_mutation_nr") if frappe.db.has_column("Purchase Invoice", "eboekhouden_mutation_nr") else None
        }
    
    # 2. Get ALL payment entries that reference mutation 7281
    payments_with_7281 = frappe.db.sql("""
        SELECT 
            pe.name,
            pe.posting_date,
            pe.paid_amount,
            pe.reference_no,
            pe.creation,
            pe.party,
            per.reference_name,
            per.allocated_amount
        FROM `tabPayment Entry` pe
        LEFT JOIN `tabPayment Entry Reference` per ON per.parent = pe.name
        WHERE pe.reference_no = '7281'
        OR pe.name IN (
            SELECT parent FROM `tabPayment Entry Reference` 
            WHERE reference_name = %s
        )
        ORDER BY pe.creation
    """, invoice_name, as_dict=True)
    
    result["payment_entries"] = payments_with_7281
    
    # 3. Check for any custom fields that might store mutation numbers
    payment_custom_fields = []
    if frappe.db.has_column("Payment Entry", "eboekhouden_mutation_nr"):
        payments_with_custom_field = frappe.db.sql("""
            SELECT name, eboekhouden_mutation_nr, reference_no, paid_amount, creation
            FROM `tabPayment Entry`
            WHERE eboekhouden_mutation_nr = '7281'
        """, as_dict=True)
        payment_custom_fields = payments_with_custom_field
    
    result["payments_with_custom_mutation_field"] = payment_custom_fields
    
    # 4. Look at the migration logs to see how many times mutation 7281 was processed
    migration_files = [
        "EBMIG-2025-00013",
        "EBMIG-2025-00014"
    ]
    
    for migration in migration_files:
        try:
            # Try different possible file patterns
            file_patterns = [
                f"/home/frappe/frappe-bench/sites/dev.veganisme.net/private/files/eboekhouden_migration_logs/failed_records_{migration}_*.json",
            ]
            
            import glob
            for pattern in file_patterns:
                files = glob.glob(pattern)
                if files:
                    with open(files[0], 'r') as f:
                        data = json.load(f)
                    
                    # Count how many times mutation 7281 appears
                    mutation_7281_count = 0
                    for record in data.get("failed_records", []):
                        if record.get("record_data", {}).get("MutatieNr") == "7281":
                            mutation_7281_count += 1
                    
                    result["mutation_data"].append({
                        "migration": migration,
                        "mutation_7281_appearances": mutation_7281_count
                    })
                    break
        except Exception as e:
            result["mutation_data"].append({
                "migration": migration,
                "error": str(e)
            })
    
    # 5. Check if there's duplicate detection logic in the payment processing
    result["duplicate_detection_check"] = {
        "has_reference_no_check": "Should prevent duplicates if reference_no is properly checked",
        "observation": "Two payments with same reference_no (7281) were created"
    }
    
    # 6. Get the creation timeline
    timeline = frappe.db.sql("""
        SELECT 
            'Payment' as doc_type,
            name as doc_name,
            creation,
            reference_no,
            paid_amount
        FROM `tabPayment Entry`
        WHERE reference_no = '7281'
        
        UNION ALL
        
        SELECT 
            'Invoice' as doc_type,
            name as doc_name,
            creation,
            eboekhouden_invoice_number as reference_no,
            grand_total as paid_amount
        FROM `tabPurchase Invoice`
        WHERE eboekhouden_invoice_number = '8008125556501050'
        
        ORDER BY creation
    """, as_dict=True)
    
    result["timeline"] = timeline
    
    return result

if __name__ == "__main__":
    print(investigate_duplicates())