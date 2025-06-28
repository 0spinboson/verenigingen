import frappe
from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
import json
from collections import defaultdict

@frappe.whitelist()
def analyze_mutation_types():
    """Analyze mutation types and their characteristics"""
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenAPI(settings)
    
    # Get mutations
    result = api.get_mutations({"limit": 2000})
    if not result["success"]:
        return {"error": "Failed to fetch mutations"}
    
    data = json.loads(result["data"])
    mutations = data.get("items", [])
    
    # Analyze by type
    type_analysis = defaultdict(lambda: {
        "count": 0,
        "with_invoice": 0,
        "with_relation": 0,
        "sample_accounts": set(),
        "sample_mutations": []
    })
    
    # Also check for patterns in descriptions
    payment_keywords = ["betaling", "payment", "ontvangen", "received", "bank"]
    invoice_keywords = ["factuur", "invoice", "rekening", "bill"]
    
    for mut in mutations:
        mut_type = mut.get("type", "unknown")
        analysis = type_analysis[mut_type]
        
        analysis["count"] += 1
        
        if mut.get("invoiceNumber"):
            analysis["with_invoice"] += 1
        
        if mut.get("relationCode"):
            analysis["with_relation"] += 1
        
        # Track which ledger accounts are used
        if mut.get("ledgerId"):
            analysis["sample_accounts"].add(mut.get("ledgerId"))
        
        # Keep sample mutations
        if len(analysis["sample_mutations"]) < 5:
            analysis["sample_mutations"].append({
                "date": mut.get("date"),
                "amount": mut.get("amount"),
                "ledgerId": mut.get("ledgerId"),
                "invoiceNumber": mut.get("invoiceNumber", ""),
                "relationCode": mut.get("relationCode", ""),
                "description": mut.get("description", "")[:50]  # First 50 chars
            })
    
    # Convert sets to counts for JSON
    for type_key in type_analysis:
        type_analysis[type_key]["unique_accounts"] = len(type_analysis[type_key]["sample_accounts"])
        del type_analysis[type_key]["sample_accounts"]
    
    # Check if we can get ledger account info to understand what types mean
    ledger_info = {}
    ledger_result = api.get_chart_of_accounts()
    if ledger_result["success"]:
        ledger_data = json.loads(ledger_result["data"])
        for account in ledger_data.get("items", []):
            ledger_info[account.get("id")] = {
                "code": account.get("code"),
                "name": account.get("name"),
                "type": account.get("type", "")
            }
    
    # Try to understand what each mutation type represents
    type_meanings = {}
    for mut_type, analysis in type_analysis.items():
        # Look at the accounts used by this type
        sample_account_ids = []
        for mut in analysis["sample_mutations"]:
            if mut["ledgerId"] and mut["ledgerId"] not in sample_account_ids:
                sample_account_ids.append(mut["ledgerId"])
        
        sample_accounts = []
        for acc_id in sample_account_ids[:3]:  # First 3 accounts
            if acc_id in ledger_info:
                info = ledger_info[acc_id]
                sample_accounts.append(f"{info['code']} - {info['name']}")
        
        type_meanings[mut_type] = {
            "count": analysis["count"],
            "has_invoices": f"{analysis['with_invoice']}/{analysis['count']} ({analysis['with_invoice']/analysis['count']*100:.1f}%)",
            "has_relations": f"{analysis['with_relation']}/{analysis['count']} ({analysis['with_relation']/analysis['count']*100:.1f}%)",
            "sample_accounts": sample_accounts,
            "sample_mutations": analysis["sample_mutations"][:2]  # First 2 samples
        }
    
    return {
        "total_mutations": len(mutations),
        "mutation_types": dict(type_meanings),
        "explanation": "Mutation 'type' field doesn't clearly distinguish invoices from payments",
        "key_finding": "Need to use ledger accounts and other fields to identify transaction types"
    }

if __name__ == "__main__":
    print(analyze_mutation_types())