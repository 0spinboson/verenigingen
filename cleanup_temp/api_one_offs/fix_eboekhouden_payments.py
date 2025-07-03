"""
API endpoints to fix E-Boekhouden payment failures
"""

import frappe
from frappe import _
import json

@frappe.whitelist()
def fix_missing_suppliers(migration_id=None):
    """
    Fix missing suppliers from E-Boekhouden migrations
    
    Args:
        migration_id: Optional specific migration to fix
        
    Returns:
        Dict with results
    """
    if not frappe.has_permission("E-Boekhouden Migration", "write"):
        frappe.throw(_("Insufficient permissions"))
    
    results = {
        "created_suppliers": [],
        "errors": [],
        "total_created": 0
    }
    
    try:
        # Get list of missing suppliers
        missing_suppliers = ['00038', '00019', '00002', '1343', '1344', '197']
        
        for code in missing_suppliers:
            # Check if supplier already exists
            if frappe.db.exists("Supplier", code):
                continue
            
            # Check alternate names
            alt_exists = False
            for pattern in [f"Supplier {code}", f"Leverancier {code}"]:
                if frappe.db.exists("Supplier", pattern):
                    alt_exists = True
                    break
            
            if alt_exists:
                continue
            
            # Create supplier
            try:
                supplier = frappe.new_doc("Supplier")
                supplier.supplier_name = code
                supplier.eboekhouden_relation_code = code
                supplier.supplier_group = frappe.db.get_value("Supplier Group", 
                    {"is_group": 0}, "name") or "All Supplier Groups"
                supplier.insert(ignore_permissions=True)
                
                results["created_suppliers"].append(code)
                results["total_created"] += 1
                
            except Exception as e:
                results["errors"].append(f"Failed to create supplier {code}: {str(e)}")
        
        frappe.db.commit()
        
    except Exception as e:
        results["errors"].append(str(e))
    
    return results

@frappe.whitelist()
def fix_cost_centers():
    """
    Fix cost centers that should be groups
    
    Returns:
        Dict with results
    """
    if not frappe.has_permission("Cost Center", "write"):
        frappe.throw(_("Insufficient permissions"))
    
    results = {
        "fixed_cost_centers": [],
        "errors": [],
        "total_fixed": 0
    }
    
    try:
        # Find cost centers with specific names that should be groups
        problem_names = ["maanden - NVV"]
        
        for name_pattern in problem_names:
            cost_centers = frappe.db.get_all("Cost Center",
                filters={"cost_center_name": ["like", f"%{name_pattern}%"]},
                fields=["name", "is_group"])
            
            for cc in cost_centers:
                if not cc.is_group:
                    try:
                        frappe.db.set_value("Cost Center", cc.name, "is_group", 1)
                        results["fixed_cost_centers"].append(cc.name)
                        results["total_fixed"] += 1
                    except Exception as e:
                        results["errors"].append(f"Failed to fix {cc.name}: {str(e)}")
        
        frappe.db.commit()
        
    except Exception as e:
        results["errors"].append(str(e))
    
    return results

