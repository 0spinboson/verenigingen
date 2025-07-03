import frappe

@frappe.whitelist()
def create_missing_item_group_and_items():
    """Create missing item group and retry creating items"""
    try:
        response = []
        response.append("=== FIXING MISSING ITEMS ===")
        
        # Create Other item group
        if not frappe.db.exists("Item Group", "Other"):
            group = frappe.new_doc("Item Group")
            group.item_group_name = "Other"
            group.parent_item_group = "All Item Groups"
            group.insert(ignore_permissions=True)
            response.append("Created 'Other' item group")
        else:
            response.append("'Other' item group already exists")
        
        # Get cached mappings
        mappings = frappe.cache().get_value("smart_item_mappings")
        if not mappings:
            response.append("No mappings found. Please run create_smart_item_mapping_system first.")
            return "\n".join(response)
        
        # Find items that weren't created (those with "Other" group)
        missing_items = [m for m in mappings if m['item_group'] == 'Other']
        response.append(f"Found {len(missing_items)} items to create")
        
        # Create missing items
        created_count = 0
        errors = []
        
        for mapping in missing_items:
            try:
                item_code = mapping['item_code']
                
                # Check if item already exists
                if frappe.db.exists("Item", item_code):
                    continue
                
                # Create new item
                item = frappe.new_doc("Item")
                item.item_code = item_code
                item.item_name = mapping['item_name']
                item.item_group = mapping['item_group']
                item.stock_uom = "Nos"
                item.is_stock_item = 0
                item.is_sales_item = mapping['is_sales_item']
                item.is_purchase_item = mapping['is_purchase_item']
                
                # Add custom field for E-Boekhouden account code
                item.custom_eboekhouden_account_code = mapping['account_code']
                
                item.insert(ignore_permissions=True)
                created_count += 1
                
            except Exception as e:
                error_msg = f"Error creating item for account {mapping['account_code']}: {str(e)}"
                errors.append(error_msg)
                continue
        
        frappe.db.commit()
        
        response.append(f"Additional items created: {created_count}")
        response.append(f"Errors: {len(errors)}")
        
        if errors:
            for error in errors[:3]:
                response.append(f"  - {error}")
        
        # Final count
        total_items = frappe.db.count("Item", {"item_code": ["like", "EB-%"]})
        response.append(f"\nTotal E-Boekhouden items in system: {total_items}")
        
        return "\n".join(response)
        
    except Exception as e:
        return f"Error: {e}\n{frappe.get_traceback()}"