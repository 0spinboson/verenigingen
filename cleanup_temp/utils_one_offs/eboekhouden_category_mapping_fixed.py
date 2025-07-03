"""
Fixed E-Boekhouden category-based mapping
Addresses issues with category detection and account classification
"""

import frappe
import json
import re
from frappe import _
from collections import defaultdict


@frappe.whitelist()
def analyze_accounts_with_proper_categories():
    """
    Analyze accounts using actual E-Boekhouden data without assumptions
    """
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        api = EBoekhoudenAPI()
        result = api.get_chart_of_accounts()
        
        if not result["success"]:
            return {"success": False, "error": "Failed to get chart of accounts"}
        
        data = json.loads(result["data"])
        accounts = data.get("items", [])
        
        # First, let's see what categories actually exist
        actual_categories = set()
        category_accounts = defaultdict(list)
        
        for account in accounts:
            category = account.get("category")
            if category:
                actual_categories.add(category)
                category_accounts[category].append(account)
        
        # For accounts without categories, use smart detection based on patterns
        no_category_accounts = []
        for account in accounts:
            if not account.get("category"):
                no_category_accounts.append(account)
        
        # Group no-category accounts by detected type
        smart_groups = group_accounts_by_type(no_category_accounts)
        
        # Build proposals
        proposals = []
        
        # 1. Add proposals for actual categories
        for category in sorted(actual_categories):
            cat_accounts = category_accounts[category]
            
            # Determine type based on category
            if category == "DEB":
                suggested_type = "Receivable"
                reason = "Debiteuren (Debtors)"
            elif category == "CRED":
                suggested_type = "Payable"
                reason = "Crediteuren (Creditors)"
            elif category == "FIN":
                # Split FIN into subcategories
                fin_groups = split_financial_accounts(cat_accounts)
                for subtype, subaccounts in fin_groups.items():
                    if subaccounts:
                        proposals.append({
                            "type": "subcategory",
                            "identifier": f"FIN_{subtype}",
                            "name": get_fin_subtype_name(subtype),
                            "parent_category": "FIN",
                            "account_count": len(subaccounts),
                            "sample_accounts": subaccounts[:3],
                            "suggested_mapping": {
                                "type": "Cash" if subtype == "cash" else "Bank",
                                "reason": f"Financial accounts - {get_fin_subtype_name(subtype)}",
                                "confidence": "high"
                            }
                        })
                continue  # Skip adding FIN as a single category
            elif category == "BAL":
                # Split BAL into subcategories based on account type
                bal_groups = split_balance_accounts(cat_accounts)
                for subtype, subaccounts in bal_groups.items():
                    if subaccounts:
                        proposals.append({
                            "type": "balance_subtype",
                            "identifier": f"BAL_{subtype}",
                            "name": get_bal_subtype_name(subtype),
                            "parent_category": "BAL",
                            "account_count": len(subaccounts),
                            "sample_accounts": subaccounts[:3],
                            "suggested_mapping": {
                                "type": subtype,
                                "reason": f"Balance sheet accounts - {get_bal_subtype_name(subtype)}",
                                "confidence": "high"
                            }
                        })
                continue  # Skip adding BAL as a single category
            elif category == "VW":
                # Split VW into income and expense subcategories
                vw_groups = split_vw_accounts(cat_accounts)
                for subtype, subaccounts in vw_groups.items():
                    if subaccounts:
                        proposals.append({
                            "type": "vw_subtype",
                            "identifier": f"VW_{subtype}",
                            "name": f"{get_vw_subtype_name(subtype)} (VW)",
                            "parent_category": "VW",
                            "account_count": len(subaccounts),
                            "sample_accounts": subaccounts[:3],
                            "suggested_mapping": {
                                "type": subtype,
                                "reason": f"Profit & Loss accounts - {subtype}",
                                "confidence": "high"
                            }
                        })
                continue  # Skip adding VW as a single category
            else:
                # For other categories, analyze content
                suggested_type, reason = analyze_category_content(category, cat_accounts)
            
                proposals.append({
                    "type": "category",
                    "identifier": category,
                    "name": f"{category} - {reason}",
                    "account_count": len(cat_accounts),
                    "sample_accounts": cat_accounts[:3],
                    "suggested_mapping": {
                        "type": suggested_type,
                        "reason": reason,
                        "confidence": "medium" if suggested_type else "low"
                    }
                })
        
        # 2. Add proposals for smart-grouped accounts without categories
        for group_type, group_accounts in smart_groups.items():
            if group_accounts:
                proposals.append({
                    "type": "smart_group",
                    "identifier": f"SMART_{group_type}",
                    "name": get_smart_group_name(group_type),
                    "account_count": len(group_accounts),
                    "sample_accounts": group_accounts[:3],
                    "suggested_mapping": {
                        "type": group_type,
                        "reason": f"Accounts detected as {group_type}",
                        "confidence": "high"
                    }
                })
        
        return {
            "success": True,
            "mapping_proposals": proposals,
            "total_proposals": len(proposals),
            "actual_categories": list(actual_categories),
            "accounts_without_category": len(no_category_accounts),
            "explanatory_notes": [
                {
                    "title": "Category Analysis",
                    "items": [
                        f"Found {len(actual_categories)} actual E-Boekhouden categories",
                        f"{len(no_category_accounts)} accounts have no category",
                        "Smart grouping applied to uncategorized accounts",
                        "Financial accounts split into Cash, Bank, and PSPs"
                    ]
                }
            ]
        }
        
    except Exception as e:
        frappe.log_error(f"Error analyzing accounts: {str(e)}")
        return {"success": False, "error": str(e)}


