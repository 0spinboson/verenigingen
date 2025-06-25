# Copyright (c) 2025, R.S.P. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, today, getdate, add_days
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import time


class EBoekhoudenMigration(Document):
    def validate(self):
        """Validate migration settings"""
        if self.migrate_transactions and not (self.date_from and self.date_to):
            frappe.throw("Date range is required when migrating transactions")
        
        if self.date_from and self.date_to and getdate(self.date_from) > getdate(self.date_to):
            frappe.throw("Date From cannot be after Date To")
    
    def on_submit(self):
        """Start migration process when document is submitted"""
        if self.migration_status == "Draft":
            self.start_migration()
    
    def start_migration(self):
        """Start the migration process"""
        try:
            self.migration_status = "In Progress"
            self.start_time = now_datetime()
            self.current_operation = "Initializing migration..."
            self.progress_percentage = 0
            self.save()
            
            # Get settings
            settings = frappe.get_single("E-Boekhouden Settings")
            if not settings.username:
                frappe.throw("E-Boekhouden Settings not configured. Please configure API settings first.")
            
            # Initialize counters
            self.total_records = 0
            self.imported_records = 0
            self.failed_records = 0
            
            migration_log = []
            
            # Phase 1: Chart of Accounts
            if self.migrate_accounts:
                self.current_operation = "Migrating Chart of Accounts..."
                self.progress_percentage = 10
                self.save()
                
                result = self.migrate_chart_of_accounts(settings)
                migration_log.append(f"Chart of Accounts: {result}")
            
            # Phase 2: Customers
            if self.migrate_customers:
                self.current_operation = "Migrating Customers..."
                self.progress_percentage = 30
                self.save()
                
                result = self.migrate_customers(settings)
                migration_log.append(f"Customers: {result}")
            
            # Phase 3: Suppliers
            if self.migrate_suppliers:
                self.current_operation = "Migrating Suppliers..."
                self.progress_percentage = 50
                self.save()
                
                result = self.migrate_suppliers(settings)
                migration_log.append(f"Suppliers: {result}")
            
            # Phase 4: Transactions
            if self.migrate_transactions:
                self.current_operation = "Migrating Transactions..."
                self.progress_percentage = 70
                self.save()
                
                result = self.migrate_transactions_data(settings)
                migration_log.append(f"Transactions: {result}")
            
            # Completion
            self.migration_status = "Completed"
            self.current_operation = "Migration completed successfully"
            self.progress_percentage = 100
            self.end_time = now_datetime()
            self.migration_summary = "\n".join(migration_log)
            self.save()
            
        except Exception as e:
            self.migration_status = "Failed"
            self.current_operation = f"Migration failed: {str(e)}"
            self.end_time = now_datetime()
            self.error_log = frappe.get_traceback()
            self.save()
            frappe.log_error(f"E-Boekhouden migration failed: {str(e)}", "E-Boekhouden Migration")
            raise
    
    def migrate_chart_of_accounts(self, settings):
        """Migrate Chart of Accounts from e-Boekhouden"""
        try:
            # Get Chart of Accounts data
            result = settings.get_api_data("Grootboekrekeningen")
            
            if not result["success"]:
                return f"Failed to fetch Chart of Accounts: {result['error']}"
            
            # Parse XML response
            accounts_data = self.parse_grootboekrekeningen_xml(result["data"])
            
            if self.dry_run:
                return f"Dry Run: Found {len(accounts_data)} accounts to migrate"
            
            # Create accounts in ERPNext
            created_count = 0
            for account_data in accounts_data:
                try:
                    self.create_account(account_data)
                    created_count += 1
                    self.imported_records += 1
                except Exception as e:
                    self.failed_records += 1
                    frappe.log_error(f"Failed to create account {account_data.get('code', 'Unknown')}: {str(e)}")
            
            self.total_records += len(accounts_data)
            return f"Created {created_count} accounts ({len(accounts_data)} total)"
            
        except Exception as e:
            return f"Error migrating Chart of Accounts: {str(e)}"
    
    def migrate_customers(self, settings):
        """Migrate Customers from e-Boekhouden"""
        try:
            # Get Relations data with customer filter
            result = settings.get_api_data("Relaties", {"Type": "C"})  # C = Customer
            
            if not result["success"]:
                return f"Failed to fetch Customers: {result['error']}"
            
            # Parse XML response  
            customers_data = self.parse_relaties_xml(result["data"])
            
            if self.dry_run:
                return f"Dry Run: Found {len(customers_data)} customers to migrate"
            
            # Create customers in ERPNext
            created_count = 0
            for customer_data in customers_data:
                try:
                    self.create_customer(customer_data)
                    created_count += 1
                    self.imported_records += 1
                except Exception as e:
                    self.failed_records += 1
                    frappe.log_error(f"Failed to create customer {customer_data.get('code', 'Unknown')}: {str(e)}")
            
            self.total_records += len(customers_data)
            return f"Created {created_count} customers ({len(customers_data)} total)"
            
        except Exception as e:
            return f"Error migrating Customers: {str(e)}"
    
    def migrate_suppliers(self, settings):
        """Migrate Suppliers from e-Boekhouden"""
        try:
            # Get Relations data with supplier filter
            result = settings.get_api_data("Relaties", {"Type": "L"})  # L = Leverancier (Supplier)
            
            if not result["success"]:
                return f"Failed to fetch Suppliers: {result['error']}"
            
            # Parse XML response
            suppliers_data = self.parse_relaties_xml(result["data"])
            
            if self.dry_run:
                return f"Dry Run: Found {len(suppliers_data)} suppliers to migrate"
            
            # Create suppliers in ERPNext
            created_count = 0
            for supplier_data in suppliers_data:
                try:
                    self.create_supplier(supplier_data)
                    created_count += 1
                    self.imported_records += 1
                except Exception as e:
                    self.failed_records += 1
                    frappe.log_error(f"Failed to create supplier {supplier_data.get('code', 'Unknown')}: {str(e)}")
            
            self.total_records += len(suppliers_data)
            return f"Created {created_count} suppliers ({len(suppliers_data)} total)"
            
        except Exception as e:
            return f"Error migrating Suppliers: {str(e)}"
    
    def migrate_transactions_data(self, settings):
        """Migrate Transactions from e-Boekhouden"""
        try:
            # Process transactions in monthly batches to avoid large data loads
            current_date = getdate(self.date_from)
            end_date = getdate(self.date_to)
            total_created = 0
            
            while current_date <= end_date:
                # Calculate month end
                if current_date.month == 12:
                    month_end = current_date.replace(year=current_date.year + 1, month=1, day=1) - timedelta(days=1)
                else:
                    month_end = current_date.replace(month=current_date.month + 1, day=1) - timedelta(days=1)
                
                month_end = min(month_end, end_date)
                
                # Get transactions for this month
                result = settings.get_api_data("Mutaties", {
                    "OpenDat": current_date.strftime("%d-%m-%Y"),
                    "SluitDat": month_end.strftime("%d-%m-%Y")
                })
                
                if result["success"]:
                    transactions_data = self.parse_mutaties_xml(result["data"])
                    
                    if self.dry_run:
                        total_created += len(transactions_data)
                    else:
                        # Create journal entries
                        for transaction_data in transactions_data:
                            try:
                                self.create_journal_entry(transaction_data)
                                total_created += 1
                                self.imported_records += 1
                            except Exception as e:
                                self.failed_records += 1
                                frappe.log_error(f"Failed to create transaction: {str(e)}")
                
                # Move to next month
                if current_date.month == 12:
                    current_date = current_date.replace(year=current_date.year + 1, month=1, day=1)
                else:
                    current_date = current_date.replace(month=current_date.month + 1, day=1)
            
            if self.dry_run:
                return f"Dry Run: Found {total_created} transactions to migrate"
            else:
                return f"Created {total_created} journal entries"
                
        except Exception as e:
            return f"Error migrating Transactions: {str(e)}"
    
    def parse_grootboekrekeningen_xml(self, xml_data):
        """Parse Chart of Accounts XML response"""
        try:
            # This is a simplified parser - you'll need to adjust based on actual XML structure
            accounts = []
            
            # Basic parsing - adjust based on actual e-Boekhouden XML structure
            if "Grootboekrekening" in xml_data:
                # Parse the XML properly here
                # For now, return mock data structure
                pass
            
            return accounts
        except Exception as e:
            frappe.log_error(f"Error parsing Chart of Accounts XML: {str(e)}")
            return []
    
    def parse_relaties_xml(self, xml_data):
        """Parse Relations (Customers/Suppliers) XML response"""
        try:
            relations = []
            
            # Basic parsing - adjust based on actual e-Boekhouden XML structure
            if "Relatie" in xml_data:
                # Parse the XML properly here
                pass
            
            return relations
        except Exception as e:
            frappe.log_error(f"Error parsing Relations XML: {str(e)}")
            return []
    
    def parse_mutaties_xml(self, xml_data):
        """Parse Transactions (Mutaties) XML response"""
        try:
            transactions = []
            
            # Basic parsing - adjust based on actual e-Boekhouden XML structure
            if "Mutatie" in xml_data:
                # Parse the XML properly here
                pass
            
            return transactions
        except Exception as e:
            frappe.log_error(f"Error parsing Transactions XML: {str(e)}")
            return []
    
    def create_account(self, account_data):
        """Create Account in ERPNext"""
        # Implementation for creating accounts
        pass
    
    def create_customer(self, customer_data):
        """Create Customer in ERPNext"""
        # Implementation for creating customers
        pass
    
    def create_supplier(self, supplier_data):
        """Create Supplier in ERPNext"""
        # Implementation for creating suppliers
        pass
    
    def create_journal_entry(self, transaction_data):
        """Create Journal Entry in ERPNext"""
        # Implementation for creating journal entries
        pass


@frappe.whitelist()
def start_migration(migration_name):
    """API method to start migration process"""
    try:
        migration = frappe.get_doc("E-Boekhouden Migration", migration_name)
        if migration.migration_status != "Draft":
            return {"success": False, "error": "Migration must be in Draft status to start"}
        
        # Start migration in background
        frappe.enqueue(
            method="verenigingen.verenigingen.doctype.e_boekhouden_migration.e_boekhouden_migration.run_migration_background",
            queue="long",
            timeout=3600,
            migration_name=migration_name
        )
        
        return {"success": True, "message": "Migration started in background"}
        
    except Exception as e:
        frappe.log_error(f"Error starting migration: {str(e)}")
        return {"success": False, "error": str(e)}


def run_migration_background(migration_name):
    """Run migration in background"""
    try:
        migration = frappe.get_doc("E-Boekhouden Migration", migration_name)
        migration.start_migration()
    except Exception as e:
        frappe.log_error(f"Background migration failed: {str(e)}")
        migration = frappe.get_doc("E-Boekhouden Migration", migration_name)
        migration.migration_status = "Failed"
        migration.error_log = str(e)
        migration.save()