"""
E-Boekhouden Mapping Analyzer
Analyzes mutations to suggest account mappings for two-stage import
"""

import frappe
from frappe.utils import today, add_months
from collections import defaultdict
import re


@frappe.whitelist()
def analyze_mutations_for_mapping(date_from=None, date_to=None, limit=1000):
    """
    Analyze E-Boekhouden mutations to suggest account mappings
    
    Args:
        date_from: Start date for analysis (defaults to 3 months ago)
        date_to: End date for analysis (defaults to today)
        limit: Maximum number of mutations to analyze
    
    Returns:
        Dictionary with analysis results and mapping suggestions
    """
    from .eboekhouden_soap_api import EBoekhoudenSOAPAPI
    
    # Get settings
    settings = frappe.get_single("E-Boekhouden Settings")
    if not settings:
        frappe.throw("E-Boekhouden Settings not configured")
    
    # Set default dates
    if not date_to:
        date_to = today()
    if not date_from:
        date_from = add_months(date_to, -3)
    
    # Initialize API
    api = EBoekhoudenSOAPAPI(settings)
    
    # Get mutations
    result = api.get_mutations(date_from=date_from, date_to=date_to)
    
    if not result["success"]:
        frappe.throw(f"Failed to fetch mutations: {result.get('error', 'Unknown error')}")
    
    mutations = result["mutations"][:limit]  # Limit for performance
    
    # Analyze mutations
    analysis = analyze_mutation_patterns(mutations)
    
    # Generate suggestions
    suggestions = generate_mapping_suggestions(analysis)
    
    # Check existing mappings
    existing_mappings = get_existing_mappings()
    
    return {
        "analysis": analysis,
        "suggestions": suggestions,
        "existing_mappings": existing_mappings,
        "mutations_analyzed": len(mutations),
        "date_range": {
            "from": date_from,
            "to": date_to
        }
    }


def analyze_mutation_patterns(mutations):
    """Analyze patterns in mutations to understand account usage"""
    account_analysis = defaultdict(lambda: {
        "count": 0,
        "mutation_types": defaultdict(int),
        "descriptions": [],
        "amounts": [],
        "counterparty_accounts": defaultdict(int),
        "typical_use": None,
        "suggested_doc_type": "Purchase Invoice"
    })
    
    # Common patterns for classification
    wage_patterns = re.compile(r"loon|salaris|wage|salary", re.IGNORECASE)
    tax_patterns = re.compile(r"belasting|tax|btw|vat|loonheffing", re.IGNORECASE)
    pension_patterns = re.compile(r"pensioen|pension|oudedagsvoorziening", re.IGNORECASE)
    social_patterns = re.compile(r"sociale|social|verzekering|insurance", re.IGNORECASE)
    bank_patterns = re.compile(r"bank|kosten|fee|charge|rente|interest", re.IGNORECASE)
    
    for mut in mutations:
        mutation_type = mut.get("Soort", "")
        description = mut.get("Omschrijving", "")
        
        # Skip sales-related mutations for this analysis
        if mutation_type in ["FactuurVerstuurd", "FactuurbetalingOntvangen"]:
            continue
        
        # Process purchase-related mutations
        if mutation_type == "FactuurOntvangen":
            for regel in mut.get("MutatieRegels", []):
                account_code = regel.get("TegenrekeningCode")
                if account_code:
                    analysis = account_analysis[account_code]
                    analysis["count"] += 1
                    analysis["mutation_types"][mutation_type] += 1
                    analysis["descriptions"].append(description[:100])
                    analysis["amounts"].append(float(regel.get("BedragExclBTW", 0)))
                    
                    # Analyze description for classification
                    if wage_patterns.search(description):
                        analysis["typical_use"] = "Wages and Salaries"
                        analysis["suggested_doc_type"] = "Journal Entry"
                    elif tax_patterns.search(description):
                        analysis["typical_use"] = "Tax Payments"
                        analysis["suggested_doc_type"] = "Journal Entry"
                    elif pension_patterns.search(description):
                        analysis["typical_use"] = "Pension Contributions"
                        analysis["suggested_doc_type"] = "Journal Entry"
                    elif social_patterns.search(description):
                        analysis["typical_use"] = "Social Charges"
                        analysis["suggested_doc_type"] = "Journal Entry"
                    elif bank_patterns.search(description):
                        analysis["typical_use"] = "Bank Charges"
                        analysis["suggested_doc_type"] = "Journal Entry"
    
    # Convert to regular dict for JSON serialization
    return dict(account_analysis)


