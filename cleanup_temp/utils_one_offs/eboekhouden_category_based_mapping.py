"""
E-Boekhouden category-based mapping
Uses E-Boekhouden's own categorization system for intelligent mapping
"""

import frappe
import json
import re
from frappe import _


# E-Boekhouden category to ERPNext type mapping
CATEGORY_MAPPING = {
    "DEB": "Receivable",      # Debiteuren
    "CRED": "Payable",        # Crediteuren  
    "FIN": None,              # Financial - needs sub-categorization
    "KAS": "Cash",            # Cash accounts
    "BAL": None,              # Balance sheet - needs analysis
    "VW": "Expense",          # Verbruiksrekeningen (expenses)
    "BEDRKST": "Expense",     # Bedrijfskosten (business costs)
    "RESULT": "Income",       # Result accounts (income/revenue)
    "BTW": "Tax",             # BTW accounts
    "EIG": "Equity",          # Eigen vermogen
}

# Special handling for FIN category based on account details
FIN_SUBCATEGORY_PATTERNS = {
    "cash": {
        "patterns": [r"\bkas\b", r"kasgeld", r"contant", r"cash"],
        "type": "Cash",
        "priority": 1
    },
    "bank": {
        "patterns": [r"bank", r"rekening", r"\brc\b", r"spaar"],
        "type": "Bank", 
        "priority": 2
    },
    "psp": {
        "patterns": [r"paypal", r"mollie", r"stripe", r"adyen", r"pay\.nl", r"tikkie"],
        "type": "Bank",  # PSPs are treated as Bank in ERPNext
        "priority": 0,   # Highest priority - most specific
        "note": "Payment Service Provider"
    }
}


@frappe.whitelist()
def analyze_accounts_by_category():
    """
    Analyze accounts using E-Boekhouden's category system
    """
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        api = EBoekhoudenAPI()
        result = api.get_chart_of_accounts()
        
        if not result["success"]:
            return {"success": False, "error": "Failed to get chart of accounts"}
        
        data = json.loads(result["data"])
        accounts = data.get("items", [])
        
        # Group by category
        category_groups = {}
        for account in accounts:
            category = account.get("category", "UNKNOWN")
            if category not in category_groups:
                category_groups[category] = []
            category_groups[category].append(account)
        
        # Analyze each category
        analysis = {}
        for category, cat_accounts in category_groups.items():
            analysis[category] = analyze_category_accounts(category, cat_accounts)
        
        return {
            "success": True,
            "category_analysis": analysis,
            "total_categories": len(category_groups),
            "account_count": len(accounts)
        }
        
    except Exception as e:
        frappe.log_error(f"Error analyzing by category: {str(e)}")
        return {"success": False, "error": str(e)}


def analyze_category_accounts(category, accounts):
    """
    Analyze accounts within a category
    """
    base_type = CATEGORY_MAPPING.get(category)
    
    # If category has a direct mapping, use it
    if base_type:
        return {
            "suggested_type": base_type,
            "is_uniform": True,
            "account_count": len(accounts),
            "sample_accounts": accounts[:3]
        }
    
    # Special handling for categories that need sub-categorization
    if category == "FIN":
        # Analyze financial accounts
        subcategories = {}
        for account in accounts:
            subcat = determine_fin_subcategory(account)
            if subcat not in subcategories:
                subcategories[subcat] = []
            subcategories[subcat].append(account)
        
        return {
            "suggested_type": "Mixed",
            "is_uniform": False,
            "subcategories": {
                subcat: {
                    "type": FIN_SUBCATEGORY_PATTERNS.get(subcat, {}).get("type", "Bank"),
                    "accounts": accs,
                    "count": len(accs)
                }
                for subcat, accs in subcategories.items()
            },
            "account_count": len(accounts)
        }
    
    elif category == "BAL":
        # Balance sheet accounts need individual analysis
        type_distribution = {}
        for account in accounts:
            acc_type = determine_balance_account_type(account)
            if acc_type not in type_distribution:
                type_distribution[acc_type] = []
            type_distribution[acc_type].append(account)
        
        return {
            "suggested_type": "Mixed",
            "is_uniform": False,
            "type_distribution": {
                acc_type: {
                    "accounts": accs,
                    "count": len(accs)
                }
                for acc_type, accs in type_distribution.items()
            },
            "account_count": len(accounts)
        }
    
    # Unknown category
    return {
        "suggested_type": "Unknown",
        "is_uniform": False,
        "account_count": len(accounts),
        "sample_accounts": accounts[:3]
    }


def determine_fin_subcategory(account):
    """
    Determine subcategory for FIN (Financial) accounts
    """
    desc_lower = account.get("description", "").lower()
    code = account.get("code", "")
    
    # Check patterns in priority order
    matches = []
    for subcat, config in FIN_SUBCATEGORY_PATTERNS.items():
        for pattern in config["patterns"]:
            if re.search(pattern, desc_lower, re.IGNORECASE):
                matches.append((subcat, config.get("priority", 99)))
                break
    
    if matches:
        # Return the match with highest priority (lowest number)
        matches.sort(key=lambda x: x[1])
        return matches[0][0]
    
    # Default for FIN accounts
    return "bank"


