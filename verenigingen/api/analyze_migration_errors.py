"""
Analyze E-Boekhouden migration errors to understand what's failing
"""

import frappe
from frappe import _
import json
import os
from collections import defaultdict

@frappe.whitelist()
def analyze_migration_errors(migration_id):
    """
    Analyze all errors from a migration to understand what's failing
    
    Args:
        migration_id: The E-Boekhouden migration ID
        
    Returns:
        Dict with detailed error analysis
    """
    if not frappe.has_permission("E-Boekhouden Migration", "read"):
        frappe.throw(_("Insufficient permissions"))
    
    try:
        # Get the migration document
        migration = frappe.get_doc("E-Boekhouden Migration", migration_id)
        
        # Look for debug log files
        debug_dir = frappe.get_site_path("private", "files", "eboekhouden_debug_logs")
        failed_records_dir = frappe.get_site_path("private", "files", "eboekhouden_migration_logs")
        
        analysis = {
            "migration_id": migration_id,
            "error_patterns": defaultdict(int),
            "error_types": defaultdict(list),
            "sample_errors": [],
            "supplier_issues": defaultdict(int),
            "transaction_types": defaultdict(int),
            "recommendations": []
        }
        
        # Find and analyze debug log
        debug_log = None
        for filename in os.listdir(debug_dir) if os.path.exists(debug_dir) else []:
            if migration_id in filename:
                debug_log = os.path.join(debug_dir, filename)
                break
        
        if debug_log and os.path.exists(debug_log):
            with open(debug_log, 'r') as f:
                content = f.read()
                
            # Parse error entries
            error_blocks = content.split("=" * 80)
            
            for block in error_blocks[:50]:  # Analyze first 50 errors
                if "MIGRATION ERROR:" in block:
                    # Extract error details
                    lines = block.strip().split('\n')
                    
                    for line in lines:
                        if "MIGRATION ERROR:" in line:
                            error_msg = line.split("MIGRATION ERROR:", 1)[1].strip()
                            
                            # Categorize by error type
                            if "Could not find Party: Supplier" in error_msg:
                                # Extract supplier code
                                import re
                                match = re.search(r'Supplier (\w+)', error_msg)
                                if match:
                                    supplier_code = match.group(1)
                                    analysis["supplier_issues"][supplier_code] += 1
                                    analysis["error_patterns"]["Missing Supplier"] += 1
                            elif "is not a group node" in error_msg:
                                analysis["error_patterns"]["Cost Center Not Group"] += 1
                            elif "mandatory" in error_msg.lower():
                                analysis["error_patterns"]["Mandatory Field Missing"] += 1
                            elif "duplicate" in error_msg.lower():
                                analysis["error_patterns"]["Duplicate Entry"] += 1
                            elif "permission" in error_msg.lower():
                                analysis["error_patterns"]["Permission Error"] += 1
                            else:
                                # Capture other patterns
                                error_key = error_msg[:50] + "..." if len(error_msg) > 50 else error_msg
                                analysis["error_patterns"][error_key] += 1
                            
                            # Add to samples
                            if len(analysis["sample_errors"]) < 10:
                                analysis["sample_errors"].append(error_msg)
        
        # Analyze failed records JSON
        failed_records_file = None
        for filename in os.listdir(failed_records_dir) if os.path.exists(failed_records_dir) else []:
            if migration_id in filename and filename.endswith(".json"):
                failed_records_file = os.path.join(failed_records_dir, filename)
                break
        
        if failed_records_file and os.path.exists(failed_records_file):
            with open(failed_records_file, 'r') as f:
                data = json.load(f)
            
            # Count by record type
            for record in data.get("failed_records", []):
                record_type = record.get("record_type", "unknown")
                analysis["transaction_types"][record_type] += 1
                
                # Extract error patterns
                error_msg = record.get("error_message", "")
                if error_msg:
                    error_type = categorize_error(error_msg)
                    analysis["error_types"][error_type].append(error_msg[:100])
        
        # Generate recommendations
        if analysis["supplier_issues"]:
            analysis["recommendations"].append({
                "issue": "Missing Suppliers",
                "count": sum(analysis["supplier_issues"].values()),
                "action": "Run fix_missing_suppliers() to create missing suppliers",
                "details": f"Missing supplier codes: {', '.join(analysis['supplier_issues'].keys())}"
            })
        
        if "Cost Center Not Group" in analysis["error_patterns"]:
            analysis["recommendations"].append({
                "issue": "Cost Center Configuration",
                "count": analysis["error_patterns"]["Cost Center Not Group"],
                "action": "Run fix_cost_centers() to fix cost center group settings",
                "details": "Cost centers need to be configured as groups"
            })
        
        # Convert defaultdicts to regular dicts for JSON serialization
        analysis["error_patterns"] = dict(analysis["error_patterns"])
        analysis["error_types"] = dict(analysis["error_types"])
        analysis["supplier_issues"] = dict(analysis["supplier_issues"])
        analysis["transaction_types"] = dict(analysis["transaction_types"])
        
        return analysis
        
    except Exception as e:
        frappe.log_error(f"Error analyzing migration: {str(e)}", "Migration Analysis Error")
        return {"error": str(e)}