def generate_mapping_suggestions(analysis):
    """Generate mapping suggestions based on analysis"""
    suggestions = []
    
    for account_code, data in analysis.items():
        if data["count"] < 2:  # Skip rarely used accounts
            continue
        
        # Create suggestion
        suggestion = {
            "account_code": account_code,
            "usage_count": data["count"],
            "suggested_type": data["suggested_doc_type"],
            "category": data["typical_use"] or "General Expenses",
            "confidence": "high" if data["count"] > 10 else "medium" if data["count"] > 5 else "low",
            "sample_descriptions": list(set(data["descriptions"]))[:5],  # Unique samples
            "average_amount": sum(data["amounts"]) / len(data["amounts"]) if data["amounts"] else 0,
            "reasons": []
        }
        
        # Add reasoning
        if data["typical_use"]:
            suggestion["reasons"].append(f"Descriptions match {data['typical_use']} patterns")
        
        if data["suggested_doc_type"] == "Journal Entry":
            suggestion["reasons"].append("Complex accounting entry requiring journal voucher")
        
        # Account code patterns (adjusted for custom numbering)
        if account_code.startswith("4"):
            if account_code.startswith("40"):
                suggestion["reasons"].append("Account code suggests expense category")
                if not data["typical_use"]:
                    suggestion["category"] = "Wages and Salaries"
                    suggestion["suggested_type"] = "Journal Entry"
            elif account_code.startswith("41"):
                suggestion["reasons"].append("Account code suggests social charges")
                if not data["typical_use"]:
                    suggestion["category"] = "Social Charges"
                    suggestion["suggested_type"] = "Journal Entry"
        
        suggestions.append(suggestion)
    
    # Sort by usage count
    suggestions.sort(key=lambda x: x["usage_count"], reverse=True)
    
    return suggestions


def get_existing_mappings():
    """Get summary of existing mappings"""
    mappings = frappe.get_all("E-Boekhouden Account Mapping",
        filters={"is_active": 1},
        fields=["name", "account_code", "account_name", "document_type", "transaction_category",
                "account_range_start", "account_range_end", "description_patterns"]
    )
    
    summary = {
        "total": len(mappings),
        "by_type": defaultdict(int),
        "by_category": defaultdict(int),
        "mappings": mappings
    }
    
    for m in mappings:
        summary["by_type"][m["document_type"]] += 1
        if m["transaction_category"]:
            summary["by_category"][m["transaction_category"]] += 1
    
    return dict(summary)


@frappe.whitelist()
def create_suggested_mappings(suggestions):
    """Create mappings from suggestions"""
    if isinstance(suggestions, str):
        import json
        suggestions = json.loads(suggestions)
    
    created = 0
    errors = []
    
    for suggestion in suggestions:
        try:
            # Check if mapping already exists
            existing = frappe.db.exists("E-Boekhouden Account Mapping", {
                "account_code": suggestion["account_code"]
            })
            
            if existing:
                continue
            
            # Create new mapping
            mapping = frappe.new_doc("E-Boekhouden Account Mapping")
            mapping.account_code = suggestion["account_code"]
            mapping.account_name = f"{suggestion['category']} - {suggestion['account_code']}"
            mapping.document_type = suggestion["suggested_type"]
            mapping.transaction_category = suggestion["category"]
            mapping.priority = 50  # Medium priority for auto-generated
            
            # Add sample descriptions as comment
            if suggestion.get("sample_descriptions"):
                mapping.sample_descriptions = "\n".join(suggestion["sample_descriptions"][:3])
            
            mapping.insert(ignore_permissions=True)
            created += 1
            
        except Exception as e:
            errors.append(f"Account {suggestion['account_code']}: {str(e)}")
    
    return {
        "created": created,
        "errors": errors,
        "message": f"Created {created} mappings"
    }


@frappe.whitelist()
def test_mapping_on_recent_data(limit=50):
    """Test current mappings on recent mutation data"""
    from .eboekhouden_soap_api import EBoekhoudenSOAPAPI
    from verenigingen.verenigingen.doctype.e_boekhouden_account_mapping.e_boekhouden_account_mapping import get_mapping_for_mutation
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenSOAPAPI(settings)
    
    # Get recent mutations
    date_to = today()
    date_from = add_months(date_to, -1)
    
    result = api.get_mutations(date_from=date_from, date_to=date_to)
    
    if not result["success"]:
        frappe.throw(f"Failed to fetch mutations: {result.get('error', 'Unknown error')}")
    
    mutations = result["mutations"][:limit]
    
    # Test mappings
    test_results = []
    
    for mut in mutations:
        if mut.get("Soort") == "FactuurOntvangen":
            for regel in mut.get("MutatieRegels", []):
                account_code = regel.get("TegenrekeningCode")
                if account_code:
                    mapping = get_mapping_for_mutation(account_code, mut.get("Omschrijving", ""))
                    
                    test_results.append({
                        "mutation_nr": mut.get("MutatieNr"),
                        "account_code": account_code,
                        "description": mut.get("Omschrijving", "")[:100],
                        "amount": float(regel.get("BedragExclBTW", 0)),
                        "mapped_to": mapping["document_type"],
                        "category": mapping["transaction_category"],
                        "mapping_used": mapping["name"]
                    })
    
    # Summarize results
    summary = {
        "total_tested": len(test_results),
        "by_document_type": defaultdict(int),
        "by_category": defaultdict(int),
        "unmapped": 0
    }
    
    for result in test_results:
        summary["by_document_type"][result["mapped_to"]] += 1
        summary["by_category"][result["category"]] += 1
        if not result["mapping_used"]:
            summary["unmapped"] += 1
    
    return {
        "summary": dict(summary),
        "details": test_results
    }