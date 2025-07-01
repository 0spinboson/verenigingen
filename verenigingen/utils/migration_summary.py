"""
Get summary of E-Boekhouden migration results
"""

import frappe

@frappe.whitelist()
def get_migration_summary():
    """Get comprehensive summary of migration results"""
    
    # Count imported records
    summary = {
        "accounts": {
            "total": frappe.db.count("Account", {"company": "R S P"}),
            "with_eboekhouden_code": frappe.db.count("Account", {
                "company": "R S P",
                "account_number": ["is", "set"]
            })
        },
        "customers": {
            "total": frappe.db.count("Customer"),
            "with_eboekhouden_code": frappe.db.count("Customer", {
                "eboekhouden_relation_code": ["is", "set"]
            })
        },
        "suppliers": {
            "total": frappe.db.count("Supplier"),
            "with_eboekhouden_code": frappe.db.count("Supplier", {
                "eboekhouden_relation_code": ["is", "set"]
            })
        },
        "sales_invoices": {
            "total": frappe.db.count("Sales Invoice", {"company": "R S P"}),
            "with_eboekhouden_number": frappe.db.count("Sales Invoice", {
                "company": "R S P",
                "eboekhouden_invoice_number": ["is", "set"]
            })
        },
        "purchase_invoices": {
            "total": frappe.db.count("Purchase Invoice", {"company": "R S P"}),
            "with_eboekhouden_number": frappe.db.count("Purchase Invoice", {
                "company": "R S P",
                "eboekhouden_invoice_number": ["is", "set"]
            })
        },
        "payments": {
            "customer_payments": frappe.db.count("Payment Entry", {
                "party_type": "Customer",
                "docstatus": 1
            }),
            "supplier_payments": frappe.db.count("Payment Entry", {
                "party_type": "Supplier",
                "docstatus": 1
            })
        },
        "journal_entries": {
            "total": frappe.db.count("Journal Entry", {"company": "R S P"}),
            "with_mutation_nr": frappe.db.count("Journal Entry", {
                "company": "R S P",
                "eboekhouden_mutation_nr": ["is", "set"]
            })
        }
    }
    
    # Get recent migrations
    recent_migrations = frappe.db.get_all("E-Boekhouden Migration",
        fields=["name", "total_records", "imported_records", "failed_records"],
        order_by="creation desc",
        limit=5
    )
    
    summary["recent_migrations"] = recent_migrations
    
    return summary

if __name__ == "__main__":
    print(get_migration_summary())