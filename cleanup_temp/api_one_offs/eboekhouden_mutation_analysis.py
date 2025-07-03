"""
Analyze E-Boekhouden mutations to understand the data structure
"""

import frappe
from frappe import _
import json

@frappe.whitelist()
def analyze_mutations():
    """
    Analyze mutations to understand why we have 3x more mutations than expected
    """
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        settings = frappe.get_single("E-Boekhouden Settings")
        if not settings.api_token:
            return {
                "success": False,
                "error": "E-Boekhouden API not configured"
            }
        
        api = EBoekhoudenAPI(settings)
        
        # Get a sample of mutations
        params = {
            "limit": 100,
            "offset": 0
        }
        
        result = api.get_mutations(params)
        if not result["success"]:
            return {
                "success": False,
                "error": "Could not fetch mutations"
            }
        
        data = json.loads(result["data"])
        mutations = data.get("items", [])
        
        # Analyze the mutations
        analysis = {
            "total_sample": len(mutations),
            "by_type": {},
            "by_entry_number": {},
            "zero_amount": 0,
            "has_invoice": 0,
            "unique_ledgers": set(),
            "sample_entries": []
        }
        
        for mut in mutations:
            # Count by type
            mut_type = mut.get("type", "unknown")
            analysis["by_type"][mut_type] = analysis["by_type"].get(mut_type, 0) + 1
            
            # Group by entry number to see how many mutations per entry
            entry_num = mut.get("entryNumber", "no_entry")
            if entry_num and entry_num != "no_entry":
                if entry_num not in analysis["by_entry_number"]:
                    analysis["by_entry_number"][entry_num] = []
                analysis["by_entry_number"][entry_num].append({
                    "type": mut_type,
                    "amount": mut.get("amount", 0),
                    "ledgerId": mut.get("ledgerId"),
                    "description": mut.get("description", ""),
                    "relationCode": mut.get("relationCode", ""),
                    "invoiceNumber": mut.get("invoiceNumber", ""),
                    "date": mut.get("date", "")
                })
            
            # Count zero amounts
            if float(mut.get("amount", 0)) == 0:
                analysis["zero_amount"] += 1
            
            # Count with invoices
            if mut.get("invoiceNumber"):
                analysis["has_invoice"] += 1
            
            # Track unique ledgers
            ledger_id = mut.get("ledgerId")
            if ledger_id:
                analysis["unique_ledgers"].add(ledger_id)
            
            # Keep first 5 as samples
            if len(analysis["sample_entries"]) < 5:
                analysis["sample_entries"].append(mut)
        
        # Calculate mutations per entry and check for conflicts
        mutations_per_entry = []
        conflicting_entries = []
        
        for entry_num, muts in analysis["by_entry_number"].items():
            mutations_per_entry.append(len(muts))
            
            # Check if this entry has multiple relation codes or dates
            relation_codes = set(m["relationCode"] for m in muts if m["relationCode"])
            dates = set(m["date"] for m in muts if m["date"])
            invoice_numbers = set(m["invoiceNumber"] for m in muts if m["invoiceNumber"])
            
            if len(relation_codes) > 1 or len(dates) > 1:
                conflicting_entries.append({
                    "entry_number": entry_num,
                    "mutation_count": len(muts),
                    "relation_codes": list(relation_codes),
                    "dates": list(dates),
                    "invoice_numbers": list(invoice_numbers)
                })
        
        avg_mutations_per_entry = sum(mutations_per_entry) / len(mutations_per_entry) if mutations_per_entry else 0
        
        # Convert sets to lists for JSON serialization
        analysis["unique_ledgers"] = len(analysis["unique_ledgers"])
        
        return {
            "success": True,
            "analysis": analysis,
            "summary": {
                "average_mutations_per_entry": round(avg_mutations_per_entry, 2),
                "entries_with_multiple_mutations": len([e for e in mutations_per_entry if e > 2]),
                "entry_number_groups": len(analysis["by_entry_number"]),
                "type_distribution": analysis["by_type"],
                "zero_amount_count": analysis["zero_amount"],
                "unique_ledger_count": analysis["unique_ledgers"],
                "conflicting_entries": len(conflicting_entries)
            },
            "conflicts": conflicting_entries[:5],  # Show first 5 conflicts
            "explanation": "E-Boekhouden stores individual debit/credit lines as separate mutations. A simple journal entry with 1 debit and 1 credit becomes 2 mutations. Complex entries with multiple lines create even more mutations."
        }
        
    except Exception as e:
        frappe.log_error(f"Mutation analysis error: {str(e)}", "E-Boekhouden")
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def get_mutation_entry_groups(limit=10):
    """
    Get examples of how mutations are grouped by entry number
    """
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        settings = frappe.get_single("E-Boekhouden Settings")
        api = EBoekhoudenAPI(settings)
        
        # Get mutations
        result = api.get_mutations({"limit": 500, "offset": 0})
        if not result["success"]:
            return {"success": False, "error": "Could not fetch mutations"}
        
        data = json.loads(result["data"])
        mutations = data.get("items", [])
        
        # Group by entry number
        entry_groups = {}
        for mut in mutations:
            entry_num = mut.get("entryNumber")
            if entry_num:
                if entry_num not in entry_groups:
                    entry_groups[entry_num] = []
                entry_groups[entry_num].append(mut)
        
        # Get examples
        examples = []
        for entry_num, muts in list(entry_groups.items())[:limit]:
            total_debit = sum(float(m.get("amount", 0)) for m in muts if m.get("type") == 0)
            total_credit = sum(float(m.get("amount", 0)) for m in muts if m.get("type") == 1)
            
            examples.append({
                "entry_number": entry_num,
                "mutation_count": len(muts),
                "total_debit": total_debit,
                "total_credit": total_credit,
                "balanced": abs(total_debit - total_credit) < 0.01,
                "mutations": muts
            })
        
        return {
            "success": True,
            "examples": examples,
            "total_entry_groups": len(entry_groups),
            "message": f"Found {len(entry_groups)} unique entry numbers from {len(mutations)} mutations"
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}