"""
Prepare system for E-Boekhouden migration
Run this before starting the migration to avoid common errors
"""

import frappe
from frappe import _

@frappe.whitelist()
def prepare_system_for_migration():
    """
    Comprehensive preparation for E-Boekhouden migration
    """
    results = []
    company = frappe.db.get_single_value("E-Boekhouden Settings", "default_company")
    
    if not company:
        return {
            "success": False,
            "error": "Please set default company in E-Boekhouden Settings first"
        }
    
    # 1. Get main cost center
    main_cc = frappe.db.get_value("Cost Center", {
        "company": company,
        "is_group": 1,
        "parent_cost_center": ["in", ["", None]]
    }, "name")
    
    results.append({
        "step": "Main Cost Center",
        "success": bool(main_cc),
        "value": main_cc or "Not found"
    })
    
    # 2. Create default Customer and Supplier
    default_customer = "E-Boekhouden Import Customer"
    if not frappe.db.exists("Customer", default_customer):
        try:
            customer = frappe.new_doc("Customer")
            customer.customer_name = default_customer
            customer.customer_type = "Company"
            customer.customer_group = frappe.db.get_value("Customer Group", {"is_group": 0}, "name") or "All Customer Groups"
            customer.territory = frappe.db.get_value("Territory", {"is_group": 0}, "name") or "All Territories"
            customer.insert(ignore_permissions=True)
            results.append({
                "step": "Default Customer",
                "success": True,
                "value": f"Created: {customer.name}"
            })
        except Exception as e:
            results.append({
                "step": "Default Customer",
                "success": False,
                "value": str(e)
            })
    else:
        results.append({
            "step": "Default Customer",
            "success": True,
            "value": "Already exists"
        })
    
    default_supplier = "E-Boekhouden Import Supplier"
    if not frappe.db.exists("Supplier", default_supplier):
        try:
            supplier = frappe.new_doc("Supplier")
            supplier.supplier_name = default_supplier
            supplier.supplier_group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name") or "All Supplier Groups"
            supplier.insert(ignore_permissions=True)
            results.append({
                "step": "Default Supplier",
                "success": True,
                "value": f"Created: {supplier.name}"
            })
        except Exception as e:
            results.append({
                "step": "Default Supplier",
                "success": False,
                "value": str(e)
            })
    else:
        results.append({
            "step": "Default Supplier",
            "success": True,
            "value": "Already exists"
        })
    
    # 3. Create suspense account for unclear transactions
    suspense_name = "E-Boekhouden Suspense Account"
    if not frappe.db.exists("Account", {"company": company, "account_name": suspense_name}):
        try:
            parent = frappe.db.get_value("Account", {
                "company": company,
                "root_type": "Asset",
                "is_group": 1
            }, "name")
            
            acc = frappe.new_doc("Account")
            acc.account_name = suspense_name
            acc.company = company
            acc.parent_account = parent
            acc.account_type = "Temporary"
            acc.root_type = "Asset"
            acc.insert(ignore_permissions=True)
            results.append({
                "step": "Suspense Account",
                "success": True,
                "value": f"Created: {acc.name}"
            })
        except Exception as e:
            results.append({
                "step": "Suspense Account",
                "success": False,
                "value": str(e)
            })
    else:
        results.append({
            "step": "Suspense Account",
            "success": True,
            "value": "Already exists"
        })
    
    # 4. Temporarily set Receivable/Payable accounts to Current Asset/Liability
    receivables_changed = 0
    payables_changed = 0
    
    # These accounts cause issues during migration if set as Receivable/Payable
    problem_accounts = {
        "Receivable": ["13500", "13510", "13600", "13900"],
        "Payable": ["19290", "44000", "44900"]
    }
    
    for acc_type, account_numbers in problem_accounts.items():
        for acc_num in account_numbers:
            account = frappe.db.get_value("Account", {
                "company": company,
                "account_number": acc_num,
                "account_type": acc_type
            }, "name")
            
            if account:
                new_type = "Current Asset" if acc_type == "Receivable" else "Current Liability"
                frappe.db.set_value("Account", account, "account_type", new_type)
                
                if acc_type == "Receivable":
                    receivables_changed += 1
                else:
                    payables_changed += 1
    
    frappe.db.commit()
    
    results.append({
        "step": "Account Type Adjustment",
        "success": True,
        "value": f"Changed {receivables_changed} Receivable and {payables_changed} Payable accounts temporarily"
    })
    
    # 5. Check API connection
    from vereiningen.utils.eboekhouden_api import test_api_connection
    api_test = test_api_connection()
    results.append({
        "step": "API Connection",
        "success": api_test.get("success", False),
        "value": "Connected" if api_test.get("success") else api_test.get("error", "Failed")
    })
    
    # Summary
    all_success = all(r["success"] for r in results)
    
    return {
        "success": all_success,
        "results": results,
        "message": "System is ready for migration!" if all_success else "Some preparation steps failed",
        "cost_center": main_cc,
        "reminder": "Remember to run 'Fix Account Types' after migration completes to restore Receivable/Payable accounts"
    }