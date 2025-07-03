"""
Comprehensive E-Boekhouden migration fix to handle all transaction types
"""

import frappe
from frappe import _
import json

@frappe.whitelist()
def apply_comprehensive_fixes():
    """
    Apply all necessary fixes for E-Boekhouden migration issues
    
    Returns:
        Dict with results
    """
    if not frappe.has_permission("E-Boekhouden Migration", "write"):
        frappe.throw(_("Insufficient permissions"))
    
    results = {
        "suppliers_fixed": 0,
        "cost_centers_fixed": 0,
        "accounts_fixed": 0,
        "errors": [],
        "warnings": []
    }
    
    try:
        # 1. Fix all missing suppliers
        supplier_codes = ['00038', '00019', '00002', '1343', '1344', '197']
        
        for code in supplier_codes:
            # Check multiple naming patterns
            exists = False
            for pattern in [code, f"Supplier {code}", f"Leverancier {code}"]:
                if frappe.db.exists("Supplier", pattern):
                    exists = True
                    break
            
            if not exists:
                try:
                    # Create supplier with code as name
                    supplier = frappe.new_doc("Supplier")
                    supplier.supplier_name = code
                    supplier.eboekhouden_relation_code = code
                    supplier.supplier_group = frappe.db.get_value("Supplier Group", 
                        {"is_group": 0}, "name") or "All Supplier Groups"
                    supplier.insert(ignore_permissions=True)
                    results["suppliers_fixed"] += 1
                except Exception as e:
                    results["errors"].append(f"Supplier {code}: {str(e)}")
        
        # 2. Fix cost centers
        cost_centers = frappe.db.get_all("Cost Center",
            filters={"cost_center_name": ["like", "%maanden - NVV%"]},
            fields=["name", "is_group"])
        
        for cc in cost_centers:
            if not cc.is_group:
                try:
                    frappe.db.set_value("Cost Center", cc.name, "is_group", 1)
                    results["cost_centers_fixed"] += 1
                except Exception as e:
                    results["errors"].append(f"Cost Center {cc.name}: {str(e)}")
        
        # 3. Fix account types for common issues
        fix_account_types(results)
        
        # 4. Ensure required entities exist
        ensure_required_entities(results)
        
        frappe.db.commit()
        
        # Generate summary
        results["summary"] = f"""
        Fixes Applied:
        - Suppliers created/fixed: {results['suppliers_fixed']}
        - Cost centers fixed: {results['cost_centers_fixed']}
        - Accounts fixed: {results['accounts_fixed']}
        - Errors: {len(results['errors'])}
        - Warnings: {len(results['warnings'])}
        """
        
    except Exception as e:
        results["errors"].append(f"Critical error: {str(e)}")
    
    return results

def fix_account_types(results):
    """Fix common account type issues"""
    try:
        # Get company
        company = frappe.db.get_single_value("E-Boekhouden Settings", "default_company")
        if not company:
            results["warnings"].append("No default company set in E-Boekhouden Settings")
            return
        
        # Common account codes that need specific types
        account_type_mappings = {
            # Bank accounts
            "1040": "Bank",
            "10440": "Bank",
            "10400": "Bank",
            
            # Receivable accounts
            "1300": "Receivable",
            "13000": "Receivable",
            "13100": "Receivable",
            
            # Payable accounts
            "1600": "Payable",
            "16000": "Payable",
            "16100": "Payable",
            "19290": "Payable",
            
            # Tax accounts
            "1820": "Tax",
            "18200": "Tax",
            "1810": "Tax",
            "18100": "Tax"
        }
        
        for code, account_type in account_type_mappings.items():
            accounts = frappe.db.get_all("Account",
                filters={
                    "account_number": code,
                    "company": company
                },
                fields=["name", "account_type"])
            
            for account in accounts:
                if account.account_type != account_type:
                    try:
                        frappe.db.set_value("Account", account.name, "account_type", account_type)
                        results["accounts_fixed"] += 1
                    except Exception as e:
                        results["warnings"].append(f"Account {account.name}: {str(e)}")
        
    except Exception as e:
        results["errors"].append(f"Account type fix error: {str(e)}")

def ensure_required_entities(results):
    """Ensure all required entities exist for migration"""
    try:
        company = frappe.db.get_single_value("E-Boekhouden Settings", "default_company")
        if not company:
            return
        
        # Ensure default item exists
        if not frappe.db.exists("Item", "E-Boekhouden Service"):
            try:
                item = frappe.new_doc("Item")
                item.item_code = "E-Boekhouden Service"
                item.item_name = "E-Boekhouden Service"
                item.item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups"
                item.stock_uom = "Nos"
                item.is_stock_item = 0
                item.include_item_in_manufacturing = 0
                item.insert(ignore_permissions=True)
                results["warnings"].append("Created default service item")
            except Exception as e:
                results["warnings"].append(f"Could not create default item: {str(e)}")
        
        # Ensure unmatched customer/supplier exist
        for party_type, party_name in [("Customer", "UNMATCHED"), ("Supplier", "UNMATCHED")]:
            if not frappe.db.exists(party_type, party_name):
                try:
                    party = frappe.new_doc(party_type)
                    if party_type == "Customer":
                        party.customer_name = party_name
                        party.customer_group = frappe.db.get_value("Customer Group", 
                            {"is_group": 0}, "name") or "All Customer Groups"
                        party.territory = frappe.db.get_value("Territory", 
                            {"is_group": 0}, "name") or "All Territories"
                    else:
                        party.supplier_name = party_name
                        party.supplier_group = frappe.db.get_value("Supplier Group", 
                            {"is_group": 0}, "name") or "All Supplier Groups"
                    party.insert(ignore_permissions=True)
                    results["warnings"].append(f"Created {party_type}: {party_name}")
                except Exception as e:
                    results["warnings"].append(f"Could not create {party_type} {party_name}: {str(e)}")
        
    except Exception as e:
        results["errors"].append(f"Entity creation error: {str(e)}")