def split_financial_accounts(accounts):
    """Split financial accounts into subcategories"""
    groups = {
        "cash": [],
        "bank": [],
        "psp": []
    }
    
    for account in accounts:
        desc_lower = account.get("description", "").lower()
        
        # Check for PSPs first (most specific)
        if any(psp in desc_lower for psp in ["paypal", "mollie", "stripe", "adyen", "pay.nl", "tikkie", "ideal", "zettle", "sumup", "square"]):
            groups["psp"].append(account)
        # Then cash
        elif any(cash in desc_lower for cash in ["kas", "kasgeld", "contant", "cash"]):
            groups["cash"].append(account)
        # Everything else is bank
        else:
            groups["bank"].append(account)
    
    return groups


def group_accounts_by_type(accounts):
    """Group accounts without categories by detected type"""
    groups = defaultdict(list)
    
    for account in accounts:
        desc_lower = account.get("description", "").lower()
        code = account.get("code", "")
        
        # Detect liability reserves first (employee-related reserves)
        if any(term in desc_lower for term in ["reservering vakantiegeld", "reservering sociale lasten"]):
            groups["Current Liability"].append(account)
        # Detect equity accounts (excluding employee reserves)
        elif any(term in desc_lower for term in ["eigen vermogen", "kapitaal", "bestemmingsreserve", "resultaat"]) or (
            "reserve" in desc_lower and not any(emp in desc_lower for emp in ["vakantiegeld", "sociale lasten"])
        ):
            groups["Equity"].append(account)
        # Income accounts
        elif any(term in desc_lower for term in ["omzet", "opbrengst", "inkomsten", "contributie", "donatie"]) or code.startswith("8"):
            groups["Income Account"].append(account)
        # Expense accounts  
        elif any(term in desc_lower for term in ["kosten", "uitgaven", "inkoop", "afschrijving"]) or code.startswith("4"):
            groups["Expense Account"].append(account)
        # Tax accounts
        elif "btw" in desc_lower:
            groups["Tax"].append(account)
        # Fixed assets
        elif any(term in desc_lower for term in ["vaste activa", "inventaris", "gebouw", "machine"]) or code.startswith("0"):
            groups["Fixed Asset"].append(account)
        # Current assets (but exclude "vooruitontvangen" which is a liability)
        elif ("vooruitontvangen" not in desc_lower and 
              (any(term in desc_lower for term in ["voorraad", "vorderingen", "te ontvangen"]) or code.startswith("1"))):
            groups["Current Asset"].append(account)
        # Liabilities (including prepaid amounts and employee reserves)
        elif any(term in desc_lower for term in ["schuld", "te betalen", "lening", "vooruitontvangen", "reservering"]) or code.startswith("2"):
            groups["Current Liability"].append(account)
        else:
            # Default based on account code
            if code:
                first_digit = code[0]
                if first_digit in ["0", "1"]:
                    groups["Current Asset"].append(account)
                elif first_digit == "2":
                    groups["Current Liability"].append(account)
                elif first_digit in ["4", "5", "6", "7"]:
                    groups["Expense Account"].append(account)
                elif first_digit == "8":
                    groups["Income Account"].append(account)
                else:
                    groups["Unknown"].append(account)
    
    return groups


def analyze_category_content(category, accounts):
    """Analyze accounts in a category to determine type"""
    # Look at account codes and descriptions
    codes = [acc.get("code", "") for acc in accounts]
    descriptions = [acc.get("description", "").lower() for acc in accounts]
    
    # Check if all accounts start with same digit
    if codes and all(c.startswith(codes[0][0]) for c in codes if c):
        first_digit = codes[0][0]
        if first_digit == "8":
            return "Income Account", "Revenue accounts"
        elif first_digit in ["4", "5", "6", "7"]:
            return "Expense Account", "Cost accounts"
    
    # Check descriptions for patterns
    desc_text = " ".join(descriptions)
    if "btw" in desc_text:
        return "Tax", "BTW accounts"
    elif any(term in desc_text for term in ["omzet", "opbrengst", "inkomsten"]):
        return "Income Account", "Revenue accounts"
    elif any(term in desc_text for term in ["kosten", "uitgaven"]):
        return "Expense Account", "Cost accounts"
    
    return None, f"Mixed accounts in category {category}"


