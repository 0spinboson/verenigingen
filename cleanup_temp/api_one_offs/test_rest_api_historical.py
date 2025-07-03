"""
Test E-Boekhouden REST API for historical data
"""

import frappe
from frappe import _
import json

@frappe.whitelist()
def test_rest_api_historical():
    """
    Test REST API to see if it returns historical data from 2018
    """
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        settings = frappe.get_single("E-Boekhouden Settings")
        api = EBoekhoudenAPI(settings)
        
        # Test with date filters
        params = {
            "dateFrom": "2018-12-31",
            "dateTo": "2019-01-31",
            "limit": 100
        }
        
        result = api.get_mutations(params)
        
        if not result["success"]:
            return {
                "success": False,
                "error": result.get("error"),
                "params": params
            }
        
        data = json.loads(result["data"])
        mutations = data.get("items", [])
        
        # Analyze dates
        date_analysis = {
            "total": len(mutations),
            "earliest": None,
            "latest": None,
            "dates_found": set(),
            "samples": []
        }
        
        for mut in mutations:
            date_str = mut.get("date", "")
            if date_str:
                date_analysis["dates_found"].add(date_str[:10])
                
                if not date_analysis["earliest"] or date_str < date_analysis["earliest"]:
                    date_analysis["earliest"] = date_str
                if not date_analysis["latest"] or date_str > date_analysis["latest"]:
                    date_analysis["latest"] = date_str
                
                if len(date_analysis["samples"]) < 5:
                    date_analysis["samples"].append({
                        "id": mut.get("id"),
                        "date": date_str[:10],
                        "description": mut.get("description", "")[:100],
                        "entryNumber": mut.get("entryNumber"),
                        "amount": mut.get("amount")
                    })
        
        date_analysis["dates_found"] = sorted(list(date_analysis["dates_found"]))
        
        return {
            "success": True,
            "api_type": "REST",
            "requested_range": f"{params['dateFrom']} to {params['dateTo']}",
            "analysis": date_analysis
        }
        
    except Exception as e:
        frappe.log_error(f"REST API historical test error: {str(e)}", "E-Boekhouden")
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def compare_rest_vs_soap():
    """
    Compare what REST and SOAP APIs return for the same date range
    """
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
        
        settings = frappe.get_single("E-Boekhouden Settings")
        
        # Test date range
        date_from = "2019-01-01"
        date_to = "2019-01-31"
        
        # Test REST API
        rest_api = EBoekhoudenAPI(settings)
        rest_params = {
            "dateFrom": date_from,
            "dateTo": date_to,
            "limit": 100
        }
        rest_result = rest_api.get_mutations(rest_params)
        
        rest_analysis = {
            "success": rest_result["success"],
            "count": 0,
            "dates": set()
        }
        
        if rest_result["success"]:
            data = json.loads(rest_result["data"])
            mutations = data.get("items", [])
            rest_analysis["count"] = len(mutations)
            for mut in mutations:
                if mut.get("date"):
                    rest_analysis["dates"].add(mut["date"][:10])
        
        # Test SOAP API
        soap_api = EBoekhoudenSOAPAPI(settings)
        soap_result = soap_api.get_mutations(date_from=date_from, date_to=date_to)
        
        soap_analysis = {
            "success": soap_result["success"],
            "count": 0,
            "dates": set()
        }
        
        if soap_result["success"]:
            soap_analysis["count"] = len(soap_result["mutations"])
            for mut in soap_result["mutations"]:
                if mut.get("Datum"):
                    soap_analysis["dates"].add(mut["Datum"][:10])
        
        # Convert sets to sorted lists
        rest_analysis["dates"] = sorted(list(rest_analysis["dates"]))
        soap_analysis["dates"] = sorted(list(soap_analysis["dates"]))
        
        return {
            "success": True,
            "date_range": f"{date_from} to {date_to}",
            "rest_api": rest_analysis,
            "soap_api": soap_analysis,
            "comparison": {
                "rest_has_data": rest_analysis["count"] > 0,
                "soap_has_data": soap_analysis["count"] > 0,
                "same_count": rest_analysis["count"] == soap_analysis["count"]
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def find_oldest_data_rest():
    """
    Try to find the oldest data available in REST API
    """
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        settings = frappe.get_single("E-Boekhouden Settings")
        api = EBoekhoudenAPI(settings)
        
        # Try without date filter first
        params = {
            "limit": 10,
            "offset": 0,
            "sort": "date",  # Try to sort by date ascending
            "sortDirection": "asc"
        }
        
        result = api.get_mutations(params)
        
        if not result["success"]:
            return {
                "success": False,
                "error": result.get("error")
            }
        
        data = json.loads(result["data"])
        mutations = data.get("items", [])
        
        oldest_mutations = []
        for mut in mutations[:5]:
            oldest_mutations.append({
                "id": mut.get("id"),
                "date": mut.get("date", ""),
                "description": mut.get("description", "")[:100],
                "entryNumber": mut.get("entryNumber")
            })
        
        return {
            "success": True,
            "message": "Tried to get oldest mutations using sort",
            "oldest_mutations": oldest_mutations,
            "total_returned": len(mutations)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }