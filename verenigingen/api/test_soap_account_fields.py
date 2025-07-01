"""
Test SOAP API GetGrootboekrekeningen to discover available account fields
Specifically looking for account type information like 'Soort'
"""

import frappe
from frappe import _
from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
import json

@frappe.whitelist()
def test_soap_account_fields():
    """
    Test function to call SOAP API's GetGrootboekrekeningen method
    and examine what fields are returned for accounts
    """
    try:
        # Initialize SOAP API client
        api = EBoekhoudenSOAPAPI()
        
        # Open session
        session_result = api.open_session()
        if not session_result["success"]:
            return {
                "success": False,
                "error": f"Failed to open session: {session_result.get('error', 'Unknown error')}"
            }
        
        # Get all accounts from SOAP API
        accounts_result = api.get_grootboekrekeningen()
        
        if not accounts_result["success"]:
            return {
                "success": False,
                "error": f"Failed to get accounts: {accounts_result.get('error', 'Unknown error')}"
            }
        
        accounts = accounts_result.get("accounts", [])
        
        if not accounts:
            return {
                "success": False,
                "error": "No accounts returned from SOAP API"
            }
        
        # Analyze the first few accounts to see all available fields
        sample_accounts = accounts[:5]  # Get first 5 accounts as samples
        
        # Get all unique field names across all accounts
        all_field_names = set()
        for account in accounts:
            all_field_names.update(account.keys())
        
        # Check specifically for type-related fields
        type_related_fields = []
        for field in all_field_names:
            if any(keyword in field.lower() for keyword in ['soort', 'type', 'categorie', 'groep', 'klasse']):
                type_related_fields.append(field)
        
        # Find accounts with different types/categories to see the variety
        account_types = {}
        for field in type_related_fields:
            values = set()
            for account in accounts:
                if field in account and account[field]:
                    values.add(account[field])
            if values:
                account_types[field] = list(values)[:10]  # Show up to 10 different values
        
        # Get specific examples of different account types
        example_accounts = []
        
        # Try to find examples of different account types
        account_codes_to_check = [
            ("1200", "Typical receivables account"),
            ("1600", "Typical payables account"),
            ("4000", "Revenue account"),
            ("7000", "Cost/expense account"),
            ("0400", "Equity account"),
            ("1000", "Asset account"),
            ("2000", "Liability account")
        ]
        
        for code_prefix, description in account_codes_to_check:
            for account in accounts:
                if account.get("Code", "").startswith(code_prefix):
                    example_accounts.append({
                        "description": description,
                        "account": account
                    })
                    break
        
        # Compare with REST API to see differences
        rest_comparison = None
        try:
            from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
            rest_api = EBoekhoudenAPI()
            # Use the chart_of_accounts method which is the REST API equivalent
            rest_result = rest_api.get_chart_of_accounts()
            
            if rest_result["success"]:
                rest_data = json.loads(rest_result["data"])
                rest_accounts = rest_data.get("items", [])
                
                if rest_accounts and len(rest_accounts) > 0:
                    rest_fields = set(rest_accounts[0].keys())
                    soap_fields = all_field_names
                    
                    # Check if REST has any type fields
                    rest_type_fields = []
                    for field in rest_fields:
                        if any(keyword in field.lower() for keyword in ['soort', 'type', 'categorie', 'groep', 'klasse']):
                            rest_type_fields.append(field)
                    
                    rest_comparison = {
                        "fields_only_in_soap": list(soap_fields - rest_fields),
                        "fields_only_in_rest": list(rest_fields - soap_fields),
                        "common_fields": list(soap_fields & rest_fields),
                        "rest_type_fields": rest_type_fields,
                        "rest_sample_account": rest_accounts[0] if rest_accounts else None
                    }
            else:
                rest_comparison = {"error": rest_result.get("error", "Failed to get REST accounts")}
        except Exception as e:
            rest_comparison = {"error": str(e)}
        
        return {
            "success": True,
            "total_accounts": len(accounts),
            "all_field_names": sorted(list(all_field_names)),
            "type_related_fields": type_related_fields,
            "account_types_found": account_types,
            "sample_accounts": sample_accounts,
            "example_accounts": example_accounts,
            "rest_api_comparison": rest_comparison,
            "recommendations": [
                f"SOAP API has 'Soort' field: {'Soort' in all_field_names}",
                f"Type-related fields found: {', '.join(type_related_fields) if type_related_fields else 'None'}",
                "Check if SOAP provides better account classification than REST API"
            ]
        }
        
    except Exception as e:
        frappe.log_error(f"Error testing SOAP account fields: {str(e)}", "SOAP Account Test")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }

