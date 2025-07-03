import frappe
import json

@frappe.whitelist()
def fetch_and_update_supplier_names():
    """Fetch supplier relations from E-Boekhouden and update supplier names with actual names"""
    try:
        response = []
        response.append("=== FETCHING AND UPDATING SUPPLIER NAMES ===")
        
        # Get E-Boekhouden API settings
        settings = frappe.get_single("E-Boekhouden Settings")
        
        # Import API class
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        api = EBoekhoudenAPI(settings)
        
        # Fetch all relations (suppliers and customers)
        response.append("Fetching relations from E-Boekhouden API...")
        relations_result = api.get_relations()
        
        if not relations_result["success"]:
            return f"Error fetching relations: {relations_result.get('error', 'Unknown error')}"
        
        # Parse relations data
        relations_data = json.loads(relations_result["data"])
        all_relations = relations_data.get("items", [])
        
        response.append(f"Found {len(all_relations)} total relations in E-Boekhouden")
        
        # Filter for suppliers only
        suppliers = [rel for rel in all_relations if rel.get("Soort") == "Leverancier"]
        response.append(f"Found {len(suppliers)} suppliers in E-Boekhouden")
        
        # Get all existing suppliers with E-Boekhouden relation codes
        existing_suppliers = frappe.db.sql("""
            SELECT name, supplier_name, eboekhouden_relation_code, supplier_type
            FROM `tabSupplier`
            WHERE eboekhouden_relation_code IS NOT NULL 
            AND eboekhouden_relation_code != ''
        """, as_dict=True)
        
        response.append(f"Found {len(existing_suppliers)} existing suppliers with E-Boekhouden codes")
        
        # Create mapping of relation codes to relation data
        relation_map = {}
        for rel in suppliers:
            rel_id = str(rel.get("ID", ""))
            if rel_id:
                relation_map[rel_id] = rel
        
        # Update existing suppliers
        updated_count = 0
        errors = []
        
        for supplier in existing_suppliers:
            try:
                relation_code = supplier.eboekhouden_relation_code
                
                if relation_code in relation_map:
                    relation_data = relation_map[relation_code]
                    
                    # Get the actual name from E-Boekhouden
                    eb_name = relation_data.get("Naam", "").strip()
                    eb_company = relation_data.get("Bedrijf", "").strip()
                    eb_contact = relation_data.get("Contactpersoon", "").strip()
                    eb_type = relation_data.get("Soort", "").strip()
                    
                    # Determine best name to use
                    new_name = eb_company or eb_contact or eb_name
                    
                    if not new_name:
                        response.append(f"  ⚠️  No usable name for supplier {supplier.name} (relation {relation_code})")
                        continue
                    
                    # Determine supplier type based on Soort and available data
                    # In E-Boekhouden, if there's a company name, it's usually business
                    if eb_company:
                        new_supplier_type = "Company"
                    elif eb_contact and not eb_company:
                        new_supplier_type = "Individual"
                    else:
                        # Default based on existing logic
                        new_supplier_type = "Company"
                    
                    # Check if we need to update
                    needs_update = False
                    updates = {}
                    
                    if supplier.supplier_name != new_name:
                        updates["supplier_name"] = new_name
                        needs_update = True
                    
                    if supplier.supplier_type != new_supplier_type:
                        updates["supplier_type"] = new_supplier_type
                        needs_update = True
                    
                    if needs_update:
                        # Check if new name conflicts with existing supplier
                        existing_with_name = frappe.db.get_value("Supplier", 
                            {"supplier_name": new_name, "name": ["!=", supplier.name]}, "name")
                        
                        if existing_with_name:
                            # Add suffix to make unique
                            new_name = f"{new_name} ({relation_code})"
                            updates["supplier_name"] = new_name
                        
                        # Update the supplier
                        frappe.db.set_value("Supplier", supplier.name, updates)
                        
                        updated_count += 1
                        response.append(f"  ✅ Updated: {supplier.supplier_name} → {new_name} ({new_supplier_type})")
                    else:
                        response.append(f"  ✓ No change needed: {supplier.supplier_name}")
                
                else:
                    response.append(f"  ❌ No relation data found for supplier {supplier.name} (code: {relation_code})")
                    
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
        response.append(f"Errors: {len(errors)}")
        
        if errors:
            response.append(f"\nErrors encountered:")
            for error in errors:
                response.append(f"  - {error}")
        
        return "\n".join(response)
        
    except Exception as e:
        return f"Error: {e}\n{frappe.get_traceback()}"


