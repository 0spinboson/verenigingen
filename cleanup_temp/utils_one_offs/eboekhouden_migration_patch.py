"""
Patch for E-Boekhouden Migration to use enhanced journal entry creation
This module patches the create_journal_entry method to handle parties properly
"""

import frappe
from frappe import _

def patch_create_journal_entry(self, transaction_data):
    """
    Patched version of create_journal_entry that uses enhanced party handling
    """
    try:
        # Import the enhanced journal entry creation function
        from verenigingen.utils.eboekhouden_journal_entry_fix import create_journal_entry_enhanced
        
        # Map e-Boekhouden transaction to ERPNext journal entry
        transaction_date = transaction_data.get('date', '')
        ledger_id = transaction_data.get('ledgerId', '')
        amount = float(transaction_data.get('amount', 0) or 0)
        transaction_type = transaction_data.get('type', 0)
        invoice_number = transaction_data.get('invoiceNumber', '').strip()
        entry_number = transaction_data.get('entryNumber', '').strip()
        
        # Create description from available fields
        description_parts = []
        if invoice_number:
            description_parts.append(f"Invoice: {invoice_number}")
        if entry_number:
            description_parts.append(f"Entry: {entry_number}")
        if ledger_id:
            description_parts.append(f"Ledger: {ledger_id}")
        
        description = " | ".join(description_parts) if description_parts else "Imported transaction"
        
        # Handle missing date
        if not transaction_date:
            self.log_error(f"Invalid transaction data: missing date for {description}")
            return False
        
        # Skip zero-amount transactions
        if amount == 0:
            return False
        
        # Convert ledgerId to account code
        account_code = self.get_account_code_from_ledger_id(ledger_id)
        if not account_code:
            self.log_error(f"Could not find account code for ledger ID {ledger_id}")
            return False
        
        # Determine debit/credit based on type and amount
        if transaction_type == 0:  # Assuming 0 = debit
            debit_amount = amount
            credit_amount = 0
        else:  # 1 = credit
            debit_amount = 0  
            credit_amount = amount
        
        # Find the account in ERPNext
        account_details = frappe.db.get_value("Account", {"account_number": account_code}, 
                                             ["name", "account_type"], as_dict=True)
        if not account_details:
            self.log_error(f"Account {account_code} not found in ERPNext")
            return False
        
        account = account_details.name
        account_type = account_details.account_type
        
        # Skip stock accounts
        if account_type == "Stock":
            frappe.logger().info(f"Skipping stock account {account_code} - must be updated via stock transactions")
            if not hasattr(self, 'skipped_stock_transactions'):
                self.skipped_stock_transactions = 0
            self.skipped_stock_transactions += 1
            return False
        
        # Get default settings
        settings = frappe.get_single("E-Boekhouden Settings")
        company = settings.default_company
        
        if not company:
            self.log_error("No default company set in E-Boekhouden Settings")
            return False
        
        # Get cost center
        cost_center = get_default_cost_center(self, company)
        
        # Prepare transaction data for enhanced function
        enhanced_data = {
            "number": entry_number,  # For duplicate prevention
            "account_code": account_code,
            "description": description,
            "date": transaction_date,
            "debit": debit_amount,
            "credit": credit_amount,
            "relation_code": transaction_data.get('relationCode')  # For party lookup
        }
        
        # Use the enhanced function
        result = create_journal_entry_enhanced(enhanced_data, company, cost_center)
        
        if result["success"]:
            if result.get("reason") == "duplicate":
                frappe.logger().info(f"Skipped duplicate: {result.get('message')}")
                return False
            else:
                frappe.logger().info(f"Created journal entry: {result.get('journal_entry')}")
                return True
        else:
            # Log error but don't stop the migration
            reason = result.get("reason", "unknown")
            message = result.get("message", "Unknown error")
            
            if reason == "account_not_found":
                frappe.logger().warning(f"Account not found: {message}")
            elif reason == "duplicate":
                frappe.logger().info(f"Duplicate skipped: {message}")
            else:
                self.log_error(f"Journal entry creation failed: {message}")
            
            return False
            
    except Exception as e:
        self.log_error(f"Failed to create journal entry: {str(e)}")
        return False

def get_default_cost_center(self, company):
    """Get default cost center for the company"""
    try:
        # First try from settings
        settings = frappe.get_single("E-Boekhouden Settings")
        if settings.default_cost_center:
            return settings.default_cost_center
        
        # Then find main cost center
        main_cc = frappe.db.get_value("Cost Center", {
            "company": company,
            "is_group": 1,
            "parent_cost_center": ["in", ["", None]]
        }, "name")
        
        if main_cc:
            return main_cc
        
        # Try company abbreviation pattern
        abbr = frappe.db.get_value("Company", company, "abbr")
        if abbr:
            main_cc = frappe.db.get_value("Cost Center", f"{company} - {abbr}", "name")
            if main_cc:
                return main_cc
        
        # Last resort - any cost center for the company
        any_cc = frappe.db.get_value("Cost Center", {"company": company}, "name")
        return any_cc
        
    except Exception as e:
        self.log_error(f"Failed to get default cost center: {str(e)}")
        return None

@frappe.whitelist()
def apply_migration_patch(migration_name):
    """
    Apply the patch to an existing migration document
    """
    try:
        migration = frappe.get_doc("E-Boekhouden Migration", migration_name)
        
        # Monkey patch the method
        migration.create_journal_entry = lambda transaction_data: patch_create_journal_entry(migration, transaction_data)
        
        # Also add the get_default_cost_center method
        migration.get_default_cost_center = lambda company: get_default_cost_center(migration, company)
        
        return {
            "success": True,
            "message": "Migration patched successfully"
        }
        
    except Exception as e:
        frappe.log_error(f"Failed to apply migration patch: {str(e)}", "E-Boekhouden Migration Patch")
        return {
            "success": False,
            "error": str(e)
        }