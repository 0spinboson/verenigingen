#!/usr/bin/env python
"""
Test the REST API migration by fetching a small batch of mutations
"""

import frappe
from frappe import _
import json

@frappe.whitelist()
def test_rest_mutation_fetch(start_id=17, end_id=100):
    """
    Test fetching mutations by ID and show the results
    """
    from .eboekhouden_rest_iterator import EBoekhoudenRESTIterator
    
    try:
        iterator = EBoekhoudenRESTIterator()
        
        results = {
            "found": [],
            "not_found": [],
            "errors": [],
            "summary": {}
        }
        
        frappe.publish_realtime(
            "eboekhouden_migration_progress",
            {"message": f"Testing REST API fetch from ID {start_id} to {end_id}..."}
        )
        
        # Try to fetch each mutation
        for mutation_id in range(int(start_id), int(end_id) + 1):
            try:
                # Try detail endpoint first (more complete data)
                mutation_data = iterator.fetch_mutation_detail(mutation_id)
                
                if mutation_data:
                    results["found"].append({
                        "id": mutation_id,
                        "type": mutation_data.get("type"),
                        "date": mutation_data.get("date"),
                        "amount": mutation_data.get("amount"),
                        "description": mutation_data.get("description", "")[:50]
                    })
                else:
                    results["not_found"].append(mutation_id)
                    
            except Exception as e:
                results["errors"].append({
                    "id": mutation_id,
                    "error": str(e)
                })
        
        # Summarize by type
        type_summary = {}
        for mutation in results["found"]:
            mut_type = mutation.get("type", "Unknown")
            type_summary[mut_type] = type_summary.get(mut_type, 0) + 1
        
        # Map type numbers to names (based on REST API documentation)
        type_names = {
            0: "Opening Balance",  # Not in official list but seen in data
            1: "Invoice received",  # Purchase Invoice
            2: "Invoice sent",      # Sales Invoice
            3: "Invoice payment received",  # Customer Payment
            4: "Invoice payment sent",      # Supplier Payment
            5: "Money received",
            6: "Money sent",
            7: "General journal entry"
        }
        
        type_summary_named = {}
        for type_num, count in type_summary.items():
            type_name = type_names.get(type_num, f"Type {type_num}")
            type_summary_named[type_name] = count
        
        results["summary"] = {
            "total_checked": end_id - start_id + 1,
            "total_found": len(results["found"]),
            "total_not_found": len(results["not_found"]),
            "total_errors": len(results["errors"]),
            "type_distribution": type_summary_named
        }
        
        # Show first few found mutations
        results["sample_mutations"] = results["found"][:5] if results["found"] else []
        
        return results
        
    except Exception as e:
        frappe.log_error(f"REST test error: {str(e)}", "E-Boekhouden REST Test")
        return {
            "error": str(e)
        }


@frappe.whitelist() 
def store_mutations_in_custom_field():
    """
    Store mutations in a custom field on the migration document for testing
    """
    from .eboekhouden_rest_iterator import EBoekhoudenRESTIterator
    
    try:
        # Get the migration document
        migration_docs = frappe.get_all("E-Boekhouden Migration", limit=1)
        if not migration_docs:
            return {
                "error": "No migration document found"
            }
        
        migration = frappe.get_doc("E-Boekhouden Migration", migration_docs[0].name)
        
        iterator = EBoekhoudenRESTIterator()
        
        # Fetch a small batch
        mutations = []
        for mutation_id in range(17, 117):  # First 100 mutations
            try:
                mutation_data = iterator.fetch_mutation_detail(mutation_id)
                if mutation_data:
                    mutations.append(mutation_data)
            except:
                pass
        
        # Store in a custom field (we'll create it if needed)
        if mutations:
            # Store as JSON string
            migration.db_set("rest_mutation_cache", json.dumps(mutations[:50]))  # Store first 50
            
            return {
                "success": True,
                "mutations_fetched": len(mutations),
                "mutations_stored": min(50, len(mutations)),
                "message": f"Stored {min(50, len(mutations))} mutations in migration document"
            }
        else:
            return {
                "success": False,
                "error": "No mutations found"
            }
            
    except Exception as e:
        frappe.log_error(f"Store mutations error: {str(e)}", "E-Boekhouden REST")
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def debug_mutation_data(mutation_id=17):
    """
    Debug a single mutation to see all fields
    """
    from .eboekhouden_rest_iterator import EBoekhoudenRESTIterator
    
    try:
        iterator = EBoekhoudenRESTIterator()
        
        # Fetch the mutation
        mutation_data = iterator.fetch_mutation_detail(int(mutation_id))
        
        if mutation_data:
            # Pretty print all fields
            import pprint
            formatted_data = pprint.pformat(mutation_data, indent=2)
            
            return {
                "success": True,
                "mutation_id": mutation_id,
                "data": mutation_data,
                "formatted": formatted_data,
                "fields": list(mutation_data.keys()),
                "type": mutation_data.get("type"),
                "type_name": get_mutation_type_name(mutation_data.get("type"))
            }
        else:
            return {
                "success": False,
                "error": f"Mutation {mutation_id} not found"
            }
            
    except Exception as e:
        frappe.log_error(f"Debug mutation error: {str(e)}", "E-Boekhouden REST Debug")
        return {
            "success": False,
            "error": str(e)
        }


def get_mutation_type_name(type_num):
    """
    Get the mutation type name from the type number
    """
    type_names = {
        0: "Opening Balance",
        1: "Invoice received",
        2: "Invoice sent", 
        3: "Invoice payment received",
        4: "Invoice payment sent",
        5: "Money received",
        6: "Money sent",
        7: "General journal entry"
    }
    return type_names.get(type_num, f"Unknown type {type_num}")