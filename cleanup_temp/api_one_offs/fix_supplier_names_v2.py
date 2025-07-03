import frappe
import json

@frappe.whitelist()
def get_all_relation_details():
    """Fetch detailed information for all relations from E-Boekhouden"""
    try:
        response = []
        response.append("=== FETCHING ALL RELATION DETAILS ===")
        
        # Get E-Boekhouden API settings
        settings = frappe.get_single("E-Boekhouden Settings")
        
        # Import API class
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        api = EBoekhoudenAPI(settings)
        
        # First, get all relation IDs
        response.append("Fetching relation list...")
        relations_result = api.get_relations()
        
        if not relations_result["success"]:
            return f"Error fetching relations: {relations_result.get('error', 'Unknown error')}"
        
        # Parse relations data
        relations_data = json.loads(relations_result["data"])
        all_relations = relations_data.get("items", [])
        
        response.append(f"Found {len(all_relations)} relations")
        
        # Get detailed information for each relation
        detailed_relations = []
        suppliers = []
        customers = []
        errors = []
        
        for i, rel in enumerate(all_relations):
            rel_id = rel.get("id")
            rel_type = rel.get("type", "")
            rel_code = rel.get("code", "")
            
            if i % 50 == 0:
                response.append(f"Processing relation {i+1}/{len(all_relations)}...")
            
            try:
                # Get detailed information
                detail_result = api.make_request(f"v1/relation/{rel_id}", "GET")
                
                if detail_result["success"]:
                    detail_data = json.loads(detail_result["data"])
                    detailed_relations.append(detail_data)
                    
                    # Categorize by type
                    if rel_type == "L":  # Leverancier = Supplier
                        suppliers.append(detail_data)
                    elif rel_type == "D":  # Debiteur = Customer  
                        customers.append(detail_data)
                    elif rel_type == "P":  # Person - could be either
                        # We'll categorize these later based on usage
                        pass
                else:
                    errors.append(f"Failed to get details for relation {rel_id}: {detail_result.get('error', 'Unknown')}")
                    
            except Exception as e:
                errors.append(f"Error processing relation {rel_id}: {str(e)}")
                continue
        
        response.append(f"\n=== SUMMARY ===")
        response.append(f"Total relations processed: {len(detailed_relations)}")
        response.append(f"Suppliers (type='L'): {len(suppliers)}")
        response.append(f"Customers (type='D'): {len(customers)}")
        response.append(f"Errors: {len(errors)}")
        
        # Show samples
        if suppliers:
            response.append(f"\n=== SAMPLE SUPPLIERS ===")
            for supplier in suppliers[:5]:
                response.append(f"ID: {supplier.get('id')}, Code: {supplier.get('code')}, Name: {supplier.get('name', 'N/A')}")
        
        if customers:
            response.append(f"\n=== SAMPLE CUSTOMERS ===")
            for customer in customers[:5]:
                response.append(f"ID: {customer.get('id')}, Code: {customer.get('code')}, Name: {customer.get('name', 'N/A')}")
        
        # Check if any of our existing supplier codes exist
        response.append(f"\n=== CHECKING EXISTING SUPPLIER CODES ===")
        existing_codes = frappe.db.sql_list("""
            SELECT eboekhouden_relation_code 
            FROM `tabSupplier` 
            WHERE eboekhouden_relation_code IS NOT NULL 
            AND eboekhouden_relation_code != ''
        """)
        
        # Create mapping of codes to detailed relations
        code_to_relation = {}
        for rel in detailed_relations:
            code = rel.get("code", "")
            if code:
                code_to_relation[code] = rel
        
        found_codes = []
        missing_codes = []
        
        for code in existing_codes:
            if code in code_to_relation:
                found_codes.append((code, code_to_relation[code]))
            else:
                missing_codes.append(code)
        
        response.append(f"Existing supplier codes found in E-Boekhouden: {len(found_codes)}")
        response.append(f"Existing supplier codes NOT found: {len(missing_codes)}")
        
        if found_codes:
            response.append(f"\nFound supplier codes:")
            for code, rel in found_codes:
                response.append(f"  {code}: {rel.get('name', 'N/A')} (Type: {rel.get('type', 'N/A')})")
        
        if missing_codes:
            response.append(f"\nMissing supplier codes: {missing_codes}")
        
        if errors:
            response.append(f"\n=== ERRORS ===")
            for error in errors[:10]:  # Show first 10 errors
                response.append(f"  - {error}")
        
        return "\n".join(response)
        
    except Exception as e:
        return f"Error: {e}\n{frappe.get_traceback()}"