@frappe.whitelist()
def retry_failed_payments(migration_id):
    """
    Retry failed supplier payments from a specific migration
    
    Args:
        migration_id: The E-Boekhouden migration ID
        
    Returns:
        Dict with results
    """
    if not frappe.has_permission("E-Boekhouden Migration", "write"):
        frappe.throw(_("Insufficient permissions"))
    
    results = {
        "retried": 0,
        "successful": 0,
        "failed": 0,
        "errors": []
    }
    
    try:
        # Get the migration document
        migration = frappe.get_doc("E-Boekhouden Migration", migration_id)
        
        # Look for failed records log file
        import os
        log_dir = frappe.get_site_path("private", "files", "eboekhouden_migration_logs")
        log_file = None
        
        # Find the log file for this migration
        for filename in os.listdir(log_dir):
            if migration_id in filename and filename.endswith(".json"):
                log_file = os.path.join(log_dir, filename)
                break
        
        if not log_file or not os.path.exists(log_file):
            return {
                "error": "No failed records log found for this migration"
            }
        
        # Read failed records
        with open(log_file, 'r') as f:
            data = json.load(f)
        
        failed_records = data.get("failed_records", [])
        
        # Import required functions
        from verenigingen.utils.eboekhouden_soap_migration import (
            process_supplier_payments, get_or_create_supplier
        )
        from verenigingen.utils.create_unreconciled_payment import create_unreconciled_payment_entry
        
        # Process each failed record
        for record in failed_records:
            if record.get("record_type") != "supplier_payment":
                continue
            
            results["retried"] += 1
            
            try:
                mutation = record.get("record_data", {})
                
                # Ensure supplier exists
                supplier_code = mutation.get("RelatieCode")
                if supplier_code:
                    supplier = get_or_create_supplier(
                        supplier_code, 
                        mutation.get("Omschrijving", "")
                    )
                    
                    # Try to create unreconciled payment
                    result = create_unreconciled_payment_entry(
                        mutation, 
                        migration.company,
                        migration.default_cost_center,
                        "Supplier"
                    )
                    
                    if result["success"]:
                        results["successful"] += 1
                    else:
                        results["failed"] += 1
                        results["errors"].append(result.get("error", "Unknown error"))
                else:
                    results["failed"] += 1
                    results["errors"].append("No supplier code in mutation")
                    
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(str(e))
        
        frappe.db.commit()
        
    except Exception as e:
        results["errors"].append(str(e))
    
    return results

@frappe.whitelist()
def get_migration_summary(migration_id):
    """
    Get summary of failed records for a migration
    
    Args:
        migration_id: The E-Boekhouden migration ID
        
    Returns:
        Dict with summary
    """
    if not frappe.has_permission("E-Boekhouden Migration", "read"):
        frappe.throw(_("Insufficient permissions"))
    
    try:
        # Look for failed records log file
        import os
        log_dir = frappe.get_site_path("private", "files", "eboekhouden_migration_logs")
        log_file = None
        
        # Find the log file for this migration
        for filename in os.listdir(log_dir):
            if migration_id in filename and filename.endswith(".json"):
                log_file = os.path.join(log_dir, filename)
                break
        
        if not log_file or not os.path.exists(log_file):
            return {
                "error": "No failed records log found for this migration"
            }
        
        # Read failed records
        with open(log_file, 'r') as f:
            data = json.load(f)
        
        # Summarize failures
        summary = {
            "migration_name": data.get("migration_name"),
            "migration_id": data.get("migration_id"),
            "timestamp": data.get("timestamp"),
            "total_failed": data.get("total_failed", 0),
            "failure_types": {},
            "missing_suppliers": set()
        }
        
        for record in data.get("failed_records", []):
            record_type = record.get("record_type", "unknown")
            
            if record_type not in summary["failure_types"]:
                summary["failure_types"][record_type] = {
                    "count": 0,
                    "errors": {}
                }
            
            summary["failure_types"][record_type]["count"] += 1
            
            # Extract error patterns
            error_msg = record.get("error_message", "")
            if "Could not find Party: Supplier" in error_msg:
                # Extract supplier code
                import re
                match = re.search(r'Supplier (\w+)', error_msg)
                if match:
                    summary["missing_suppliers"].add(match.group(1))
                    
                error_key = "Missing supplier"
            else:
                error_key = error_msg.split(":")[0] if ":" in error_msg else error_msg[:50]
            
            if error_key not in summary["failure_types"][record_type]["errors"]:
                summary["failure_types"][record_type]["errors"][error_key] = 0
            summary["failure_types"][record_type]["errors"][error_key] += 1
        
        # Convert set to list for JSON serialization
        summary["missing_suppliers"] = list(summary["missing_suppliers"])
        
        return summary
        
    except Exception as e:
        return {"error": str(e)}