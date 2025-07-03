"""
E-Boekhouden Migration with Improved Logging

Enhanced migration functions that use aggregated logging
"""

import frappe
from frappe import _
from .eboekhouden_migration_logger import MigrationLogger


class EBoekhoudenMigrationImproved:
    """Improved migration class with better logging"""
    
    def __init__(self, migration_doc):
        self.migration_doc = migration_doc
        self.logger = MigrationLogger(migration_doc.name)
        
    def migrate_chart_of_accounts(self):
        """Migrate chart of accounts with improved logging"""
        try:
            from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
            
            settings = frappe.get_single("E-Boekhouden Settings")
            api = EBoekhoudenAPI(settings)
            
            # Get Chart of Accounts
            self.logger.log_info("Fetching chart of accounts from E-Boekhouden")
            result = api.get_chart_of_accounts()
            
            if not result["success"]:
                self.logger.log_error("api_error", f"Failed to fetch Chart of Accounts: {result['error']}")
                return False
            
            # Parse response
            import json
            data = json.loads(result["data"])
            accounts_data = data.get("items", [])
            
            self.logger.log_info(f"Found {len(accounts_data)} accounts to process")
            
            # Process accounts
            for account_data in accounts_data:
                account_code = account_data.get('code', '')
                account_name = account_data.get('description', '')
                
                try:
                    # Check if account exists
                    existing = frappe.db.exists("Account", {
                        "account_number": account_code,
                        "company": self.migration_doc.company
                    })
                    
                    if existing:
                        # Update existing account
                        self._update_account(existing, account_data)
                        self.logger.log_success("account_updated", f"{account_code} - {account_name}")
                    else:
                        # Create new account
                        self._create_account(account_data)
                        self.logger.log_success("account_created", f"{account_code} - {account_name}")
                        
                except Exception as e:
                    self.logger.log_error(
                        "account_failed",
                        str(e),
                        {"code": account_code, "name": account_name}
                    )
            
            # Save summary
            summary = self.logger.get_formatted_summary()
            self.migration_doc.migration_summary = summary
            self.migration_doc.save()
            
            # Log only if there were errors
            self.logger.save_to_log()
            
            return True
            
        except Exception as e:
            self.logger.log_error("migration_failed", str(e))
            self.logger.save_to_log()
            raise
    
    def migrate_transactions(self, from_date, to_date):
        """Migrate transactions with improved logging"""
        try:
            from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
            
            settings = frappe.get_single("E-Boekhouden Settings")
            api = EBoekhoudenAPI(settings)
            
            # Get transactions
            self.logger.log_info(f"Fetching transactions from {from_date} to {to_date}")
            
            params = {
                "dateFrom": from_date,
                "dateTo": to_date
            }
            
            result = api.get_mutations(params)
            
            if not result["success"]:
                self.logger.log_error("api_error", f"Failed to fetch transactions: {result['error']}")
                return False
            
            # Parse response
            import json
            data = json.loads(result["data"])
            transactions = data.get("items", [])
            
            self.logger.log_info(f"Found {len(transactions)} transactions to process")
            
            # Group transactions by entry number
            entry_groups = {}
            for trans in transactions:
                entry_num = trans.get("entryNumber", trans.get("id"))
                if entry_num not in entry_groups:
                    entry_groups[entry_num] = []
                entry_groups[entry_num].append(trans)
            
            # Process each entry group
            for entry_num, transactions in entry_groups.items():
                try:
                    self._create_journal_entry(entry_num, transactions)
                    self.logger.log_success("journal_entry_created", f"Entry {entry_num}")
                    
                except Exception as e:
                    # Extract meaningful error info
                    error_msg = str(e)
                    if "Missing mandatory fields" in error_msg:
                        self.logger.log_error(
                            "journal_entry_failed",
                            "Missing mandatory fields",
                            {"entry": entry_num, "full_error": error_msg}
                        )
                    elif "does not exist" in error_msg:
                        self.logger.log_error(
                            "journal_entry_failed",
                            "Account does not exist",
                            {"entry": entry_num, "full_error": error_msg}
                        )
                    else:
                        self.logger.log_error(
                            "journal_entry_failed",
                            error_msg,
                            {"entry": entry_num}
                        )
            
            # Save summary
            summary = self.logger.get_formatted_summary()
            self.migration_doc.migration_summary = summary
            self.migration_doc.save()
            
            # Log only if there were errors
            self.logger.save_to_log()
            
            return True
            
        except Exception as e:
            self.logger.log_error("migration_failed", str(e))
            self.logger.save_to_log()
            raise
    
    def _create_account(self, account_data):
        """Create account - implementation details"""
        # This would contain the actual account creation logic
        # For now, just a placeholder
        pass
    
    def _update_account(self, account_name, account_data):
        """Update account - implementation details"""
        # This would contain the actual account update logic
        # For now, just a placeholder
        pass
    
    def _create_journal_entry(self, entry_num, transactions):
        """Create journal entry - implementation details"""
        # This would contain the actual journal entry creation logic
        # For now, just a placeholder
        pass


@frappe.whitelist()
def migrate_with_improved_logging(migration_name):
    """
    Run migration with improved logging
    """
    try:
        migration_doc = frappe.get_doc("E-Boekhouden Migration", migration_name)
        improved_migration = EBoekhoudenMigrationImproved(migration_doc)
        
        # Run migration steps
        if migration_doc.migrate_chart_of_accounts:
            improved_migration.migrate_chart_of_accounts()
        
        if migration_doc.migrate_transactions:
            improved_migration.migrate_transactions(
                migration_doc.date_from,
                migration_doc.date_to
            )
        
        return {
            "success": True,
            "summary": improved_migration.logger.get_summary()
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }