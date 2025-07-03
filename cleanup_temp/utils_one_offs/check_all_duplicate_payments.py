"""
Check for any other duplicate payments in the system
"""

import frappe

@frappe.whitelist()
def check_duplicate_payments():
    """Find all duplicate payments based on reference_no"""
    
    # Find all reference_no values that appear more than once
    duplicates = frappe.db.sql("""
        SELECT 
            reference_no,
            COUNT(*) as count,
            GROUP_CONCAT(name) as payment_entries,
            SUM(paid_amount) as total_amount
        FROM `tabPayment Entry`
        WHERE reference_no IS NOT NULL 
        AND reference_no != ''
        AND docstatus != 2
        GROUP BY reference_no
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC
    """, as_dict=True)
    
    result = {
        "total_duplicate_groups": len(duplicates),
        "duplicates": []
    }
    
    # Get details for each duplicate group
    for dup in duplicates[:10]:  # First 10 groups
        # Get individual payment details
        payments = frappe.db.sql("""
            SELECT 
                pe.name,
                pe.party_type,
                pe.party,
                pe.paid_amount,
                pe.posting_date,
                pe.creation,
                pe.docstatus,
                per.reference_name as invoice
            FROM `tabPayment Entry` pe
            LEFT JOIN `tabPayment Entry Reference` per ON per.parent = pe.name
            WHERE pe.reference_no = %s
            AND pe.docstatus != 2
            ORDER BY pe.creation
        """, dup.reference_no, as_dict=True)
        
        result["duplicates"].append({
            "reference_no": dup.reference_no,
            "duplicate_count": dup.count,
            "total_amount": dup.total_amount,
            "payments": payments
        })
    
    # Also check for payments without reference_no that might be duplicates
    # based on same invoice, amount, and date
    potential_duplicates = frappe.db.sql("""
        SELECT 
            per.reference_name as invoice,
            pe.paid_amount,
            pe.posting_date,
            COUNT(*) as count,
            GROUP_CONCAT(pe.name) as payment_entries
        FROM `tabPayment Entry` pe
        INNER JOIN `tabPayment Entry Reference` per ON per.parent = pe.name
        WHERE pe.docstatus = 1
        GROUP BY per.reference_name, pe.paid_amount, pe.posting_date
        HAVING COUNT(*) > 1
    """, as_dict=True)
    
    result["potential_duplicates_without_ref"] = potential_duplicates
    
    # Summary statistics
    result["summary"] = {
        "total_payments": frappe.db.count("Payment Entry", {"docstatus": 1}),
        "payments_with_reference_no": frappe.db.count("Payment Entry", {
            "docstatus": 1,
            "reference_no": ["is", "set"]
        }),
        "supplier_payments": frappe.db.count("Payment Entry", {
            "docstatus": 1,
            "party_type": "Supplier"
        })
    }
    
    return result

if __name__ == "__main__":
    print(check_duplicate_payments())