"""
Enhanced E-Boekhouden Payment Migration

This module provides enhanced migration functionality that properly identifies
and creates Payment Entries for bank and cash transactions from E-Boekhouden.
"""

import frappe
from frappe import _
from frappe.utils import getdate, flt, today
import json
from datetime import datetime

class EBoekhoudenPaymentMigration:
    """Enhanced migration that creates proper Payment Entries"""
    
    def __init__(self, migration_doc=None):
        self.migration_doc = migration_doc
        self.payment_count = 0
        self.journal_count = 0
        self.errors = []
        self._account_cache = {}
        self._relation_cache = {}
        
    def migrate_transactions_enhanced(self, transactions, accounts_mapping, relations_mapping):
        """
        Enhanced transaction migration that creates Payment Entries for payments
        
        Args:
            transactions: List of transaction data from E-Boekhouden
            accounts_mapping: Dict mapping ledger IDs to account codes
            relations_mapping: Dict mapping relation IDs to customer/supplier names
        """
        
        # Build caches
        self._build_account_cache(accounts_mapping)
        self._build_relation_cache(relations_mapping)
        
        # Group transactions by entry number for proper double-entry handling
        grouped_transactions = self._group_transactions_by_entry(transactions)
        
        # Process each transaction group
        for entry_num, trans_group in grouped_transactions.items():
            try:
                self._process_transaction_group(trans_group)
            except Exception as e:
                self.errors.append(f"Error processing entry {entry_num}: {str(e)}")
                frappe.log_error(f"Transaction group error: {str(e)}", "E-Boekhouden Payment Migration")
        
        return {
            "payment_entries_created": self.payment_count,
            "journal_entries_created": self.journal_count,
            "errors": self.errors
        }
    
    def _build_account_cache(self, accounts_mapping):
        """Build cache of ERPNext accounts"""
        for ledger_id, account_code in accounts_mapping.items():
            account = frappe.db.get_value(
                "Account", 
                {"account_number": account_code},
                ["name", "account_type", "root_type"],
                as_dict=True
            )
            if account:
                self._account_cache[ledger_id] = account
    
    def _build_relation_cache(self, relations_mapping):
        """Build cache of customers and suppliers"""
        for relation_id, relation_data in relations_mapping.items():
            # Check if it's a customer
            customer = frappe.db.get_value(
                "Customer",
                {"customer_name": relation_data.get("name")},
                "name"
            )
            if customer:
                self._relation_cache[relation_id] = {
                    "type": "Customer",
                    "name": customer
                }
                continue
            
            # Check if it's a supplier
            supplier = frappe.db.get_value(
                "Supplier",
                {"supplier_name": relation_data.get("name")},
                "name"
            )
            if supplier:
                self._relation_cache[relation_id] = {
                    "type": "Supplier",
                    "name": supplier
                }
    
    def _group_transactions_by_entry(self, transactions):
        """Group transactions by entry number for double-entry processing"""
        grouped = {}
        for trans in transactions:
            entry_num = trans.get("entryNumber", trans.get("id"))
            if entry_num not in grouped:
                grouped[entry_num] = []
            grouped[entry_num].append(trans)
        return grouped
    
    def _process_transaction_group(self, trans_group):
        """Process a group of transactions that form a complete entry"""
        
        # Identify if this is a payment transaction
        payment_info = self._identify_payment_transaction(trans_group)
        
        if payment_info:
            self._create_payment_entry(payment_info)
            self.payment_count += 1
        else:
            # Create regular journal entry for non-payment transactions
            self._create_journal_entry(trans_group)
            self.journal_count += 1
    
    def _identify_payment_transaction(self, trans_group):
        """
        Identify if transaction group represents a payment
        
        Returns dict with payment info if it's a payment, None otherwise
        """
        
        # Look for bank/cash accounts (15xx, 16xx codes)
        bank_cash_trans = None
        party_trans = None
        
        for trans in trans_group:
            ledger_id = str(trans.get("ledgerId", ""))
            account_info = self._account_cache.get(ledger_id)
            
            if not account_info:
                continue
            
            account_code = frappe.db.get_value("Account", account_info["name"], "account_number")
            
            # Check if it's a bank or cash account
            if account_code and (account_code.startswith("15") or account_code.startswith("16")):
                bank_cash_trans = trans
                bank_cash_trans["account_info"] = account_info
            
            # Check if it has a relation (customer/supplier)
            relation_id = trans.get("relationId")
            if relation_id and relation_id in self._relation_cache:
                party_trans = trans
                party_trans["party_info"] = self._relation_cache[relation_id]
        
        # If we have both bank/cash and a party, it's a payment
        if bank_cash_trans and party_trans:
            # Determine payment type and amounts
            amount = abs(float(bank_cash_trans.get("amount", 0)))
            
            # If bank/cash is debit (positive), it's a receipt from customer
            # If bank/cash is credit (negative), it's a payment to supplier
            is_receipt = float(bank_cash_trans.get("amount", 0)) > 0
            
            return {
                "is_receipt": is_receipt,
                "party_type": party_trans["party_info"]["type"],
                "party": party_trans["party_info"]["name"],
                "bank_account": bank_cash_trans["account_info"]["name"],
                "amount": amount,
                "date": trans_group[0].get("date"),
                "description": trans_group[0].get("description", ""),
                "invoice_number": trans_group[0].get("invoiceNumber"),
                "entry_number": trans_group[0].get("entryNumber"),
                "transactions": trans_group
            }
        
        return None
    
    def _create_payment_entry(self, payment_info):
        """Create a Payment Entry for identified payment transaction"""
        
        try:
            # Get settings
            settings = frappe.get_single("E-Boekhouden Settings")
            company = settings.default_company
            
            # Parse date
            posting_date = self._parse_date(payment_info["date"])
            
            # Determine payment type based on party type and direction
            if payment_info["is_receipt"]:
                payment_type = "Receive"
                paid_from = None
                paid_to = payment_info["bank_account"]
            else:
                payment_type = "Pay"
                paid_from = payment_info["bank_account"]
                paid_to = None
            
            # Create payment entry
            payment_entry = frappe.get_doc({
                "doctype": "Payment Entry",
                "payment_type": payment_type,
                "posting_date": posting_date,
                "company": company,
                "party_type": payment_info["party_type"],
                "party": payment_info["party"],
                "paid_amount": payment_info["amount"],
                "received_amount": payment_info["amount"],
                "reference_no": payment_info.get("invoice_number") or payment_info.get("entry_number"),
                "reference_date": posting_date,
                "remarks": f"Migrated from E-Boekhouden: {payment_info.get('description', '')}",
            })
            
            # Set accounts based on payment direction
            if payment_type == "Receive":
                payment_entry.paid_to = paid_to
                # For receipts, paid_from will be set automatically to party's receivable account
            else:
                payment_entry.paid_from = paid_from
                # For payments, paid_to will be set automatically to party's payable account
            
            # If there's an invoice reference, try to link it
            if payment_info.get("invoice_number"):
                self._link_payment_to_invoice(payment_entry, payment_info)
            
            # Save the payment entry
            payment_entry.insert(ignore_permissions=True)
            
            # Add comment with migration details
            frappe.get_doc({
                "doctype": "Comment",
                "comment_type": "Info",
                "reference_doctype": "Payment Entry",
                "reference_name": payment_entry.name,
                "content": f"Migrated from E-Boekhouden entry: {payment_info.get('entry_number')}"
            }).insert(ignore_permissions=True)
            
            return payment_entry.name
            
        except Exception as e:
            frappe.log_error(
                f"Failed to create payment entry: {str(e)}\nPayment info: {json.dumps(payment_info, indent=2)}", 
                "E-Boekhouden Payment Migration"
            )
            raise
    
    def _create_journal_entry(self, trans_group):
        """Create journal entry for non-payment transactions"""
        
        try:
            settings = frappe.get_single("E-Boekhouden Settings")
            company = settings.default_company
            
            # Parse date from first transaction
            posting_date = self._parse_date(trans_group[0].get("date"))
            
            # Build description
            descriptions = []
            for trans in trans_group:
                if trans.get("description"):
                    descriptions.append(trans["description"])
            
            user_remark = " | ".join(descriptions) if descriptions else "Migrated from E-Boekhouden"
            
            # Create journal entry
            journal_entry = frappe.get_doc({
                "doctype": "Journal Entry",
                "posting_date": posting_date,
                "company": company,
                "user_remark": user_remark,
                "accounts": []
            })
            
            # Add account entries
            for trans in trans_group:
                ledger_id = str(trans.get("ledgerId", ""))
                account_info = self._account_cache.get(ledger_id)
                
                if not account_info:
                    continue
                
                amount = float(trans.get("amount", 0))
                
                # E-Boekhouden uses positive for debit, negative for credit
                debit = amount if amount > 0 else 0
                credit = abs(amount) if amount < 0 else 0
                
                journal_entry.append("accounts", {
                    "account": account_info["name"],
                    "debit_in_account_currency": debit,
                    "credit_in_account_currency": credit,
                    "user_remark": trans.get("description", ""),
                    "cost_center": settings.default_cost_center
                })
            
            # Only create if we have valid entries and they balance
            if len(journal_entry.accounts) >= 2:
                journal_entry.insert(ignore_permissions=True)
                return journal_entry.name
            
        except Exception as e:
            frappe.log_error(
                f"Failed to create journal entry: {str(e)}", 
                "E-Boekhouden Payment Migration"
            )
            raise
    
    def _link_payment_to_invoice(self, payment_entry, payment_info):
        """Try to link payment to existing invoice"""
        
        invoice_number = payment_info.get("invoice_number")
        if not invoice_number:
            return
        
        # Search for invoice
        invoice = None
        if payment_info["party_type"] == "Customer":
            invoice = frappe.db.get_value(
                "Sales Invoice",
                {"customer": payment_info["party"], "remarks": ["like", f"%{invoice_number}%"]},
                "name"
            )
        else:  # Supplier
            invoice = frappe.db.get_value(
                "Purchase Invoice",
                {"supplier": payment_info["party"], "remarks": ["like", f"%{invoice_number}%"]},
                "name"
            )
        
        if invoice:
            # Add reference to the invoice
            payment_entry.append("references", {
                "reference_doctype": "Sales Invoice" if payment_info["party_type"] == "Customer" else "Purchase Invoice",
                "reference_name": invoice,
                "allocated_amount": payment_info["amount"]
            })
    
    def _parse_date(self, date_str):
        """Parse date from E-Boekhouden format"""
        if not date_str:
            return today()
        
        try:
            # Handle ISO format with time
            if 'T' in date_str:
                return datetime.strptime(date_str.split('T')[0], '%Y-%m-%d').date()
            else:
                return datetime.strptime(date_str, '%Y-%m-%d').date()
        except:
            return today()


