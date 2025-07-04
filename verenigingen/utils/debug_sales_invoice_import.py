"""
Debug Sales Invoice Import Issue
"""

import frappe
from frappe import _
import json

@frappe.whitelist()
def debug_sales_invoice_creation():
    """Debug why Sales Invoice creation fails with expense account error"""
    
    try:
        # Get the problematic mutation data
        mutation_273 = frappe.db.get_value(
            "EBoekhouden REST Mutation Cache",
            {"mutation_id": 273},
            ["mutation_data"],
            as_dict=True
        )
        
        if not mutation_273:
            return "Mutation 273 not found in cache"
        
        mutation_data = json.loads(mutation_273.mutation_data)
        
        # Test creating a Sales Invoice with minimal fields first
        si = frappe.new_doc("Sales Invoice")
        si.company = "Ned Ver Vegan"
        si.posting_date = mutation_data.get("date", "2019-01-01")
        
        # Get or create customer
        customer = frappe.db.get_value("Customer", 
            {"eboekhouden_relation_code": mutation_data.get("relationId")},
            "name"
        )
        
        if not customer:
            # Try generic customer
            customer = frappe.db.get_value("Customer", {"name": "Generic Customer"}, "name")
            if not customer:
                customer_doc = frappe.new_doc("Customer")
                customer_doc.customer_name = "Generic Customer"
                customer_doc.customer_group = "All Customer Groups"
                customer_doc.territory = "All Territories"
                customer_doc.save(ignore_permissions=True)
                customer = customer_doc.name
        
        si.customer = customer
        
        # Test 1: Add a simple item without any account mapping
        result = {
            "tests": [],
            "mutation_data": mutation_data,
            "customer": customer
        }
        
        # Test with basic E-Boekhouden Import Item
        try:
            si_test1 = frappe.copy_doc(si)
            si_test1.append("items", {
                "item_code": "E-Boekhouden Import Item",
                "item_name": "E-Boekhouden Import Item",
                "qty": 1,
                "rate": 100
            })
            si_test1.save()
            result["tests"].append({
                "test": "Basic item without accounts",
                "success": True,
                "message": "Sales invoice created successfully"
            })
        except Exception as e:
            result["tests"].append({
                "test": "Basic item without accounts",
                "success": False,
                "error": str(e),
                "traceback": frappe.get_traceback()
            })
        
        # Test 2: Add item with income account
        try:
            si_test2 = frappe.copy_doc(si)
            
            # Get a valid income account
            income_account = frappe.db.get_value("Account", {
                "company": "Ned Ver Vegan",
                "account_type": "Income Account",
                "is_group": 0
            }, "name")
            
            si_test2.append("items", {
                "item_code": "E-Boekhouden Import Item",
                "item_name": "E-Boekhouden Import Item",
                "qty": 1,
                "rate": 100,
                "income_account": income_account
            })
            si_test2.save()
            result["tests"].append({
                "test": "Item with income account",
                "success": True,
                "income_account": income_account,
                "message": "Sales invoice created successfully"
            })
        except Exception as e:
            result["tests"].append({
                "test": "Item with income account",
                "success": False,
                "error": str(e),
                "traceback": frappe.get_traceback()
            })
        
        # Test 3: Check if the item has expense account configured
        item_defaults = frappe.get_all("Item Default", 
            filters={"parent": "E-Boekhouden Import Item"},
            fields=["company", "expense_account", "income_account"]
        )
        
        result["item_defaults"] = item_defaults
        
        # Test 4: Try with the actual mutation data using smart mapper
        try:
            from verenigingen.utils.smart_tegenrekening_mapper import create_invoice_line_for_tegenrekening
            
            ledger_id = None
            amount = 0
            description = mutation_data.get("description", "")
            
            # Extract from rows
            rows = mutation_data.get("rows", [])
            if rows:
                ledger_id = rows[0].get("ledgerId")
                for row in rows:
                    amount += abs(float(row.get("amount", 0)))
            
            line_dict = create_invoice_line_for_tegenrekening(
                tegenrekening_code=str(ledger_id) if ledger_id else None,
                amount=amount,
                description=description,
                transaction_type="sales"
            )
            
            result["smart_mapper_result"] = line_dict
            
            # Try creating with smart mapper result
            si_test3 = frappe.copy_doc(si)
            si_test3.append("items", line_dict)
            si_test3.save()
            result["tests"].append({
                "test": "With smart mapper",
                "success": True,
                "line_dict": line_dict,
                "message": "Sales invoice created successfully"
            })
        except Exception as e:
            result["tests"].append({
                "test": "With smart mapper",
                "success": False,
                "error": str(e),
                "traceback": frappe.get_traceback()
            })
        
        # Test 5: Check if "Kostprijs omzet grondstoffen" exists anywhere
        # Search in accounts
        accounts_search = frappe.db.sql("""
            SELECT name, account_name 
            FROM `tabAccount` 
            WHERE account_name LIKE '%Kostprijs%' 
                OR account_name LIKE '%omzet%' 
                OR account_name LIKE '%grondstoffen%'
            LIMIT 10
        """, as_dict=True)
        
        result["account_search"] = accounts_search
        
        # Search in items
        items_search = frappe.db.sql("""
            SELECT name, item_name, description
            FROM `tabItem`
            WHERE item_name LIKE '%Kostprijs%'
                OR description LIKE '%Kostprijs%'
            LIMIT 10
        """, as_dict=True)
        
        result["items_search"] = items_search
        
        return result
        
    except Exception as e:
        return {
            "error": str(e),
            "traceback": frappe.get_traceback()
        }


