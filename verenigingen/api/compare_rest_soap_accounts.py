"""
Compare REST API vs SOAP API for Chart of Accounts data completeness
"""

import frappe
from frappe import _
import json

@frappe.whitelist()
def compare_rest_soap_accounts():
    """Compare what data REST vs SOAP API provides for Chart of Accounts"""
    try:
        # REST API data
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        rest_api = EBoekhoudenAPI()
        
        rest_result = rest_api.get_chart_of_accounts()
        if not rest_result["success"]:
            return {"success": False, "error": "Failed to get REST API data"}
        
        rest_data = json.loads(rest_result["data"])
        rest_accounts = rest_data.get("items", [])
        
        # SOAP API data
        from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
        soap_api = EBoekhoudenSOAPAPI()
        
        soap_result = soap_api.get_grootboekrekeningen()
        if not soap_result["success"]:
            return {"success": False, "error": "Failed to get SOAP API data"}
        
        soap_accounts = soap_result.get("accounts", [])
        
        # Compare data fields
        rest_sample = rest_accounts[0] if rest_accounts else {}
        soap_sample = soap_accounts[0] if soap_accounts else {}
        
        # Map accounts by code for detailed comparison
        rest_by_code = {str(acc.get('code')): acc for acc in rest_accounts}
        soap_by_code = {str(acc.get('Code')): acc for acc in soap_accounts}
        
        # Find a few accounts present in both for detailed comparison
        comparison_samples = []
        common_codes = set(rest_by_code.keys()) & set(soap_by_code.keys())
        
        for code in list(common_codes)[:5]:  # Compare first 5 common accounts
            rest_acc = rest_by_code[code]
            soap_acc = soap_by_code[code]
            
            comparison_samples.append({
                "code": code,
                "rest_data": rest_acc,
                "soap_data": soap_acc,
                "rest_fields": list(rest_acc.keys()),
                "soap_fields": list(soap_acc.keys()),
                "soap_only_fields": [f for f in soap_acc.keys() if f not in str(rest_acc)]
            })
        
        # Analyze account type information
        type_analysis = analyze_account_type_info(rest_accounts, soap_accounts)
        
        return {
            "success": True,
            "summary": {
                "rest_account_count": len(rest_accounts),
                "soap_account_count": len(soap_accounts),
                "rest_fields": list(rest_sample.keys()) if rest_sample else [],
                "soap_fields": list(soap_sample.keys()) if soap_sample else [],
                "common_accounts": len(common_codes)
            },
            "field_comparison": {
                "rest_sample": rest_sample,
                "soap_sample": soap_sample,
                "comparison_samples": comparison_samples
            },
            "type_analysis": type_analysis,
            "recommendation": determine_recommendation(rest_sample, soap_sample, type_analysis)
        }
        
    except Exception as e:
        frappe.log_error(f"Error comparing REST/SOAP accounts: {str(e)}")
        return {"success": False, "error": str(e)}

def analyze_account_type_info(rest_accounts, soap_accounts):
    """Analyze what account type information is available in each API"""
    analysis = {
        "rest": {
            "has_category": False,
            "has_group": False,
            "category_values": set(),
            "group_values": set()
        },
        "soap": {
            "has_categorie": False,
            "has_groep": False,
            "categorie_values": set(),
            "groep_values": set(),
            "additional_type_fields": []
        }
    }
    
    # Analyze REST accounts
    for acc in rest_accounts[:50]:  # Sample first 50
        if 'category' in acc and acc['category']:
            analysis['rest']['has_category'] = True
            analysis['rest']['category_values'].add(acc['category'])
        if 'group' in acc and acc['group']:
            analysis['rest']['has_group'] = True
            analysis['rest']['group_values'].add(acc['group'])
    
    # Analyze SOAP accounts
    for acc in soap_accounts[:50]:  # Sample first 50
        if 'Categorie' in acc and acc['Categorie']:
            analysis['soap']['has_categorie'] = True
            analysis['soap']['categorie_values'].add(acc['Categorie'])
        if 'Groep' in acc and acc['Groep']:
            analysis['soap']['has_groep'] = True
            analysis['soap']['groep_values'].add(acc['Groep'])
        
        # Check for additional type-related fields
        type_fields = ['Type', 'Soort', 'RekeningType', 'BalansOfVerliesWinst']
        for field in type_fields:
            if field in acc and acc[field]:
                analysis['soap']['additional_type_fields'].append(field)
    
    # Convert sets to lists for JSON serialization
    analysis['rest']['category_values'] = list(analysis['rest']['category_values'])
    analysis['rest']['group_values'] = list(analysis['rest']['group_values'])
    analysis['soap']['categorie_values'] = list(analysis['soap']['categorie_values'])
    analysis['soap']['groep_values'] = list(analysis['soap']['groep_values'])
    analysis['soap']['additional_type_fields'] = list(set(analysis['soap']['additional_type_fields']))
    
    return analysis

