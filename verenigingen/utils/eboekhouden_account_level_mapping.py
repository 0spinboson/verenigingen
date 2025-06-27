"""
Account-level mapping for E-Boekhouden
Allows mapping individual accounts instead of just groups
"""

import frappe
import json
import re
from frappe import _


@frappe.whitelist()
def analyze_liquid_assets_detailed():
    """
    Analyze liquid assets group and suggest individual account mappings
    """
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        api = EBoekhoudenAPI()
        result = api.get_chart_of_accounts()
        
        if not result["success"]:
            return {"success": False, "error": "Failed to get chart of accounts"}
        
        data = json.loads(result["data"])
        accounts = data.get("items", [])
        
        # Find liquid asset accounts (typically group 002 or accounts starting with 10)
        liquid_accounts = []
        for account in accounts:
            # Check if it's a liquid asset by group or account number pattern
            is_liquid = (
                account.get("group") == "002" or 
                account.get("code", "").startswith("10") or
                "liquide" in account.get("description", "").lower() or
                "kas" in account.get("description", "").lower() or
                "bank" in account.get("description", "").lower()
            )
            
            if is_liquid:
                # Determine suggested type based on account name
                suggested_type = suggest_liquid_asset_type(
                    account.get("code", ""),
                    account.get("description", "")
                )
                
                liquid_accounts.append({
                    "code": account.get("code"),
                    "description": account.get("description"),
                    "group": account.get("group"),
                    "suggested_type": suggested_type["type"],
                    "suggestion_reason": suggested_type["reason"],
                    "confidence": suggested_type["confidence"]
                })
        
        # Group by suggested type for summary
        type_summary = {}
        for acc in liquid_accounts:
            typ = acc["suggested_type"]
            if typ not in type_summary:
                type_summary[typ] = []
            type_summary[typ].append(acc)
        
        return {
            "success": True,
            "liquid_accounts": liquid_accounts,
            "total_accounts": len(liquid_accounts),
            "type_summary": type_summary,
            "recommendations": [
                "Cash: Physical cash accounts (kas, kasgeld)",
                "Bank: Traditional bank accounts (bank, rekening-courant)",
                "Bank: Payment service providers (PayPal, Mollie, Stripe)",
                "Current Asset: Other liquid assets that don't fit above"
            ]
        }
        
    except Exception as e:
        frappe.log_error(f"Error analyzing liquid assets: {str(e)}")
        return {"success": False, "error": str(e)}


def suggest_liquid_asset_type(code, description):
    """
    Suggest account type for a liquid asset based on code and description
    
    Returns dict with type, reason, and confidence
    """
    desc_lower = description.lower()
    
    # Cash patterns
    cash_patterns = [
        r'\bkas\b',           # kas
        r'kasgeld',           # cash money
        r'cash',              # English cash
        r'kleine kas',        # petty cash
        r'contant'            # cash/immediate
    ]
    
    # Bank patterns
    bank_patterns = [
        r'bank',              # bank
        r'rekening-courant',  # current account
        r'rc\b',              # r/c abbreviation
        r'spaar',             # savings
        r'deposito'           # deposit
    ]
    
    # Payment Service Provider patterns
    psp_patterns = [
        r'paypal',
        r'mollie',
        r'stripe',
        r'adyen',
        r'pay\.nl',
        r'buckaroo',
        r'multisafepay',
        r'ideal',             # Though iDEAL might be a receivable
        r'tikkie',
        r'payment service',
        r'psp\b',
        r'payment provider'
    ]
    
    # Check for PSP first (most specific)
    for pattern in psp_patterns:
        if re.search(pattern, desc_lower, re.IGNORECASE):
            return {
                "type": "Bank",  # PSPs are typically treated as Bank in ERPNext
                "reason": f"Payment service provider (matched '{pattern}')",
                "confidence": "high",
                "note": "Consider creating a separate PSP account group under Bank accounts"
            }
    
    # Check for cash
    for pattern in cash_patterns:
        if re.search(pattern, desc_lower, re.IGNORECASE):
            return {
                "type": "Cash",
                "reason": f"Physical cash account (matched '{pattern}')",
                "confidence": "high"
            }
    
    # Check for bank
    for pattern in bank_patterns:
        if re.search(pattern, desc_lower, re.IGNORECASE):
            return {
                "type": "Bank",
                "reason": f"Bank account (matched '{pattern}')",
                "confidence": "high"
            }
    
    # Default for liquid assets
    return {
        "type": "Bank",  # Default to Bank for unmatched liquid assets
        "reason": "Liquid asset without specific pattern - defaulting to Bank",
        "confidence": "low"
    }


@frappe.whitelist()
def create_account_level_mapping_dialog():
    """
    Create a more detailed mapping dialog that allows account-level mapping
    """
    try:
        detailed_analysis = analyze_liquid_assets_detailed()
        
        if not detailed_analysis["success"]:
            return detailed_analysis
        
        # Create proposals for individual accounts or sub-groups
        proposals = []
        
        # Group similar accounts
        account_groups = {}
        for acc in detailed_analysis["liquid_accounts"]:
            key = f"{acc['suggested_type']}_{acc['suggestion_reason']}"
            if key not in account_groups:
                account_groups[key] = {
                    "type": acc["suggested_type"],
                    "reason": acc["suggestion_reason"],
                    "accounts": []
                }
            account_groups[key]["accounts"].append(acc)
        
        # Create proposals from groups
        for group_key, group_data in account_groups.items():
            # If only one account, make individual proposal
            if len(group_data["accounts"]) == 1:
                acc = group_data["accounts"][0]
                proposals.append({
                    "type": "account",
                    "identifier": acc["code"],
                    "name": acc["description"],
                    "account_count": 1,
                    "suggested_mapping": {
                        "type": acc["suggested_type"],
                        "reason": acc["suggestion_reason"],
                        "confidence": acc["confidence"]
                    },
                    "sample_accounts": [acc]
                })
            else:
                # Make group proposal
                sample_desc = " / ".join([a["description"] for a in group_data["accounts"][:3]])
                if len(group_data["accounts"]) > 3:
                    sample_desc += f" (and {len(group_data['accounts']) - 3} more)"
                
                proposals.append({
                    "type": "account_group",
                    "identifier": f"group_{group_data['type']}",
                    "name": sample_desc,
                    "account_count": len(group_data["accounts"]),
                    "suggested_mapping": {
                        "type": group_data["type"],
                        "reason": group_data["reason"],
                        "confidence": "high"
                    },
                    "sample_accounts": group_data["accounts"][:3]
                })
        
        return {
            "success": True,
            "mapping_proposals": proposals,
            "total_proposals": len(proposals),
            "liquid_asset_analysis": detailed_analysis
        }
        
    except Exception as e:
        frappe.log_error(f"Error creating account-level mapping: {str(e)}")
        return {"success": False, "error": str(e)}