@frappe.whitelist()
def update_supplier_names_from_eboekhouden():
    """Update supplier names using actual E-Boekhouden relation data"""
    try:
        response = []
        response.append("=== UPDATING SUPPLIER NAMES FROM E-BOEKHOUDEN ===")
        
        # Get E-Boekhouden API settings
        settings = frappe.get_single("E-Boekhouden Settings")
        
        # Import API class
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        api = EBoekhoudenAPI(settings)
        
        # Get all relations
        response.append("Fetching all relations from E-Boekhouden...")
        relations_result = api.get_relations()
        
        if not relations_result["success"]:
            return f"Error fetching relations: {relations_result.get('error', 'Unknown error')}"
        
        relations_data = json.loads(relations_result["data"])
        all_relations = relations_data.get("items", [])
        
        # Get detailed data for all relations
        detailed_relations = {}
        for rel in all_relations:
            rel_id = rel.get("id")
            rel_code = rel.get("code", "")
            
            if rel_code:  # Only process if we have a code
                try:
                    detail_result = api.make_request(f"v1/relation/{rel_id}", "GET")
                    if detail_result["success"]:
                        detail_data = json.loads(detail_result["data"])
                        detailed_relations[rel_code] = detail_data
                except:
                    continue
        
        response.append(f"Retrieved detailed data for {len(detailed_relations)} relations")
        
        # Get existing suppliers with E-Boekhouden codes
        existing_suppliers = frappe.db.sql("""
            SELECT name, supplier_name, supplier_type, eboekhouden_relation_code
            FROM `tabSupplier`
            WHERE eboekhouden_relation_code IS NOT NULL 
            AND eboekhouden_relation_code != ''
        """, as_dict=True)
        
        response.append(f"Found {len(existing_suppliers)} existing suppliers with relation codes")
        
        # Update suppliers
        updated_count = 0
        not_found_count = 0
        errors = []
        
        for supplier in existing_suppliers:
            try:
                relation_code = supplier.eboekhouden_relation_code
                
                if relation_code in detailed_relations:
                    relation_data = detailed_relations[relation_code]
                    
                    # Extract name information
                    eb_name = relation_data.get("name", "").strip()
                    eb_contact = relation_data.get("contact", "").strip()  
                    eb_type = relation_data.get("type", "").strip()
                    
                    # Determine best name
                    if eb_name:
                        new_name = eb_name
                    elif eb_contact:
                        new_name = eb_contact
                    else:
                        response.append(f"  ⚠️  No usable name for supplier {supplier.name} (code: {relation_code})")
                        continue
                    
                    # Determine supplier type
                    # Type 'L' = Leverancier (Supplier), likely business
                    # Type 'P' = Person, could be individual
                    # Type 'D' = Debiteur (Customer), but might be used as supplier too
                    if eb_type == "L":
                        new_supplier_type = "Company"  # Business supplier
                    elif eb_type == "P":
                        new_supplier_type = "Individual"  # Person
                    else:
                        new_supplier_type = supplier.supplier_type  # Keep existing
                    
                    # Check if update is needed
                    needs_update = False
                    updates = {}
                    
                    if supplier.supplier_name != new_name:
                        updates["supplier_name"] = new_name
                        needs_update = True
                    
                    if supplier.supplier_type != new_supplier_type:
                        updates["supplier_type"] = new_supplier_type
                        needs_update = True
                    
                    if needs_update:
                        # Check for name conflicts
                        existing_with_name = frappe.db.get_value("Supplier", 
                            {"supplier_name": new_name, "name": ["!=", supplier.name]}, "name")
                        
                        if existing_with_name:
                            new_name = f"{new_name} ({relation_code})"
                            updates["supplier_name"] = new_name
                        
                        # Update the supplier
                        frappe.db.set_value("Supplier", supplier.name, updates)
                        
                        updated_count += 1
                        response.append(f"  ✅ Updated: {supplier.supplier_name} → {new_name} ({new_supplier_type})")
                    else:
                        response.append(f"  ✓ No change: {supplier.supplier_name}")
                
                else:
                    not_found_count += 1
                    response.append(f"  ❌ Not found: {supplier.supplier_name} (code: {relation_code})")
                    
            except Exception as e:
                error_msg = f"Error updating supplier {supplier.name}: {str(e)}"
                errors.append(error_msg)
                response.append(f"  ❌ {error_msg}")
        
        # Commit changes
        frappe.db.commit()
        
        # Summary
        response.append(f"\n=== SUMMARY ===")
        response.append(f"Total suppliers processed: {len(existing_suppliers)}")
        response.append(f"Suppliers updated: {updated_count}")
        response.append(f"Suppliers not found in E-Boekhouden: {not_found_count}")
        response.append(f"Errors: {len(errors)}")
        
        return "\n".join(response)
        
    except Exception as e:
        return f"Error: {e}\n{frappe.get_traceback()}"