def determine_recommendation(rest_sample, soap_sample, type_analysis):
    """Determine which API is better for Chart of Accounts"""
    rest_score = 0
    soap_score = 0
    reasons = []
    
    # Check basic fields
    if 'code' in rest_sample or 'id' in rest_sample:
        rest_score += 1
    if 'Code' in soap_sample or 'ID' in soap_sample:
        soap_score += 1
    
    if 'description' in rest_sample:
        rest_score += 1
    if 'Omschrijving' in soap_sample:
        soap_score += 1
    
    # Check type information
    if type_analysis['rest']['has_category']:
        rest_score += 2
        reasons.append("REST has category field")
    if type_analysis['soap']['has_categorie']:
        soap_score += 2
        reasons.append("SOAP has Categorie field")
    
    if type_analysis['rest']['has_group']:
        rest_score += 1
        reasons.append("REST has group field")
    if type_analysis['soap']['has_groep']:
        soap_score += 1
        reasons.append("SOAP has Groep field")
    
    if type_analysis['soap']['additional_type_fields']:
        soap_score += 2
        reasons.append(f"SOAP has additional type fields: {', '.join(type_analysis['soap']['additional_type_fields'])}")
    
    # Check for unique SOAP fields that might be useful
    soap_unique_fields = set(soap_sample.keys()) - set(rest_sample.keys())
    if len(soap_unique_fields) > 3:
        soap_score += 1
        reasons.append(f"SOAP has {len(soap_unique_fields)} unique fields")
    
    recommendation = {
        "rest_score": rest_score,
        "soap_score": soap_score,
        "reasons": reasons,
        "verdict": "SOAP API" if soap_score > rest_score else "REST API" if rest_score > soap_score else "Both are equivalent"
    }
    
    # Additional context
    if not type_analysis['rest']['has_category'] and not type_analysis['soap']['has_categorie']:
        recommendation["note"] = "Neither API provides complete account type information. Manual mapping or smart detection will be needed."
    elif type_analysis['soap']['has_categorie'] and not type_analysis['rest']['has_category']:
        recommendation["note"] = "SOAP API provides better account categorization which is essential for proper ERPNext account type mapping."
    
    return recommendation

@frappe.whitelist()
def test_specific_account_comparison(account_code):
    """Compare a specific account between REST and SOAP"""
    try:
        # REST API
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        rest_api = EBoekhoudenAPI()
        
        rest_result = rest_api.get_chart_of_accounts()
        rest_account = None
        
        if rest_result["success"]:
            rest_data = json.loads(rest_result["data"])
            for acc in rest_data.get("items", []):
                if str(acc.get('code')) == str(account_code):
                    rest_account = acc
                    break
        
        # SOAP API
        from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
        soap_api = EBoekhoudenSOAPAPI()
        
        soap_result = soap_api.get_grootboekrekeningen()
        soap_account = None
        
        if soap_result["success"]:
            for acc in soap_result.get("accounts", []):
                if str(acc.get('Code')) == str(account_code):
                    soap_account = acc
                    break
        
        # Smart type detection
        from verenigingen.utils.eboekhouden_smart_account_typing import get_smart_account_type
        smart_type = None
        if rest_account:
            smart_type, smart_root = get_smart_account_type(rest_account)
        
        return {
            "success": True,
            "account_code": account_code,
            "rest_account": rest_account,
            "soap_account": soap_account,
            "smart_detection": {
                "type": smart_type,
                "root": smart_root
            } if smart_type else None,
            "comparison": {
                "rest_has_data": bool(rest_account),
                "soap_has_data": bool(soap_account),
                "unique_soap_fields": list(set(soap_account.keys()) - set(rest_account.keys())) if rest_account and soap_account else [],
                "unique_rest_fields": list(set(rest_account.keys()) - set(soap_account.keys())) if rest_account and soap_account else []
            }
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}