def categorize_error(error_msg):
    """Categorize an error message into a type"""
    error_lower = error_msg.lower()
    
    if "could not find" in error_lower or "not found" in error_lower:
        return "Missing Reference"
    elif "mandatory" in error_lower or "required" in error_lower:
        return "Validation Error"
    elif "duplicate" in error_lower:
        return "Duplicate Entry"
    elif "permission" in error_lower or "not allowed" in error_lower:
        return "Permission Error"
    elif "group" in error_lower:
        return "Configuration Error"
    elif "amount" in error_lower or "balance" in error_lower:
        return "Financial Error"
    elif "date" in error_lower or "time" in error_lower:
        return "Date/Time Error"
    else:
        return "Other Error"

@frappe.whitelist()
def get_unhandled_mutations(migration_id):
    """
    Get details about unhandled mutation types
    
    Args:
        migration_id: The E-Boekhouden migration ID
        
    Returns:
        Dict with unhandled mutation analysis
    """
    if not frappe.has_permission("E-Boekhouden Migration", "read"):
        frappe.throw(_("Insufficient permissions"))
    
    try:
        # Get migration stats from the document
        migration = frappe.get_doc("E-Boekhouden Migration", migration_id)
        
        # Parse the summary to find unhandled mutations
        summary = migration.import_summary or ""
        
        unhandled_info = {
            "total_unhandled": 0,
            "mutation_types": [],
            "recommendations": []
        }
        
        # Look for unhandled mutations in the summary
        if "unhandled_mutations" in summary:
            import re
            match = re.search(r'unhandled_mutations["\']?\s*:\s*(\d+)', summary)
            if match:
                unhandled_info["total_unhandled"] = int(match.group(1))
        
        # Check debug logs for unhandled mutation types
        debug_dir = frappe.get_site_path("private", "files", "eboekhouden_debug_logs")
        
        if os.path.exists(debug_dir):
            for filename in os.listdir(debug_dir):
                if migration_id in filename:
                    debug_file = os.path.join(debug_dir, filename)
                    with open(debug_file, 'r') as f:
                        content = f.read()
                    
                    # Look for unhandled mutation type messages
                    unhandled_types = set()
                    for line in content.split('\n'):
                        if "Unhandled mutation type" in line:
                            # Extract mutation type
                            match = re.search(r"Unhandled mutation type '([^']+)'", line)
                            if match:
                                unhandled_types.add(match.group(1))
                    
                    unhandled_info["mutation_types"] = list(unhandled_types)
        
        # Add recommendations
        if unhandled_info["total_unhandled"] > 0:
            unhandled_info["recommendations"].append({
                "issue": "Unhandled Mutation Types",
                "action": "These mutation types need handlers implemented in the migration code",
                "details": f"Types found: {', '.join(unhandled_info['mutation_types'])}"
            })
        
        return unhandled_info
        
    except Exception as e:
        return {"error": str(e)}

@frappe.whitelist() 
def create_error_summary_report(migration_id):
    """
    Create a comprehensive error summary report for a migration
    
    Args:
        migration_id: The E-Boekhouden migration ID
        
    Returns:
        Formatted report as HTML
    """
    if not frappe.has_permission("E-Boekhouden Migration", "read"):
        frappe.throw(_("Insufficient permissions"))
    
    try:
        # Get analysis
        analysis = analyze_migration_errors(migration_id)
        unhandled = get_unhandled_mutations(migration_id)
        
        # Create HTML report
        html = f"""
        <h2>E-Boekhouden Migration Error Analysis</h2>
        <p><strong>Migration ID:</strong> {migration_id}</p>
        
        <h3>Error Summary</h3>
        <table class="table table-bordered">
            <thead>
                <tr>
                    <th>Error Pattern</th>
                    <th>Count</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for pattern, count in sorted(analysis.get("error_patterns", {}).items(), key=lambda x: -x[1]):
            html += f"<tr><td>{pattern}</td><td>{count}</td></tr>"
        
        html += """
            </tbody>
        </table>
        
        <h3>Transaction Type Failures</h3>
        <table class="table table-bordered">
            <thead>
                <tr>
                    <th>Transaction Type</th>
                    <th>Failed Count</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for tx_type, count in analysis.get("transaction_types", {}).items():
            html += f"<tr><td>{tx_type}</td><td>{count}</td></tr>"
        
        html += """
            </tbody>
        </table>
        
        <h3>Recommendations</h3>
        <ul>
        """
        
        for rec in analysis.get("recommendations", []):
            html += f"""
            <li>
                <strong>{rec['issue']}</strong> ({rec.get('count', 'N/A')} occurrences)<br>
                Action: {rec['action']}<br>
                {rec.get('details', '')}
            </li>
            """
        
        if unhandled.get("total_unhandled", 0) > 0:
            html += f"""
            <li>
                <strong>Unhandled Mutations</strong> ({unhandled['total_unhandled']} mutations)<br>
                Types: {', '.join(unhandled.get('mutation_types', []))}
            </li>
            """
        
        html += """
        </ul>
        
        <h3>Sample Errors</h3>
        <pre>
        """
        
        for error in analysis.get("sample_errors", [])[:5]:
            html += f"{error}\n"
        
        html += "</pre>"
        
        return {"html": html}
        
    except Exception as e:
        return {"error": str(e)}