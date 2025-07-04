"""
Debug specific mutation 548 that's failing
"""

import frappe
from frappe import _

@frappe.whitelist()
def debug_mutation_548():
    """Debug what mutation 548 is trying to do"""
    
    try:
        # Check if we have this mutation in any existing invoice
        existing_invoice = frappe.db.get_value("Purchase Invoice",
            {"bill_no": "EBH-548"},
            ["name", "supplier", "total", "docstatus"],
            as_dict=True
        )
        
        # Check the ledger mapping for this mutation
        # First, let's see what ledger IDs might be involved
        from verenigingen.utils.eboekhouden_rest_iterator import EBoekhoudenRESTIterator
        
        iterator = EBoekhoudenRESTIterator()
        
        # Try to fetch mutation 548
        mutation_data = iterator.fetch_mutation_detail(548)
        
        result = {
            "existing_invoice": existing_invoice,
            "mutation_data": None,
            "ledger_analysis": []
        }
        
        if mutation_data:
            result["mutation_data"] = mutation_data
            
            # Analyze the ledgers in this mutation
            rows = mutation_data.get("rows", [])
            for row in rows:
                ledger_id = str(row.get("ledgerId"))
                
                # Get the mapping
                mapping = frappe.db.get_value("E-Boekhouden Ledger Mapping",
                    {"ledger_id": ledger_id},
                    ["ledger_code", "ledger_name", "erpnext_account"],
                    as_dict=True
                )
                
                # Get account details if mapped
                account_details = None
                if mapping and mapping.erpnext_account:
                    account_details = frappe.db.get_value("Account",
                        mapping.erpnext_account,
                        ["account_name", "account_type"],
                        as_dict=True
                    )
                
                result["ledger_analysis"].append({
                    "ledger_id": ledger_id,
                    "amount": row.get("amount"),
                    "description": row.get("description"),
                    "mapping": mapping,
                    "account_details": account_details
                })
        
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "traceback": frappe.get_traceback()
        }