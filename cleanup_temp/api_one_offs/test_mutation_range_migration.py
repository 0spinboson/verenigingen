"""
Test mutation range-based migration
"""

import frappe
from frappe import _

@frappe.whitelist()
def test_get_highest_mutation_number():
    """Test getting the highest mutation number"""
    from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenSOAPAPI(settings)
    
    result = api.get_highest_mutation_number()
    
    if result["success"]:
        return {
            "success": True,
            "highest_mutation_number": result["highest_mutation_number"],
            "message": f"Highest mutation number found: {result['highest_mutation_number']}"
        }
    else:
        return {
            "success": False,
            "error": result.get("error", "Failed to get highest mutation number")
        }

@frappe.whitelist()
def test_mutation_range_retrieval():
    """Test retrieving mutations by ID range"""
    from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenSOAPAPI(settings)
    
    # First get highest number
    highest_result = api.get_highest_mutation_number()
    if not highest_result["success"]:
        return {
            "success": False,
            "error": "Failed to get highest mutation number"
        }
    
    highest = highest_result["highest_mutation_number"]
    
    # Test getting a small range
    test_ranges = [
        (1, 100),
        (101, 200),
        (max(1, highest - 99), highest)  # Last 100 mutations
    ]
    
    results = []
    
    for start, end in test_ranges:
        result = api.get_mutations(mutation_nr_from=start, mutation_nr_to=end)
        
        if result["success"]:
            mutations = result["mutations"]
            mutation_numbers = []
            
            for mut in mutations:
                mut_nr = mut.get("MutatieNr")
                if mut_nr:
                    mutation_numbers.append(int(mut_nr))
            
            results.append({
                "range": f"{start}-{end}",
                "count": len(mutations),
                "mutation_numbers": sorted(mutation_numbers)[:10],  # First 10
                "has_gaps": check_for_gaps(mutation_numbers) if mutation_numbers else False
            })
        else:
            results.append({
                "range": f"{start}-{end}",
                "error": result.get("error", "Failed")
            })
    
    return {
        "success": True,
        "highest_mutation_number": highest,
        "test_results": results
    }

def check_for_gaps(numbers):
    """Check if there are gaps in mutation numbers"""
    if not numbers:
        return False
    
    sorted_nums = sorted(numbers)
    for i in range(1, len(sorted_nums)):
        if sorted_nums[i] - sorted_nums[i-1] > 1:
            return True
    return False

@frappe.whitelist()
def test_batch_migration():
    """Test migration with small batch to verify the approach"""
    from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenSOAPAPI(settings)
    
    # Get just the first 50 mutations as a test
    result = api.get_mutations(mutation_nr_from=1, mutation_nr_to=50)
    
    if not result["success"]:
        return {
            "success": False,
            "error": result.get("error", "Failed to get mutations")
        }
    
    mutations = result["mutations"]
    
    # Analyze the mutations
    mutation_types = {}
    mutation_samples = []
    
    for mut in mutations[:10]:  # First 10 as samples
        mut_type = mut.get("Soort", "Unknown")
        mutation_types[mut_type] = mutation_types.get(mut_type, 0) + 1
        
        mutation_samples.append({
            "MutatieNr": mut.get("MutatieNr"),
            "Datum": mut.get("Datum"),
            "Soort": mut.get("Soort"),
            "Omschrijving": mut.get("Omschrijving", "")[:50],
            "HasMutatieRegels": len(mut.get("MutatieRegels", [])) > 0
        })
    
    return {
        "success": True,
        "total_mutations": len(mutations),
        "mutation_types": mutation_types,
        "samples": mutation_samples,
        "message": "Test batch retrieved successfully"
    }

if __name__ == "__main__":
    print(test_get_highest_mutation_number())