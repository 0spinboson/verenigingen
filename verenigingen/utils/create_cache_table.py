#!/usr/bin/env python
"""
Create the EBoekhouden REST Mutation Cache table
"""

import frappe
from frappe import _

@frappe.whitelist()
def create_cache_table():
    """Create the cache table"""
    try:
        # Get the DocType
        doctype = frappe.get_doc("DocType", "EBoekhouden REST Mutation Cache")
        
        # Recreate the table
        from frappe.model.db_schema import DbManager
        db_manager = DbManager(doctype)
        db_manager.sync()
        
        frappe.db.commit()
        
        return {
            "success": True,
            "message": "Cache table created successfully"
        }
        
    except Exception as e:
        frappe.log_error(f"Error creating cache table: {str(e)}", "E-Boekhouden Cache")
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def create_doctype_and_table():
    """Create the DocType if it doesn't exist"""
    try:
        # Check if DocType already exists
        if not frappe.db.exists("DocType", "EBoekhouden REST Mutation Cache"):
            # Create the DocType
            doctype = frappe.new_doc("DocType")
            doctype.name = "EBoekhouden REST Mutation Cache"
            doctype.module = "Verenigingen"
            doctype.naming_rule = "By fieldname"
            doctype.autoname = "field:mutation_id"
            
            # Add fields
            fields = [
                {"fieldname": "mutation_id", "label": "Mutation ID", "fieldtype": "Int", "reqd": 1, "unique": 1, "in_list_view": 1},
                {"fieldname": "mutation_data", "label": "Mutation Data", "fieldtype": "JSON", "description": "Complete mutation data from REST API"},
                {"fieldname": "mutation_type", "label": "Mutation Type", "fieldtype": "Int", "in_list_view": 1},
                {"fieldname": "mutation_date", "label": "Mutation Date", "fieldtype": "Date", "in_list_view": 1},
                {"fieldname": "amount", "label": "Amount", "fieldtype": "Currency"},
                {"fieldname": "ledger_id", "label": "Ledger ID", "fieldtype": "Int"},
                {"fieldname": "relation_id", "label": "Relation ID", "fieldtype": "Int"},
                {"fieldname": "invoice_number", "label": "Invoice Number", "fieldtype": "Data"},
                {"fieldname": "entry_number", "label": "Entry Number", "fieldtype": "Data"},
                {"fieldname": "description", "label": "Description", "fieldtype": "Text"},
                {"fieldname": "fetched_at", "label": "Fetched At", "fieldtype": "Datetime", "default": "__timestamp"}
            ]
            
            for field_data in fields:
                field = doctype.append("fields", {})
                field.update(field_data)
            
            # Add permissions
            perm = doctype.append("permissions", {})
            perm.role = "System Manager"
            perm.read = 1
            perm.write = 1
            perm.create = 1
            perm.delete = 1
            
            doctype.save()
            frappe.db.commit()
            
            # Create the table
            from frappe.model.db_schema import DbManager
            db_manager = DbManager(doctype)
            db_manager.sync()
            
            return {
                "success": True,
                "message": "DocType and table created successfully"
            }
        else:
            # DocType exists, just create the table
            return create_cache_table()
            
    except Exception as e:
        frappe.log_error(f"Error creating DocType: {str(e)}", "E-Boekhouden Cache")
        return {
            "success": False,
            "error": str(e)
        }