@frappe.whitelist()
def validate_migration_readiness():
    """
    Check if system is ready for migration
    
    Returns:
        Dict with validation results
    """
    if not frappe.has_permission("E-Boekhouden Settings", "read"):
        frappe.throw(_("Insufficient permissions"))
    
    validation = {
        "ready": True,
        "issues": [],
        "warnings": []
    }
    
    try:
        # Check E-Boekhouden settings
        settings = frappe.get_single("E-Boekhouden Settings")
        
        if not settings.default_company:
            validation["ready"] = False
            validation["issues"].append("No default company set in E-Boekhouden Settings")
        
        if not settings.gebruikersnaam or not settings.get_password("wachtwoord"):
            validation["ready"] = False
            validation["issues"].append("E-Boekhouden credentials not configured")
        
        # Check cost centers
        if settings.default_company:
            cost_centers = frappe.db.count("Cost Center", {
                "company": settings.default_company,
                "is_group": 0
            })
            
            if cost_centers == 0:
                validation["ready"] = False
                validation["issues"].append("No cost centers found for company")
        
        # Check for common issues
        problem_cost_centers = frappe.db.get_all("Cost Center",
            filters={
                "cost_center_name": ["like", "%maanden - NVV%"],
                "is_group": 0
            })
        
        if problem_cost_centers:
            validation["warnings"].append(f"{len(problem_cost_centers)} cost centers need to be fixed")
        
        # Check for missing suppliers
        supplier_codes = ['00038', '00019', '00002', '1343', '1344', '197']
        missing = []
        
        for code in supplier_codes:
            exists = False
            for pattern in [code, f"Supplier {code}", f"Leverancier {code}"]:
                if frappe.db.exists("Supplier", pattern):
                    exists = True
                    break
            if not exists:
                missing.append(code)
        
        if missing:
            validation["warnings"].append(f"Missing suppliers: {', '.join(missing)}")
        
        # Check account types
        if settings.default_company:
            bank_accounts = frappe.db.count("Account", {
                "company": settings.default_company,
                "account_type": "Bank",
                "is_group": 0
            })
            
            if bank_accounts == 0:
                validation["warnings"].append("No bank accounts configured")
        
    except Exception as e:
        validation["ready"] = False
        validation["issues"].append(f"Validation error: {str(e)}")
    
    return validation

@frappe.whitelist()
def get_migration_statistics():
    """
    Get statistics about E-Boekhouden migrations
    
    Returns:
        Dict with statistics
    """
    if not frappe.has_permission("E-Boekhouden Migration", "read"):
        frappe.throw(_("Insufficient permissions"))
    
    try:
        stats = {
            "total_migrations": frappe.db.count("E-Boekhouden Migration"),
            "successful_migrations": 0,
            "failed_migrations": 0,
            "total_imported": {
                "sales_invoices": 0,
                "purchase_invoices": 0,
                "payments": 0,
                "journal_entries": 0
            },
            "total_errors": 0,
            "common_errors": {}
        }
        
        # Get all migrations
        migrations = frappe.db.get_all("E-Boekhouden Migration",
            fields=["name", "status", "import_summary"])
        
        for migration in migrations:
            if migration.status == "Completed":
                stats["successful_migrations"] += 1
            else:
                stats["failed_migrations"] += 1
            
            # Parse summary if available
            if migration.import_summary:
                try:
                    # Extract counts from summary
                    summary = migration.import_summary
                    
                    # Look for patterns in summary
                    import re
                    
                    # Sales invoices
                    match = re.search(r'sales.*?invoices.*?created.*?(\d+)', summary, re.IGNORECASE)
                    if match:
                        stats["total_imported"]["sales_invoices"] += int(match.group(1))
                    
                    # Purchase invoices
                    match = re.search(r'purchase.*?invoices.*?created.*?(\d+)', summary, re.IGNORECASE)
                    if match:
                        stats["total_imported"]["purchase_invoices"] += int(match.group(1))
                    
                    # Payments
                    match = re.search(r'payments.*?processed.*?(\d+)', summary, re.IGNORECASE)
                    if match:
                        stats["total_imported"]["payments"] += int(match.group(1))
                    
                    # Journal entries
                    match = re.search(r'journal.*?entries.*?created.*?(\d+)', summary, re.IGNORECASE)
                    if match:
                        stats["total_imported"]["journal_entries"] += int(match.group(1))
                    
                    # Errors
                    match = re.search(r'System Errors.*?(\d+)', summary)
                    if match:
                        stats["total_errors"] += int(match.group(1))
                    
                except:
                    pass
        
        return stats
        
    except Exception as e:
        return {"error": str(e)}