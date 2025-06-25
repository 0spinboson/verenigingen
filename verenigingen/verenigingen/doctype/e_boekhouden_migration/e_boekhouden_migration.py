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
        if getattr(self, 'migrate_transactions', 0) and not (self.date_from and self.date_to):
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
            if not settings.api_token:
                frappe.throw("E-Boekhouden Settings not configured. Please configure API token first.")
            
            # Initialize counters
            self.total_records = 0
            self.imported_records = 0
            self.failed_records = 0
            
            migration_log = []
            
            # Phase 1: Chart of Accounts
            if getattr(self, 'migrate_accounts', 0):
                self.current_operation = "Migrating Chart of Accounts..."
                self.progress_percentage = 10
                self.save()
                
                result = self.migrate_chart_of_accounts(settings)
                migration_log.append(f"Chart of Accounts: {result}")
            
            # Phase 2: Cost Centers
            if getattr(self, 'migrate_cost_centers', 0):
                self.current_operation = "Migrating Cost Centers..."
                self.progress_percentage = 20
                self.save()
                
                result = self.migrate_cost_centers(settings)
                migration_log.append(f"Cost Centers: {result}")
            
            # Phase 3: Customers
            if getattr(self, 'migrate_customers', 0):
                self.current_operation = "Migrating Customers..."
                self.progress_percentage = 40
                self.save()
                
                result = self.migrate_customers(settings)
                migration_log.append(f"Customers: {result}")
            
            # Phase 4: Suppliers
            if getattr(self, 'migrate_suppliers', 0):
                self.current_operation = "Migrating Suppliers..."
                self.progress_percentage = 60
                self.save()
                
                result = self.migrate_suppliers(settings)
                migration_log.append(f"Suppliers: {result}")
            
            # Phase 5: Transactions
            if getattr(self, 'migrate_transactions', 0):
                self.current_operation = "Migrating Transactions..."
                self.progress_percentage = 80
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
                return f"Dry Run: Found {len(accounts_data)} accounts to migrate"
            
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
                    self.log_error(f"Failed to create account {account_data.get('code', 'Unknown')}: {str(e)}")
            
            self.total_records += len(accounts_data)
            return f"Created {created_count} accounts, skipped {skipped_count} ({len(accounts_data)} total)"
            
        except Exception as e:
            return f"Error migrating Chart of Accounts: {str(e)}"
    
    def migrate_cost_centers(self, settings):
        """Migrate Cost Centers from e-Boekhouden"""
        try:
            from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
            
            # Get Cost Centers data using new API
            api = EBoekhoudenAPI(settings)
            result = api.get_cost_centers()
            
            if not result["success"]:
                return f"Failed to fetch Cost Centers: {result['error']}"
            
            # Parse JSON response
            import json
            data = json.loads(result["data"])
            cost_centers_data = data.get("items", [])
            
            if self.dry_run:
                return f"Dry Run: Found {len(cost_centers_data)} cost centers to migrate"
            
            # Create cost centers in ERPNext
            created_count = 0
            skipped_count = 0
            
            for cost_center_data in cost_centers_data:
                try:
                    if self.create_cost_center(cost_center_data):
                        created_count += 1
                        self.imported_records += 1
                    else:
                        skipped_count += 1
                except Exception as e:
                    self.failed_records += 1
                    self.log_error(f"Failed to create cost center {cost_center_data.get('description', 'Unknown')}: {str(e)}")
            
            self.total_records += len(cost_centers_data)
            return f"Created {created_count} cost centers, skipped {skipped_count} ({len(cost_centers_data)} total)"
            
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
        """Migrate Transactions from e-Boekhouden"""
        try:
            from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
            
            # Get Mutations data using new API
            api = EBoekhoudenAPI(settings)
            
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
                
                # Get transactions for this month using new API
                params = {
                    "dateFrom": current_date.strftime("%Y-%m-%d"),
                    "dateTo": month_end.strftime("%Y-%m-%d")
                }
                result = api.get_mutations(params)
                
                if result["success"]:
                    # Parse JSON response
                    import json
                    data = json.loads(result["data"])
                    transactions_data = data.get("items", [])
                    
                    if self.dry_run:
                        total_created += len(transactions_data)
                    else:
                        # Create journal entries
                        for transaction_data in transactions_data:
                            try:
                                if self.create_journal_entry(transaction_data):
                                    total_created += 1
                                    self.imported_records += 1
                            except Exception as e:
                                self.failed_records += 1
                                self.log_error(f"Failed to create transaction: {str(e)}")
                
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
    
    def log_error(self, message):
        """Log error message"""
        frappe.log_error(message, "E-Boekhouden Migration")
        if hasattr(self, 'error_details'):
            self.error_details += f"\n{message}"
        else:
            self.error_details = message
    
    def create_account(self, account_data):
        """Create Account in ERPNext"""
        try:
            # Map e-Boekhouden account to ERPNext account
            account_code = account_data.get('code', '')
            account_name = account_data.get('description', '')
            category = account_data.get('category', '')
            
            if not account_code or not account_name:
                self.log_error(f"Invalid account data: code={account_code}, name={account_name}")
                return False
            
            # Check if account already exists
            if frappe.db.exists("Account", {"account_number": account_code}):
                self.log_error(f"Account {account_code} already exists, skipping")
                return False
            
            # Map e-Boekhouden categories to ERPNext account types
            account_type_mapping = {
                'BTWRC': 'Tax',
                'AF6': 'Tax', 
                'AF19': 'Tax',
                'AFOVERIG': 'Tax',
                'VOOR': 'Tax',
                'VW': 'Expense',
                'BAL': 'Asset',
                'FIN': 'Bank',
                'KAS': 'Cash'
            }
            
            account_type = account_type_mapping.get(category, 'Expense')  # Default to Expense
            
            # Determine root type based on account type
            root_type_mapping = {
                'Asset': 'Asset',
                'Bank': 'Asset', 
                'Cash': 'Asset',
                'Liability': 'Liability',
                'Equity': 'Equity',
                'Income': 'Income',
                'Expense': 'Expense',
                'Tax': 'Liability'
            }
            
            root_type = root_type_mapping.get(account_type, 'Expense')
            
            # Get default company
            settings = frappe.get_single("E-Boekhouden Settings")
            company = settings.default_company
            
            if not company:
                self.log_error("No default company set in E-Boekhouden Settings")
                return False
            
            # Find appropriate parent account
            parent_account = self.get_parent_account(account_type, root_type, company)
            
            # Create new account
            account = frappe.get_doc({
                'doctype': 'Account',
                'account_name': account_name,
                'account_number': account_code,
                'parent_account': parent_account,
                'company': company,
                'account_type': account_type if account_type != 'Expense' else None,
                'root_type': root_type,
                'is_group': 0,
                'disabled': 0
            })
            
            account.insert(ignore_permissions=True)
            self.log_error(f"Created account: {account_code} - {account_name}")
            return True
            
        except Exception as e:
            self.log_error(f"Failed to create account {account_code}: {str(e)}")
            return False
    
    def get_parent_account(self, account_type, root_type, company):
        """Get appropriate parent account for the new account"""
        try:
            # Try to find existing parent accounts
            if account_type == 'Tax':
                # Look for Tax Assets or Duties and Taxes
                parent = frappe.db.get_value("Account", {
                    "company": company,
                    "account_name": ["in", ["Tax Assets", "Duties and Taxes", "VAT"]],
                    "is_group": 1
                }, "name")
                if parent:
                    return parent
            
            elif account_type == 'Bank':
                parent = frappe.db.get_value("Account", {
                    "company": company,
                    "account_type": "Bank",
                    "is_group": 1
                }, "name")
                if parent:
                    return parent
            
            elif account_type == 'Cash':
                parent = frappe.db.get_value("Account", {
                    "company": company,
                    "account_type": "Cash",
                    "is_group": 1
                }, "name")
                if parent:
                    return parent
            
            # Fallback to root account based on root_type
            root_account = frappe.db.get_value("Account", {
                "company": company,
                "root_type": root_type,
                "is_group": 1,
                "parent_account": ""
            }, "name")
            
            return root_account
            
        except Exception as e:
            self.log_error(f"Error finding parent account: {str(e)}")
            # Return the first root account as last resort
            return frappe.db.get_value("Account", {
                "company": company,
                "is_group": 1,
                "parent_account": ""
            }, "name")
    
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
            
            # Check if cost center already exists
            if frappe.db.exists("Cost Center", {"cost_center_name": description}):
                self.log_error(f"Cost Center '{description}' already exists, skipping")
                return False
            
            # Get default company
            settings = frappe.get_single("E-Boekhouden Settings")
            company = settings.default_company
            
            if not company:
                self.log_error("No default company set in E-Boekhouden Settings")
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
                self.log_error(f"No parent cost center found for company {company}")
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
            self.log_error(f"Created cost center: {description}")
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
            
            # Use company name if available, otherwise contact name, otherwise name
            display_name = company_name or contact_name or customer_name
            
            if not display_name:
                self.log_error(f"Invalid customer data: no name available")
                return False
            
            # Check if customer already exists
            if frappe.db.exists("Customer", {"customer_name": display_name}):
                self.log_error(f"Customer '{display_name}' already exists, skipping")
                return False
            
            # Get default settings
            settings = frappe.get_single("E-Boekhouden Settings")
            
            # Create new customer
            customer = frappe.get_doc({
                'doctype': 'Customer',
                'customer_name': display_name,
                'customer_type': 'Company' if company_name else 'Individual',
                'customer_group': 'All Customer Groups',  # Default customer group
                'territory': 'All Territories',  # Default territory
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
            
            self.log_error(f"Created customer: {display_name}")
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
            
            # Use company name if available, otherwise contact name, otherwise name
            display_name = company_name or contact_name or supplier_name
            
            if not display_name:
                self.log_error(f"Invalid supplier data: no name available")
                return False
            
            # Check if supplier already exists
            if frappe.db.exists("Supplier", {"supplier_name": display_name}):
                self.log_error(f"Supplier '{display_name}' already exists, skipping")
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
            
            self.log_error(f"Created supplier: {display_name}")
            return True
            
        except Exception as e:
            self.log_error(f"Failed to create supplier {display_name}: {str(e)}")
            return False
    
    def create_journal_entry(self, transaction_data):
        """Create Journal Entry in ERPNext"""
        try:
            # Map e-Boekhouden transaction to ERPNext journal entry
            transaction_date = transaction_data.get('date', '')
            description = transaction_data.get('description', '').strip()
            debit_amount = float(transaction_data.get('debit', 0) or 0)
            credit_amount = float(transaction_data.get('credit', 0) or 0)
            account_code = transaction_data.get('accountCode', '')
            
            if not transaction_date or not description:
                self.log_error(f"Invalid transaction data: missing date or description")
                return False
            
            if debit_amount == 0 and credit_amount == 0:
                self.log_error(f"Invalid transaction data: no amount specified")
                return False
            
            # Find the account in ERPNext
            account = frappe.db.get_value("Account", {"account_number": account_code}, "name")
            if not account:
                self.log_error(f"Account {account_code} not found in ERPNext")
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
            self.log_error(f"Created journal entry: {description}")
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
            self.log_error(f"Created contact for customer: {customer_name}")
            
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
            self.log_error(f"Created contact for supplier: {supplier_name}")
            
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
            self.log_error(f"Created address for customer: {customer_name}")
            
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
            self.log_error(f"Created address for supplier: {supplier_name}")
            
        except Exception as e:
            self.log_error(f"Failed to create address for supplier {supplier_name}: {str(e)}")
    
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