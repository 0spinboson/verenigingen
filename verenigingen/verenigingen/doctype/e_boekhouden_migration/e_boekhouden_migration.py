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
        # Debug logging
        frappe.logger().debug(f"Validating migration: {self.migration_name}, Status: {self.migration_status}")
        
        if getattr(self, 'migrate_transactions', 0) and not (self.date_from and self.date_to):
            frappe.throw("Date range is required when migrating transactions")
        
        if self.date_from and self.date_to and getdate(self.date_from) > getdate(self.date_to):
            frappe.throw("Date From cannot be after Date To")
    
    def on_submit(self):
        """Start migration process when document is submitted"""
        frappe.logger().debug(f"Migration submitted: {self.migration_name}, Status: {self.migration_status}")
        if self.migration_status == "Draft":
            self.start_migration()
    
    def start_migration(self):
        """Start the migration process"""
        try:
            self.db_set({
                "migration_status": "In Progress",
                "start_time": frappe.utils.now_datetime(),
                "current_operation": "Initializing migration...",
                "progress_percentage": 0
            })
            frappe.db.commit()
            
            # Get settings
            settings = frappe.get_single("E-Boekhouden Settings")
            if not settings.api_token:
                frappe.throw("E-Boekhouden Settings not configured. Please configure API token first.")
            
            # Initialize counters
            self.total_records = 0
            self.imported_records = 0
            self.failed_records = 0
            
            migration_log = []
            self.failed_record_details = []  # Track details of failed records
            
            # Phase 0: Full Initial Migration Cleanup
            if getattr(self, 'migration_type', '') == 'Full Initial Migration':
                self.db_set({
                    "current_operation": "Performing initial cleanup for full migration...",
                    "progress_percentage": 2
                })
                frappe.db.commit()
                
                try:
                    # Use the enhanced cleanup function
                    cleanup_result = debug_cleanup_all_imported_data(settings.default_company)
                    if cleanup_result["success"]:
                        cleanup_summary = f"Cleaned up existing data: {cleanup_result['results']}"
                        migration_log.append(f"Initial Cleanup: {cleanup_summary}")
                        self.log_error(f"Full migration cleanup completed: {cleanup_summary}", "cleanup", cleanup_result["results"])
                    else:
                        # Log error but continue - don't fail migration for cleanup issues
                        error_msg = f"Initial cleanup warning: {cleanup_result.get('error', 'Unknown error')}"
                        migration_log.append(f"Initial Cleanup: {error_msg}")
                        self.log_error(error_msg, "cleanup_warning")
                except Exception as e:
                    # Log error but continue
                    error_msg = f"Initial cleanup failed: {str(e)}"
                    migration_log.append(f"Initial Cleanup: {error_msg}")
                    self.log_error(error_msg, "cleanup_error")
            
            # Phase 1: Chart of Accounts
            if getattr(self, 'migrate_accounts', 0):
                self.db_set({
                    "current_operation": "Migrating Chart of Accounts...",
                    "progress_percentage": 10
                })
                frappe.db.commit()
                
                # Use getattr to avoid field/method name conflict
                migrate_method = getattr(self.__class__, 'migrate_chart_of_accounts')
                result = migrate_method(self, settings)
                migration_log.append(f"Chart of Accounts: {result}")
            
            # Phase 2: Cost Centers
            if getattr(self, 'migrate_cost_centers', 0):
                self.db_set({
                    "current_operation": "Migrating Cost Centers...",
                    "progress_percentage": 20
                })
                frappe.db.commit()
                
                # Use getattr to avoid field/method name conflict
                migrate_method = getattr(self.__class__, 'migrate_cost_centers')
                result = migrate_method(self, settings)
                migration_log.append(f"Cost Centers: {result}")
            
            # Phase 3: Customers
            if getattr(self, 'migrate_customers', 0):
                self.db_set({
                    "current_operation": "Migrating Customers...",
                    "progress_percentage": 40
                })
                frappe.db.commit()
                
                # Use getattr to avoid field/method name conflict
                migrate_method = getattr(self.__class__, 'migrate_customers')
                result = migrate_method(self, settings)
                migration_log.append(f"Customers: {result}")
            
            # Phase 4: Suppliers
            if getattr(self, 'migrate_suppliers', 0):
                self.db_set({
                    "current_operation": "Migrating Suppliers...",
                    "progress_percentage": 60
                })
                frappe.db.commit()
                
                # Use getattr to avoid field/method name conflict
                migrate_method = getattr(self.__class__, 'migrate_suppliers')
                result = migrate_method(self, settings)
                migration_log.append(f"Suppliers: {result}")
            
            # Phase 5: Transactions
            if getattr(self, 'migrate_transactions', 0):
                self.db_set({
                    "current_operation": "Migrating Transactions...",
                    "progress_percentage": 80
                })
                frappe.db.commit()
                
                # Use getattr to avoid field/method name conflict
                migrate_method = getattr(self.__class__, 'migrate_transactions_data')
                result = migrate_method(self, settings)
                migration_log.append(f"Transactions: {result}")
            
            # Phase 6: Stock Transactions
            if getattr(self, 'migrate_stock_transactions', 0):
                self.db_set({
                    "current_operation": "Migrating Stock Transactions...",
                    "progress_percentage": 90
                })
                frappe.db.commit()
                
                # Use getattr to avoid field/method name conflict
                migrate_method = getattr(self.__class__, 'migrate_stock_transactions_data')
                result = migrate_method(self, settings)
                migration_log.append(f"Stock Transactions: {result}")
            
            # Completion
            self.db_set({
                "migration_status": "Completed",
                "current_operation": "Migration completed successfully",
                "progress_percentage": 100,
                "end_time": frappe.utils.now_datetime(),
                "migration_summary": "\n".join(migration_log)
            })
            
            # Save failed records to file
            if self.failed_record_details:
                self.save_failed_records_log()
                
            frappe.db.commit()
            
        except Exception as e:
            self.db_set({
                "migration_status": "Failed",
                "current_operation": f"Migration failed: {str(e)}",
                "end_time": frappe.utils.now_datetime(),
                "error_log": frappe.get_traceback()
            })
            frappe.db.commit()
            frappe.log_error(f"E-Boekhouden migration failed: {str(e)}", "E-Boekhouden Migration")
            raise
    
    def clear_existing_accounts(self, settings):
        """Clear all existing imported accounts before importing new ones"""
        try:
            company = settings.default_company
            if not company:
                return {"success": False, "error": "No default company set"}
            
            # Get all accounts for the company that have account numbers (imported accounts)
            existing_accounts = frappe.get_all("Account", 
                filters={
                    "company": company,
                    "account_number": ["!=", ""]
                },
                fields=["name", "account_name", "account_number"],
                order_by="lft desc"  # Delete child accounts first
            )
            
            if not existing_accounts:
                return {"success": True, "message": "No existing imported accounts to clear", "deleted_count": 0}
            
            if self.dry_run:
                return {
                    "success": True, 
                    "message": f"Dry Run: Would delete {len(existing_accounts)} imported accounts",
                    "deleted_count": 0
                }
            
            # Delete accounts (delete in reverse tree order to avoid constraint issues)
            deleted_count = 0
            errors = []
            
            for account in existing_accounts:
                try:
                    # Check if account has any GL entries
                    has_gl_entries = frappe.db.exists("GL Entry", {"account": account.name})
                    if has_gl_entries:
                        # Force delete even with GL entries since this is a nuke operation
                        frappe.db.delete("GL Entry", {"account": account.name})
                    
                    frappe.delete_doc("Account", account.name, force=True)
                    deleted_count += 1
                    frappe.logger().info(f"Deleted account: {account.account_number} - {account.account_name}")
                    
                except Exception as e:
                    error_msg = f"Failed to delete account {account.account_number} ({account.name}): {str(e)}"
                    errors.append(error_msg)
                    self.log_error(error_msg, "account_deletion", account)
            
            frappe.db.commit()
            
            result_msg = f"Cleared {deleted_count} existing accounts"
            if errors:
                result_msg += f", {len(errors)} errors"
            
            return {
                "success": True, 
                "message": result_msg,
                "deleted_count": deleted_count,
                "errors": errors
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    def migrate_chart_of_accounts(self, settings):
        """Migrate Chart of Accounts from e-Boekhouden"""
        try:
            # Clear existing accounts if requested
            if getattr(self, 'clear_existing_accounts', 0):
                self.db_set({
                    "current_operation": "Clearing existing accounts...",
                    "progress_percentage": 5
                })
                frappe.db.commit()
                
                clear_result = self.clear_existing_accounts(settings)
                if not clear_result["success"]:
                    return f"Failed to clear existing accounts: {clear_result['error']}"
                else:
                    frappe.logger().info(f"Cleared accounts: {clear_result['message']}")
            
            from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
            
            # Get Chart of Accounts data using new API
            api = EBoekhoudenAPI(settings)
            result = api.get_chart_of_accounts()
            
            if not result["success"]:
                return f"Failed to fetch Chart of Accounts: {result['error']}"
            
            # Parse JSON response
            import json
            data = json.loads(result["data"])
            accounts_data = data.get("items", [])
            
            if self.dry_run:
                dry_run_msg = f"Dry Run: Found {len(accounts_data)} accounts to migrate"
                if getattr(self, 'clear_existing_accounts', 0):
                    clear_result = self.clear_existing_accounts(settings)
                    dry_run_msg += f"\n{clear_result['message']}"
                return dry_run_msg
            
            # Analyze account hierarchy to determine which should be groups
            from verenigingen.utils.eboekhouden_account_group_fix import analyze_account_hierarchy
            group_accounts = analyze_account_hierarchy(accounts_data)
            frappe.logger().info(f"Identified {len(group_accounts)} accounts that should be groups")
            
            # Store group accounts for use in create_account
            self._group_accounts = group_accounts
            
            # Create accounts in ERPNext
            created_count = 0
            skipped_count = 0
            
            for account_data in accounts_data:
                try:
                    if self.create_account(account_data):
                        created_count += 1
                        self.imported_records += 1
                    else:
                        skipped_count += 1
                except Exception as e:
                    self.failed_records += 1
                    self.log_error(f"Failed to create account {account_data.get('code', 'Unknown')}: {str(e)}", "account", account_data)
            
            self.total_records += len(accounts_data)
            return f"Created {created_count} accounts, skipped {skipped_count} ({len(accounts_data)} total)"
            
        except Exception as e:
            return f"Error migrating Chart of Accounts: {str(e)}"
    
    def migrate_cost_centers(self, settings):
        """Migrate Cost Centers from e-Boekhouden with proper hierarchy"""
        try:
            # Use the fixed cost center migration
            from verenigingen.utils.eboekhouden_cost_center_fix import (
                migrate_cost_centers_with_hierarchy, 
                cleanup_cost_centers
            )
            
            result = migrate_cost_centers_with_hierarchy(settings)
            
            if result["success"]:
                self.imported_records += result["created"]
                self.total_records += result["total"]
                
                # Run cleanup to fix any orphaned cost centers
                if settings.default_company:
                    cleanup_result = cleanup_cost_centers(settings.default_company)
                    if cleanup_result["success"] and cleanup_result["fixed"] > 0:
                        self.log_error(f"Fixed {cleanup_result['fixed']} orphaned cost centers")
                
                if result.get("errors"):
                    for error in result["errors"][:5]:  # Log first 5 errors
                        self.log_error(f"Cost center error: {error}")
                
                return result["message"]
            else:
                return f"Error: {result.get('error', 'Unknown error')}"
            
            # Old implementation below for reference
            # from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
            # 
            # # Get Cost Centers data using new API
            # api = EBoekhoudenAPI(settings)
            # result = api.get_cost_centers()
            # 
            # if not result["success"]:
            #     return f"Failed to fetch Cost Centers: {result['error']}"
            # 
            # # Parse JSON response
            # import json
            # data = json.loads(result["data"])
            # cost_centers_data = data.get("items", [])
            # 
            # if self.dry_run:
            #     return f"Dry Run: Found {len(cost_centers_data)} cost centers to migrate"
            # 
            # # Create cost centers in ERPNext
            # created_count = 0
            # skipped_count = 0
        except Exception as e:
            return f"Error migrating Cost Centers: {str(e)}"
    
    def migrate_customers(self, settings):
        """Migrate Customers from e-Boekhouden"""
        try:
            from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
            
            # Get Customers data using new API
            api = EBoekhoudenAPI(settings)
            result = api.get_customers()
            
            if not result["success"]:
                return f"Failed to fetch Customers: {result['error']}"
            
            # Parse JSON response
            import json
            data = json.loads(result["data"])
            customers_data = data.get("items", [])
            
            if self.dry_run:
                return f"Dry Run: Found {len(customers_data)} customers to migrate"
            
            # Create customers in ERPNext
            created_count = 0
            skipped_count = 0
            
            for customer_data in customers_data:
                try:
                    if self.create_customer(customer_data):
                        created_count += 1
                        self.imported_records += 1
                    else:
                        skipped_count += 1
                except Exception as e:
                    self.failed_records += 1
                    self.log_error(f"Failed to create customer {customer_data.get('name', 'Unknown')}: {str(e)}")
            
            self.total_records += len(customers_data)
            return f"Created {created_count} customers, skipped {skipped_count} ({len(customers_data)} total)"
            
        except Exception as e:
            return f"Error migrating Customers: {str(e)}"
    
    def migrate_suppliers(self, settings):
        """Migrate Suppliers from e-Boekhouden"""
        try:
            from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
            
            # Get Suppliers data using new API
            api = EBoekhoudenAPI(settings)
            result = api.get_suppliers()
            
            if not result["success"]:
                return f"Failed to fetch Suppliers: {result['error']}"
            
            # Parse JSON response
            import json
            data = json.loads(result["data"])
            suppliers_data = data.get("items", [])
            
            if self.dry_run:
                return f"Dry Run: Found {len(suppliers_data)} suppliers to migrate"
            
            # Create suppliers in ERPNext
            created_count = 0
            skipped_count = 0
            
            for supplier_data in suppliers_data:
                try:
                    if self.create_supplier(supplier_data):
                        created_count += 1
                        self.imported_records += 1
                    else:
                        skipped_count += 1
                except Exception as e:
                    self.failed_records += 1
                    self.log_error(f"Failed to create supplier {supplier_data.get('name', 'Unknown')}: {str(e)}")
            
            self.total_records += len(suppliers_data)
            return f"Created {created_count} suppliers, skipped {skipped_count} ({len(suppliers_data)} total)"
            
        except Exception as e:
            return f"Error migrating Suppliers: {str(e)}"
    
    def migrate_transactions_data(self, settings):
        """Migrate Transactions from e-Boekhouden using SOAP API"""
        try:
            # Check if we should use SOAP API (default to True)
            use_soap = getattr(self, 'use_soap_api', True)
            
            if use_soap:
                # Use the new SOAP-based migration
                from verenigingen.utils.eboekhouden_soap_migration import migrate_using_soap
                
                # Check if we should use account mappings
                use_account_mappings = getattr(self, 'use_account_mappings', True)
                
                result = migrate_using_soap(self, settings, use_account_mappings)
                
                if result["success"]:
                    stats = result["stats"]
                    # Update counters in database directly to avoid document conflicts
                    imported = (stats["invoices_created"] + 
                               stats["payments_processed"] + 
                               stats["journal_entries_created"])
                    
                    # Get categorized results for better reporting
                    categorized = stats.get("categorized_results", {})
                    
                    # Calculate "failed" based on actual errors, not retries
                    actual_failures = 0
                    if "categories" in categorized:
                        # Count validation errors and system errors as failures
                        actual_failures = (categorized["categories"].get("validation_error", {}).get("count", 0) +
                                         categorized["categories"].get("system_error", {}).get("count", 0))
                    else:
                        # Fallback to old method
                        actual_failures = len(stats["errors"])
                    
                    total = stats["total_mutations"]
                    
                    self.db_set({
                        "imported_records": self.imported_records + imported,
                        "failed_records": self.failed_records + actual_failures,
                        "total_records": self.total_records + total
                    })
                    
                    # Use the improved message from categorizer
                    return result["message"]
                else:
                    return f"Error: {result.get('error', 'Unknown error')}"
            else:
                # Use the old REST API grouped migration
                from verenigingen.utils.eboekhouden_grouped_migration import migrate_mutations_grouped
                
                result = migrate_mutations_grouped(self, settings)
                
                if result["success"]:
                    self.imported_records += result["created"]
                    self.failed_records += result["failed"]
                    self.total_records += result["total_mutations"]
                    
                    return (f"Created {result['created']} journal entries from "
                           f"{result['total_mutations']} mutations "
                           f"({result['grouped_entries']} grouped, "
                           f"{result['ungrouped_mutations']} ungrouped)")
                else:
                    return f"Error: {result.get('error', 'Unknown error')}"
        except Exception as e:
            return f"Error migrating Transactions: {str(e)}"
    
    def migrate_stock_transactions_data(self, settings):
        """Migrate Stock Transactions from e-Boekhouden"""
        try:
            # Use the fixed stock migration that properly handles E-Boekhouden limitations
            from verenigingen.utils.stock_migration_fixed import migrate_stock_transactions_safe
            
            # Get date range
            date_from = self.date_from if self.date_from else None
            date_to = self.date_to if self.date_to else None
            
            # Run migration - returns a message or result dict
            result = migrate_stock_transactions_safe(self, date_from, date_to)
            
            # If result is a dict, extract the message
            if isinstance(result, dict):
                message = result.get("message", "Stock migration completed")
                # Update counters if available
                if "skipped" in result:
                    self.total_records += result["skipped"]
                if "processed" in result:
                    self.imported_records += result["processed"]
                return message
            else:
                # Result is already a message string
                return result
            
        except Exception as e:
            # Log full error without truncation
            frappe.log_error(
                title="Stock Transaction Migration Error",
                message=f"Error migrating stock transactions:\n{str(e)}\n\n{frappe.get_traceback()}"
            )
            return f"Error migrating Stock Transactions: {str(e)[:100]}..."  # Truncate for display
    
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
    
    def log_error(self, message, record_type=None, record_data=None):
        """Enhanced error logging with detailed debugging information"""
        # Create a short title for the error log
        if record_type:
            title = f"E-Boekhouden {record_type} Error"
        else:
            # Extract first part of message for title
            title = message.split(":")[0] if ":" in message else message
            title = title[:100]  # Ensure it's not too long
        
        # Ensure title is within 140 character limit
        if len(title) > 140:
            title = title[:137] + "..."
        
        # Enhanced error logging with full details
        enhanced_message = f"MIGRATION ERROR: {message}"
        
        # Add record data context if available
        if record_data:
            enhanced_message += f"\n\nRECORD DATA:\n{json.dumps(record_data, indent=2, default=str)}"
        
        # Add stack trace for debugging
        try:
            import traceback
            enhanced_message += f"\n\nSTACK TRACE:\n{traceback.format_exc()}"
        except:
            pass
        
        # Add additional context
        enhanced_message += f"\n\nCONTEXT:"
        enhanced_message += f"\n- Migration: {self.migration_name}"
        enhanced_message += f"\n- Timestamp: {frappe.utils.now_datetime()}"
        enhanced_message += f"\n- Record Type: {record_type or 'Unknown'}"
        
        try:
            frappe.log_error(enhanced_message, title)
        except Exception as e:
            # If logging fails, try with a generic title
            try:
                frappe.log_error(enhanced_message, "E-Boekhouden Migration Error")
            except:
                # Last resort - just print to console
                frappe.logger().error(f"E-Boekhouden Migration: {enhanced_message}")
        
        # Also save to debug file immediately
        self.save_debug_error(message, record_type, record_data, enhanced_message)
        
        if hasattr(self, 'error_details'):
            self.error_details += f"\n{message}"
        else:
            self.error_details = message
            
        # Track failed record details if provided
        if record_type and record_data and hasattr(self, 'failed_record_details'):
            self.failed_record_details.append({
                'timestamp': frappe.utils.now_datetime(),
                'record_type': record_type,
                'error_message': message,
                'record_data': record_data,
                'enhanced_message': enhanced_message
            })
    
    def create_account(self, account_data, use_enhanced=False):
        """Create Account in ERPNext"""
        try:
            # Use enhanced migration if available and enabled
            if use_enhanced:
                try:
                    from verenigingen.utils.eboekhouden_migration_enhancements import EnhancedAccountMigration
                    enhanced_migrator = EnhancedAccountMigration(self)
                    result = enhanced_migrator.analyze_and_create_account(account_data)
                    
                    account_code = account_data.get('code', '')
                    account_name = account_data.get('description', '')
                    
                    if result["status"] == "created":
                        frappe.logger().info(f"Created account: {account_code} - {account_name} (Group: {result.get('group', 'N/A')})")
                        return True
                    elif result["status"] == "skipped":
                        frappe.logger().info(f"Skipped: {account_code} - {account_name} ({result.get('reason', '')})")
                        return False
                    else:
                        self.log_error(f"Failed: {account_code} - {account_name}: {result.get('error', '')}")
                        return False
                except ImportError:
                    # Fall back to standard migration
                    pass
            
            # Standard migration logic
            # Map e-Boekhouden account to ERPNext account
            account_code = account_data.get('code', '')
            account_name = account_data.get('description', '')
            category = account_data.get('category', '')
            
            if not account_code or not account_name:
                self.log_error(f"Invalid account data: code={account_code}, name={account_name}")
                return False
            
            # Truncate account name if too long (ERPNext limit is 140 chars)
            if len(account_name) > 120:  # Leave room for account code
                account_name = account_name[:120] + "..."
                frappe.logger().info(f"Truncated long account name for {account_code}")
            
            # Create full account name with code
            full_account_name = f"{account_code} - {account_name}"
            if len(full_account_name) > 140:
                # If still too long, truncate the description part more aggressively
                max_desc_length = 140 - len(account_code) - 3  # 3 for " - "
                account_name = account_name[:max_desc_length]
                full_account_name = f"{account_code} - {account_name}"
            
            # Check if account already exists
            if frappe.db.exists("Account", {"account_number": account_code}):
                frappe.logger().info(f"Account {account_code} already exists, skipping")
                return False
            
            # Map e-Boekhouden categories to ERPNext account types and root types
            # ERPNext valid account types: Bank, Cash, Receivable, Payable, Tax, etc.
            category_mapping = {
                'BTWRC': {'account_type': 'Tax', 'root_type': 'Liability'},
                'AF6': {'account_type': 'Tax', 'root_type': 'Liability'}, 
                'AF19': {'account_type': 'Tax', 'root_type': 'Liability'},
                'AFOVERIG': {'account_type': 'Tax', 'root_type': 'Liability'},
                'VOOR': {'account_type': 'Tax', 'root_type': 'Liability'},
                'VW': {'account_type': '', 'root_type': 'Expense'},  # No specific type for general expense
                'BAL': {'account_type': 'Fixed Asset', 'root_type': 'Asset'},  # Balance sheet assets
                'FIN': {'account_type': 'Bank', 'root_type': 'Asset'},
                'KAS': {'account_type': 'Cash', 'root_type': 'Asset'}
            }
            
            # Get mapping or default
            mapping = category_mapping.get(category, {'account_type': '', 'root_type': 'Expense'})
            account_type = mapping['account_type']
            root_type = mapping['root_type']
            
            # For account codes, try to infer type from the code itself if category mapping fails
            if not account_type and account_code:
                if account_code.startswith(('1', '2')):  # Asset accounts typically start with 1-2
                    if account_code.startswith('15'):  # Bank accounts often 15xx
                        account_type = 'Bank'
                        root_type = 'Asset'
                    elif account_code.startswith('16'):  # Cash accounts often 16xx
                        account_type = 'Cash' 
                        root_type = 'Asset'
                    elif account_code.startswith('13'):  # Receivables often 13xx
                        # Don't use 'Receivable' type to avoid party requirements in journal entries
                        account_type = 'Current Asset'
                        root_type = 'Asset'
                    else:
                        account_type = 'Current Asset'
                        root_type = 'Asset'
                elif account_code.startswith(('3', '4')):  # Asset/Liability accounts typically 3-4
                    if account_code.startswith('30'):  # Inventory/Stock accounts often 30xx
                        # Stock accounts require special handling - create as Current Asset for migration
                        # but note that they should be converted to Stock type manually if needed
                        account_type = 'Current Asset'
                        root_type = 'Asset'
                        frappe.logger().info(f"Account {account_code} appears to be inventory - created as Current Asset, convert to Stock type manually if needed")
                    elif account_code.startswith('44'):  # Payables often 44xx
                        # Don't use 'Payable' type to avoid party requirements in journal entries
                        account_type = 'Current Liability'
                        root_type = 'Liability'
                    elif account_code.startswith('4'):
                        account_type = 'Current Liability'
                        root_type = 'Liability'
                    else:  # Account codes starting with 3 (non-30)
                        account_type = 'Current Asset'
                        root_type = 'Asset'
                elif account_code.startswith('5'):  # Equity typically 5
                    account_type = ''
                    root_type = 'Equity'
                elif account_code.startswith('8'):  # Income typically 8
                    account_type = ''
                    root_type = 'Income'
                elif account_code.startswith(('6', '7')):  # Expenses typically 6-7
                    account_type = ''
                    root_type = 'Expense'
            
            # Get default company
            settings = frappe.get_single("E-Boekhouden Settings")
            company = settings.default_company
            
            if not company:
                self.log_error("No default company set in E-Boekhouden Settings")
                return False
            
            # Find appropriate parent account
            parent_account = self.get_parent_account(account_type, root_type, company)
            
            # Determine if this should be a group account
            # An account should be a group if:
            # 1. It has no parent (root account)
            # 2. It's identified as a group from hierarchy analysis
            # 3. It might have child accounts
            is_group = 0
            
            # Check if this account was identified as a group
            if hasattr(self, '_group_accounts') and account_code in self._group_accounts:
                is_group = 1
                frappe.logger().info(f"Creating account {account_code} as group (has children)")
            elif not parent_account:
                # Root accounts must be groups in ERPNext
                is_group = 1
                frappe.logger().info(f"Creating root account {account_code} as group")
            
            # Create new account
            account_doc = {
                'doctype': 'Account',
                'account_name': full_account_name,  # Use the properly formatted name
                'account_number': account_code,
                'parent_account': parent_account,
                'company': company,
                'root_type': root_type,
                'is_group': is_group,
                'disabled': 0
            }
            
            # Only set account_type if it's not empty (some accounts don't need a specific type)
            if account_type:
                account_doc['account_type'] = account_type
            
            account = frappe.get_doc(account_doc)
            
            account.insert(ignore_permissions=True)
            frappe.logger().info(f"Created account: {account_code} - {account_name}")
            return True
            
        except Exception as e:
            # account_code might not be defined if error occurs early
            account_ref = account_data.get('code', 'Unknown') if 'account_data' in locals() else 'Unknown'
            self.log_error(f"Failed to create account {account_ref}: {str(e)}", "account", account_data if 'account_data' in locals() else {})
            return False
    
    def get_parent_account(self, account_type, root_type, company):
        """Get appropriate parent account for the new account with enhanced logic"""
        try:
            # Enhanced parent account finding logic
            parent = None
            
            # First, try to find existing parent accounts by type
            if account_type == 'Tax':
                # Look for Tax Assets or Duties and Taxes - try multiple variations
                tax_parent_names = [
                    "Tax Assets", "Duties and Taxes", "VAT", "BTW", "Belastingen",
                    "Current Liabilities", "Schulden op korte termijn"
                ]
                
                for parent_name in tax_parent_names:
                    parent = frappe.db.get_value("Account", {
                        "company": company,
                        "account_name": ["like", f"%{parent_name}%"],
                        "is_group": 1
                    }, "name")
                    if parent:
                        break
            
            elif account_type == 'Bank':
                # Look for Bank group accounts
                bank_parent_names = ["Bank", "Liquide middelen", "Kas en Bank"]
                
                for parent_name in bank_parent_names:
                    parent = frappe.db.get_value("Account", {
                        "company": company,
                        "account_name": ["like", f"%{parent_name}%"],
                        "is_group": 1
                    }, "name")
                    if parent:
                        break
                
                # If no specific bank group, try by account type
                if not parent:
                    parent = frappe.db.get_value("Account", {
                        "company": company,
                        "account_type": "Bank",
                        "is_group": 1
                    }, "name")
            
            elif account_type == 'Cash':
                # Look for Cash group accounts
                cash_parent_names = ["Cash", "Kas", "Liquide middelen"]
                
                for parent_name in cash_parent_names:
                    parent = frappe.db.get_value("Account", {
                        "company": company,
                        "account_name": ["like", f"%{parent_name}%"],
                        "is_group": 1
                    }, "name")
                    if parent:
                        break
                
                # If no specific cash group, try by account type
                if not parent:
                    parent = frappe.db.get_value("Account", {
                        "company": company,
                        "account_type": "Cash", 
                        "is_group": 1
                    }, "name")
            
            # If still no parent found, use enhanced fallback logic
            if not parent:
                # Try to find or create appropriate group accounts based on root_type
                parent = self.find_or_create_parent_group(root_type, company)
            
            # Final fallback: get the root account for this root_type
            if not parent:
                parent = frappe.db.get_value("Account", {
                    "company": company,
                    "root_type": root_type,
                    "is_group": 1,
                    "parent_account": ["in", ["", None]]
                }, "name")
            
            return parent
            
        except Exception as e:
            self.log_error(f"Error finding parent account for {account_type}/{root_type}: {str(e)}")
            # Return any group account as last resort
            return frappe.db.get_value("Account", {
                "company": company,
                "is_group": 1
            }, "name", order_by="lft")
    
    def find_or_create_parent_group(self, root_type, company):
        """Find or create appropriate parent group account"""
        try:
            # Define parent group mappings for each root type
            parent_group_mappings = {
                'Asset': ['Current Assets', 'Vlottende activa', 'Activa'],
                'Liability': ['Current Liabilities', 'Schulden op korte termijn', 'Passiva'],
                'Equity': ['Capital Account', 'Eigen vermogen', 'Kapitaal'],
                'Income': ['Direct Income', 'Opbrengsten', 'Inkomsten'],
                'Expense': ['Direct Expenses', 'Kosten', 'Uitgaven']
            }
            
            # Try to find existing parent group
            potential_parents = parent_group_mappings.get(root_type, [])
            
            for parent_name in potential_parents:
                parent = frappe.db.get_value("Account", {
                    "company": company,
                    "account_name": ["like", f"%{parent_name}%"],
                    "root_type": root_type,
                    "is_group": 1
                }, "name")
                if parent:
                    return parent
            
            # If no specific parent found, look for any group under this root_type
            parent_accounts = frappe.db.get_all("Account", {
                "company": company,
                "root_type": root_type,
                "is_group": 1
            }, ["name", "parent_account"], order_by="lft")
            
            # Return the first non-root group account
            for acc in parent_accounts:
                if acc.parent_account:  # Not a root account
                    return acc.name
            
            # If only root accounts exist, return the root
            if parent_accounts:
                return parent_accounts[0].name
            
            return None
            
        except Exception as e:
            frappe.logger().error(f"Error in find_or_create_parent_group: {str(e)}")
            return None
    
    def create_cost_center(self, cost_center_data):
        """Create Cost Center in ERPNext"""
        try:
            # Map e-Boekhouden cost center to ERPNext cost center
            description = cost_center_data.get('description', '')
            parent_id = cost_center_data.get('parentId', 0)
            active = cost_center_data.get('active', True)
            
            if not description:
                self.log_error(f"Invalid cost center data: no description")
                return False
            
            # Get default company
            settings = frappe.get_single("E-Boekhouden Settings")
            company = settings.default_company
            
            if not company:
                self.log_error("No default company set in E-Boekhouden Settings")
                return False
            
            # Check if cost center already exists
            existing_cc = frappe.db.get_value("Cost Center", {
                "cost_center_name": description,
                "company": company
            }, "name")
            if existing_cc:
                # Return False but don't log as error - this is expected for existing data
                return False
            
            # Determine parent cost center
            parent_cost_center = None
            if parent_id and parent_id != 0:
                # Try to find parent by description (this is simplified - ideally we'd map IDs)
                parent_cost_center = frappe.db.get_value("Cost Center", {
                    "company": company,
                    "is_group": 1
                }, "name")
            
            if not parent_cost_center:
                # Get the root cost center for the company
                parent_cost_center = frappe.db.get_value("Cost Center", {
                    "company": company,
                    "is_group": 1,
                    "parent_cost_center": ""
                }, "name")
            
            if not parent_cost_center:
                # Try to create root cost center if it doesn't exist
                from verenigingen.utils.eboekhouden_cost_center_fix import ensure_root_cost_center
                parent_cost_center = ensure_root_cost_center(company)
                
                if not parent_cost_center:
                    self.log_error(f"Could not create or find root cost center for company {company}")
                    return False
            
            # Create new cost center
            cost_center = frappe.get_doc({
                'doctype': 'Cost Center',
                'cost_center_name': description,
                'parent_cost_center': parent_cost_center,
                'company': company,
                'is_group': 0,
                'disabled': not active
            })
            
            cost_center.insert(ignore_permissions=True)
            frappe.logger().info(f"Created cost center: {description}")
            return True
            
        except Exception as e:
            self.log_error(f"Failed to create cost center {description}: {str(e)}")
            return False
    
    def create_customer(self, customer_data):
        """Create Customer in ERPNext"""
        try:
            # Map e-Boekhouden relation to ERPNext customer
            customer_name = customer_data.get('name', '').strip()
            company_name = customer_data.get('companyName', '').strip()
            contact_name = customer_data.get('contactName', '').strip()
            email = customer_data.get('email', '').strip()
            customer_id = customer_data.get('id', '')
            
            # Use company name if available, otherwise contact name, otherwise name, otherwise ID
            display_name = company_name or contact_name or customer_name
            
            if not display_name:
                if customer_id:
                    display_name = f"Customer {customer_id}"
                else:
                    self.log_error(f"Invalid customer data: no name or ID available")
                    return False
            
            # Check if customer already exists
            if frappe.db.exists("Customer", {"customer_name": display_name}):
                frappe.logger().info(f"Customer '{display_name}' already exists, skipping")
                return False
            
            # Get default settings
            settings = frappe.get_single("E-Boekhouden Settings")
            
            # Get proper territory (avoid "Rest Of The World")
            territory = self.get_proper_territory_for_customer(customer_data)
            
            # Create new customer
            customer = frappe.get_doc({
                'doctype': 'Customer',
                'customer_name': display_name,
                'customer_type': 'Company' if company_name else 'Individual',
                'customer_group': 'All Customer Groups',  # Default customer group
                'territory': territory,
                'default_currency': settings.default_currency or 'EUR',
                'disabled': 0
            })
            
            customer.insert(ignore_permissions=True)
            
            # Create contact if contact details are available
            if contact_name or email:
                self.create_contact_for_customer(customer.name, customer_data)
            
            # Create address if address details are available
            if any([customer_data.get('address'), customer_data.get('city'), customer_data.get('postalCode')]):
                self.create_address_for_customer(customer.name, customer_data)
            
            frappe.logger().info(f"Created customer: {display_name}")
            return True
            
        except Exception as e:
            self.log_error(f"Failed to create customer {display_name}: {str(e)}")
            return False
    
    def create_supplier(self, supplier_data):
        """Create Supplier in ERPNext"""
        try:
            # Map e-Boekhouden relation to ERPNext supplier
            supplier_name = supplier_data.get('name', '').strip()
            company_name = supplier_data.get('companyName', '').strip()
            contact_name = supplier_data.get('contactName', '').strip()
            email = supplier_data.get('email', '').strip()
            supplier_id = supplier_data.get('id', '')
            
            # Use company name if available, otherwise contact name, otherwise name, otherwise ID
            display_name = company_name or contact_name or supplier_name
            
            if not display_name:
                if supplier_id:
                    display_name = f"Supplier {supplier_id}"
                else:
                    self.log_error(f"Invalid supplier data: no name or ID available")
                    return False
            
            # Check if supplier already exists
            if frappe.db.exists("Supplier", {"supplier_name": display_name}):
                frappe.logger().info(f"Supplier '{display_name}' already exists, skipping")
                return False
            
            # Get default settings
            settings = frappe.get_single("E-Boekhouden Settings")
            
            # Create new supplier
            supplier = frappe.get_doc({
                'doctype': 'Supplier',
                'supplier_name': display_name,
                'supplier_type': 'Company' if company_name else 'Individual',
                'supplier_group': 'All Supplier Groups',  # Default supplier group
                'default_currency': settings.default_currency or 'EUR',
                'disabled': 0
            })
            
            # Add VAT number if available
            vat_number = supplier_data.get('vatNumber', '').strip()
            if vat_number:
                supplier.tax_id = vat_number
            
            supplier.insert(ignore_permissions=True)
            
            # Create contact if contact details are available
            if contact_name or email:
                self.create_contact_for_supplier(supplier.name, supplier_data)
            
            # Create address if address details are available
            if any([supplier_data.get('address'), supplier_data.get('city'), supplier_data.get('postalCode')]):
                self.create_address_for_supplier(supplier.name, supplier_data)
            
            frappe.logger().info(f"Created supplier: {display_name}")
            return True
            
        except Exception as e:
            self.log_error(f"Failed to create supplier {display_name}: {str(e)}")
            return False
    
    def create_journal_entry(self, transaction_data):
        """Create Journal Entry in ERPNext"""
        try:
            # Map e-Boekhouden transaction to ERPNext journal entry
            # e-Boekhouden API format: {id, type, date, invoiceNumber, ledgerId, amount, entryNumber}
            transaction_date = transaction_data.get('date', '')
            ledger_id = transaction_data.get('ledgerId', '')
            amount = float(transaction_data.get('amount', 0) or 0)
            transaction_type = transaction_data.get('type', 0)  # 0=debit, 1=credit typically
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
            
            # Convert ledgerId to account code - need to look up in chart of accounts
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
            
            # Skip stock accounts - they can only be updated via stock transactions
            if account_type == "Stock":
                frappe.logger().info(f"Skipping stock account {account_code} - must be updated via stock transactions")
                # Track skipped stock transactions
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
            
            # Parse transaction date
            try:
                from datetime import datetime
                if 'T' in transaction_date:
                    posting_date = datetime.strptime(transaction_date.split('T')[0], '%Y-%m-%d').date()
                else:
                    posting_date = datetime.strptime(transaction_date, '%Y-%m-%d').date()
            except ValueError:
                self.log_error(f"Invalid date format: {transaction_date}")
                return False
            
            # Create journal entry
            journal_entry = frappe.get_doc({
                'doctype': 'Journal Entry',
                'company': company,
                'posting_date': posting_date,
                'voucher_type': 'Journal Entry',
                'user_remark': f"Migrated from e-Boekhouden: {description}",
                'accounts': []
            })
            
            # Add the account entry
            journal_entry.append('accounts', {
                'account': account,
                'debit_in_account_currency': debit_amount if debit_amount > 0 else 0,
                'credit_in_account_currency': credit_amount if credit_amount > 0 else 0,
                'user_remark': description,
                'cost_center': settings.default_cost_center
            })
            
            # For balance, we need to create a balancing entry
            # This is a simplified approach - in reality you'd need to group transactions properly
            if debit_amount > 0:
                # Find a suitable contra account (e.g., suspense account)
                contra_account = self.get_suspense_account(company)
                if contra_account:
                    journal_entry.append('accounts', {
                        'account': contra_account,
                        'credit_in_account_currency': debit_amount,
                        'user_remark': f"Contra entry for: {description}",
                        'cost_center': settings.default_cost_center
                    })
            elif credit_amount > 0:
                # Find a suitable contra account
                contra_account = self.get_suspense_account(company)
                if contra_account:
                    journal_entry.append('accounts', {
                        'account': contra_account,
                        'debit_in_account_currency': credit_amount,
                        'user_remark': f"Contra entry for: {description}",
                        'cost_center': settings.default_cost_center
                    })
            
            if len(journal_entry.accounts) < 2:
                self.log_error(f"Could not create balanced journal entry for transaction: {description}")
                return False
            
            journal_entry.insert(ignore_permissions=True)
            frappe.logger().info(f"Created journal entry: {description}")
            return True
            
        except Exception as e:
            self.log_error(f"Failed to create journal entry: {str(e)}")
            return False
    
    def create_contact_for_customer(self, customer_name, customer_data):
        """Create contact for customer"""
        try:
            contact_name = customer_data.get('contactName', '').strip()
            email = customer_data.get('email', '').strip()
            phone = customer_data.get('phone', '').strip()
            
            if not contact_name and not email:
                return
            
            contact = frappe.get_doc({
                'doctype': 'Contact',
                'first_name': contact_name or email.split('@')[0],
                'email_ids': [{'email_id': email, 'is_primary': 1}] if email else [],
                'phone_nos': [{'phone': phone, 'is_primary_phone': 1}] if phone else [],
                'links': [{'link_doctype': 'Customer', 'link_name': customer_name}]
            })
            
            contact.insert(ignore_permissions=True)
            frappe.logger().info(f"Created contact for customer: {customer_name}")
            
        except Exception as e:
            self.log_error(f"Failed to create contact for customer {customer_name}: {str(e)}")
    
    def create_contact_for_supplier(self, supplier_name, supplier_data):
        """Create contact for supplier"""
        try:
            contact_name = supplier_data.get('contactName', '').strip()
            email = supplier_data.get('email', '').strip()
            phone = supplier_data.get('phone', '').strip()
            
            if not contact_name and not email:
                return
            
            contact = frappe.get_doc({
                'doctype': 'Contact',
                'first_name': contact_name or email.split('@')[0],
                'email_ids': [{'email_id': email, 'is_primary': 1}] if email else [],
                'phone_nos': [{'phone': phone, 'is_primary_phone': 1}] if phone else [],
                'links': [{'link_doctype': 'Supplier', 'link_name': supplier_name}]
            })
            
            contact.insert(ignore_permissions=True)
            frappe.logger().info(f"Created contact for supplier: {supplier_name}")
            
        except Exception as e:
            self.log_error(f"Failed to create contact for supplier {supplier_name}: {str(e)}")
    
    def create_address_for_customer(self, customer_name, customer_data):
        """Create address for customer"""
        try:
            address_line1 = customer_data.get('address', '').strip()
            city = customer_data.get('city', '').strip()
            postal_code = customer_data.get('postalCode', '').strip()
            country = customer_data.get('country', 'Netherlands').strip()
            
            if not address_line1 and not city:
                return
            
            address = frappe.get_doc({
                'doctype': 'Address',
                'address_title': f"{customer_name} Address",
                'address_line1': address_line1,
                'city': city,
                'pincode': postal_code,
                'country': country,
                'links': [{'link_doctype': 'Customer', 'link_name': customer_name}]
            })
            
            address.insert(ignore_permissions=True)
            frappe.logger().info(f"Created address for customer: {customer_name}")
            
        except Exception as e:
            self.log_error(f"Failed to create address for customer {customer_name}: {str(e)}")
    
    def create_address_for_supplier(self, supplier_name, supplier_data):
        """Create address for supplier"""
        try:
            address_line1 = supplier_data.get('address', '').strip()
            city = supplier_data.get('city', '').strip()
            postal_code = supplier_data.get('postalCode', '').strip()
            country = supplier_data.get('country', 'Netherlands').strip()
            
            if not address_line1 and not city:
                return
            
            address = frappe.get_doc({
                'doctype': 'Address',
                'address_title': f"{supplier_name} Address",
                'address_line1': address_line1,
                'city': city,
                'pincode': postal_code,
                'country': country,
                'links': [{'link_doctype': 'Supplier', 'link_name': supplier_name}]
            })
            
            address.insert(ignore_permissions=True)
            frappe.logger().info(f"Created address for supplier: {supplier_name}")
            
        except Exception as e:
            self.log_error(f"Failed to create address for supplier {supplier_name}: {str(e)}")
    
    def get_proper_territory_for_customer(self, customer_data):
        """Get appropriate territory for customer, avoiding 'Rest Of The World'"""
        try:
            # Try to determine territory from customer data
            country = customer_data.get('country', '').strip()
            if country:
                # Check if territory exists for this country
                territory = frappe.db.get_value("Territory", {"territory_name": country}, "name")
                if territory:
                    return territory
            
            # Get the company's home country territory
            default_country = frappe.db.get_default("country")
            if default_country:
                home_territory = frappe.db.get_value("Territory", {"territory_name": default_country}, "name")
                if home_territory:
                    return home_territory
            
            # Get territories, preferring specific ones over "Rest Of The World"
            territories = frappe.get_all("Territory", 
                filters={"is_group": 0}, 
                fields=["name", "territory_name"],
                order_by="territory_name")
            
            # Filter out "Rest Of The World" and similar generic territories
            preferred_territories = [t for t in territories 
                if not any(word in t.territory_name.lower() 
                    for word in ['rest', 'world', 'other', 'misc', 'unknown'])]
            
            if preferred_territories:
                return preferred_territories[0].name
            
            # Fall back to any territory if needed
            return territories[0].name if territories else "All Territories"
            
        except Exception as e:
            self.log_error(f"Error determining territory: {str(e)}")
            return "All Territories"
    
    def get_account_code_from_ledger_id(self, ledger_id):
        """Convert e-Boekhouden ledger ID to account code"""
        try:
            # First, try to get chart of accounts and build a mapping
            if not hasattr(self, '_ledger_id_mapping'):
                self._ledger_id_mapping = {}
                
                from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
                settings = frappe.get_single("E-Boekhouden Settings")
                api = EBoekhoudenAPI(settings)
                
                result = api.get_chart_of_accounts()
                if result["success"]:
                    import json
                    data = json.loads(result["data"])
                    accounts = data.get("items", [])
                    
                    # Build mapping of ledger ID to account code
                    for account in accounts:
                        account_id = account.get('id')
                        account_code = account.get('code')
                        if account_id and account_code:
                            self._ledger_id_mapping[str(account_id)] = account_code
            
            # Look up the ledger ID in our mapping
            return self._ledger_id_mapping.get(str(ledger_id))
            
        except Exception as e:
            self.log_error(f"Error converting ledger ID {ledger_id} to account code: {str(e)}")
            return None
    
    def get_suspense_account(self, company):
        """Get or create suspense account for balancing entries"""
        try:
            # Try to find existing suspense account
            suspense_account = frappe.db.get_value("Account", {
                "company": company,
                "account_name": ["like", "%suspense%"]
            }, "name")
            
            if suspense_account:
                return suspense_account
            
            # If not found, look for temporary account
            temp_account = frappe.db.get_value("Account", {
                "company": company,
                "account_name": ["like", "%temporary%"]
            }, "name")
            
            if temp_account:
                return temp_account
            
            # As last resort, return the first liability account
            liability_account = frappe.db.get_value("Account", {
                "company": company,
                "root_type": "Liability",
                "is_group": 0
            }, "name")
            
            return liability_account
            
        except Exception as e:
            self.log_error(f"Error finding suspense account: {str(e)}")
            return None
    
    def save_debug_error(self, message, record_type, record_data, enhanced_message):
        """Save error immediately to debug file for analysis"""
        try:
            import os
            from datetime import datetime
            
            # Create logs directory if it doesn't exist
            log_dir = frappe.get_site_path("private", "files", "eboekhouden_debug_logs")
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            # Create debug filename
            timestamp = datetime.now().strftime("%Y%m%d")
            filename = f"debug_errors_{self.name}_{timestamp}.txt"
            filepath = os.path.join(log_dir, filename)
            
            # Append error to debug file
            with open(filepath, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*80}\n")
                f.write(f"ERROR TIMESTAMP: {frappe.utils.now_datetime()}\n")
                f.write(f"RECORD TYPE: {record_type or 'Unknown'}\n")
                f.write(f"{'='*80}\n")
                f.write(enhanced_message)
                f.write(f"\n{'='*80}\n\n")
                
        except Exception as e:
            frappe.logger().error(f"Failed to save debug error: {str(e)}")
    
    def save_failed_records_log(self):
        """Save detailed log of failed records to a file"""
        try:
            import os
            from datetime import datetime
            
            # Create logs directory if it doesn't exist
            log_dir = frappe.get_site_path("private", "files", "eboekhouden_migration_logs")
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            # Create filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"failed_records_{self.name}_{timestamp}.json"
            filepath = os.path.join(log_dir, filename)
            
            # Save the failed records
            with open(filepath, 'w') as f:
                json.dump({
                    'migration_name': self.name,
                    'migration_id': self.migration_name,
                    'timestamp': frappe.utils.now_datetime(),
                    'total_failed': self.failed_records,
                    'failed_records': self.failed_record_details
                }, f, indent=2, default=str)
            
            # Add note to migration summary
            self.migration_summary += f"\n\nFailed records log saved to: {filename}"
            frappe.logger().info(f"Failed records log saved to: {filepath}")
            
        except Exception as e:
            frappe.log_error(f"Failed to save failed records log: {str(e)}")


@frappe.whitelist()
def start_migration_api(migration_name, dry_run=1):
    """API method to start migration process"""
    try:
        migration = frappe.get_doc("E-Boekhouden Migration", migration_name)
        if migration.migration_status != "Draft":
            return {"success": False, "error": "Migration must be in Draft status to start"}
        
        # Update migration settings and initialize counters
        migration.dry_run = int(dry_run)
        migration.migration_status = "In Progress"
        migration.start_time = frappe.utils.now_datetime()
        migration.current_operation = "Initializing migration..."
        migration.progress_percentage = 0
        
        # Initialize counters - THIS IS THE FIX!
        migration.total_records = 0
        migration.imported_records = 0
        migration.failed_records = 0
        
        migration.save()
        
        # Start migration directly without submission
        migration.start_migration()
        
        return {"success": True, "message": "Migration started successfully"}
        
    except Exception as e:
        frappe.log_error(f"Error starting migration: {str(e)}")
        return {"success": False, "error": str(e)}

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


@frappe.whitelist()
def debug_cleanup_all_imported_data(company=None):
    """Debug function to completely clean up all imported data for fresh migration"""
    try:
        # Get default company if not provided
        if not company:
            settings = frappe.get_single("E-Boekhouden Settings")
            company = settings.default_company
        
        if not company:
            return {"success": False, "error": "No company specified"}
        
        results = {}
        
        # 1. Clean up Journal Entries (proper cancellation sequence)
        journal_entries_deleted = 0
        try:
            journal_entries = frappe.get_all("Journal Entry", 
                filters={
                    "company": company,
                    "user_remark": ["like", "%Migrated from e-Boekhouden%"]
                },
                fields=["name", "docstatus"])
            
            for je in journal_entries:
                try:
                    je_doc = frappe.get_doc("Journal Entry", je.name)
                    
                    # Cancel if submitted
                    if je_doc.docstatus == 1:
                        # Set ignore_linked_doctypes to handle GL Entries
                        je_doc.ignore_linked_doctypes = (
                            "GL Entry",
                            "Stock Ledger Entry",
                            "Payment Ledger Entry",
                            "Repost Payment Ledger",
                            "Repost Payment Ledger Items",
                            "Repost Accounting Ledger",
                            "Repost Accounting Ledger Items"
                        )
                        je_doc.cancel()
                    
                    # Delete after cancellation
                    frappe.delete_doc("Journal Entry", je.name)
                    journal_entries_deleted += 1
                except Exception as e:
                    frappe.log_error(f"Failed to delete Journal Entry {je.name}: {str(e)}")
                    pass
        except Exception as e:
            frappe.log_error(f"Error cleaning journal entries: {str(e)}")
        
        results["journal_entries_deleted"] = journal_entries_deleted
        
        # 2. Clean up Payment Entries (proper cancellation sequence)
        payment_entries_deleted = 0
        
        def cleanup_payment_entries(pe_list, method_name):
            deleted = 0
            for pe in pe_list:
                try:
                    if not frappe.db.exists("Payment Entry", pe.name):
                        continue
                    
                    # First, aggressively clean up any GL Entries for this Payment Entry
                    try:
                        frappe.db.sql("""
                            DELETE FROM `tabGL Entry` 
                            WHERE voucher_type = 'Payment Entry' 
                            AND voucher_no = %s
                        """, pe.name)
                    except:
                        pass
                        
                    pe_doc = frappe.get_doc("Payment Entry", pe.name)
                    
                    # Cancel if submitted
                    if pe_doc.docstatus == 1:
                        # Set ignore_linked_doctypes to handle GL Entries properly
                        pe_doc.ignore_linked_doctypes = (
                            "GL Entry",
                            "Stock Ledger Entry", 
                            "Payment Ledger Entry",
                            "Repost Payment Ledger",
                            "Repost Payment Ledger Items",
                            "Repost Accounting Ledger", 
                            "Repost Accounting Ledger Items",
                            "Unreconcile Payment",
                            "Unreconcile Payment Entries",
                        )
                        try:
                            pe_doc.cancel()
                        except:
                            # If cancellation fails, try direct status update
                            frappe.db.sql("UPDATE `tabPayment Entry` SET docstatus = 2 WHERE name = %s", pe.name)
                    
                    # Delete after cancellation - try multiple approaches
                    try:
                        frappe.delete_doc("Payment Entry", pe.name)
                    except:
                        # If delete_doc fails, try direct SQL deletion
                        try:
                            frappe.db.sql("DELETE FROM `tabPayment Entry` WHERE name = %s", pe.name)
                        except:
                            pass
                    
                    deleted += 1
                except Exception as e:
                    frappe.log_error(f"Failed to delete Payment Entry {pe.name} via {method_name}: {str(e)}")
                    pass
            return deleted
        
        # Method 1: By eboekhouden_mutation_nr (most reliable)
        try:
            mutation_nr_entries = frappe.get_all("Payment Entry", filters=[
                ["company", "=", company],
                ["eboekhouden_mutation_nr", "is", "set"],
                ["eboekhouden_mutation_nr", "!=", ""],
                ["docstatus", "!=", 2]
            ], fields=["name", "docstatus"])
            
            payment_entries_deleted += cleanup_payment_entries(mutation_nr_entries, "mutation_nr")
        except Exception as e:
            frappe.log_error(f"Error with mutation_nr cleanup method: {str(e)}")
        
        # Method 2: By numeric reference_no (backup method) - using SQL query due to regexp limitation
        try:
            numeric_ref_entries = frappe.db.sql("""
                SELECT name, docstatus FROM `tabPayment Entry`
                WHERE company = %s
                AND reference_no REGEXP '^[0-9]+$'
                AND docstatus != 2
            """, (company,), as_dict=True)
            
            payment_entries_deleted += cleanup_payment_entries(numeric_ref_entries, "numeric_ref")
        except Exception as e:
            frappe.log_error(f"Error with numeric_ref cleanup method: {str(e)}")
        
        # Method 3: By remarks pattern (catch remaining entries)
        try:
            remarks_entries = frappe.get_all("Payment Entry", filters=[
                ["company", "=", company],
                ["remarks", "like", "%Mutation Nr:%"],
                ["docstatus", "!=", 2]
            ], fields=["name", "docstatus"])
            
            payment_entries_deleted += cleanup_payment_entries(remarks_entries, "remarks")
        except Exception as e:
            frappe.log_error(f"Error with remarks cleanup method: {str(e)}")
        
        results["payment_entries_deleted"] = payment_entries_deleted
        
        # 3. Clean up Sales Invoices (proper cancellation sequence)
        sales_invoices_deleted = 0
        try:
            sales_invoices = frappe.get_all("Sales Invoice",
                filters={
                    "company": company,
                    "remarks": ["like", "%e-Boekhouden%"]
                },
                fields=["name", "docstatus"])
            
            for si in sales_invoices:
                try:
                    si_doc = frappe.get_doc("Sales Invoice", si.name)
                    
                    # Cancel if submitted
                    if si_doc.docstatus == 1:
                        si_doc.ignore_linked_doctypes = (
                            "GL Entry",
                            "Stock Ledger Entry",
                            "Payment Ledger Entry",
                            "Repost Payment Ledger",
                            "Repost Payment Ledger Items",
                            "Repost Accounting Ledger",
                            "Repost Accounting Ledger Items"
                        )
                        si_doc.cancel()
                    
                    # Delete after cancellation
                    frappe.delete_doc("Sales Invoice", si.name)
                    sales_invoices_deleted += 1
                except Exception as e:
                    frappe.log_error(f"Failed to delete Sales Invoice {si.name}: {str(e)}")
                    pass
        except Exception as e:
            frappe.log_error(f"Error cleaning sales invoices: {str(e)}")
        
        results["sales_invoices_deleted"] = sales_invoices_deleted
        
        # 4. Clean up Purchase Invoices (proper cancellation sequence)
        purchase_invoices_deleted = 0
        try:
            purchase_invoices = frappe.get_all("Purchase Invoice",
                filters={
                    "company": company,
                    "remarks": ["like", "%e-Boekhouden%"]
                },
                fields=["name", "docstatus"])
            
            for pi in purchase_invoices:
                try:
                    pi_doc = frappe.get_doc("Purchase Invoice", pi.name)
                    
                    # Cancel if submitted
                    if pi_doc.docstatus == 1:
                        pi_doc.ignore_linked_doctypes = (
                            "GL Entry",
                            "Stock Ledger Entry",
                            "Payment Ledger Entry",
                            "Repost Payment Ledger",
                            "Repost Payment Ledger Items",
                            "Repost Accounting Ledger",
                            "Repost Accounting Ledger Items"
                        )
                        pi_doc.cancel()
                    
                    # Delete after cancellation
                    frappe.delete_doc("Purchase Invoice", pi.name)
                    purchase_invoices_deleted += 1
                except Exception as e:
                    frappe.log_error(f"Failed to delete Purchase Invoice {pi.name}: {str(e)}")
                    pass
        except Exception as e:
            frappe.log_error(f"Error cleaning purchase invoices: {str(e)}")
        
        results["purchase_invoices_deleted"] = purchase_invoices_deleted
        
        # 5. Clean up GL Entries (Note: These should be handled automatically by cancellation above)
        gl_entries_deleted = 0
        try:
            # Only clean up orphaned GL Entries that might be left behind
            gl_entries = frappe.db.get_all("GL Entry", 
                filters={
                    "company": company, 
                    "remarks": ["like", "%e-Boekhouden%"]
                })
            
            for gl in gl_entries:
                try:
                    # Use SQL delete for GL Entries as they don't have document controllers
                    frappe.db.sql("DELETE FROM `tabGL Entry` WHERE name = %s", gl.name)
                    gl_entries_deleted += 1
                except Exception as e:
                    frappe.log_error(f"Failed to delete GL Entry {gl.name}: {str(e)}")
                    pass
        except Exception as e:
            frappe.log_error(f"Error cleaning GL entries: {str(e)}")
        
        results["gl_entries_deleted"] = gl_entries_deleted
        
        # 6. Clean up Customers (optional - be careful with this)
        customers = frappe.get_all("Customer", 
            filters={"customer_name": ["like", "%e-Boekhouden%"]})
        
        for customer in customers:
            try:
                frappe.delete_doc("Customer", customer.name, force=True)
            except:
                pass
        results["customers_deleted"] = len(customers)
        
        # 7. Clean up Suppliers (optional - be careful with this)
        suppliers = frappe.get_all("Supplier",
            filters={"supplier_name": ["like", "%e-Boekhouden%"]})
        
        for supplier in suppliers:
            try:
                frappe.delete_doc("Supplier", supplier.name, force=True)
            except:
                pass
        results["suppliers_deleted"] = len(suppliers)
        
        frappe.db.commit()
        
        return {
            "success": True,
            "message": "Cleanup completed successfully",
            "results": results
        }
        
    except Exception as e:
        frappe.db.rollback()
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def debug_cleanup_gl_entries_only(company=None):
    """Debug function to specifically clean up GL Entries created by E-Boekhouden import"""
    try:
        # Get default company if not provided
        if not company:
            settings = frappe.get_single("E-Boekhouden Settings")
            company = settings.default_company
        
        if not company:
            return {"success": False, "error": "No company specified"}
        
        results = {"gl_entries_deleted": 0, "errors": []}
        
        # Method 1: Clean up GL Entries linked to E-Boekhouden Payment Entries
        try:
            # Get Payment Entry names that are from E-Boekhouden
            payment_entries = frappe.db.sql("""
                SELECT name FROM `tabPayment Entry` 
                WHERE company = %s 
                AND (
                    eboekhouden_mutation_nr IS NOT NULL 
                    OR reference_no REGEXP '^[0-9]+$'
                    OR remarks LIKE '%%Mutation Nr:%%'
                )
            """, (company,), as_dict=True)
            
            pe_names = [pe.name for pe in payment_entries]
            
            if pe_names:
                # Get GL Entries for these Payment Entries
                gl_entries = frappe.db.sql("""
                    SELECT name FROM `tabGL Entry`
                    WHERE company = %s
                    AND voucher_type = 'Payment Entry'
                    AND voucher_no IN ({})
                """.format(','.join(['%s'] * len(pe_names))), 
                [company] + pe_names, as_dict=True)
                
                for gl in gl_entries:
                    try:
                        frappe.db.sql("DELETE FROM `tabGL Entry` WHERE name = %s", gl.name)
                        results["gl_entries_deleted"] += 1
                    except Exception as e:
                        results["errors"].append(f"Failed to delete GL Entry {gl.name}: {str(e)}")
        except Exception as e:
            results["errors"].append(f"Error cleaning Payment Entry GL Entries: {str(e)}")
        
        # Method 2: Clean up GL Entries linked to E-Boekhouden Invoices
        try:
            # Sales Invoice GL Entries
            si_gl_entries = frappe.db.sql("""
                SELECT gl.name FROM `tabGL Entry` gl
                JOIN `tabSales Invoice` si ON gl.voucher_no = si.name
                WHERE gl.company = %s
                AND gl.voucher_type = 'Sales Invoice'
                AND si.remarks LIKE '%%e-Boekhouden%%'
            """, (company,), as_dict=True)
            
            for gl in si_gl_entries:
                try:
                    frappe.db.sql("DELETE FROM `tabGL Entry` WHERE name = %s", gl.name)
                    results["gl_entries_deleted"] += 1
                except Exception as e:
                    results["errors"].append(f"Failed to delete Sales Invoice GL Entry {gl.name}: {str(e)}")
            
            # Purchase Invoice GL Entries
            pi_gl_entries = frappe.db.sql("""
                SELECT gl.name FROM `tabGL Entry` gl
                JOIN `tabPurchase Invoice` pi ON gl.voucher_no = pi.name
                WHERE gl.company = %s
                AND gl.voucher_type = 'Purchase Invoice'
                AND pi.remarks LIKE '%%e-Boekhouden%%'
            """, (company,), as_dict=True)
            
            for gl in pi_gl_entries:
                try:
                    frappe.db.sql("DELETE FROM `tabGL Entry` WHERE name = %s", gl.name)
                    results["gl_entries_deleted"] += 1
                except Exception as e:
                    results["errors"].append(f"Failed to delete Purchase Invoice GL Entry {gl.name}: {str(e)}")
        except Exception as e:
            results["errors"].append(f"Error cleaning Invoice GL Entries: {str(e)}")
        
        # Method 3: Clean up GL Entries linked to E-Boekhouden Journal Entries
        try:
            je_gl_entries = frappe.db.sql("""
                SELECT gl.name FROM `tabGL Entry` gl
                JOIN `tabJournal Entry` je ON gl.voucher_no = je.name
                WHERE gl.company = %s
                AND gl.voucher_type = 'Journal Entry'
                AND je.user_remark LIKE '%%Migrated from e-Boekhouden%%'
            """, (company,), as_dict=True)
            
            for gl in je_gl_entries:
                try:
                    frappe.db.sql("DELETE FROM `tabGL Entry` WHERE name = %s", gl.name)
                    results["gl_entries_deleted"] += 1
                except Exception as e:
                    results["errors"].append(f"Failed to delete Journal Entry GL Entry {gl.name}: {str(e)}")
        except Exception as e:
            results["errors"].append(f"Error cleaning Journal Entry GL Entries: {str(e)}")
        
        # Method 4: Clean up any remaining GL Entries with E-Boekhouden in remarks
        try:
            direct_gl_entries = frappe.db.sql("""
                SELECT name FROM `tabGL Entry`
                WHERE company = %s
                AND remarks LIKE '%%e-Boekhouden%%'
            """, (company,), as_dict=True)
            
            for gl in direct_gl_entries:
                try:
                    frappe.db.sql("DELETE FROM `tabGL Entry` WHERE name = %s", gl.name)
                    results["gl_entries_deleted"] += 1
                except Exception as e:
                    results["errors"].append(f"Failed to delete direct GL Entry {gl.name}: {str(e)}")
        except Exception as e:
            results["errors"].append(f"Error cleaning direct GL Entries: {str(e)}")
        
        frappe.db.commit()
        
        return {
            "success": True,
            "message": f"GL Entry cleanup completed. Deleted {results['gl_entries_deleted']} entries.",
            "results": results
        }
        
    except Exception as e:
        frappe.db.rollback()
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def debug_analyze_cleanup_requirements(company=None):
    """Analyze what E-Boekhouden data exists and needs cleanup"""
    try:
        # Get default company if not provided
        if not company:
            settings = frappe.get_single("E-Boekhouden Settings")
            company = settings.default_company
        
        if not company:
            return {"success": False, "error": "No company specified"}
        
        analysis = {}
        
        # 1. Analyze Payment Entries
        payment_analysis = {}
        
        # Count by mutation number field
        mutation_nr_count = frappe.db.count("Payment Entry", filters=[
            ["company", "=", company],
            ["eboekhouden_mutation_nr", "is", "set"],
            ["docstatus", "!=", 2]
        ])
        payment_analysis["by_mutation_nr"] = mutation_nr_count
        
        # Count by numeric reference - using SQL query due to regexp limitation
        numeric_ref_count = frappe.db.sql("""
            SELECT COUNT(*) as count FROM `tabPayment Entry`
            WHERE company = %s
            AND reference_no REGEXP '^[0-9]+$'
            AND docstatus != 2
        """, (company,), as_dict=True)[0].count
        payment_analysis["by_numeric_ref"] = numeric_ref_count
        
        # Count by remarks pattern
        remarks_count = frappe.db.count("Payment Entry", filters=[
            ["company", "=", company],
            ["remarks", "like", "%Mutation Nr:%"],
            ["docstatus", "!=", 2]
        ])
        payment_analysis["by_remarks"] = remarks_count
        
        # Count by document status
        draft_pe = frappe.db.count("Payment Entry", filters=[
            ["company", "=", company],
            ["eboekhouden_mutation_nr", "is", "set"],
            ["docstatus", "=", 0]
        ])
        submitted_pe = frappe.db.count("Payment Entry", filters=[
            ["company", "=", company],
            ["eboekhouden_mutation_nr", "is", "set"],
            ["docstatus", "=", 1]
        ])
        cancelled_pe = frappe.db.count("Payment Entry", filters=[
            ["company", "=", company],
            ["eboekhouden_mutation_nr", "is", "set"],
            ["docstatus", "=", 2]
        ])
        
        payment_analysis["by_status"] = {
            "draft": draft_pe,
            "submitted": submitted_pe,
            "cancelled": cancelled_pe
        }
        
        analysis["payment_entries"] = payment_analysis
        
        # 2. Analyze GL Entries
        gl_analysis = {}
        
        # GL Entries linked to Payment Entries
        pe_gl_count = frappe.db.sql("""
            SELECT COUNT(*) as count FROM `tabGL Entry` gl
            JOIN `tabPayment Entry` pe ON gl.voucher_no = pe.name
            WHERE gl.company = %s
            AND gl.voucher_type = 'Payment Entry'
            AND pe.eboekhouden_mutation_nr IS NOT NULL
        """, (company,), as_dict=True)[0].count
        gl_analysis["payment_entry_linked"] = pe_gl_count
        
        # GL Entries linked to Invoices
        si_gl_count = frappe.db.sql("""
            SELECT COUNT(*) as count FROM `tabGL Entry` gl
            JOIN `tabSales Invoice` si ON gl.voucher_no = si.name
            WHERE gl.company = %s
            AND gl.voucher_type = 'Sales Invoice'
            AND si.remarks LIKE '%%e-Boekhouden%%'
        """, (company,), as_dict=True)[0].count
        gl_analysis["sales_invoice_linked"] = si_gl_count
        
        pi_gl_count = frappe.db.sql("""
            SELECT COUNT(*) as count FROM `tabGL Entry` gl
            JOIN `tabPurchase Invoice` pi ON gl.voucher_no = pi.name
            WHERE gl.company = %s
            AND gl.voucher_type = 'Purchase Invoice'
            AND pi.remarks LIKE '%%e-Boekhouden%%'
        """, (company,), as_dict=True)[0].count
        gl_analysis["purchase_invoice_linked"] = pi_gl_count
        
        # GL Entries linked to Journal Entries
        je_gl_count = frappe.db.sql("""
            SELECT COUNT(*) as count FROM `tabGL Entry` gl
            JOIN `tabJournal Entry` je ON gl.voucher_no = je.name
            WHERE gl.company = %s
            AND gl.voucher_type = 'Journal Entry'
            AND je.user_remark LIKE '%%Migrated from e-Boekhouden%%'
        """, (company,), as_dict=True)[0].count
        gl_analysis["journal_entry_linked"] = je_gl_count
        
        # Direct GL Entries with e-Boekhouden in remarks
        direct_gl_count = frappe.db.count("GL Entry", filters=[
            ["company", "=", company],
            ["remarks", "like", "%e-Boekhouden%"]
        ])
        gl_analysis["direct_remarks"] = direct_gl_count
        
        analysis["gl_entries"] = gl_analysis
        
        # 3. Analyze Invoices
        invoice_analysis = {}
        
        sales_invoices = frappe.db.count("Sales Invoice", filters=[
            ["company", "=", company],
            ["remarks", "like", "%e-Boekhouden%"]
        ])
        invoice_analysis["sales_invoices"] = sales_invoices
        
        purchase_invoices = frappe.db.count("Purchase Invoice", filters=[
            ["company", "=", company],
            ["remarks", "like", "%e-Boekhouden%"]
        ])
        invoice_analysis["purchase_invoices"] = purchase_invoices
        
        analysis["invoices"] = invoice_analysis
        
        # 4. Analyze Journal Entries
        journal_entries = frappe.db.count("Journal Entry", filters=[
            ["company", "=", company],
            ["user_remark", "like", "%Migrated from e-Boekhouden%"]
        ])
        analysis["journal_entries"] = journal_entries
        
        # 5. Analyze Customers and Suppliers
        customers = frappe.db.count("Customer", filters=[
            ["customer_name", "like", "%e-Boekhouden%"]
        ])
        suppliers = frappe.db.count("Supplier", filters=[
            ["supplier_name", "like", "%e-Boekhouden%"]
        ])
        
        analysis["parties"] = {
            "customers": customers,
            "suppliers": suppliers
        }
        
        # 6. Generate cleanup recommendations
        recommendations = []
        
        if submitted_pe > 0:
            recommendations.append(f"❗ {submitted_pe} submitted Payment Entries need proper cancellation before deletion")
        
        if pe_gl_count > 0:
            recommendations.append(f"❗ {pe_gl_count} GL Entries are linked to Payment Entries")
        
        if (si_gl_count + pi_gl_count + je_gl_count) > 0:
            recommendations.append(f"❗ {si_gl_count + pi_gl_count + je_gl_count} GL Entries are linked to Invoices/Journal Entries")
        
        if direct_gl_count > 0:
            recommendations.append(f"⚠️ {direct_gl_count} GL Entries have e-Boekhouden in remarks")
        
        recommendations.append("✅ Use the improved debug_cleanup_all_imported_data() function for safe cleanup")
        recommendations.append("✅ Use debug_cleanup_gl_entries_only() if GL Entries remain after main cleanup")
        
        analysis["recommendations"] = recommendations
        
        return {
            "success": True,
            "message": "Analysis completed successfully",
            "analysis": analysis
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

    def stage_eboekhouden_data(self, settings):
        """Stage E-Boekhouden data for manual review before processing"""
        try:
            from .eboekhouden_soap_api import EBoekhoudenSOAPAPI
            
            # Initialize API
            api = EBoekhoudenSOAPAPI(settings)
            
            # Step 1: Retrieve and analyze Chart of Accounts
            self.db_set({
                "current_operation": "Retrieving Chart of Accounts for analysis...",
                "progress_percentage": 32
            })
            frappe.db.commit()
            
            accounts_result = api.get_grootboekrekeningen()
            if not accounts_result["success"]:
                return {"success": False, "error": f"Failed to retrieve accounts: {accounts_result['error']}"}
            
            # Store account analysis for manual review
            account_analysis = self.analyze_account_structure(accounts_result["accounts"])
            
            # Step 2: Retrieve Relations for customer/supplier analysis
            self.db_set({
                "current_operation": "Retrieving relations data...",
                "progress_percentage": 35
            })
            frappe.db.commit()
            
            relations_result = api.get_relaties()
            if not relations_result["success"]:
                return {"success": False, "error": f"Failed to retrieve relations: {relations_result['error']}"}
            
            # Step 3: Sample mutation data for mapping analysis
            self.db_set({
                "current_operation": "Sampling transaction data for mapping analysis...",
                "progress_percentage": 38
            })
            frappe.db.commit()
            
            # Get a representative sample of mutations
            sample_result = api.get_mutations(
                date_from=frappe.utils.add_months(frappe.utils.today(), -3),
                date_to=frappe.utils.today()
            )
            
            if not sample_result["success"]:
                return {"success": False, "error": f"Failed to retrieve sample mutations: {sample_result['error']}"}
            
            # Analyze mapping requirements
            mapping_analysis = self.analyze_mapping_requirements(sample_result["mutations"])
            
            # Store staging data
            staging_data = {
                "accounts": accounts_result["accounts"],
                "account_analysis": account_analysis,
                "relations": relations_result["relations"],
                "sample_mutations": sample_result["mutations"][:100],  # Store first 100 for analysis
                "mapping_analysis": mapping_analysis,
                "staged_at": frappe.utils.now_datetime()
            }
            
            # Save staging data to migration document
            self.db_set({
                "staging_data": json.dumps(staging_data, default=str),
                "migration_status": "Data Staged",
                "current_operation": "Data staging completed - ready for configuration"
            })
            frappe.db.commit()
            
            return {
                "success": True,
                "message": f"Staged {len(accounts_result['accounts'])} accounts, {len(relations_result['relations'])} relations, analyzed {len(sample_result['mutations'])} sample transactions",
                "analysis": {
                    "accounts": account_analysis,
                    "mappings": mapping_analysis
                }
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def analyze_account_structure(self, accounts):
        """Analyze the account structure to suggest proper account types"""
        analysis = {
            "total_accounts": len(accounts),
            "by_category": {},
            "account_type_suggestions": [],
            "potential_issues": []
        }
        
        for account in accounts:
            category = account.get("Categorie", "Unknown")
            analysis["by_category"][category] = analysis["by_category"].get(category, 0) + 1
            
            # Suggest account types based on code patterns and categories
            code = account.get("Code", "")
            name = account.get("Omschrijving", "").lower()
            
            suggestion = self.suggest_account_type(code, name, category)
            if suggestion:
                analysis["account_type_suggestions"].append({
                    "code": code,
                    "name": account.get("Omschrijving", ""),
                    "category": category,
                    "suggested_type": suggestion["type"],
                    "confidence": suggestion["confidence"],
                    "reason": suggestion["reason"]
                })
        
        return analysis
    
    def suggest_account_type(self, code, name, category):
        """Suggest ERPNext account type based on E-Boekhouden account info"""
        suggestions = []
        
        # Code-based suggestions
        if code.startswith("1"):
            if "kas" in name or "bank" in name or "giro" in name:
                suggestions.append({"type": "Bank", "confidence": 0.9, "reason": "Bank/cash account pattern"})
            elif "debiteuren" in name or "vorderingen" in name:
                suggestions.append({"type": "Receivable", "confidence": 0.8, "reason": "Receivables pattern"})
            else:
                suggestions.append({"type": "Asset", "confidence": 0.7, "reason": "Asset account range"})
        
        elif code.startswith("2"):
            if "crediteuren" in name or "schulden" in name:
                suggestions.append({"type": "Payable", "confidence": 0.8, "reason": "Payables pattern"})
            else:
                suggestions.append({"type": "Liability", "confidence": 0.7, "reason": "Liability account range"})
        
        elif code.startswith("3"):
            suggestions.append({"type": "Equity", "confidence": 0.8, "reason": "Equity account range"})
        
        elif code.startswith("4"):
            suggestions.append({"type": "Income", "confidence": 0.8, "reason": "Income account range"})
        
        elif code.startswith("5") or code.startswith("6") or code.startswith("7"):
            suggestions.append({"type": "Expense", "confidence": 0.8, "reason": "Expense account range"})
        
        # Category-based suggestions
        category_mappings = {
            "Omzet": {"type": "Income", "confidence": 0.9},
            "Kosten": {"type": "Expense", "confidence": 0.9},
            "Activa": {"type": "Asset", "confidence": 0.8},
            "Passiva": {"type": "Liability", "confidence": 0.8}
        }
        
        if category in category_mappings:
            suggestions.append({
                **category_mappings[category],
                "reason": f"Category '{category}' mapping"
            })
        
        # Return highest confidence suggestion
        if suggestions:
            return max(suggestions, key=lambda x: x["confidence"])
        
        return None
    
    def analyze_mapping_requirements(self, mutations):
        """Analyze mutations to identify mapping patterns and requirements"""
        analysis = {
            "total_mutations": len(mutations),
            "by_type": {},
            "account_usage": {},
            "unmapped_patterns": [],
            "suggested_mappings": []
        }
        
        for mutation in mutations:
            mut_type = mutation.get("Soort", "Unknown")
            analysis["by_type"][mut_type] = analysis["by_type"].get(mut_type, 0) + 1
            
            # Analyze account usage in mutation lines
            for line in mutation.get("MutatieRegels", []):
                account_code = line.get("TegenrekeningCode")
                if account_code:
                    if account_code not in analysis["account_usage"]:
                        analysis["account_usage"][account_code] = {
                            "count": 0,
                            "sample_descriptions": [],
                            "amount_range": {"min": None, "max": None}
                        }
                    
                    usage = analysis["account_usage"][account_code]
                    usage["count"] += 1
                    
                    # Store sample descriptions
                    desc = line.get("Omschrijving") or mutation.get("Omschrijving", "")
                    if desc and len(usage["sample_descriptions"]) < 5:
                        usage["sample_descriptions"].append(desc)
                    
                    # Track amount ranges
                    amount = float(line.get("BedragExclBTW", 0) or 0)
                    if amount:
                        if usage["amount_range"]["min"] is None or amount < usage["amount_range"]["min"]:
                            usage["amount_range"]["min"] = amount
                        if usage["amount_range"]["max"] is None or amount > usage["amount_range"]["max"]:
                            usage["amount_range"]["max"] = amount
        
        return analysis


@frappe.whitelist()
def get_staging_data_for_review(migration_name):
    """Get staged data for manual review and configuration"""
    try:
        migration_doc = frappe.get_doc("E-Boekhouden Migration", migration_name)
        
        if not migration_doc.staging_data:
            return {"success": False, "error": "No staging data available"}
        
        staging_data = json.loads(migration_doc.staging_data)
        
        # Enhance with current mapping status
        enhanced_data = {
            "migration_status": migration_doc.migration_status,
            "staging_info": {
                "staged_at": staging_data.get("staged_at"),
                "accounts_count": len(staging_data.get("accounts", [])),
                "relations_count": len(staging_data.get("relations", [])),
                "sample_mutations_count": len(staging_data.get("sample_mutations", []))
            },
            "account_analysis": staging_data.get("account_analysis", {}),
            "mapping_analysis": staging_data.get("mapping_analysis", {}),
            "current_mappings": get_current_account_mappings(migration_doc.company),
            "configuration_status": assess_configuration_status(migration_doc.company, staging_data)
        }
        
        return {
            "success": True,
            "data": enhanced_data
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def create_manual_account_mapping(migration_name, account_code, description_pattern, document_type, transaction_category, reason):
    """Create a manual override for account mapping"""
    try:
        # Create or update account mapping
        existing = frappe.db.exists("E-Boekhouden Account Mapping", {
            "account_code": account_code,
            "is_manual_override": 1
        })
        
        if existing:
            mapping_doc = frappe.get_doc("E-Boekhouden Account Mapping", existing)
        else:
            mapping_doc = frappe.new_doc("E-Boekhouden Account Mapping")
            mapping_doc.account_code = account_code
            mapping_doc.is_manual_override = 1
        
        # Update mapping details
        mapping_doc.update({
            "description_pattern": description_pattern,
            "document_type": document_type,
            "transaction_category": transaction_category,
            "override_reason": reason,
            "priority": 100,  # High priority for manual overrides
            "is_active": 1,
            "migration_reference": migration_name
        })
        
        mapping_doc.save()
        
        return {
            "success": True,
            "message": f"Manual mapping created for account {account_code}",
            "mapping_name": mapping_doc.name
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def preview_mapping_impact(migration_name, account_code=None, limit=50):
    """Preview what documents will be created with current mappings"""
    try:
        migration_doc = frappe.get_doc("E-Boekhouden Migration", migration_name)
        
        if not migration_doc.staging_data:
            return {"success": False, "error": "No staging data available"}
        
        staging_data = json.loads(migration_doc.staging_data)
        sample_mutations = staging_data.get("sample_mutations", [])
        
        if account_code:
            # Filter mutations for specific account
            filtered_mutations = []
            for mutation in sample_mutations:
                for line in mutation.get("MutatieRegels", []):
                    if line.get("TegenrekeningCode") == account_code:
                        filtered_mutations.append(mutation)
                        break
            sample_mutations = filtered_mutations
        
        # Limit the preview
        sample_mutations = sample_mutations[:limit]
        
        preview_results = []
        
        for mutation in sample_mutations:
            # Apply current mapping logic
            from verenigingen.verenigingen.doctype.e_boekhouden_account_mapping.e_boekhouden_account_mapping import get_mapping_for_mutation
            
            document_type = "Purchase Invoice"  # Default
            transaction_category = "General Expenses"
            mapping_name = None
            
            # Check each mutation line for account mapping
            for regel in mutation.get("MutatieRegels", []):
                account_code = regel.get("TegenrekeningCode")
                if account_code:
                    mapping = get_mapping_for_mutation(account_code, mutation.get("Omschrijving", ""))
                    if mapping and mapping.get("name"):
                        document_type = mapping["document_type"]
                        transaction_category = mapping["transaction_category"]
                        mapping_name = mapping["name"]
                        break
            
            preview_results.append({
                "mutation_nr": mutation.get("MutatieNr"),
                "date": mutation.get("Datum"),
                "description": mutation.get("Omschrijving", ""),
                "amount": sum(float(r.get("BedragInclBTW", 0) or 0) for r in mutation.get("MutatieRegels", [])),
                "will_create": document_type,
                "category": transaction_category,
                "mapping_used": mapping_name,
                "account_codes": [r.get("TegenrekeningCode") for r in mutation.get("MutatieRegels", []) if r.get("TegenrekeningCode")]
            })
        
        # Summary statistics
        summary = {
            "total_previewed": len(preview_results),
            "by_document_type": {},
            "by_category": {},
            "unmapped_count": 0
        }
        
        for result in preview_results:
            doc_type = result["will_create"]
            category = result["category"]
            
            summary["by_document_type"][doc_type] = summary["by_document_type"].get(doc_type, 0) + 1
            summary["by_category"][category] = summary["by_category"].get(category, 0) + 1
            
            if not result["mapping_used"]:
                summary["unmapped_count"] += 1
        
        return {
            "success": True,
            "preview": preview_results,
            "summary": summary
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def approve_and_continue_migration(migration_name):
    """Approve current configuration and continue with migration"""
    try:
        migration_doc = frappe.get_doc("E-Boekhouden Migration", migration_name)
        
        if migration_doc.migration_status != "Data Staged":
            return {"success": False, "error": f"Migration must be in 'Data Staged' status, currently: {migration_doc.migration_status}"}
        
        # Update status to continue migration
        migration_doc.db_set({
            "migration_status": "Configuration Approved",
            "current_operation": "Configuration approved - resuming migration...",
            "progress_percentage": 45
        })
        frappe.db.commit()
        
        # Continue with the actual migration
        settings = frappe.get_single("E-Boekhouden Settings")
        
        migration_doc.db_set({
            "current_operation": "Processing transactions with approved configuration...",
            "progress_percentage": 50
        })
        frappe.db.commit()
        
        # Use SOAP API migration with current mappings
        from verenigingen.utils.eboekhouden_soap_migration import migrate_using_soap
        result = migrate_using_soap(migration_doc, settings, True)  # Force use of account mappings
        
        if result["success"]:
            migration_doc.db_set({
                "migration_status": "Completed",
                "current_operation": f"Migration completed successfully",
                "progress_percentage": 100,
                "end_time": frappe.utils.now_datetime()
            })
            
            # Update summary
            summary = f"Migration completed: {result['stats']['invoices_created']} invoices, {result['stats']['payments_processed']} payments created"
            if result["stats"]["errors"]:
                summary += f", {len(result['stats']['errors'])} errors"
            
            migration_doc.db_set("migration_summary", summary)
            frappe.db.commit()
            
            return {
                "success": True,
                "message": summary,
                "stats": result["stats"]
            }
        else:
            migration_doc.db_set({
                "migration_status": "Failed",
                "current_operation": f"Migration failed: {result.get('error', 'Unknown error')}",
                "error_log": str(result.get("error", ""))
            })
            frappe.db.commit()
            
            return {
                "success": False,
                "error": result.get("error", "Migration failed")
            }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_current_account_mappings(company):
    """Get current account mappings for the company"""
    mappings = frappe.get_all("E-Boekhouden Account Mapping",
        filters={"is_active": 1},
        fields=["name", "account_code", "account_name", "description_pattern", 
                "document_type", "transaction_category", "priority", "usage_count",
                "is_manual_override"],
        order_by="priority desc, usage_count desc"
    )
    
    return mappings


def assess_configuration_status(company, staging_data):
    """Assess the configuration readiness for migration"""
    status = {
        "accounts_configured": False,
        "mappings_configured": False,
        "ready_for_migration": False,
        "issues": [],
        "recommendations": []
    }
    
    # Check account configuration
    account_analysis = staging_data.get("account_analysis", {})
    if account_analysis.get("account_type_suggestions"):
        unmapped_accounts = [s for s in account_analysis["account_type_suggestions"] if s["confidence"] < 0.8]
        if unmapped_accounts:
            status["issues"].append(f"{len(unmapped_accounts)} accounts have low confidence type suggestions")
            status["recommendations"].append("Review and manually configure account types for better accuracy")
        else:
            status["accounts_configured"] = True
    
    # Check mapping configuration
    current_mappings = get_current_account_mappings(company)
    mapping_analysis = staging_data.get("mapping_analysis", {})
    
    if mapping_analysis.get("account_usage"):
        unmapped_accounts = []
        for account_code, usage in mapping_analysis["account_usage"].items():
            has_mapping = any(m["account_code"] == account_code for m in current_mappings)
            if not has_mapping and usage["count"] > 1:  # Only care about frequently used accounts
                unmapped_accounts.append(account_code)
        
        if unmapped_accounts:
            status["issues"].append(f"{len(unmapped_accounts)} frequently used accounts have no mappings")
            status["recommendations"].append("Create account mappings for frequently used accounts")
        else:
            status["mappings_configured"] = True
    
    # Overall readiness
    status["ready_for_migration"] = status["accounts_configured"] and status["mappings_configured"]
    
    if status["ready_for_migration"]:
        status["recommendations"].append("Configuration looks good - ready to proceed with migration")
    
    return status


@frappe.whitelist()
def debug_nuclear_cleanup_all_imported_data(company=None):
    """Nuclear option: Aggressively clean up all imported data using direct SQL where needed"""
    try:
        # Get default company if not provided
        if not company:
            settings = frappe.get_single("E-Boekhouden Settings")
            company = settings.default_company
        
        if not company:
            return {"success": False, "error": "No company specified"}
        
        results = {}
        
        # 1. First, nuclear cleanup of ALL GL Entries related to E-Boekhouden
        gl_deleted = 0
        try:
            # Delete GL Entries linked to Payment Entries with mutation numbers
            result = frappe.db.sql("""
                DELETE gl FROM `tabGL Entry` gl
                JOIN `tabPayment Entry` pe ON gl.voucher_no = pe.name
                WHERE gl.company = %s
                AND gl.voucher_type = 'Payment Entry'
                AND (
                    pe.eboekhouden_mutation_nr IS NOT NULL 
                    OR pe.reference_no REGEXP '^[0-9]+$'
                    OR pe.remarks LIKE '%%Mutation Nr:%%'
                )
            """, (company,))
            gl_deleted += result or 0
            
            # Delete GL Entries linked to E-Boekhouden invoices
            result = frappe.db.sql("""
                DELETE gl FROM `tabGL Entry` gl
                JOIN `tabSales Invoice` si ON gl.voucher_no = si.name
                WHERE gl.company = %s
                AND gl.voucher_type = 'Sales Invoice'
                AND si.remarks LIKE '%%e-Boekhouden%%'
            """, (company,))
            gl_deleted += result or 0
            
            result = frappe.db.sql("""
                DELETE gl FROM `tabGL Entry` gl
                JOIN `tabPurchase Invoice` pi ON gl.voucher_no = pi.name
                WHERE gl.company = %s
                AND gl.voucher_type = 'Purchase Invoice'
                AND pi.remarks LIKE '%%e-Boekhouden%%'
            """, (company,))
            gl_deleted += result or 0
            
            # Delete GL Entries linked to Journal Entries
            result = frappe.db.sql("""
                DELETE gl FROM `tabGL Entry` gl
                JOIN `tabJournal Entry` je ON gl.voucher_no = je.name
                WHERE gl.company = %s
                AND gl.voucher_type = 'Journal Entry'
                AND je.user_remark LIKE '%%Migrated from e-Boekhouden%%'
            """, (company,))
            gl_deleted += result or 0
            
            # Delete any remaining GL Entries with e-Boekhouden in remarks
            result = frappe.db.sql("""
                DELETE FROM `tabGL Entry`
                WHERE company = %s
                AND remarks LIKE '%%e-Boekhouden%%'
            """, (company,))
            gl_deleted += result or 0
            
        except Exception as e:
            frappe.log_error(f"Error in nuclear GL Entry cleanup: {str(e)}")
        
        results["gl_entries_deleted"] = gl_deleted
        
        # 2. Nuclear cleanup of Payment Entries
        payment_deleted = 0
        try:
            # Direct SQL deletion of Payment Entries
            result = frappe.db.sql("""
                DELETE FROM `tabPayment Entry`
                WHERE company = %s
                AND (
                    eboekhouden_mutation_nr IS NOT NULL 
                    OR reference_no REGEXP '^[0-9]+$'
                    OR remarks LIKE '%%Mutation Nr:%%'
                )
            """, (company,))
            payment_deleted = result or 0
        except Exception as e:
            frappe.log_error(f"Error in nuclear Payment Entry cleanup: {str(e)}")
        
        results["payment_entries_deleted"] = payment_deleted
        
        # 3. Nuclear cleanup of Journal Entries
        je_deleted = 0
        try:
            result = frappe.db.sql("""
                DELETE FROM `tabJournal Entry`
                WHERE company = %s
                AND user_remark LIKE '%%Migrated from e-Boekhouden%%'
            """, (company,))
            je_deleted = result or 0
        except Exception as e:
            frappe.log_error(f"Error in nuclear Journal Entry cleanup: {str(e)}")
        
        results["journal_entries_deleted"] = je_deleted
        
        # 4. Nuclear cleanup of Sales Invoices
        si_deleted = 0
        try:
            result = frappe.db.sql("""
                DELETE FROM `tabSales Invoice`
                WHERE company = %s
                AND remarks LIKE '%%e-Boekhouden%%'
            """, (company,))
            si_deleted = result or 0
        except Exception as e:
            frappe.log_error(f"Error in nuclear Sales Invoice cleanup: {str(e)}")
        
        results["sales_invoices_deleted"] = si_deleted
        
        # 5. Nuclear cleanup of Purchase Invoices
        pi_deleted = 0
        try:
            result = frappe.db.sql("""
                DELETE FROM `tabPurchase Invoice`
                WHERE company = %s
                AND remarks LIKE '%%e-Boekhouden%%'
            """, (company,))
            pi_deleted = result or 0
        except Exception as e:
            frappe.log_error(f"Error in nuclear Purchase Invoice cleanup: {str(e)}")
        
        results["purchase_invoices_deleted"] = pi_deleted
        
        # 6. Clean up orphaned customer/supplier data (optional)
        customers_deleted = 0
        suppliers_deleted = 0
        try:
            # Only delete if they don't have other transactions
            result = frappe.db.sql("""
                DELETE FROM `tabCustomer`
                WHERE customer_name LIKE '%%e-Boekhouden%%'
                OR customer_name LIKE 'Customer %'
            """)
            customers_deleted = result or 0
            
            result = frappe.db.sql("""
                DELETE FROM `tabSupplier`
                WHERE supplier_name LIKE '%%e-Boekhouden%%'
                OR supplier_name LIKE 'Supplier %'
            """)
            suppliers_deleted = result or 0
        except Exception as e:
            frappe.log_error(f"Error in nuclear Customer/Supplier cleanup: {str(e)}")
        
        results["customers_deleted"] = customers_deleted
        results["suppliers_deleted"] = suppliers_deleted
        
        frappe.db.commit()
        
        return {
            "success": True,
            "message": "Nuclear cleanup completed successfully",
            "results": results
        }
        
    except Exception as e:
        frappe.db.rollback()
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def debug_cleanup_transactions_only(company=None):
    """Debug function to clean up only transaction data (Journal Entries, Payment Entries, etc.)"""
    try:
        # Get default company if not provided
        if not company:
            settings = frappe.get_single("E-Boekhouden Settings")
            company = settings.default_company
        
        if not company:
            return {"success": False, "error": "No company specified"}
        
        results = {}
        
        # Clean up Journal Entries
        journal_entries = frappe.get_all("Journal Entry", 
            filters={
                "company": company,
                "user_remark": ["like", "%Migrated from e-Boekhouden%"]
            })
        
        for je in journal_entries:
            try:
                frappe.delete_doc("Journal Entry", je.name, force=True)
            except:
                pass
        results["journal_entries_deleted"] = len(journal_entries)
        
        # Clean up Payment Entries (using multiple identification methods)
        payment_entries_deleted = 0
        
        # Method 1: By eboekhouden_mutation_nr (most reliable)
        try:
            mutation_nr_entries = frappe.get_all("Payment Entry", filters=[
                ["company", "=", company],
                ["eboekhouden_mutation_nr", "is", "set"],
                ["eboekhouden_mutation_nr", "!=", ""],
                ["docstatus", "!=", 2]
            ])
            
            for pe in mutation_nr_entries:
                try:
                    frappe.delete_doc("Payment Entry", pe.name, force=True)
                    payment_entries_deleted += 1
                except:
                    pass
        except:
            pass
        
        # Method 2: By numeric reference_no (backup method)
        try:
            numeric_ref_entries = frappe.get_all("Payment Entry", filters=[
                ["company", "=", company],
                ["reference_no", "regexp", "^[0-9]+$"],
                ["docstatus", "!=", 2]
            ])
            
            for pe in numeric_ref_entries:
                try:
                    if frappe.db.exists("Payment Entry", pe.name):
                        frappe.delete_doc("Payment Entry", pe.name, force=True)
                        payment_entries_deleted += 1
                except:
                    pass
        except:
            pass
        
        # Method 3: By remarks pattern (catch remaining entries)
        try:
            remarks_entries = frappe.get_all("Payment Entry", filters=[
                ["company", "=", company],
                ["remarks", "like", "%Mutation Nr:%"],
                ["docstatus", "!=", 2]
            ])
            
            for pe in remarks_entries:
                try:
                    if frappe.db.exists("Payment Entry", pe.name):
                        frappe.delete_doc("Payment Entry", pe.name, force=True)
                        payment_entries_deleted += 1
                except:
                    pass
        except:
            pass
        
        results["payment_entries_deleted"] = payment_entries_deleted
        
        # Clean up GL Entries
        gl_entries = frappe.db.get_all("GL Entry", 
            filters={"company": company, "remarks": ["like", "%e-Boekhouden%"]})
        
        for gl in gl_entries:
            try:
                frappe.db.delete("GL Entry", gl.name)
            except:
                pass
        results["gl_entries_deleted"] = len(gl_entries)
        
        frappe.db.commit()
        
        return {
            "success": True,
            "message": "Transaction cleanup completed successfully", 
            "results": results
        }
        
    except Exception as e:
        frappe.db.rollback()
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def debug_get_error_analysis(migration_name=None):
    """Debug function to analyze and categorize errors from the migration"""
    try:
        # Get the most recent migration if none specified
        if not migration_name:
            migration = frappe.get_all("E-Boekhouden Migration", 
                order_by="creation desc", limit=1)
            if migration:
                migration_name = migration[0].name
            else:
                return {"success": False, "error": "No migrations found"}
        
        migration_doc = frappe.get_doc("E-Boekhouden Migration", migration_name)
        
        # Analyze failed records
        failed_records = getattr(migration_doc, 'failed_record_details', [])
        
        error_categories = {}
        error_summary = {
            "total_errors": len(failed_records),
            "parent_account_errors": 0,
            "unknown_errors": 0,
            "validation_errors": 0,
            "other_errors": 0
        }
        
        for record in failed_records:
            error_msg = record.get('error_message', '')
            record_type = record.get('record_type', 'unknown')
            
            # Categorize errors
            if 'parent_account' in error_msg.lower():
                error_summary["parent_account_errors"] += 1
                category = "parent_account"
            elif 'unknown error' in error_msg.lower():
                error_summary["unknown_errors"] += 1
                category = "unknown"
            elif any(word in error_msg.lower() for word in ['validation', 'required', 'invalid']):
                error_summary["validation_errors"] += 1
                category = "validation"
            else:
                error_summary["other_errors"] += 1
                category = "other"
            
            if category not in error_categories:
                error_categories[category] = []
            
            error_categories[category].append({
                "record_type": record_type,
                "error": error_msg,
                "timestamp": record.get('timestamp'),
                "record_data": record.get('record_data', {})
            })
        
        return {
            "success": True,
            "migration_name": migration_name,
            "error_summary": error_summary,
            "error_categories": error_categories,
            "migration_status": migration_doc.migration_status,
            "migration_summary": migration_doc.migration_summary
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def debug_cleanup_payment_entries_only(company=None):
    """Debug function to clean up only e-Boekhouden Payment Entries"""
    try:
        # Get default company if not provided
        if not company:
            settings = frappe.get_single("E-Boekhouden Settings")
            company = settings.default_company
        
        if not company:
            return {"success": False, "error": "No company specified"}
        
        results = {
            "by_mutation_nr": 0,
            "by_reference_no": 0,
            "by_remarks": 0,
            "by_title": 0,
            "total_deleted": 0,
            "errors": []
        }
        
        # Method 1: By eboekhouden_mutation_nr (most reliable)
        try:
            mutation_nr_entries = frappe.get_all("Payment Entry", filters=[
                ["company", "=", company],
                ["eboekhouden_mutation_nr", "is", "set"],
                ["eboekhouden_mutation_nr", "!=", ""],
                ["docstatus", "!=", 2]
            ])
            
            for pe in mutation_nr_entries:
                try:
                    # First cancel if submitted
                    doc = frappe.get_doc("Payment Entry", pe.name)
                    if doc.docstatus == 1:
                        doc.cancel()
                        frappe.db.commit()
                    
                    frappe.delete_doc("Payment Entry", pe.name, force=True)
                    results["by_mutation_nr"] += 1
                except Exception as e:
                    results["errors"].append(f"Failed to delete {pe.name}: {str(e)}")
        except Exception as e:
            results["errors"].append(f"Error querying by mutation_nr: {str(e)}")
        
        # Method 2: By numeric reference_no (backup method)
        try:
            numeric_ref_entries = frappe.get_all("Payment Entry", filters=[
                ["company", "=", company],
                ["reference_no", "regexp", "^[0-9]+$"],
                ["docstatus", "!=", 2]
            ])
            
            for pe in numeric_ref_entries:
                try:
                    if frappe.db.exists("Payment Entry", pe.name):
                        # First cancel if submitted
                        doc = frappe.get_doc("Payment Entry", pe.name)
                        if doc.docstatus == 1:
                            doc.cancel()
                            frappe.db.commit()
                        
                        frappe.delete_doc("Payment Entry", pe.name, force=True)
                        results["by_reference_no"] += 1
                except Exception as e:
                    results["errors"].append(f"Failed to delete {pe.name}: {str(e)}")
        except Exception as e:
            results["errors"].append(f"Error querying by reference_no: {str(e)}")
        
        # Method 3: By remarks pattern (catch remaining entries)
        try:
            remarks_entries = frappe.get_all("Payment Entry", filters=[
                ["company", "=", company],
                ["remarks", "like", "%Mutation Nr:%"],
                ["docstatus", "!=", 2]
            ])
            
            for pe in remarks_entries:
                try:
                    if frappe.db.exists("Payment Entry", pe.name):
                        # First cancel if submitted
                        doc = frappe.get_doc("Payment Entry", pe.name)
                        if doc.docstatus == 1:
                            doc.cancel()
                            frappe.db.commit()
                        
                        frappe.delete_doc("Payment Entry", pe.name, force=True)
                        results["by_remarks"] += 1
                except Exception as e:
                    results["errors"].append(f"Failed to delete {pe.name}: {str(e)}")
        except Exception as e:
            results["errors"].append(f"Error querying by remarks: {str(e)}")
        
        # Method 4: By title pattern (unreconciled payments)
        try:
            title_entries = frappe.get_all("Payment Entry", filters=[
                ["company", "=", company],
                ["title", "like", "%UNRECONCILED%"],
                ["docstatus", "!=", 2]
            ])
            
            for pe in title_entries:
                try:
                    if frappe.db.exists("Payment Entry", pe.name):
                        # First cancel if submitted
                        doc = frappe.get_doc("Payment Entry", pe.name)
                        if doc.docstatus == 1:
                            doc.cancel()
                            frappe.db.commit()
                        
                        frappe.delete_doc("Payment Entry", pe.name, force=True)
                        results["by_title"] += 1
                except Exception as e:
                    results["errors"].append(f"Failed to delete {pe.name}: {str(e)}")
        except Exception as e:
            results["errors"].append(f"Error querying by title: {str(e)}")
        
        results["total_deleted"] = (results["by_mutation_nr"] + 
                                   results["by_reference_no"] + 
                                   results["by_remarks"] +
                                   results["by_title"])
        
        frappe.db.commit()
        
        return {
            "success": True,
            "message": f"Deleted {results['total_deleted']} e-Boekhouden payment entries",
            "details": results
        }
        
    except Exception as e:
        frappe.db.rollback()
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def debug_fix_parent_account_errors(migration_name=None):
    """Debug function to analyze and attempt to fix parent account errors"""
    try:
        # Get the most recent migration if none specified
        if not migration_name:
            migration = frappe.get_all("E-Boekhouden Migration", 
                order_by="creation desc", limit=1)
            if migration:
                migration_name = migration[0].name
            else:
                return {"success": False, "error": "No migrations found"}
        
        migration_doc = frappe.get_doc("E-Boekhouden Migration", migration_name)
        
        # Get company
        settings = frappe.get_single("E-Boekhouden Settings")
        company = settings.default_company
        
        if not company:
            return {"success": False, "error": "No default company set"}
        
        # Get failed records with parent account errors
        failed_records = getattr(migration_doc, 'failed_record_details', [])
        parent_account_errors = []
        
        for record in failed_records:
            error_msg = record.get('error_message', '')
            if 'parent_account' in error_msg.lower():
                parent_account_errors.append(record)
        
        # Analyze the errors and suggest fixes
        fixes_suggested = []
        
        for error_record in parent_account_errors:
            record_data = error_record.get('record_data', {})
            account_code = record_data.get('code', '')
            account_name = record_data.get('description', '')
            
            # Suggest parent account based on account code
            suggested_parent = None
            if account_code.startswith('1'):
                suggested_parent = "Current Assets"
            elif account_code.startswith('2'):
                suggested_parent = "Fixed Assets"
            elif account_code.startswith('3'):
                suggested_parent = "Current Liabilities"
            elif account_code.startswith('4'):
                suggested_parent = "Current Liabilities"
            elif account_code.startswith('5'):
                suggested_parent = "Capital Account"
            elif account_code.startswith('8'):
                suggested_parent = "Direct Income"
            elif account_code.startswith('6') or account_code.startswith('7'):
                suggested_parent = "Direct Expenses"
            
            # Try to find the actual parent account in the system
            if suggested_parent:
                parent_account = frappe.db.get_value("Account", {
                    "company": company,
                    "account_name": ["like", f"%{suggested_parent}%"],
                    "is_group": 1
                }, "name")
                
                if parent_account:
                    fixes_suggested.append({
                        "account_code": account_code,
                        "account_name": account_name,
                        "suggested_parent": parent_account,
                        "error": error_record.get('error_message')
                    })
        
        return {
            "success": True,
            "migration_name": migration_name,
            "total_parent_account_errors": len(parent_account_errors),
            "fixes_suggested": fixes_suggested,
            "company": company
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}
