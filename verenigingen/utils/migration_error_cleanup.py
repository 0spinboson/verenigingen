"""
Clean up migration errors and provide summary
"""

import frappe
from frappe import _


@frappe.whitelist()
def summarize_migration_errors(migration_name=None):
    """
    Summarize migration errors in a readable format
    """
    
    # Get recent error logs related to E-Boekhouden migration
    filters = {
        "error": ["like", "%Boekhouden%"],
        "creation": [">", frappe.utils.add_days(frappe.utils.now(), -1)]  # Last 24 hours
    }
    
    if migration_name:
        filters["error"] = ["like", f"%{migration_name}%"]
    
    error_logs = frappe.get_all(
        "Error Log",
        filters=filters,
        fields=["name", "error", "creation"],
        order_by="creation desc",
        limit=20
    )
    
    # Analyze errors
    error_summary = {}
    
    for log in error_logs:
        error_text = log.error or ""
        
        # Categorize errors
        if "Duplicate entry" in error_text and "Warehouse" in error_text:
            category = "Duplicate Warehouse"
            key = "warehouse_duplicate"
        elif "cannot be a fraction" in error_text:
            category = "Fractional Quantity"
            key = "fractional_quantity"
        elif "No parent cost center" in error_text:
            category = "Missing Cost Center"
            key = "missing_cost_center"
        elif "Error Log" in error_text and "will get truncated" in error_text:
            category = "Cascading Error Title"
            key = "cascading_error"
        else:
            category = "Other"
            key = "other"
        
        if key not in error_summary:
            error_summary[key] = {
                "category": category,
                "count": 0,
                "samples": []
            }
        
        error_summary[key]["count"] += 1
        
        # Keep first 2 samples
        if len(error_summary[key]["samples"]) < 2:
            error_summary[key]["samples"].append({
                "log_name": log.name,
                "created": log.creation,
                "error_preview": error_text[:200] + "..." if len(error_text) > 200 else error_text
            })
    
    # Generate summary report
    report_lines = []
    report_lines.append("=" * 60)
    report_lines.append("E-BOEKHOUDEN MIGRATION ERROR SUMMARY")
    report_lines.append("=" * 60)
    report_lines.append(f"Total error logs analyzed: {len(error_logs)}")
    report_lines.append("")
    
    for key, data in error_summary.items():
        report_lines.append(f"\n{data['category']}: {data['count']} occurrence(s)")
        report_lines.append("-" * 40)
        
        if key == "warehouse_duplicate":
            report_lines.append("Issue: Warehouse 'e-Boekhouden Migration - RSP' already exists")
            report_lines.append("Solution: The migration will now reuse the existing warehouse")
            
        elif key == "fractional_quantity":
            report_lines.append("Issue: Stock quantities cannot be fractional (e.g., 1971.79)")
            report_lines.append("Solution: Stock migration has been updated to skip these entries")
            report_lines.append("Action: Use manual stock adjustment after migration")
            
        elif key == "cascading_error":
            report_lines.append("Issue: Error titles becoming too long due to nesting")
            report_lines.append("Solution: Error logging has been improved to truncate titles properly")
            
        elif key == "missing_cost_center":
            report_lines.append("Issue: No root cost center exists for the company")
            report_lines.append("Solution: Cost centers are now auto-created when missing")
    
    report_lines.append("\n" + "=" * 60)
    report_lines.append("RECOMMENDATIONS:")
    report_lines.append("1. Re-run the migration - most issues have been fixed")
    report_lines.append("2. Stock entries require manual adjustment post-migration")
    report_lines.append("3. Check 'Map Account Types' button to fix receivable/payable accounts")
    
    return "\n".join(report_lines)


@frappe.whitelist()
def clean_cascading_error_logs():
    """
    Clean up cascading error logs that have become unreadable
    """
    
    # Find error logs with cascading titles
    cascading_logs = frappe.db.sql("""
        SELECT name, error
        FROM `tabError Log`
        WHERE error LIKE '%will get truncated%'
        AND error LIKE '%Error Log%'
        AND creation > DATE_SUB(NOW(), INTERVAL 7 DAY)
    """, as_dict=True)
    
    cleaned = 0
    
    for log in cascading_logs:
        try:
            # Extract the root cause
            error_text = log.error
            
            # Find the actual error message
            if "IntegrityError" in error_text:
                if "Duplicate entry" in error_text:
                    import re
                    match = re.search(r"Duplicate entry '([^']+)'", error_text)
                    if match:
                        root_cause = f"Duplicate entry: {match.group(1)}"
                    else:
                        root_cause = "Duplicate entry error"
                else:
                    root_cause = "Database integrity error"
            elif "cannot be a fraction" in error_text:
                root_cause = "Fractional quantity not allowed in stock entry"
            else:
                # Try to extract first meaningful error
                lines = error_text.split(":")
                for line in lines:
                    if "Error" not in line and len(line.strip()) > 10:
                        root_cause = line.strip()[:100]
                        break
                else:
                    root_cause = "Migration error"
            
            # Update the error log with cleaned title
            frappe.db.set_value(
                "Error Log",
                log.name,
                "error",
                f"[CLEANED] {root_cause}\n\nOriginal cascading error has been cleaned for readability."
            )
            cleaned += 1
            
        except Exception as e:
            print(f"Could not clean log {log.name}: {str(e)}")
    
    frappe.db.commit()
    
    return {
        "success": True,
        "cleaned": cleaned,
        "message": f"Cleaned {cleaned} cascading error logs"
    }