def determine_balance_account_type(account):
    """
    Determine type for BAL (Balance) accounts
    """
    desc_lower = account.get("description", "").lower()
    code = account.get("code", "")
    
    # Common balance sheet patterns
    if "eigen vermogen" in desc_lower or "kapitaal" in desc_lower:
        return "Equity"
    elif "voorraad" in desc_lower or "inventaris" in desc_lower:
        return "Stock"
    elif "vaste activa" in desc_lower:
        return "Fixed Asset"
    elif "vorderingen" in desc_lower or "te ontvangen" in desc_lower:
        return "Receivable"
    elif "schulden" in desc_lower or "te betalen" in desc_lower:
        return "Payable"
    elif "btw" in desc_lower:
        return "Tax"
    else:
        # Default based on account code ranges
        if code.startswith("0"):
            return "Fixed Asset"
        elif code.startswith("1"):
            return "Current Asset"
        elif code.startswith("2"):
            return "Current Liability"
        else:
            return "Current Asset"


@frappe.whitelist()
def get_category_based_mapping_proposals():
    """
    Get mapping proposals based on E-Boekhouden categories
    """
    try:
        analysis = analyze_accounts_by_category()
        if not analysis["success"]:
            return analysis
        
        proposals = []
        
        for category, cat_data in analysis["category_analysis"].items():
            if cat_data["is_uniform"]:
                # Single proposal for uniform categories
                proposals.append({
                    "type": "category",
                    "identifier": category,
                    "name": f"{category} - {get_category_name(category)}",
                    "account_count": cat_data["account_count"],
                    "sample_accounts": cat_data.get("sample_accounts", []),
                    "suggested_mapping": {
                        "type": cat_data["suggested_type"],
                        "reason": f"E-Boekhouden category {category}",
                        "confidence": "high"
                    }
                })
            else:
                # Multiple proposals for mixed categories
                if category == "FIN" and "subcategories" in cat_data:
                    for subcat, subcat_data in cat_data["subcategories"].items():
                        subcat_name = {
                            "cash": "Kas (Cash)",
                            "bank": "Bankrekeningen",
                            "psp": "Payment Service Providers"
                        }.get(subcat, subcat)
                        
                        proposals.append({
                            "type": "subcategory",
                            "identifier": f"{category}_{subcat}",
                            "name": f"{subcat_name}",
                            "parent_category": category,
                            "account_count": subcat_data["count"],
                            "sample_accounts": subcat_data["accounts"][:3],
                            "suggested_mapping": {
                                "type": subcat_data["type"],
                                "reason": f"Financial accounts - {subcat_name}",
                                "confidence": "high"
                            }
                        })
                elif category == "BAL" and "type_distribution" in cat_data:
                    for acc_type, type_data in cat_data["type_distribution"].items():
                        proposals.append({
                            "type": "balance_type",
                            "identifier": f"{category}_{acc_type}",
                            "name": f"Balance accounts - {acc_type}",
                            "parent_category": category,
                            "account_count": type_data["count"],
                            "sample_accounts": type_data["accounts"][:3],
                            "suggested_mapping": {
                                "type": acc_type,
                                "reason": f"Balance sheet accounts of type {acc_type}",
                                "confidence": "medium"
                            }
                        })
        
        # Add explanatory notes
        notes = [
            {
                "title": "E-Boekhouden Category System",
                "items": [
                    "DEB: Debiteuren (Receivables)",
                    "CRED: Crediteuren (Payables)",
                    "FIN: Financial accounts (split into Cash, Bank, PSPs)",
                    "KAS: Cash accounts",
                    "VW: Expenses",
                    "BTW: Tax accounts",
                    "EIG: Equity accounts"
                ]
            }
        ]
        
        if any(p["identifier"].startswith("FIN_") for p in proposals):
            notes.append({
                "title": "Financial Account Handling",
                "items": [
                    "FIN category is automatically split based on account names",
                    "Payment providers (PayPal, Mollie) are mapped as Bank accounts",
                    "Consider creating a PSP sub-group in your Chart of Accounts"
                ]
            })
        
        return {
            "success": True,
            "mapping_proposals": proposals,
            "total_proposals": len(proposals),
            "explanatory_notes": notes
        }
        
    except Exception as e:
        frappe.log_error(f"Error getting category proposals: {str(e)}")
        return {"success": False, "error": str(e)}


def get_category_name(category):
    """Get descriptive name for category code"""
    names = {
        "DEB": "Debiteuren",
        "CRED": "Crediteuren",
        "FIN": "Financiële rekeningen",
        "KAS": "Kas",
        "BAL": "Balansrekeningen",
        "VW": "Verbruiksrekeningen",
        "BEDRKST": "Bedrijfskosten",
        "RESULT": "Resultaatrekeningen",
        "BTW": "BTW rekeningen",
        "EIG": "Eigen vermogen"
    }
    return names.get(category, category)