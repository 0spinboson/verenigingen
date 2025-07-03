import frappe
from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
import json
from collections import defaultdict

@frappe.whitelist()
def analyze_entry_numbers():
    """Analyze what entryNumbers are and how they're used"""
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenAPI(settings)
    
    # Get a sample of mutations
    result = api.get_mutations({"limit": 1000})
    if not result["success"]:
        return {"error": "Failed to fetch mutations"}
    
    data = json.loads(result["data"])
    mutations = data.get("items", [])
    
    # Analyze entryNumbers
    with_entry = []
    without_entry = []
    entry_groups = defaultdict(list)
    
    for mut in mutations:
        entry_num = mut.get("entryNumber")
        if entry_num:
            with_entry.append(mut)
            entry_groups[entry_num].append(mut)
        else:
            without_entry.append(mut)
    
    # Analyze the groups
    group_analysis = []
    for entry_num, muts in list(entry_groups.items())[:5]:  # First 5 groups
        total_debit = 0
        total_credit = 0
        accounts = []
        
        for m in muts:
            amount = float(m.get("amount", 0))
            mut_type = m.get("type", 0)
            
            # Type 0 seems to be debit, others credit
            if mut_type == 0:
                total_debit += amount
            else:
                total_credit += amount
            
            accounts.append({
                "date": m.get("date"),
                "type": mut_type,
                "amount": amount,
                "ledgerId": m.get("ledgerId"),
                "description": m.get("description", ""),
                "invoiceNumber": m.get("invoiceNumber", "")
            })
        
        group_analysis.append({
            "entryNumber": entry_num,
            "mutation_count": len(muts),
            "total_debit": round(total_debit, 2),
            "total_credit": round(total_credit, 2),
            "balanced": abs(total_debit - total_credit) < 0.01,
            "accounts": accounts
        })
    
    # Sample mutations without entry numbers
    sample_without = []
    for mut in without_entry[:10]:
        sample_without.append({
            "id": mut.get("id"),
            "date": mut.get("date"),
            "type": mut.get("type"),
            "amount": mut.get("amount"),
            "ledgerId": mut.get("ledgerId"),
            "description": mut.get("description", ""),
            "invoiceNumber": mut.get("invoiceNumber", "")
        })
    
    return {
        "total_mutations": len(mutations),
        "with_entry_number": len(with_entry),
        "without_entry_number": len(without_entry),
        "unique_entry_numbers": len(entry_groups),
        "entry_groups_sample": group_analysis,
        "mutations_without_entry_sample": sample_without,
        "conclusion": "entryNumbers group related mutations into complete journal entries"
    }

if __name__ == "__main__":
    print(analyze_entry_numbers())