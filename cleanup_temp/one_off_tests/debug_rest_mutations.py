import frappe

@frappe.whitelist()
def test_rest_mutations():
    """Test what the REST iterator is actually returning"""
    try:
        from verenigingen.utils.eboekhouden_rest_iterator import EBoekhoudenRESTIterator
        
        iterator = EBoekhoudenRESTIterator()
        
        # Test each mutation type
        test_types = [0, 1, 2, 3, 4, 5, 6, 7]
        results = {}
        
        for mutation_type in test_types:
            try:
                # Fetch just first 5 of each type for testing
                mutations = iterator.fetch_mutations_by_type(mutation_type, limit=5)
                results[mutation_type] = {
                    "count": len(mutations),
                    "sample": mutations[0] if mutations else None
                }
            except Exception as e:
                results[mutation_type] = {
                    "error": str(e)
                }
        
        return {"success": True, "results": results}
        
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

@frappe.whitelist()
def test_rest_range_estimation():
    """Test the range estimation"""
    try:
        from verenigingen.utils.eboekhouden_rest_iterator import EBoekhoudenRESTIterator
        
        iterator = EBoekhoudenRESTIterator()
        range_result = iterator.estimate_id_range()
        
        return {"success": True, "range_result": range_result}
        
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

@frappe.whitelist()
def test_specific_mutations():
    """Test specific mutation IDs"""
    try:
        from verenigingen.utils.eboekhouden_rest_iterator import EBoekhoudenRESTIterator
        
        iterator = EBoekhoudenRESTIterator()
        
        # Test some specific IDs
        test_ids = [0, 1, 100, 500, 1000, 7000, 7142]
        results = {}
        
        for test_id in test_ids:
            mutation = iterator.fetch_mutation_detail(test_id)
            results[test_id] = {
                "exists": bool(mutation),
                "data": mutation.get("id") if mutation else None,
                "type": mutation.get("type") if mutation else None,
                "date": mutation.get("date") if mutation else None
            }
        
        return {"success": True, "results": results}
        
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }