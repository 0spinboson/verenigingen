import frappe
from frappe import _

@frappe.whitelist()
def test_soap_migration():
    """Test the SOAP-based migration"""
    
    # First add the custom fields
    from verenigingen.utils.eboekhouden_soap_migration import add_eboekhouden_custom_fields
    fields_result = add_eboekhouden_custom_fields()
    
    # Test the SOAP API connection
    from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenSOAPAPI(settings)
    
    # Test getting mutations
    test_result = api.get_mutations(date_from="2025-06-01", date_to="2025-06-30")
    
    if not test_result["success"]:
        return {
            "success": False,
            "error": f"SOAP API test failed: {test_result.get('error')}"
        }
    
    # Analyze what we would import
    mutations = test_result["mutations"]
    
    # Group by type
    by_type = {}
    for mut in mutations:
        soort = mut.get("Soort", "Unknown")
        if soort not in by_type:
            by_type[soort] = 0
        by_type[soort] += 1
    
    # Check for required accounts
    company = settings.default_company
    checks = {
        "company": bool(company),
        "cost_center": bool(frappe.db.get_value("Cost Center", {
            "company": company,
            "is_group": 1,
            "parent_cost_center": ["in", ["", None]]
        }, "name")),
        "bank_account": bool(frappe.db.get_value("Account", {
            "company": company,
            "account_type": "Bank",
            "is_group": 0
        }, "name")),
        "income_account": bool(frappe.db.get_value("Account", {
            "company": company,
            "account_type": "Income Account",
            "is_group": 0
        }, "name"))
    }
    
    return {
        "success": True,
        "custom_fields": fields_result,
        "soap_test": {
            "total_mutations": len(mutations),
            "by_type": by_type,
            "sample_mutation": mutations[0] if mutations else None
        },
        "system_ready": all(checks.values()),
        "checks": checks,
        "recommendation": "System is ready for SOAP migration" if all(checks.values()) else "Fix missing items before migration"
    }

@frappe.whitelist()
def preview_soap_migration(date_from=None, date_to=None):
    """Preview what would be imported with SOAP migration"""
    
    from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenSOAPAPI(settings)
    
    # Default to last month if no dates provided
    if not date_from:
        date_from = frappe.utils.add_days(frappe.utils.today(), -30)
    if not date_to:
        date_to = frappe.utils.today()
    
    result = api.get_mutations(date_from=date_from, date_to=date_to)
    
    if not result["success"]:
        return result
    
    mutations = result["mutations"]
    
    # Analyze what would be created
    preview = {
        "date_range": f"{date_from} to {date_to}",
        "total_mutations": len(mutations),
        "by_type": {},
        "invoices_to_create": [],
        "payments_to_process": [],
        "bank_transactions": []
    }
    
    for mut in mutations:
        soort = mut.get("Soort", "Unknown")
        
        if soort not in preview["by_type"]:
            preview["by_type"][soort] = {
                "count": 0,
                "total_amount": 0
            }
        
        preview["by_type"][soort]["count"] += 1
        
        # Calculate total from mutation lines
        total = 0
        for regel in mut.get("MutatieRegels", []):
            total += float(regel.get("BedragInclBTW", 0))
        
        preview["by_type"][soort]["total_amount"] += total
        
        # Sample data for each type
        if soort == "FactuurVerstuurd" and len(preview["invoices_to_create"]) < 5:
            preview["invoices_to_create"].append({
                "invoice_no": mut.get("Factuurnummer"),
                "date": mut.get("Datum"),
                "customer": mut.get("RelatieCode"),
                "amount": total,
                "description": mut.get("Omschrijving", "")[:50]
            })
        elif "betaling" in soort.lower() and len(preview["payments_to_process"]) < 5:
            preview["payments_to_process"].append({
                "date": mut.get("Datum"),
                "invoice": mut.get("Factuurnummer"),
                "amount": total,
                "type": soort,
                "description": mut.get("Omschrijving", "")[:50]
            })
        elif soort in ["GeldOntvangen", "GeldUitgegeven"] and len(preview["bank_transactions"]) < 5:
            preview["bank_transactions"].append({
                "date": mut.get("Datum"),
                "amount": total,
                "type": soort,
                "description": mut.get("Omschrijving", "")[:80]
            })
    
    return {
        "success": True,
        "preview": preview
    }