@frappe.whitelist()
def create_suppliers_from_relations():
    """Create suppliers for all E-Boekhouden relations that don't exist yet"""
    try:
        response = []
        response.append("=== CREATING SUPPLIERS FROM E-BOEKHOUDEN RELATIONS ===")
        
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
        
        # Filter for suppliers only
        suppliers = [rel for rel in all_relations if rel.get("Soort") == "Leverancier"]
        response.append(f"Found {len(suppliers)} suppliers in E-Boekhouden")
        
        # Get existing relation codes
        existing_codes = set(frappe.db.sql_list("""
            SELECT eboekhouden_relation_code 
            FROM `tabSupplier` 
            WHERE eboekhouden_relation_code IS NOT NULL 
            AND eboekhouden_relation_code != ''
        """))
        
        response.append(f"Found {len(existing_codes)} existing suppliers with relation codes")
        
        # Create suppliers for missing relations
        created_count = 0
        errors = []
        
        for rel in suppliers:
            try:
                rel_id = str(rel.get("ID", ""))
                
                if not rel_id or rel_id in existing_codes:
                    continue  # Skip if no ID or already exists
                
                # Get supplier data
                eb_name = rel.get("Naam", "").strip()
                eb_company = rel.get("Bedrijf", "").strip()
                eb_contact = rel.get("Contactpersoon", "").strip()
                eb_email = rel.get("Email", "").strip()
                eb_phone = rel.get("Telefoon", "").strip()
                eb_address = rel.get("Adres", "").strip()
                eb_postal_code = rel.get("Postcode", "").strip()
                eb_city = rel.get("Plaats", "").strip()
                eb_country = rel.get("Land", "").strip()
                eb_vat = rel.get("BTWNummer", "").strip()
                
                # Determine supplier name
                supplier_name = eb_company or eb_contact or eb_name
                
                if not supplier_name:
                    supplier_name = f"Supplier {rel_id}"
                
                # Determine supplier type
                supplier_type = "Company" if eb_company else "Individual"
                
                # Check for name conflicts
                name_counter = 1
                original_name = supplier_name
                while frappe.db.exists("Supplier", {"supplier_name": supplier_name}):
                    supplier_name = f"{original_name} ({name_counter})"
                    name_counter += 1
                
                # Create supplier
                supplier = frappe.new_doc("Supplier")
                supplier.supplier_name = supplier_name
                supplier.supplier_type = supplier_type
                supplier.supplier_group = "All Supplier Groups"
                supplier.eboekhouden_relation_code = rel_id
                
                if eb_vat:
                    supplier.tax_id = eb_vat
                
                supplier.insert(ignore_permissions=True)
                
                # Create contact if we have contact details
                if eb_contact or eb_email or eb_phone:
                    contact = frappe.new_doc("Contact")
                    contact.first_name = eb_contact or supplier_name
                    
                    if eb_email:
                        contact.append("email_ids", {
                            "email_id": eb_email,
                            "is_primary": 1
                        })
                    
                    if eb_phone:
                        contact.append("phone_nos", {
                            "phone": eb_phone,
                            "is_primary_phone": 1
                        })
                    
                    contact.append("links", {
                        "link_doctype": "Supplier",
                        "link_name": supplier.name
                    })
                    
                    contact.insert(ignore_permissions=True)
                
                # Create address if we have address details
                if eb_address or eb_city or eb_postal_code:
                    address = frappe.new_doc("Address")
                    address.address_title = supplier_name
                    address.address_line1 = eb_address
                    address.city = eb_city
                    address.pincode = eb_postal_code
                    address.country = eb_country or "Netherlands"
                    
                    address.append("links", {
                        "link_doctype": "Supplier",
                        "link_name": supplier.name
                    })
                    
                    address.insert(ignore_permissions=True)
                
                created_count += 1
                response.append(f"  ✅ Created: {supplier_name} ({supplier_type}) - ID: {rel_id}")
                
            except Exception as e:
                error_msg = f"Error creating supplier for relation {rel_id}: {str(e)}"
                errors.append(error_msg)
                response.append(f"  ❌ {error_msg}")
        
        # Commit changes
        frappe.db.commit()
        
        # Summary
        response.append(f"\n=== SUMMARY ===")
        response.append(f"Total E-Boekhouden suppliers: {len(suppliers)}")
        response.append(f"Already existing: {len(existing_codes)}")
        response.append(f"New suppliers created: {created_count}")
        response.append(f"Errors: {len(errors)}")
        
        if errors:
            response.append(f"\nErrors encountered:")
            for error in errors:
                response.append(f"  - {error}")
        
        return "\n".join(response)
        
    except Exception as e:
        return f"Error: {e}\n{frappe.get_traceback()}"


@frappe.whitelist()
def analyze_current_supplier_names():
    """Analyze current supplier names and E-Boekhouden relation data"""
    try:
        response = []
        response.append("=== ANALYZING CURRENT SUPPLIER NAMES ===")
        
        # Get current suppliers with E-Boekhouden codes
        suppliers = frappe.db.sql("""
            SELECT name, supplier_name, supplier_type, eboekhouden_relation_code
            FROM `tabSupplier`
            WHERE eboekhouden_relation_code IS NOT NULL 
            AND eboekhouden_relation_code != ''
            ORDER BY supplier_name
        """, as_dict=True)
        
        response.append(f"Found {len(suppliers)} suppliers with E-Boekhouden relation codes:")
        
        # Categorize suppliers by naming pattern
        numbered_names = []
        meaningful_names = []
        
        for supplier in suppliers:
            name = supplier.supplier_name
            code = supplier.eboekhouden_relation_code
            
            # Check if name is just a number or "Supplier X"
            if (name.isdigit() or 
                name.startswith("Supplier ") or 
                name == code):
                numbered_names.append(supplier)
            else:
                meaningful_names.append(supplier)
        
        response.append(f"\n=== NAMING ANALYSIS ===")
        response.append(f"Suppliers with numbered/generic names: {len(numbered_names)}")
        response.append(f"Suppliers with meaningful names: {len(meaningful_names)}")
        
        if numbered_names:
            response.append(f"\nSuppliers needing name updates:")
            for supplier in numbered_names[:10]:  # Show first 10
                response.append(f"  - {supplier.name}: '{supplier.supplier_name}' (code: {supplier.eboekhouden_relation_code})")
            
            if len(numbered_names) > 10:
                response.append(f"  ... and {len(numbered_names) - 10} more")
        
        if meaningful_names:
            response.append(f"\nSuppliers with good names (sample):")
            for supplier in meaningful_names[:5]:  # Show first 5
                response.append(f"  - {supplier.name}: '{supplier.supplier_name}' ({supplier.supplier_type})")
        
        return "\n".join(response)
        
    except Exception as e:
        return f"Error: {e}\n{frappe.get_traceback()}"