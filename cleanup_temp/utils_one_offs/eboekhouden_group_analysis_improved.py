"""
Improved E-Boekhouden Group Analysis
Fixes issues with group name parsing for multi-word names and short words
"""

import frappe
import json
from collections import Counter
import re


def find_common_phrases(descriptions, min_occurrences=None):
    """
    Find common phrases (multi-word sequences) in descriptions
    """
    if not descriptions:
        return []
    
    if min_occurrences is None:
        min_occurrences = max(2, len(descriptions) // 2)
    
    # Store all phrases (1-4 word sequences)
    phrases = []
    
    for desc in descriptions:
        # Clean and normalize the description
        desc_clean = re.sub(r'[^\w\s-]', '', desc.lower())
        words = desc_clean.split()
        
        # Extract phrases of different lengths
        for phrase_len in range(1, min(5, len(words) + 1)):  # 1-4 word phrases
            for i in range(len(words) - phrase_len + 1):
                phrase = ' '.join(words[i:i + phrase_len])
                # Skip very short single words, but keep multi-word phrases
                if phrase_len == 1 and len(phrase) < 3:
                    continue
                # Skip numeric-only phrases unless they're group codes
                if phrase.isdigit() and len(phrase) < 3:
                    continue
                phrases.append(phrase)
    
    # Count phrase occurrences
    phrase_counts = Counter(phrases)
    
    # Filter by minimum occurrences
    common_phrases = [(phrase, count) for phrase, count in phrase_counts.items() 
                      if count >= min_occurrences]
    
    # Sort by length (prefer longer phrases) and then by frequency
    common_phrases.sort(key=lambda x: (len(x[0].split()), x[1]), reverse=True)
    
    # Remove subphrases if a longer phrase contains them
    filtered_phrases = []
    for phrase, count in common_phrases:
        # Check if this phrase is a substring of any already selected phrase
        is_substring = False
        for selected, _ in filtered_phrases:
            if phrase in selected and phrase != selected:
                is_substring = True
                break
        if not is_substring:
            filtered_phrases.append((phrase, count))
    
    return filtered_phrases


@frappe.whitelist()
def get_group_mapping_improved():
    """
    Get improved group mapping with better name inference
    """
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        # Get the E-Boekhouden settings
        settings = frappe.get_single("E-Boekhouden Settings")
        api = EBoekhoudenAPI(settings)
        
        # Get chart of accounts
        result = api.get_chart_of_accounts()
        if not result["success"]:
            return {"success": False, "error": "Failed to get chart of accounts"}
        
        data = json.loads(result["data"])
        accounts = data.get("items", [])
        
        # Group accounts by group code
        groups = {}
        for account in accounts:
            group_code = account.get("group", "")
            if not group_code:
                continue
                
            if group_code not in groups:
                groups[group_code] = {
                    "code": group_code,
                    "accounts": [],
                    "inferred_name": "",
                    "categories": set(),
                    "account_range": {"min": "9999", "max": "0000"}
                }
            
            groups[group_code]["accounts"].append({
                "code": account.get("code", ""),
                "description": account.get("description", ""),
                "category": account.get("category", "")
            })
            
            # Track categories
            if account.get("category"):
                groups[group_code]["categories"].add(account.get("category"))
            
            # Track account number range
            acc_code = account.get("code", "")
            if acc_code < groups[group_code]["account_range"]["min"]:
                groups[group_code]["account_range"]["min"] = acc_code
            if acc_code > groups[group_code]["account_range"]["max"]:
                groups[group_code]["account_range"]["max"] = acc_code
        
        # Infer group names with improved logic
        for group_code, group_data in groups.items():
            accounts_in_group = group_data["accounts"]
            
            # Special handling for specific groups based on known patterns
            if group_code == "002":
                # For liquid assets, check if we can be more specific
                descriptions = [acc["description"] for acc in accounts_in_group]
                has_kas = any("kas" in d.lower() for d in descriptions)
                has_bank = any("bank" in d.lower() for d in descriptions)
                has_psp = any(any(psp in d.lower() for psp in ["paypal", "mollie", "stripe"]) for d in descriptions)
                
                if has_kas and not has_bank and not has_psp:
                    groups[group_code]["inferred_name"] = "Kas (Cash)"
                elif has_bank and not has_kas and not has_psp:
                    groups[group_code]["inferred_name"] = "Bankrekeningen"
                elif has_psp:
                    groups[group_code]["inferred_name"] = "Liquide middelen (incl. PSPs)"
                else:
                    groups[group_code]["inferred_name"] = "Liquide middelen (gemengd)"
                    groups[group_code]["mixed_types"] = True
            elif group_code == "005":
                groups[group_code]["inferred_name"] = "Eigen vermogen"
            elif group_code == "022":
                # Look for common pattern in descriptions
                descriptions = [acc["description"] for acc in accounts_in_group]
                if any("btw" in desc.lower() for desc in descriptions):
                    groups[group_code]["inferred_name"] = "BTW rekeningen"
                else:
                    # Use improved phrase detection
                    common_phrases = find_common_phrases(descriptions)
                    if common_phrases:
                        groups[group_code]["inferred_name"] = common_phrases[0][0].title()
                    else:
                        groups[group_code]["inferred_name"] = f"Groep {group_code}"
            elif group_data["categories"] == {"DEB"}:
                groups[group_code]["inferred_name"] = "Debiteuren"
            elif group_data["categories"] == {"CRED"}:
                groups[group_code]["inferred_name"] = "Crediteuren"
            elif group_data["categories"] == {"FIN"}:
                groups[group_code]["inferred_name"] = "Financiële rekeningen"
            else:
                # Use improved phrase detection for other groups
                descriptions = [acc["description"] for acc in accounts_in_group]
                common_phrases = find_common_phrases(descriptions)
                
                if common_phrases:
                    # Use the most common phrase
                    best_phrase = common_phrases[0][0]
                    # Capitalize appropriately
                    groups[group_code]["inferred_name"] = ' '.join(
                        word.capitalize() for word in best_phrase.split()
                    )
                else:
                    groups[group_code]["inferred_name"] = f"Groep {group_code}"
        
        # Convert to list for display
        group_list = []
        for group_code, group_data in sorted(groups.items()):
            group_list.append({
                "group_code": group_code,
                "inferred_name": group_data["inferred_name"],
                "account_count": len(group_data["accounts"]),
                "categories": list(group_data["categories"]),
                "account_range": f"{group_data['account_range']['min']} - {group_data['account_range']['max']}",
                "sample_accounts": group_data["accounts"][:3]
            })
        
        return {
            "success": True,
            "groups": group_list,
            "total_groups": len(groups),
            "group_details": groups
        }
        
    except Exception as e:
        import traceback
        frappe.log_error(traceback.format_exc(), "E-Boekhouden Group Analysis Improved")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def analyze_account_categories_improved(use_groups=True):
    """
    Improved version that uses better group name detection
    """
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        api = EBoekhoudenAPI()
        
        # Get improved group analysis
        if use_groups:
            group_result = get_group_mapping_improved()
            if not group_result["success"]:
                return group_result
            
            # Build proposals from groups
            proposals = []
            for group in group_result["groups"]:
                # Determine suggested account type using Dutch patterns
                from verenigingen.utils.dutch_account_patterns import suggest_account_type_from_dutch
                
                suggested_type, confidence, reason = suggest_account_type_from_dutch(
                    group["inferred_name"], 
                    group["group_code"]
                )
                
                # Override with category-based suggestions if no pattern match
                if not suggested_type and "DEB" in group["categories"]:
                    suggested_type = "Receivable"
                    reason = "Category DEB (Debtors)"
                    confidence = "high"
                elif not suggested_type and "CRED" in group["categories"]:
                    suggested_type = "Payable"
                    reason = "Category CRED (Creditors)"
                    confidence = "high"
                elif not suggested_type and "FIN" in group["categories"]:
                    suggested_type = "Bank"
                    reason = "Category FIN (Financial)"
                    confidence = "medium"
                
                proposal = {
                    "type": "group",
                    "identifier": group["group_code"],
                    "name": group["inferred_name"],
                    "account_count": group["account_count"],
                    "sample_accounts": group["sample_accounts"],
                    "categories": group["categories"],
                    "suggested_mapping": {
                        "type": suggested_type,
                        "reason": reason,
                        "confidence": confidence if suggested_type else "low"
                    },
                    "current_erpnext_types": []  # Would need to look these up
                }
                
                proposals.append(proposal)
            
            return {
                "success": True,
                "mapping_proposals": proposals,
                "total_proposals": len(proposals),
                "group_analysis": group_result["group_details"]
            }
        
        # Fall back to category-based analysis if groups not used
        from verenigingen.utils.eboekhouden_account_type_mapping import analyze_account_categories
        return analyze_account_categories(use_groups=False)
        
    except Exception as e:
        import traceback
        frappe.log_error(traceback.format_exc(), "Account Category Analysis Improved")
        return {"success": False, "error": str(e)}