def get_fin_subtype_name(subtype):
    """Get display name for financial subtype"""
    names = {
        "cash": "Kas (Cash)",
        "bank": "Bankrekeningen (Bank)",
        "psp": "Payment Service Providers"
    }
    return names.get(subtype, subtype)


def split_balance_accounts(accounts):
    """Split balance sheet (BAL) accounts into appropriate subtypes"""
    # Use the same logic as group_accounts_by_type but for BAL accounts
    groups = {
        "Current Asset": [],
        "Fixed Asset": [],
        "Current Liability": [],
        "Equity": [],
        "Income Account": [],
        "Expense Account": []
    }
    
    for account in accounts:
        desc_lower = account.get("description", "").lower()
        code = account.get("code", "")
        
        # Apply the same detection logic as in group_accounts_by_type
        # Detect liability reserves first (employee-related reserves)
        if any(term in desc_lower for term in ["reservering vakantiegeld", "reservering sociale lasten"]):
            groups["Current Liability"].append(account)
        # Detect equity accounts (excluding employee reserves)
        elif any(term in desc_lower for term in ["eigen vermogen", "kapitaal", "bestemmingsreserve", "resultaat"]) or (
            "reserve" in desc_lower and not any(emp in desc_lower for emp in ["vakantiegeld", "sociale lasten"])
        ):
            groups["Equity"].append(account)
        # Income accounts
        elif any(term in desc_lower for term in ["omzet", "opbrengst", "inkomsten", "rentebaten"]) or code.startswith("8") or code.startswith("9"):
            groups["Income Account"].append(account)
        # Expense accounts  
        elif any(term in desc_lower for term in ["kosten", "uitgaven", "afschrijving"]):
            groups["Expense Account"].append(account)
        # Fixed assets
        elif any(term in desc_lower for term in ["vaste activa", "inventaris", "gebouw", "machine", "apparatuur"]) or code.startswith("0"):
            groups["Fixed Asset"].append(account)
        # Current assets (but exclude "vooruitontvangen" which is a liability)
        elif ("vooruitontvangen" not in desc_lower and 
              (any(term in desc_lower for term in ["voorraad", "vorderingen", "te ontvangen"]) or code.startswith("1"))):
            groups["Current Asset"].append(account)
        # Liabilities (including prepaid amounts and employee reserves)
        elif any(term in desc_lower for term in ["schuld", "te betalen", "lening", "vooruitontvangen", "reservering"]) or code.startswith("2"):
            groups["Current Liability"].append(account)
        else:
            # Default based on account code
            if code:
                first_digit = code[0]
                if first_digit in ["0"]:
                    groups["Fixed Asset"].append(account)
                elif first_digit == "1":
                    groups["Current Asset"].append(account)
                elif first_digit == "2":
                    groups["Current Liability"].append(account)
                elif first_digit in ["8", "9"]:
                    groups["Income Account"].append(account)
    
    # Remove empty groups
    return {k: v for k, v in groups.items() if v}


def get_bal_subtype_name(subtype):
    """Get display name for balance sheet subtypes"""
    names = {
        "Current Asset": "Vlottende Activa",
        "Fixed Asset": "Vaste Activa", 
        "Current Liability": "Kortlopende Schulden",
        "Equity": "Eigen Vermogen",
        "Income Account": "Opbrengsten",
        "Expense Account": "Kosten"
    }
    return names.get(subtype, subtype)


def split_vw_accounts(accounts):
    """Split VW accounts into income and expense based on account code"""
    groups = {
        "Income Account": [],
        "Expense Account": []
    }
    
    for account in accounts:
        code = account.get("code", "")
        desc_lower = account.get("description", "").lower()
        
        # Use account code as primary indicator
        if code.startswith("8") or code.startswith("9"):
            groups["Income Account"].append(account)
        elif code.startswith(("4", "5", "6", "7")):
            groups["Expense Account"].append(account)
        else:
            # Fall back to description analysis
            if any(term in desc_lower for term in ["inkomsten", "opbrengst", "omzet", "subsidie", "bijdrage", "donatie"]):
                groups["Income Account"].append(account)
            else:
                # Default to expense for VW accounts
                groups["Expense Account"].append(account)
    
    # Remove empty groups
    return {k: v for k, v in groups.items() if v}


def get_vw_subtype_name(subtype):
    """Get display name for VW subtypes"""
    names = {
        "Income Account": "Inkomsten & Opbrengsten",
        "Expense Account": "Kosten & Uitgaven"
    }
    return names.get(subtype, subtype)


def get_smart_group_name(group_type):
    """Get display name for smart groups"""
    names = {
        "Equity": "Eigen Vermogen & Reserves",
        "Income Account": "Omzet & Opbrengsten",
        "Expense Account": "Kosten & Uitgaven",
        "Tax": "BTW Rekeningen",
        "Fixed Asset": "Vaste Activa",
        "Current Asset": "Vlottende Activa",
        "Current Liability": "Kortlopende Schulden",
        "Unknown": "Overige Rekeningen"
    }
    return names.get(group_type, group_type)