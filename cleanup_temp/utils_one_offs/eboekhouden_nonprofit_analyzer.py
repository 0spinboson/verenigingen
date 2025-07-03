"""
E-Boekhouden account analyzer for nonprofit organizations
Provides better categorization and document type suggestions
"""

import frappe
from frappe import _
import re

def analyze_nonprofit_accounts(accounts):
    """Analyze accounts with nonprofit-specific patterns"""
    
    categorized_accounts = {
        "income": {
            "membership": [],
            "donations": [],
            "events": [],
            "other": []
        },
        "expenses": {
            "office": [],
            "program": [],
            "volunteer": [],
            "marketing": [],
            "professional": [],
            "bank": [],
            "tax": [],
            "other": []
        }
    }
    
    # Income patterns
    income_patterns = {
        "membership": [
            r"contributie|contribution|membership|lidmaatschap",
            r"member\s+fee|leden\s+bijdrage"
        ],
        "donations": [
            r"donatie|donation|gift|schenking|bijdrage",
            r"sponsor|subsidie|grant"
        ],
        "events": [
            r"evenement|event|congres|conference",
            r"workshop|cursus|training|seminar",
            r"ticket|deelname|participation"
        ]
    }
    
    # Expense patterns
    expense_patterns = {
        "office": [
            r"huur|rent|kantoor|office",
            r"telefoon|phone|internet|communicatie",
            r"verzekering|insurance|energie|utilities",
            r"schoonmaak|cleaning|onderhoud|maintenance"
        ],
        "program": [
            r"project|programma|activiteit|activity",
            r"materiaal|material|voorraad|supplies",
            r"uitvoering|implementation|execution"
        ],
        "volunteer": [
            r"vrijwilliger|volunteer|reiskosten|travel",
            r"vergoeding|reimbursement|onkosten|expenses",
            r"training\s+vrijwilliger|volunteer\s+training"
        ],
        "marketing": [
            r"marketing|reclame|advertising|promotie",
            r"website|social\s+media|communicatie",
            r"drukwerk|printing|publicatie|publication"
        ],
        "professional": [
            r"accountant|boekhouder|accounting",
            r"juridisch|legal|advocaat|lawyer",
            r"consultant|advies|advisory|consultancy"
        ],
        "bank": [
            r"bankkosten|bank\s+charges|bank\s+fee",
            r"betalingsverkeer|payment\s+processing",
            r"mollie|paypal|stripe|payment\s+provider"
        ],
        "tax": [
            r"belasting|tax|btw|vat",
            r"aangifte|declaration|fiscaal|fiscal"
        ]
    }
    
    # Compile patterns
    compiled_income_patterns = {}
    for category, patterns in income_patterns.items():
        compiled_income_patterns[category] = re.compile("|".join(patterns), re.IGNORECASE)
    
    compiled_expense_patterns = {}
    for category, patterns in expense_patterns.items():
        compiled_expense_patterns[category] = re.compile("|".join(patterns), re.IGNORECASE)
    
    # Analyze each account
    for account in accounts:
        code = account.get("Code", "")
        name = account.get("Omschrijving", "")
        account_type = account.get("Soort", "")
        
        # Skip balance sheet accounts
        if account_type in ["Balans", "Balance"]:
            continue
        
        account_info = {
            "code": code,
            "name": name,
            "type": account_type,
            "suggested_doc_type": None,
            "category": None,
            "confidence": "low"
        }
        
        # Check if it's income or expense based on code
        is_income = False
        if code.startswith("8") or "opbrengst" in name.lower() or "omzet" in name.lower():
            is_income = True
            account_info["suggested_doc_type"] = "Sales Invoice"
        else:
            # Default to Purchase Invoice for expenses
            account_info["suggested_doc_type"] = "Purchase Invoice"
        
        # Try to categorize
        matched = False
        
        if is_income:
            for category, pattern in compiled_income_patterns.items():
                if pattern.search(name):
                    categorized_accounts["income"][category].append(account_info)
                    account_info["category"] = category
                    account_info["confidence"] = "high"
                    matched = True
                    break
            
            if not matched:
                categorized_accounts["income"]["other"].append(account_info)
                account_info["category"] = "other_income"
                account_info["confidence"] = "medium"
        else:
            # Check for special cases first
            if "mollie" in name.lower() or "paypal" in name.lower():
                # Payment processor fees should be Journal Entry
                account_info["suggested_doc_type"] = "Journal Entry"
                categorized_accounts["expenses"]["bank"].append(account_info)
                account_info["category"] = "bank"
                account_info["confidence"] = "high"
                matched = True
            elif "vrijwilliger" in name.lower() and ("vergoeding" in name.lower() or "onkosten" in name.lower()):
                # Volunteer reimbursements should be Expense Claim
                account_info["suggested_doc_type"] = "Expense Claim"
                categorized_accounts["expenses"]["volunteer"].append(account_info)
                account_info["category"] = "volunteer"
                account_info["confidence"] = "high"
                matched = True
            else:
                # Check patterns
                for category, pattern in compiled_expense_patterns.items():
                    if pattern.search(name):
                        categorized_accounts["expenses"][category].append(account_info)
                        account_info["category"] = category
                        account_info["confidence"] = "high"
                        matched = True
                        break
            
            if not matched:
                categorized_accounts["expenses"]["other"].append(account_info)
                account_info["category"] = "other_expenses"
                account_info["confidence"] = "low"
    
    return categorized_accounts