@frappe.whitelist()
def migrate_payments_from_eboekhouden(migration_name=None, date_from=None, date_to=None):
    """
    Migrate payments from E-Boekhouden, creating proper Payment Entries
    
    Can be called directly or from a migration document
    """
    
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        # Get API instance
        api = EBoekhoudenAPI()
        
        # Get chart of accounts for mapping
        accounts_result = api.get_chart_of_accounts()
        if not accounts_result["success"]:
            frappe.throw(_("Failed to get chart of accounts from E-Boekhouden"))
        
        accounts_data = json.loads(accounts_result["data"])
        accounts = accounts_data.get("items", [])
        
        # Build ledger ID to account code mapping
        accounts_mapping = {}
        for account in accounts:
            account_id = str(account.get('id', ''))
            account_code = account.get('code', '')
            if account_id and account_code:
                accounts_mapping[account_id] = account_code
        
        # Get relations for party mapping
        relations_result = api.get_relations()
        if not relations_result["success"]:
            frappe.throw(_("Failed to get relations from E-Boekhouden"))
        
        relations_data = json.loads(relations_result["data"])
        relations = relations_data.get("items", [])
        
        # Build relation mapping
        relations_mapping = {}
        for relation in relations:
            relation_id = str(relation.get('id', ''))
            if relation_id:
                relations_mapping[relation_id] = {
                    "name": relation.get('companyName') or relation.get('name', ''),
                    "type": relation.get('type', '')
                }
        
        # Get transactions
        params = {}
        if date_from:
            params['dateFrom'] = date_from
        if date_to:
            params['dateTo'] = date_to
        
        transactions_result = api.get_mutations(params)
        if not transactions_result["success"]:
            frappe.throw(_("Failed to get transactions from E-Boekhouden"))
        
        transactions_data = json.loads(transactions_result["data"])
        transactions = transactions_data.get("items", [])
        
        # Run enhanced migration
        migrator = EBoekhoudenPaymentMigration()
        result = migrator.migrate_transactions_enhanced(
            transactions, 
            accounts_mapping,
            relations_mapping
        )
        
        frappe.db.commit()
        
        return {
            "success": True,
            "message": _(
                "Migration completed. Created {0} Payment Entries and {1} Journal Entries"
            ).format(result["payment_entries_created"], result["journal_entries_created"]),
            "details": result
        }
        
    except Exception as e:
        frappe.log_error(f"Payment migration error: {str(e)}", "E-Boekhouden Payment Migration")
        frappe.db.rollback()
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def identify_existing_payment_transactions():
    """
    Identify existing journal entries that should have been payment entries
    
    This helps clean up previous migrations
    """
    
    try:
        # Find journal entries from E-Boekhouden migration
        journal_entries = frappe.db.sql("""
            SELECT 
                je.name,
                je.posting_date,
                je.user_remark,
                jea.account,
                jea.debit_in_account_currency,
                jea.credit_in_account_currency,
                acc.account_number,
                acc.account_type
            FROM `tabJournal Entry` je
            JOIN `tabJournal Entry Account` jea ON jea.parent = je.name
            JOIN `tabAccount` acc ON acc.name = jea.account
            WHERE 
                je.user_remark LIKE '%e-Boekhouden%'
                AND (acc.account_number LIKE '15%' OR acc.account_number LIKE '16%')
            ORDER BY je.posting_date DESC
        """, as_dict=True)
        
        # Group by journal entry
        grouped = {}
        for entry in journal_entries:
            if entry.name not in grouped:
                grouped[entry.name] = {
                    "posting_date": entry.posting_date,
                    "user_remark": entry.user_remark,
                    "accounts": []
                }
            grouped[entry.name]["accounts"].append({
                "account": entry.account,
                "account_number": entry.account_number,
                "account_type": entry.account_type,
                "debit": entry.debit_in_account_currency,
                "credit": entry.credit_in_account_currency
            })
        
        # Identify which ones are likely payments
        payment_candidates = []
        for je_name, je_data in grouped.items():
            has_bank_cash = any(
                acc["account_number"].startswith(("15", "16")) 
                for acc in je_data["accounts"]
            )
            
            if has_bank_cash and len(je_data["accounts"]) >= 2:
                payment_candidates.append({
                    "journal_entry": je_name,
                    "date": je_data["posting_date"],
                    "description": je_data["user_remark"],
                    "accounts": je_data["accounts"]
                })
        
        return {
            "success": True,
            "total_journal_entries": len(grouped),
            "payment_candidates": len(payment_candidates),
            "candidates": payment_candidates[:10]  # First 10 as sample
        }
        
    except Exception as e:
        frappe.log_error(f"Error identifying payment transactions: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }