#!/usr/bin/env python3

import frappe

def create_direct_debit_fields_only():
    """Create only the Direct Debit Batch custom fields"""
    
    try:
        frappe.init()
        frappe.connect()
        
        # Direct Debit Batch fields with correct syntax
        fields = [
            {
                'fieldname': 'custom_reconciliation_status',
                'label': 'Reconciliation Status',
                'fieldtype': 'Select',
                'options': '\nPending\nFully Reconciled\nPartially Reconciled\nManual Review Required\nReturns Processed',
                'insert_after': 'status',
                'read_only': 0,
                'description': 'Overall reconciliation status'
            },
            {
                'fieldname': 'custom_related_bank_transactions',
                'label': 'Related Bank Transactions',
                'fieldtype': 'Long Text',
                'insert_after': 'custom_reconciliation_status',
                'read_only': 0,
                'description': 'Bank transaction references related to this batch'
            }
        ]
        
        for field in fields:
            # Check if field already exists
            existing = frappe.db.exists("Custom Field", {"dt": "Direct Debit Batch", "fieldname": field["fieldname"]})
            
            if not existing:
                custom_field = frappe.get_doc({
                    "doctype": "Custom Field",
                    "dt": "Direct Debit Batch",
                    "fieldname": field["fieldname"],
                    "label": field["label"],
                    "fieldtype": field["fieldtype"],
                    "options": field.get("options", ""),
                    "insert_after": field["insert_after"],
                    "read_only": field.get("read_only", 0),
                    "description": field.get("description", "")
                })
                custom_field.insert()
                print(f"Created custom field: Direct Debit Batch.{field['fieldname']}")
            else:
                print(f"Custom field already exists: Direct Debit Batch.{field['fieldname']}")
        
        frappe.db.commit()
        print("Direct Debit Batch custom fields setup completed successfully")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    create_direct_debit_fields_only()