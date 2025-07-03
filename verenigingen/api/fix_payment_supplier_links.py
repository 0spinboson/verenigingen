"""
Fix supplier links in failed payment entries
"""

import frappe
from frappe import _
import json
import os

@frappe.whitelist()
def analyze_payment_failures(migration_id):
    """
    Analyze why payments are failing with supplier link errors
    
    Args:
        migration_id: The E-Boekhouden migration ID
        
    Returns:
        Dict with analysis
    """
    if not frappe.has_permission("E-Boekhouden Migration", "read"):
        frappe.throw(_("Insufficient permissions"))
    
    try:
        # Get supplier mapping
        supplier_map = {
            "00038": "NL86INGB0002445588 INGBNL2A Belastingdienst TRIO DOS NL 20250530 31751360 STRD 1008125556501040",
            "00019": "René Beemer",
            "00002": "NL10RABO0373122209 RABONL2U Koninklijke PostNL B.V. E REF 070200537218 010000338072 NL96ZZZ273620000000 RE MI USTD 1106-2519359",
            "1343": "Univ Leiden",
            "1344": "Harmke Berghuis",
            "197": "Trai Vegan"
        }
        
        analysis = {
            "migration_id": migration_id,
            "supplier_issues": {},
            "purchase_invoice_issues": [],
            "recommendations": []
        }
        
        # Check for purchase invoices with wrong supplier references
        for code, correct_name in supplier_map.items():
            # Find purchase invoices that might have wrong supplier
            wrong_invoices = frappe.db.get_all("Purchase Invoice",
                filters={
                    "supplier": code,
                    "docstatus": ["!=", 2]
                },
                fields=["name", "supplier", "outstanding_amount"])
            
            if wrong_invoices:
                analysis["purchase_invoice_issues"].extend(wrong_invoices)
                analysis["supplier_issues"][code] = {
                    "correct_name": correct_name,
                    "invoices_with_wrong_supplier": len(wrong_invoices),
                    "total_outstanding": sum(inv.get("outstanding_amount", 0) for inv in wrong_invoices)
                }
        
        # Add recommendations
        if analysis["supplier_issues"]:
            analysis["recommendations"].append({
                "issue": "Purchase invoices have incorrect supplier references",
                "action": "Run fix_purchase_invoice_suppliers() to update supplier references",
                "impact": f"{len(analysis['purchase_invoice_issues'])} invoices need updating"
            })
        
        return analysis
        
    except Exception as e:
        return {"error": str(e)}

@frappe.whitelist()
def fix_purchase_invoice_suppliers():
    """
    Fix supplier references in purchase invoices
    
    Returns:
        Dict with results
    """
    if not frappe.has_permission("Purchase Invoice", "write"):
        frappe.throw(_("Insufficient permissions"))
    
    results = {
        "fixed_invoices": 0,
        "errors": [],
        "details": []
    }
    
    try:
        # Supplier code to correct name mapping
        supplier_map = {
            "00038": "NL86INGB0002445588 INGBNL2A Belastingdienst TRIO DOS NL 20250530 31751360 STRD 1008125556501040",
            "00019": "René Beemer", 
            "00002": "NL10RABO0373122209 RABONL2U Koninklijke PostNL B.V. E REF 070200537218 010000338072 NL96ZZZ273620000000 RE MI USTD 1106-2519359",
            "1343": "Univ Leiden",
            "1344": "Harmke Berghuis",
            "197": "Trai Vegan"
        }
        
        for code, correct_name in supplier_map.items():
            # Verify correct supplier exists
            if not frappe.db.exists("Supplier", correct_name):
                results["errors"].append(f"Supplier '{correct_name}' not found for code {code}")
                continue
            
            # Find purchase invoices with wrong supplier
            invoices = frappe.db.get_all("Purchase Invoice",
                filters={
                    "supplier": code,
                    "docstatus": ["!=", 2]  # Not cancelled
                },
                fields=["name", "docstatus"])
            
            for invoice in invoices:
                try:
                    # Update the supplier
                    frappe.db.set_value("Purchase Invoice", invoice["name"], "supplier", correct_name)
                    results["fixed_invoices"] += 1
                    results["details"].append(f"Updated {invoice['name']}: {code} → {correct_name}")
                except Exception as e:
                    results["errors"].append(f"Could not update {invoice['name']}: {str(e)}")
        
        frappe.db.commit()
        
    except Exception as e:
        results["errors"].append(str(e))
    
    return results