def generate_nonprofit_suggestions(analysis):
    """Generate mapping suggestions for nonprofit organizations"""
    suggestions = []
    
    # Process income accounts
    for category, accounts in analysis["income"].items():
        for account in accounts:
            suggestion = {
                "account_code": account["code"],
                "account_name": account["name"],
                "suggested_type": account["suggested_doc_type"],
                "category": get_category_label("income", category),
                "confidence": account["confidence"],
                "reasons": []
            }
            
            if category == "membership":
                suggestion["reasons"].append("Account name suggests membership income")
            elif category == "donations":
                suggestion["reasons"].append("Account name suggests donations or grants")
            elif category == "events":
                suggestion["reasons"].append("Account name suggests event-related income")
            
            suggestions.append(suggestion)
    
    # Process expense accounts
    for category, accounts in analysis["expenses"].items():
        for account in accounts:
            suggestion = {
                "account_code": account["code"],
                "account_name": account["name"],
                "suggested_type": account["suggested_doc_type"],
                "category": get_category_label("expenses", category),
                "confidence": account["confidence"],
                "reasons": []
            }
            
            if account["suggested_doc_type"] == "Expense Claim":
                suggestion["reasons"].append("Likely volunteer/employee reimbursement")
            elif account["suggested_doc_type"] == "Journal Entry":
                suggestion["reasons"].append("Bank/payment processor transaction")
            elif category == "professional":
                suggestion["reasons"].append("Professional services typically require invoice")
            
            suggestions.append(suggestion)
    
    # Sort by confidence and code
    suggestions.sort(key=lambda x: (x["confidence"], x["account_code"]), reverse=True)
    
    return suggestions

def get_category_label(main_type, category):
    """Get user-friendly category label"""
    labels = {
        "income": {
            "membership": "Membership Income",
            "donations": "Donations",
            "events": "Event Income",
            "other": "Other Income"
        },
        "expenses": {
            "office": "Office Expenses",
            "program": "Program Expenses",
            "volunteer": "Volunteer Expenses",
            "marketing": "Marketing & Communications",
            "professional": "Professional Services",
            "bank": "Bank Charges",
            "tax": "Tax Payments",
            "other": "General Expenses"
        }
    }
    
    return labels.get(main_type, {}).get(category, "Other")

@frappe.whitelist()
def analyze_accounts_nonprofit():
    """Main function for nonprofit account analysis"""
    from .eboekhouden_soap_api import EBoekhoudenSOAPAPI
    
    # Get settings
    settings = frappe.get_single("E-Boekhouden Settings")
    if not settings:
        frappe.throw("E-Boekhouden Settings not configured")
    
    # Initialize API
    api = EBoekhoudenSOAPAPI(settings)
    
    # Get chart of accounts
    result = api.get_grootboekrekeningen()
    
    if not result["success"]:
        frappe.throw(f"Failed to fetch accounts: {result.get('error', 'Unknown error')}")
    
    accounts = result["accounts"]
    
    # Analyze accounts
    analysis = analyze_nonprofit_accounts(accounts)
    
    # Generate suggestions
    suggestions = generate_nonprofit_suggestions(analysis)
    
    # Get existing mappings
    existing_mappings = frappe.get_all("E-Boekhouden Account Mapping",
        filters={"is_active": 1},
        fields=["account_code", "document_type", "transaction_category"]
    )
    
    existing_codes = [m["account_code"] for m in existing_mappings]
    
    # Filter out already mapped accounts
    new_suggestions = [s for s in suggestions if s["account_code"] not in existing_codes]
    
    return {
        "analysis": analysis,
        "suggestions": new_suggestions,
        "existing_mappings": {
            "total": len(existing_mappings),
            "by_type": get_mapping_summary(existing_mappings)
        },
        "accounts_analyzed": len(accounts)
    }

def get_mapping_summary(mappings):
    """Summarize existing mappings by type"""
    summary = {}
    for mapping in mappings:
        doc_type = mapping.get("document_type", "Unknown")
        summary[doc_type] = summary.get(doc_type, 0) + 1
    return summary