import frappe
from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
import json
from collections import defaultdict

@frappe.whitelist()
def analyze_mutation_fields():
    """Analyze actual mutation fields to find transaction types and descriptions"""
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenAPI(settings)
    
    # Get a sample of mutations
    result = api.get_mutations({"limit": 100})
    if not result["success"]:
        return {"error": "Failed to fetch mutations"}
    
    data = json.loads(result["data"])
    mutations = data.get("items", [])
    
    # Check what fields are actually present
    all_fields = set()
    for mut in mutations:
        all_fields.update(mut.keys())
    
    # Look for the transaction type field and description field
    type_distribution = defaultdict(int)
    sample_mutations = []
    
    for i, mut in enumerate(mutations[:20]):  # First 20 mutations
        # Check various possible field names for transaction type
        transaction_type = (
            mut.get("transactionType") or 
            mut.get("transaction_type") or
            mut.get("mutationType") or 
            mut.get("mutation_type") or
            mut.get("soort") or
            mut.get("mutatiesoort") or
            "NOT FOUND"
        )
        
        # Check for description fields
        description = (
            mut.get("omschrijving") or
            mut.get("description") or
            mut.get("beschrijving") or
            mut.get("memo") or
            ""
        )
        
        type_distribution[transaction_type] += 1
        
        sample_mutations.append({
            "index": i,
            "date": mut.get("date"),
            "amount": mut.get("amount"),
            "type_field": mut.get("type"),
            "transaction_type": transaction_type,
            "description": description,
            "invoiceNumber": mut.get("invoiceNumber", ""),
            "all_fields": list(mut.keys())
        })
    
    # Try to find mutations with specific patterns
    payment_sent = []
    payment_received = []
    money_received = []
    money_spent = []
    
    for mut in mutations:
        desc = str(mut.get("description", "") or mut.get("omschrijving", "") or "").lower()
        
        if "factuurbetaling verstuurd" in desc:
            payment_sent.append(mut)
        elif "factuurbetaling ontvangen" in desc:
            payment_received.append(mut)
        elif "geld ontvangen" in desc:
            money_received.append(mut)
        elif "geld uitgegeven" in desc:
            money_spent.append(mut)
    
    return {
        "total_mutations": len(mutations),
        "available_fields": sorted(list(all_fields)),
        "type_distribution": dict(type_distribution),
        "sample_mutations": sample_mutations[:10],
        "categorized_mutations": {
            "factuurbetaling_verstuurd": len(payment_sent),
            "factuurbetaling_ontvangen": len(payment_received),
            "geld_ontvangen": len(money_received),
            "geld_uitgegeven": len(money_spent),
            "samples": {
                "payment_sent": payment_sent[:2],
                "payment_received": payment_received[:2],
                "money_received": money_received[:2],
                "money_spent": money_spent[:2]
            }
        },
        "note": "Looking for transaction type and description fields"
    }

if __name__ == "__main__":
    print(analyze_mutation_fields())