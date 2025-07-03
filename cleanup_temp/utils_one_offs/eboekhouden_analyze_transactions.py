"""
Analyze E-Boekhouden transactions to suggest account mappings
"""

import frappe
from frappe import _
from collections import defaultdict
import json

@frappe.whitelist()
def analyze_eboekhouden_transactions():
    """Analyze all transactions to suggest account type mappings"""
    
    from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenSOAPAPI(settings)
    
    # Get sample transactions for analysis
    result = api.get_mutations(
        date_from="2025-01-01",
        date_to="2025-06-30"
    )
    
    if not result["success"]:
        return {"error": result.get("error")}
    
    # Analyze account usage patterns
    account_analysis = defaultdict(lambda: {
        "count": 0,
        "descriptions": [],
        "relation_codes": set(),
        "amounts": [],
        "mutation_types": set(),
        "suggested_type": "purchase_invoice",
        "confidence": "low"
    })
    
    for mut in result.get("mutations", []):
        mutation_type = mut.get("Soort")
        description = mut.get("Omschrijving", "")
        relation_code = mut.get("RelatieCode")
        
        for regel in mut.get("MutatieRegels", []):
            account_code = regel.get("TegenrekeningCode")
            if not account_code:
                continue
                
            analysis = account_analysis[account_code]
            analysis["count"] += 1
            analysis["mutation_types"].add(mutation_type)
            
            # Keep sample descriptions (max 5)
            if len(analysis["descriptions"]) < 5 and description:
                analysis["descriptions"].append(description[:100])
            
            if relation_code:
                analysis["relation_codes"].add(relation_code)
                
            amount = float(regel.get("BedragInvoer", 0))
            analysis["amounts"].append(amount)
    
    # Apply heuristics to suggest document types
    suggestions = []
    
    for account_code, data in account_analysis.items():
        suggestion = {
            "account_code": account_code,
            "usage_count": data["count"],
            "sample_descriptions": data["descriptions"],
            "avg_amount": sum(data["amounts"]) / len(data["amounts"]) if data["amounts"] else 0,
            "unique_relations": len(data["relation_codes"]),
            "mutation_types": list(data["mutation_types"])
        }
        
        # Analyze patterns to suggest type
        desc_lower = " ".join(data["descriptions"]).lower()
        
        # High confidence patterns
        if any(keyword in desc_lower for keyword in ["loonheffing", "belastingdienst", "tax", "btw"]):
            suggestion["suggested_type"] = "journal_entry"
            suggestion["category"] = "tax_payment"
            suggestion["confidence"] = "high"
            suggestion["reason"] = "Tax-related keywords found"
            
        elif any(keyword in desc_lower for keyword in ["salaris", "loon", "wage", "salary"]):
            suggestion["suggested_type"] = "journal_entry"
            suggestion["category"] = "wages"
            suggestion["confidence"] = "high"
            suggestion["reason"] = "Wage-related keywords found"
            
        elif any(keyword in desc_lower for keyword in ["pensioen", "pension", "verzekering", "insurance"]):
            suggestion["suggested_type"] = "journal_entry"
            suggestion["category"] = "benefits"
            suggestion["confidence"] = "medium"
            suggestion["reason"] = "Benefits/insurance keywords found"
            
        # Medium confidence - based on account patterns
        elif account_code.startswith("4") and len(account_code) >= 4:
            # Likely expense account
            if data["unique_relations"] <= 2:
                suggestion["suggested_type"] = "journal_entry"
                suggestion["category"] = "recurring_expense"
                suggestion["confidence"] = "medium"
                suggestion["reason"] = "Expense account with few relations"
            else:
                suggestion["suggested_type"] = "purchase_invoice"
                suggestion["category"] = "supplier_expense"
                suggestion["confidence"] = "medium"
                suggestion["reason"] = "Expense account with multiple suppliers"
        
        else:
            # Default
            suggestion["suggested_type"] = "purchase_invoice"
            suggestion["category"] = "general"
            suggestion["confidence"] = "low"
            suggestion["reason"] = "Default classification"
        
        # Get account name if available
        account_name = frappe.db.get_value("Account", 
            {"account_number": account_code, "company": settings.default_company}, 
            "account_name")
        
        if account_name:
            suggestion["account_name"] = account_name
        
        suggestions.append(suggestion)
    
    # Sort by usage count
    suggestions.sort(key=lambda x: x["usage_count"], reverse=True)
    
    # Create analysis report
    report = {
        "analysis_date": frappe.utils.now(),
        "total_mutations_analyzed": len(result.get("mutations", [])),
        "unique_accounts": len(suggestions),
        "suggestions": suggestions,
        "summary": {
            "high_confidence": len([s for s in suggestions if s.get("confidence") == "high"]),
            "medium_confidence": len([s for s in suggestions if s.get("confidence") == "medium"]),
            "low_confidence": len([s for s in suggestions if s.get("confidence") == "low"])
        }
    }
    
    # Save to file for review
    file_name = f"eboekhouden_analysis_{frappe.utils.now().replace(' ', '_').replace(':', '')}.json"
    file_path = frappe.get_site_path("private", "files", file_name)
    
    with open(file_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    # Create mappings that can be reviewed
    create_suggested_mappings(suggestions)
    
    return {
        "success": True,
        "analysis_file": file_name,
        "summary": report["summary"],
        "message": f"Analysis complete. Found {len(suggestions)} unique accounts. Review suggested mappings in E-Boekhouden Account Mapping."
    }

def create_suggested_mappings(suggestions):
    """Create account mapping records for review"""
    
    for suggestion in suggestions[:50]:  # Create top 50 for review
        # Check if mapping already exists
        existing = frappe.db.exists("E-Boekhouden Account Mapping", {
            "account_code": suggestion["account_code"]
        })
        
        if not existing:
            try:
                mapping = frappe.new_doc("E-Boekhouden Account Mapping")
                mapping.account_code = suggestion["account_code"]
                mapping.account_name = suggestion.get("account_name", "")
                mapping.document_type = suggestion["suggested_type"]
                mapping.category = suggestion.get("category", "general")
                mapping.confidence = suggestion.get("confidence", "low")
                mapping.reason = suggestion.get("reason", "")
                mapping.usage_count = suggestion.get("usage_count", 0)
                mapping.sample_description = "\n".join(suggestion.get("sample_descriptions", []))[:500]
                mapping.is_active = 1 if suggestion.get("confidence") == "high" else 0
                mapping.insert(ignore_permissions=True)
            except Exception as e:
                frappe.log_error(f"Failed to create mapping for {suggestion['account_code']}: {str(e)}")

if __name__ == "__main__":
    print(analyze_eboekhouden_transactions())