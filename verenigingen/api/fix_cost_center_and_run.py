import frappe
from frappe import _

@frappe.whitelist()
def fix_cost_center_and_prepare():
    """Fix cost center issue and prepare for migration"""
    
    company = frappe.db.get_single_value("E-Boekhouden Settings", "default_company")
    if not company:
        return {"success": False, "error": "No default company set in E-Boekhouden Settings"}
    
    # Check current cost centers
    existing_cc = frappe.get_all("Cost Center", 
        filters={"company": company},
        fields=["name", "cost_center_name", "parent_cost_center", "is_group"])
    
    # Find or create root cost center
    root_cc = None
    
    # First try to find existing root
    for cc in existing_cc:
        if cc.is_group and not cc.parent_cost_center:
            root_cc = cc.name
            break
    
    # If no root found, try company abbreviation pattern
    if not root_cc:
        abbr = frappe.db.get_value("Company", company, "abbr")
        if abbr:
            expected_name = f"{company} - {abbr}"
            if frappe.db.exists("Cost Center", expected_name):
                root_cc = expected_name
    
    # Create root cost center if still not found
    if not root_cc:
        try:
            cc_doc = frappe.new_doc("Cost Center")
            cc_doc.cost_center_name = company
            cc_doc.company = company
            cc_doc.is_group = 1
            cc_doc.parent_cost_center = ""
            cc_doc.insert(ignore_permissions=True)
            root_cc = cc_doc.name
            frappe.db.commit()
        except Exception as e:
            # Try with a different name
            try:
                cc_doc = frappe.new_doc("Cost Center")
                cc_doc.cost_center_name = f"Main - {company}"
                cc_doc.company = company
                cc_doc.is_group = 1
                cc_doc.parent_cost_center = ""
                cc_doc.insert(ignore_permissions=True)
                root_cc = cc_doc.name
                frappe.db.commit()
            except Exception as e2:
                return {
                    "success": False,
                    "error": f"Could not create root cost center: {str(e2)}",
                    "existing_cost_centers": existing_cc
                }
    
    # Test the SOAP API
    from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenSOAPAPI(settings)
    
    test_result = api.get_mutations(date_from="2025-05-01", date_to="2025-05-31")
    
    if not test_result["success"]:
        return {
            "success": False,
            "error": f"SOAP API test failed: {test_result.get('error')}"
        }
    
    return {
        "success": True,
        "company": company,
        "root_cost_center": root_cc,
        "existing_cost_centers": len(existing_cc),
        "soap_test": {
            "mutations_found": test_result["count"],
            "connection": "OK"
        },
        "ready_for_migration": True
    }

@frappe.whitelist()
def run_soap_migration_for_may():
    """Run the SOAP migration for May 2025"""
    
    # First ensure cost center exists
    prep_result = fix_cost_center_and_prepare()
    if not prep_result["success"]:
        return prep_result
    
    # Get the migration document
    migration_name = "EBMIG-2025-00006"
    migration = frappe.get_doc("E-Boekhouden Migration", migration_name)
    
    # Ensure it's set to use SOAP API
    migration.use_soap_api = 1
    migration.save()
    
    # Run just the transactions migration using SOAP
    settings = frappe.get_single("E-Boekhouden Settings")
    
    try:
        from verenigingen.utils.eboekhouden_soap_migration import migrate_using_soap
        
        result = migrate_using_soap(migration, settings)
        
        if result["success"]:
            # Update the migration document
            stats = result["stats"]
            migration.current_operation = f"SOAP Migration completed: {result['message']}"
            migration.save()
            frappe.db.commit()
            
            return {
                "success": True,
                "message": result["message"],
                "stats": stats,
                "cost_center": prep_result["root_cost_center"]
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Unknown error"),
                "cost_center": prep_result["root_cost_center"]
            }
            
    except Exception as e:
        frappe.log_error(f"SOAP Migration error: {str(e)}", "E-Boekhouden")
        return {
            "success": False,
            "error": str(e),
            "traceback": frappe.get_traceback()
        }

@frappe.whitelist()
def preview_may_mutations():
    """Preview what would be imported for May 2025"""
    
    from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenSOAPAPI(settings)
    
    result = api.get_mutations(date_from="2025-05-01", date_to="2025-05-31")
    
    if not result["success"]:
        return result
    
    mutations = result["mutations"]
    
    # Analyze by type
    by_type = {}
    sample_transactions = {
        "invoices": [],
        "payments": [],
        "bank": []
    }
    
    for mut in mutations:
        soort = mut.get("Soort", "Unknown")
        if soort not in by_type:
            by_type[soort] = 0
        by_type[soort] += 1
        
        # Collect samples
        if soort == "FactuurVerstuurd" and len(sample_transactions["invoices"]) < 5:
            sample_transactions["invoices"].append({
                "date": mut.get("Datum", "")[:10],
                "invoice": mut.get("Factuurnummer"),
                "customer": mut.get("RelatieCode"),
                "description": mut.get("Omschrijving", "")[:80]
            })
        elif "betaling" in soort.lower() and len(sample_transactions["payments"]) < 5:
            sample_transactions["payments"].append({
                "date": mut.get("Datum", "")[:10],
                "type": soort,
                "invoice": mut.get("Factuurnummer"),
                "description": mut.get("Omschrijving", "")[:80]
            })
        elif soort in ["GeldOntvangen", "GeldUitgegeven"] and len(sample_transactions["bank"]) < 5:
            sample_transactions["bank"].append({
                "date": mut.get("Datum", "")[:10],
                "type": soort,
                "description": mut.get("Omschrijving", "")[:80]
            })
    
    return {
        "success": True,
        "total_mutations": len(mutations),
        "by_type": by_type,
        "samples": sample_transactions,
        "date_range": "May 2025"
    }

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        print(preview_may_mutations())
    else:
        print(fix_cost_center_and_prepare())