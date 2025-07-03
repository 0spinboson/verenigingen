"""
Monkey patch for E-Boekhouden migration to fix supplier creation issues
This ensures suppliers are created with consistent naming
"""

import frappe
from frappe import _

# Store original functions
_original_get_or_create_supplier = None
_original_process_supplier_payments = None
_original_process_purchase_invoices = None

def patch_eboekhouden_migration():
    """Apply patches to fix supplier creation issues in E-Boekhouden migration"""
    
    # Import the module
    from verenigingen.utils import eboekhouden_soap_migration as migration_module
    
    # Store original functions
    global _original_get_or_create_supplier, _original_process_supplier_payments, _original_process_purchase_invoices
    _original_get_or_create_supplier = migration_module.get_or_create_supplier
    _original_process_supplier_payments = migration_module.process_supplier_payments
    _original_process_purchase_invoices = migration_module.process_purchase_invoices
    
    # Enhanced get_or_create_supplier that ensures suppliers exist with correct naming
    def enhanced_get_or_create_supplier(code, description="", relation_data=None):
        """Enhanced version that ensures suppliers exist with the code as the name"""
        if not code:
            return _original_get_or_create_supplier(code, description, relation_data)
        
        # First check if supplier exists with code as name (for compatibility)
        if frappe.db.exists("Supplier", code):
            return code
        
        # Then use original logic
        supplier = _original_get_or_create_supplier(code, description, relation_data)
        
        # Also create a supplier with just the code as name for backward compatibility
        if supplier and supplier != code:
            try:
                # Create an alias supplier with just the code
                alias_supplier = frappe.new_doc("Supplier")
                alias_supplier.supplier_name = code
                alias_supplier.eboekhouden_relation_code = code
                alias_supplier.supplier_group = frappe.db.get_value("Supplier Group", 
                    {"is_group": 0}, "name") or "All Supplier Groups"
                alias_supplier.insert(ignore_permissions=True)
                frappe.db.commit()
            except:
                # Ignore if already exists or other error
                pass
        
        return supplier
    
    # Enhanced process_purchase_invoices that ensures suppliers exist
    def enhanced_process_purchase_invoices(mutations, company, cost_center, migration_doc, relation_data_map=None):
        """Enhanced version that pre-creates suppliers"""
        
        # Pre-create all suppliers to avoid issues later
        for mut in mutations:
            supplier_code = mut.get("RelatieCode")
            if supplier_code:
                # Ensure supplier exists with both naming conventions
                relation_data = relation_data_map.get(supplier_code) if relation_data_map else None
                enhanced_get_or_create_supplier(supplier_code, mut.get("Omschrijving", ""), relation_data)
        
        # Call original function
        return _original_process_purchase_invoices(mutations, company, cost_center, migration_doc, relation_data_map)
    
    # Enhanced process_supplier_payments that handles missing suppliers
    def enhanced_process_supplier_payments(mutations, company, cost_center, migration_doc, relation_data_map=None):
        """Enhanced version that ensures suppliers exist before processing payments"""
        
        # Import the migration fixes
        from .eboekhouden_migration_fixes import ensure_supplier_exists
        
        # Pre-process all mutations to ensure suppliers exist
        for mut in mutations:
            supplier_code = mut.get("RelatieCode")
            if supplier_code:
                relation_data = relation_data_map.get(supplier_code) if relation_data_map else None
                ensure_supplier_exists(supplier_code, relation_data)
        
        # Call original function with enhanced error handling
        try:
            return _original_process_supplier_payments(mutations, company, cost_center, migration_doc, relation_data_map)
        except frappe.exceptions.LinkValidationError as e:
            if "Could not find Party: Supplier" in str(e):
                # Extract supplier code from error message
                import re
                match = re.search(r'Supplier (\w+)', str(e))
                if match:
                    supplier_code = match.group(1)
                    # Try to create the supplier
                    ensure_supplier_exists(supplier_code)
                    # Retry the operation
                    return _original_process_supplier_payments(mutations, company, cost_center, migration_doc, relation_data_map)
            raise
    
    # Apply patches
    migration_module.get_or_create_supplier = enhanced_get_or_create_supplier
    migration_module.process_supplier_payments = enhanced_process_supplier_payments
    migration_module.process_purchase_invoices = enhanced_process_purchase_invoices
    
    # Also patch the migrate_using_soap to fix cost centers at start
    original_migrate_using_soap = migration_module.migrate_using_soap
    
    def enhanced_migrate_using_soap(migration_doc, settings, use_account_mappings=True):
        """Enhanced migration that fixes known issues before processing"""
        
        # Import and run pre-migration fixes
        from .eboekhouden_migration_fixes import enhance_migration_process
        enhance_migration_process()
        
        # Call original function
        return original_migrate_using_soap(migration_doc, settings, use_account_mappings)
    
    migration_module.migrate_using_soap = enhanced_migrate_using_soap

def unpatch_eboekhouden_migration():
    """Remove patches and restore original functions"""
    from verenigingen.utils import eboekhouden_soap_migration as migration_module
    
    global _original_get_or_create_supplier, _original_process_supplier_payments, _original_process_purchase_invoices
    
    if _original_get_or_create_supplier:
        migration_module.get_or_create_supplier = _original_get_or_create_supplier
    if _original_process_supplier_payments:
        migration_module.process_supplier_payments = _original_process_supplier_payments
    if _original_process_purchase_invoices:
        migration_module.process_purchase_invoices = _original_process_purchase_invoices