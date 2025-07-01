import frappe
from frappe import _
import json

@frappe.whitelist()
def analyze_skipped_mutations(migration_name=None):
    """Analyze why mutations are being skipped in the migration"""
    
    if not migration_name:
        # Get the latest migration
        migration_name = frappe.db.get_value(
            "E-Boekhouden Migration",
            {"migration_status": "Completed"},
            "name",
            order_by="creation desc"
        )
    
    if not migration_name:
        return {"error": "No completed migrations found"}
    
    # Initialize analysis
    analysis = {
        "migration_name": migration_name,
        "skip_reasons": {
            "no_invoice_number": 0,
            "already_imported": 0,
            "invoice_not_found": 0,
            "already_paid": 0,
            "zero_amount": 0,
            "duplicate_payment": 0,
            "other": 0
        },
        "by_mutation_type": {},
        "samples": {
            "no_invoice_number": [],
            "already_imported": [],
            "invoice_not_found": []
        }
    }
    
    # Get SOAP API settings
    from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    settings = frappe.get_single("E-Boekhouden Settings")
    
    try:
        api = EBoekhoudenSOAPAPI(settings)
        
        # Get all mutations
        highest_result = api.get_highest_mutation_number()
        if not highest_result["success"]:
            return {"error": "Failed to get mutations"}
        
        highest_mutation_nr = highest_result["highest_mutation_number"]
        
        # Process in batches
        batch_size = 500
        current_nr = 1
        
        while current_nr <= highest_mutation_nr:
            batch_end = min(current_nr + batch_size - 1, highest_mutation_nr)
            
            result = api.get_mutations(mutation_nr_from=current_nr, mutation_nr_to=batch_end)
            
            if result["success"]:
                for mut in result["mutations"]:
                    analyze_single_mutation(mut, analysis)
            
            current_nr = batch_end + 1
            
            # Limit analysis to first 2000 mutations for performance
            if current_nr > 2000:
                analysis["note"] = "Analysis limited to first 2000 mutations"
                break
    
    except Exception as e:
        analysis["error"] = str(e)
    
    return analysis

def analyze_single_mutation(mutation, analysis):
    """Analyze why a single mutation might be skipped"""
    
    soort = mutation.get("Soort", "Unknown")
    mutation_nr = mutation.get("MutatieNr")
    
    # Initialize type counter
    if soort not in analysis["by_mutation_type"]:
        analysis["by_mutation_type"][soort] = {
            "total": 0,
            "skip_reasons": {}
        }
    
    analysis["by_mutation_type"][soort]["total"] += 1
    
    # Check skip reasons based on mutation type
    if soort == "FactuurVerstuurd":
        # Sales invoice
        invoice_no = mutation.get("Factuurnummer")
        
        if not invoice_no:
            record_skip_reason(analysis, soort, "no_invoice_number", mutation)
        elif frappe.db.exists("Sales Invoice", {"eboekhouden_invoice_number": invoice_no}):
            record_skip_reason(analysis, soort, "already_imported", mutation)
            
    elif soort == "FactuurOntvangen":
        # Purchase invoice
        invoice_no = mutation.get("Factuurnummer")
        
        if not invoice_no:
            record_skip_reason(analysis, soort, "no_invoice_number", mutation)
        elif frappe.db.exists("Purchase Invoice", {"eboekhouden_invoice_number": invoice_no}):
            record_skip_reason(analysis, soort, "already_imported", mutation)
            
    elif soort == "FactuurbetalingOntvangen":
        # Customer payment
        invoice_no = mutation.get("Factuurnummer")
        
        if not invoice_no:
            record_skip_reason(analysis, soort, "no_invoice_number", mutation)
        else:
            # Check if payment exists
            if frappe.db.exists("Payment Entry", [
                ["reference_no", "=", mutation_nr],
                ["docstatus", "!=", 2]
            ]):
                record_skip_reason(analysis, soort, "already_imported", mutation)
            # Check if invoice exists
            elif not frappe.db.exists("Sales Invoice", {"eboekhouden_invoice_number": invoice_no}):
                record_skip_reason(analysis, soort, "invoice_not_found", mutation)
                
    elif soort == "FactuurbetalingVerstuurd":
        # Supplier payment
        invoice_no = mutation.get("Factuurnummer")
        
        if not invoice_no:
            record_skip_reason(analysis, soort, "no_invoice_number", mutation)
        else:
            # Check if payment exists
            if frappe.db.exists("Payment Entry", [
                ["reference_no", "=", mutation_nr],
                ["docstatus", "!=", 2]
            ]):
                record_skip_reason(analysis, soort, "already_imported", mutation)
            # Check if invoice exists
            elif not frappe.db.exists("Purchase Invoice", {"eboekhouden_invoice_number": invoice_no}):
                record_skip_reason(analysis, soort, "invoice_not_found", mutation)
                
    elif soort in ["GeldOntvangen", "GeldUitgegeven"]:
        # Bank transactions
        if frappe.db.exists("Journal Entry", {"eboekhouden_mutation_nr": mutation_nr}):
            record_skip_reason(analysis, soort, "already_imported", mutation)
        else:
            # Check if amount is zero
            total_amount = 0
            for regel in mutation.get("MutatieRegels", []):
                total_amount += float(regel.get("BedragInclBTW", 0))
            
            if total_amount == 0:
                record_skip_reason(analysis, soort, "zero_amount", mutation)
                
    elif soort == "Memoriaal":
        # Manual journal entries
        if frappe.db.exists("Journal Entry", {"eboekhouden_mutation_nr": mutation_nr}):
            record_skip_reason(analysis, soort, "already_imported", mutation)

def record_skip_reason(analysis, mutation_type, reason, mutation):
    """Record why a mutation was skipped"""
    
    # Overall counter
    analysis["skip_reasons"][reason] += 1
    
    # Per-type counter
    if reason not in analysis["by_mutation_type"][mutation_type]["skip_reasons"]:
        analysis["by_mutation_type"][mutation_type]["skip_reasons"][reason] = 0
    analysis["by_mutation_type"][mutation_type]["skip_reasons"][reason] += 1
    
    # Store samples (max 3 per reason)
    if reason in analysis["samples"] and len(analysis["samples"][reason]) < 3:
        analysis["samples"][reason].append({
            "mutation_nr": mutation.get("MutatieNr"),
            "type": mutation_type,
            "invoice_no": mutation.get("Factuurnummer"),
            "description": mutation.get("Omschrijving", "")[:50]
        })

@frappe.whitelist()
def get_migration_skip_summary():
    """Get a summary of skipped mutations from the latest migration"""
    
    analysis = analyze_skipped_mutations()
    
    if "error" in analysis:
        return analysis
    
    # Create summary
    summary = {
        "migration": analysis["migration_name"],
        "skip_reasons_summary": analysis["skip_reasons"],
        "type_breakdown": {}
    }
    
    # Summarize by type
    for mut_type, data in analysis["by_mutation_type"].items():
        summary["type_breakdown"][mut_type] = {
            "total": data["total"],
            "skipped": sum(data["skip_reasons"].values()),
            "main_reason": max(data["skip_reasons"].items(), key=lambda x: x[1])[0] if data["skip_reasons"] else "none"
        }
    
    return summary