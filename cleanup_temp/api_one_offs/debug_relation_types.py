import frappe
import json

@frappe.whitelist()
def analyze_relation_types():
    """Analyze the types of relations in E-Boekhouden to understand the Soort field"""
    try:
        response = []
        response.append("=== ANALYZING E-BOEKHOUDEN RELATION TYPES ===")
        
        # Get E-Boekhouden API settings
        settings = frappe.get_single("E-Boekhouden Settings")
        
        # Import API class
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        api = EBoekhoudenAPI(settings)
        
        # Fetch all relations
        response.append("Fetching relations from E-Boekhouden API...")
        relations_result = api.get_relations()
        
        if not relations_result["success"]:
            return f"Error fetching relations: {relations_result.get('error', 'Unknown error')}"
        
        # Parse relations data
        relations_data = json.loads(relations_result["data"])
        all_relations = relations_data.get("items", [])
        
        response.append(f"Found {len(all_relations)} total relations")
        
        # Analyze relation types
        type_counts = {}
        soort_counts = {}
        sample_relations = {}
        
        for rel in all_relations:
            # Count by Soort field
            soort = rel.get("Soort", "")
            soort_counts[soort] = soort_counts.get(soort, 0) + 1
            
            # Keep sample for each type
            if soort not in sample_relations:
                sample_relations[soort] = rel
        
        response.append(f"\n=== SOORT FIELD ANALYSIS ===")
        for soort, count in sorted(soort_counts.items()):
            response.append(f"'{soort}': {count} relations")
        
        response.append(f"\n=== SAMPLE RELATIONS BY TYPE ===")
        for soort, sample in sample_relations.items():
            response.append(f"\nType: '{soort}'")
            response.append(f"  Sample ID: {sample.get('ID', 'N/A')}")
            response.append(f"  Naam: {sample.get('Naam', 'N/A')}")
            response.append(f"  Bedrijf: {sample.get('Bedrijf', 'N/A')}")
            response.append(f"  Contactpersoon: {sample.get('Contactpersoon', 'N/A')}")
            response.append(f"  Sample keys: {list(sample.keys())}")
        
        # Look for our specific relation codes
        response.append(f"\n=== SEARCHING FOR EXISTING SUPPLIER CODES ===")
        existing_codes = ['00002', '00019', '00038', '00058', '201', '1343', '1344', '197']
        
        found_relations = {}
        for rel in all_relations:
            rel_id = str(rel.get("ID", ""))
            if rel_id in existing_codes:
                found_relations[rel_id] = rel
        
        response.append(f"Found {len(found_relations)} of {len(existing_codes)} existing codes in E-Boekhouden:")
        
        for code in existing_codes:
            if code in found_relations:
                rel = found_relations[code]
                response.append(f"  ✅ {code}: {rel.get('Naam', 'N/A')} (Soort: '{rel.get('Soort', 'N/A')}')")
            else:
                response.append(f"  ❌ {code}: Not found in E-Boekhouden")
        
        return "\n".join(response)
        
    except Exception as e:
        return f"Error: {e}\n{frappe.get_traceback()}"


@frappe.whitelist()
def find_specific_relation(relation_id):
    """Find a specific relation by ID"""
    try:
        response = []
        response.append(f"=== SEARCHING FOR RELATION ID: {relation_id} ===")
        
        # Get E-Boekhouden API settings
        settings = frappe.get_single("E-Boekhouden Settings")
        
        # Import API class
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        api = EBoekhoudenAPI(settings)
        
        # Fetch all relations
        relations_result = api.get_relations()
        
        if not relations_result["success"]:
            return f"Error fetching relations: {relations_result.get('error', 'Unknown error')}"
        
        # Parse relations data
        relations_data = json.loads(relations_result["data"])
        all_relations = relations_data.get("items", [])
        
        # Find the specific relation
        found_relation = None
        for rel in all_relations:
            if str(rel.get("ID", "")) == str(relation_id):
                found_relation = rel
                break
        
        if found_relation:
            response.append(f"✅ Found relation {relation_id}:")
            for key, value in found_relation.items():
                response.append(f"  {key}: {value}")
        else:
            response.append(f"❌ Relation {relation_id} not found in E-Boekhouden")
            response.append(f"Total relations searched: {len(all_relations)}")
        
        return "\n".join(response)
        
    except Exception as e:
        return f"Error: {e}\n{frappe.get_traceback()}"