@frappe.whitelist()
def create_payment_retry_batch(migration_id):
    """
    Create a batch of payment entries that can be retried
    
    Args:
        migration_id: The E-Boekhouden migration ID
        
    Returns:
        Dict with batch details
    """
    if not frappe.has_permission("E-Boekhouden Migration", "write"):
        frappe.throw(_("Insufficient permissions"))
    
    try:
        # Read failed records
        log_dir = frappe.get_site_path("private", "files", "eboekhouden_migration_logs")
        log_file = None
        
        for filename in os.listdir(log_dir):
            if migration_id in filename and filename.endswith(".json"):
                log_file = os.path.join(log_dir, filename)
                break
        
        if not log_file:
            return {"error": "No failed records log found"}
        
        with open(log_file, 'r') as f:
            data = json.load(f)
        
        # Prepare retry batch
        batch = {
            "migration_id": migration_id,
            "total_failed": data.get("total_failed", 0),
            "supplier_payment_failures": [],
            "retry_ready": []
        }
        
        # Get supplier mapping
        from verenigingen.utils.eboekhouden_soap_migration import get_or_create_supplier
        
        for record in data.get("failed_records", []):
            if record.get("record_type") == "supplier_payment":
                mutation = record.get("record_data", {})
                supplier_code = mutation.get("RelatieCode")
                
                if supplier_code:
                    # Get correct supplier name
                    correct_supplier = get_or_create_supplier(
                        supplier_code,
                        mutation.get("Omschrijving", "")
                    )
                    
                    batch["retry_ready"].append({
                        "mutation": mutation,
                        "supplier_code": supplier_code,
                        "correct_supplier": correct_supplier,
                        "invoice_number": mutation.get("Factuurnummer")
                    })
        
        batch["total_retry_ready"] = len(batch["retry_ready"])
        
        # Save batch for processing
        batch_file = os.path.join(log_dir, f"retry_batch_{migration_id}.json")
        with open(batch_file, 'w') as f:
            json.dump(batch, f, indent=2)
        
        return {
            "batch_created": True,
            "batch_file": batch_file,
            "total_ready": batch["total_retry_ready"]
        }
        
    except Exception as e:
        return {"error": str(e)}

@frappe.whitelist()
def get_failed_payment_summary(migration_id):
    """
    Get a summary of failed payments grouped by issue type
    
    Args:
        migration_id: The E-Boekhouden migration ID
        
    Returns:
        Dict with summary
    """
    if not frappe.has_permission("E-Boekhouden Migration", "read"):
        frappe.throw(_("Insufficient permissions"))
    
    try:
        # Read the debug log to understand the actual errors
        debug_dir = frappe.get_site_path("private", "files", "eboekhouden_debug_logs")
        debug_file = None
        
        for filename in os.listdir(debug_dir):
            if migration_id in filename:
                debug_file = os.path.join(debug_dir, filename)
                break
        
        if not debug_file:
            return {"error": "No debug log found"}
        
        summary = {
            "total_errors": 0,
            "supplier_not_found": {},
            "invoice_not_found": 0,
            "other_errors": []
        }
        
        with open(debug_file, 'r') as f:
            content = f.read()
        
        # Parse error blocks
        import re
        
        # Count supplier not found errors
        supplier_errors = re.findall(r'Could not find Party: Supplier (\w+)', content)
        for supplier in supplier_errors:
            if supplier not in summary["supplier_not_found"]:
                summary["supplier_not_found"][supplier] = 0
            summary["supplier_not_found"][supplier] += 1
            summary["total_errors"] += 1
        
        # Count invoice not found  
        invoice_errors = len(re.findall(r'invoice_not_found', content))
        summary["invoice_not_found"] = invoice_errors
        summary["total_errors"] += invoice_errors
        
        return summary
        
    except Exception as e:
        return {"error": str(e)}