@frappe.whitelist()
def compare_specific_account(account_code):
    """
    Compare a specific account between SOAP and REST APIs
    to see field differences
    """
    try:
        # Get from SOAP
        soap_api = EBoekhoudenSOAPAPI()
        session_result = soap_api.open_session()
        if not session_result["success"]:
            return {"success": False, "error": "Failed to open SOAP session"}
        
        soap_accounts = soap_api.get_grootboekrekeningen()
        soap_account = None
        if soap_accounts["success"]:
            for acc in soap_accounts["accounts"]:
                if acc.get("Code") == account_code:
                    soap_account = acc
                    break
        
        # Get from REST
        rest_account = None
        try:
            from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
            rest_api = EBoekhoudenAPI()
            rest_result = rest_api.get_chart_of_accounts()
            
            if rest_result["success"]:
                rest_data = json.loads(rest_result["data"])
                rest_accounts = rest_data.get("items", [])
                
                for acc in rest_accounts:
                    if acc.get("Code") == account_code or acc.get("code") == account_code:
                        rest_account = acc
                        break
            else:
                rest_account = {"error": rest_result.get("error", "Failed to get REST accounts")}
        except Exception as e:
            rest_account = {"error": str(e)}
        
        return {
            "success": True,
            "account_code": account_code,
            "soap_account": soap_account,
            "rest_account": rest_account,
            "comparison": {
                "soap_has_soort": "Soort" in (soap_account or {}),
                "rest_has_soort": "Soort" in (rest_account or {}),
                "soap_fields": list(soap_account.keys()) if soap_account else [],
                "rest_fields": list(rest_account.keys()) if rest_account and "error" not in rest_account else []
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def quick_test_receivables_account():
    """
    Quick test specifically for account 1300 (Debiteuren/Receivables)
    to check if SOAP API provides 'Soort' field
    """
    try:
        # Initialize SOAP API
        api = EBoekhoudenSOAPAPI()
        
        # Open session
        session_result = api.open_session()
        if not session_result["success"]:
            return {"success": False, "error": "Failed to open SOAP session"}
        
        # Get accounts
        accounts_result = api.get_grootboekrekeningen()
        if not accounts_result["success"]:
            return {"success": False, "error": "Failed to get accounts"}
        
        # Find account 1300
        account_1300 = None
        for account in accounts_result["accounts"]:
            if account.get("Code") == "1300":
                account_1300 = account
                break
        
        # Also check REST API for comparison
        rest_1300 = None
        try:
            from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
            rest_api = EBoekhoudenAPI()
            rest_result = rest_api.get_chart_of_accounts()
            
            if rest_result["success"]:
                rest_data = json.loads(rest_result["data"])
                for acc in rest_data.get("items", []):
                    if acc.get("Code") == "1300" or acc.get("code") == "1300":
                        rest_1300 = acc
                        break
        except:
            pass
        
        return {
            "success": True,
            "account_1300_soap": account_1300,
            "account_1300_rest": rest_1300,
            "soap_has_soort": bool(account_1300 and "Soort" in account_1300),
            "rest_has_type_field": bool(rest_1300 and any(k for k in rest_1300.keys() if 'type' in k.lower() or 'soort' in k.lower())),
            "summary": {
                "soap_fields": list(account_1300.keys()) if account_1300 else [],
                "rest_fields": list(rest_1300.keys()) if rest_1300 else []
            }
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    # Test the function
    result = test_soap_account_fields()
    print(json.dumps(result, indent=2))