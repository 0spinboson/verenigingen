"""
Test fetching opening balance mutation
"""

import frappe
from frappe import _

@frappe.whitelist() 
def test_fetch_mutation_zero():
    """Test fetching mutation ID 0"""
    
    try:
        from verenigingen.utils.eboekhouden_rest_iterator import EBoekhoudenRESTIterator
        
        iterator = EBoekhoudenRESTIterator()
        
        # Try to fetch mutation 0 directly
        result = {
            "method_1_detail": None,
            "method_2_by_id": None
        }
        
        # Method 1: Direct detail fetch
        try:
            detail = iterator.fetch_mutation_detail(0)
            if detail:
                result["method_1_detail"] = {
                    "found": True,
                    "id": detail.get("id"),
                    "type": detail.get("type"),
                    "date": detail.get("date"),
                    "description": detail.get("description"),
                    "rows_count": len(detail.get("rows", []))
                }
        except Exception as e:
            result["method_1_detail"] = {"error": str(e)}
        
        # Method 2: By ID
        try:
            by_id = iterator.fetch_mutation_by_id(0)
            if by_id:
                result["method_2_by_id"] = {
                    "found": True,
                    "id": by_id.get("id"),
                    "type": by_id.get("type"),
                    "date": by_id.get("date"),
                    "description": by_id.get("description")
                }
        except Exception as e:
            result["method_2_by_id"] = {"error": str(e)}
        
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }