import frappe
import json

@frappe.whitelist()
def quick_relation_sample():
    """Get a small sample of relation details to understand the data structure"""
    try:
        response = []
        response.append("=== QUICK RELATION SAMPLE ===")
        
        # Get E-Boekhouden API settings
        settings = frappe.get_single("E-Boekhouden Settings")
        
        # Import API class
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        api = EBoekhoudenAPI(settings)
        
        # Get first 10 relations
        relations_result = api.make_request("v1/relation", "GET", {"limit": 10})
        
        if not relations_result["success"]:
            return f"Error: {relations_result.get('error', 'Unknown error')}"
        
        relations_data = json.loads(relations_result["data"])
        relations = relations_data.get("items", [])
        
        response.append(f"Found {len(relations)} relations")
        
        # Get details for first few relations
        type_counts = {}
        
        for i, rel in enumerate(relations[:5]):
            rel_id = rel.get("id")
            rel_type = rel.get("type")
            rel_code = rel.get("code")
            
            response.append(f"\nRelation {i+1}: ID={rel_id}, Type={rel_type}, Code={rel_code}")
            
            # Count types
            type_counts[rel_type] = type_counts.get(rel_type, 0) + 1
            
            # Get detailed info
            try:
                detail_result = api.make_request(f"v1/relation/{rel_id}", "GET")
                if detail_result["success"]:
                    detail_data = json.loads(detail_result["data"])
                    response.append(f"  Name: {detail_data.get('name', 'N/A')}")
                    response.append(f"  Contact: {detail_data.get('contact', 'N/A')}")
                    response.append(f"  Email: {detail_data.get('emailAddress', 'N/A')}")
                    response.append(f"  Type: {detail_data.get('type', 'N/A')}")
                else:
                    response.append(f"  Error getting details: {detail_result.get('error', 'Unknown')}")
            except Exception as e:
                response.append(f"  Exception getting details: {str(e)}")
        
        response.append(f"\n=== TYPE COUNTS (from sample) ===")
        for rel_type, count in type_counts.items():
            response.append(f"Type '{rel_type}': {count}")
        
        return "\n".join(response)
        
    except Exception as e:
        return f"Error: {e}\n{frappe.get_traceback()}"