@frappe.whitelist()
def check_erpnext_validations():
    """Check ERPNext validation hooks that might be causing the error"""
    
    try:
        # Check if there are any custom validations on Sales Invoice
        hooks = frappe.get_hooks()
        
        result = {
            "doc_events": {},
            "custom_fields": [],
            "server_scripts": []
        }
        
        # Check doc_events for Sales Invoice
        doc_events = hooks.get("doc_events", {})
        if "Sales Invoice" in doc_events:
            result["doc_events"]["Sales Invoice"] = doc_events["Sales Invoice"]
        
        # Check for any wildcard events
        if "*" in doc_events:
            result["doc_events"]["*"] = doc_events["*"]
        
        # Check custom fields on Sales Invoice Item
        custom_fields = frappe.get_all("Custom Field",
            filters={"dt": "Sales Invoice Item"},
            fields=["fieldname", "fieldtype", "label", "mandatory", "default"]
        )
        result["custom_fields"] = custom_fields
        
        # Check for server scripts
        server_scripts = frappe.get_all("Server Script",
            filters={
                "script_type": ["in", ["Before Save", "Before Submit", "Before Insert"]],
                "reference_doctype": ["in", ["Sales Invoice", "Sales Invoice Item"]]
            },
            fields=["name", "script_type", "reference_doctype"]
        )
        result["server_scripts"] = server_scripts
        
        # Check accounting dimensions
        from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import get_accounting_dimensions
        dimensions = get_accounting_dimensions()
        result["accounting_dimensions"] = dimensions
        
        # Check if expense account is being validated somewhere
        validation_files = []
        
        # Common ERPNext validation files
        validation_paths = [
            "/home/frappe/frappe-bench/apps/erpnext/erpnext/accounts/doctype/sales_invoice/sales_invoice.py",
            "/home/frappe/frappe-bench/apps/erpnext/erpnext/accounts/doctype/sales_invoice_item/sales_invoice_item.py",
            "/home/frappe/frappe-bench/apps/erpnext/erpnext/controllers/accounts_controller.py",
            "/home/frappe/frappe-bench/apps/erpnext/erpnext/stock/get_item_details.py"
        ]
        
        for path in validation_paths:
            try:
                with open(path, 'r') as f:
                    content = f.read()
                    if "expense_account" in content.lower() or "kostprijs" in content.lower():
                        validation_files.append({
                            "file": path,
                            "has_expense_account": "expense_account" in content.lower(),
                            "has_kostprijs": "kostprijs" in content.lower()
                        })
            except:
                pass
        
        result["validation_files"] = validation_files
        
        return result
        
    except Exception as e:
        return {
            "error": str(e),
            "traceback": frappe.get_traceback()
        }