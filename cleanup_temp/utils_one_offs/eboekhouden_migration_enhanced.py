"""
Enhanced E-Boekhouden Migration with Proper Payment Handling

This module provides the enhanced migration logic that will be integrated
into the main E-Boekhouden migration doctype to properly handle payments.
"""

import frappe
from frappe import _
from frappe.utils import getdate, flt, today
import json
from datetime import datetime


class EnhancedEBoekhoudenMigration:
    """Enhanced migration handler that properly identifies and creates payment entries"""
    
    def __init__(self, settings=None):
        self.settings = settings or frappe.get_single("E-Boekhouden Settings")
        self.stats = {
            "payment_entries": 0,
            "journal_entries": 0,
            "skipped": 0,
            "errors": []
        }
        
        # Define Dutch bank account patterns
        # These are typical ranges for Dutch accounting
        self.bank_account_patterns = [
            (1100, 1199),  # Traditional bank accounts range
            (1200, 1299),  # Additional bank accounts
            (1000, 1099),  # Some systems use 10xx for bank accounts
        ]
        
        # Cash account patterns
        self.cash_account_patterns = [
            (1600, 1699),  # Cash accounts
            (1001, 1001),  # Some use 1001 for main cash
        ]
        
        # Build cache for account lookups
        self._account_cache = {}
        self._relation_cache = {}
        
    def is_bank_account(self, account_code):
        """Check if account code represents a bank account"""
        if not account_code:
            return False
            
        # Try to parse as integer
        try:
            code_num = int(account_code)
            for start, end in self.bank_account_patterns:
                if start <= code_num <= end:
                    return True
        except ValueError:
            pass
            
        return False
    
    def is_cash_account(self, account_code):
        """Check if account code represents a cash account"""
        if not account_code:
            return False
            
        try:
            code_num = int(account_code)
            for start, end in self.cash_account_patterns:
                if start <= code_num <= end:
                    return True
        except ValueError:
            pass
            
        return False
    
    def migrate_transaction_batch(self, transactions, account_mapping, relation_mapping):
        """
        Migrate a batch of transactions with proper payment identification
        
        Args:
            transactions: List of transaction objects from E-Boekhouden
            account_mapping: Dict mapping ledger IDs to account info
            relation_mapping: Dict mapping relation IDs to party info
        """
        
        # Build caches
        self._build_caches(account_mapping, relation_mapping)
        
        # Group transactions by entry number
        grouped = self._group_by_entry(transactions)
        
        # Process each group
        for entry_id, trans_group in grouped.items():
            try:
                self._process_entry_group(trans_group)
            except Exception as e:
                self.stats["errors"].append({
                    "entry": entry_id,
                    "error": str(e),
                    "transactions": trans_group
                })
                frappe.log_error(f"Migration error for entry {entry_id}: {str(e)}", 
                               "E-Boekhouden Migration")
        
        return self.stats
    
    def _build_caches(self, account_mapping, relation_mapping):
        """Build internal caches for efficient lookups"""
        
        # Account cache - ledger ID to ERPNext account info
        for ledger_id, account_info in account_mapping.items():
            account_code = account_info.get("code", "")
            erpnext_account = frappe.db.get_value(
                "Account",
                {"account_number": account_code},
                ["name", "account_type", "root_type"],
                as_dict=True
            )
            if erpnext_account:
                self._account_cache[str(ledger_id)] = {
                    **erpnext_account,
                    "account_code": account_code,
                    "is_bank": self.is_bank_account(account_code),
                    "is_cash": self.is_cash_account(account_code)
                }
        
        # Relation cache - relation ID to party info
        for relation_id, relation_info in relation_mapping.items():
            party_name = relation_info.get("name", "")
            
            # Check if customer exists
            customer = frappe.db.get_value("Customer", {"customer_name": party_name})
            if customer:
                self._relation_cache[str(relation_id)] = {
                    "party_type": "Customer",
                    "party": customer
                }
                continue
                
            # Check if supplier exists
            supplier = frappe.db.get_value("Supplier", {"supplier_name": party_name})
            if supplier:
                self._relation_cache[str(relation_id)] = {
                    "party_type": "Supplier", 
                    "party": supplier
                }
    
    def _group_by_entry(self, transactions):
        """Group transactions by entry number for double-entry processing"""
        grouped = {}
        
        for trans in transactions:
            # Use entry number as grouping key, fallback to ID
            entry_key = trans.get("entryNumber") or trans.get("id")
            
            if entry_key not in grouped:
                grouped[entry_key] = []
            grouped[entry_key].append(trans)
            
        return grouped
    
    def _process_entry_group(self, trans_group):
        """Process a group of transactions forming one accounting entry"""
        
        # Analyze the group to determine entry type
        analysis = self._analyze_entry_group(trans_group)
        
        if analysis["is_payment"]:
            self._create_payment_entry(analysis)
            self.stats["payment_entries"] += 1
        elif analysis["skip"]:
            self.stats["skipped"] += 1
        else:
            self._create_journal_entry(trans_group)
            self.stats["journal_entries"] += 1
    
    def _analyze_entry_group(self, trans_group):
        """
        Analyze transaction group to determine if it's a payment
        
        Returns dict with analysis results
        """
        
        result = {
            "is_payment": False,
            "skip": False,
            "payment_info": None,
            "has_bank_or_cash": False,
            "has_party": False,
            "transactions": trans_group
        }
        
        # Look for key components
        bank_cash_trans = None
        party_trans = None
        
        for trans in trans_group:
            ledger_id = str(trans.get("ledgerId", ""))
            account_info = self._account_cache.get(ledger_id)
            
            if not account_info:
                continue
                
            # Check for bank/cash account
            if account_info.get("is_bank") or account_info.get("is_cash"):
                bank_cash_trans = trans
                bank_cash_trans["_account_info"] = account_info
                result["has_bank_or_cash"] = True
            
            # Check for party relation
            relation_id = str(trans.get("relationId", ""))
            if relation_id and relation_id in self._relation_cache:
                party_trans = trans
                party_trans["_party_info"] = self._relation_cache[relation_id]
                result["has_party"] = True
            
            # Skip stock accounts
            if account_info.get("account_type") == "Stock":
                result["skip"] = True
                return result
        
        # If we have bank/cash AND a party, it's a payment
        if bank_cash_trans and party_trans:
            amount = abs(float(bank_cash_trans.get("amount", 0)))
            is_receipt = float(bank_cash_trans.get("amount", 0)) > 0
            
            result["is_payment"] = True
            result["payment_info"] = {
                "bank_cash_account": bank_cash_trans["_account_info"]["name"],
                "bank_cash_type": "Bank" if bank_cash_trans["_account_info"]["is_bank"] else "Cash",
                "party_type": party_trans["_party_info"]["party_type"],
                "party": party_trans["_party_info"]["party"],
                "amount": amount,
                "is_receipt": is_receipt,
                "payment_type": "Receive" if is_receipt else "Pay",
                "date": trans_group[0].get("date"),
                "description": trans_group[0].get("description", ""),
                "invoice_number": trans_group[0].get("invoiceNumber"),
                "entry_number": trans_group[0].get("entryNumber")
            }
        
        return result
    
    def _create_payment_entry(self, analysis):
        """Create a payment entry from analyzed transaction group"""
        
        payment_info = analysis["payment_info"]
        
        try:
            # Create payment entry document
            pe = frappe.new_doc("Payment Entry")
            pe.payment_type = payment_info["payment_type"]
            pe.posting_date = self._parse_date(payment_info["date"])
            pe.company = self.settings.default_company
            pe.party_type = payment_info["party_type"]
            pe.party = payment_info["party"]
            
            # Set amounts
            pe.paid_amount = payment_info["amount"]
            pe.received_amount = payment_info["amount"]
            
            # Set payment account based on type
            if payment_info["payment_type"] == "Receive":
                pe.paid_to = payment_info["bank_cash_account"]
                # paid_from will be set automatically from party
            else:
                pe.paid_from = payment_info["bank_cash_account"]
                # paid_to will be set automatically from party
            
            # Set references
            if payment_info.get("invoice_number"):
                pe.reference_no = payment_info["invoice_number"]
            elif payment_info.get("entry_number"):
                pe.reference_no = f"EB-{payment_info['entry_number']}"
            
            pe.reference_date = pe.posting_date
            
            # Add remarks
            remarks = [
                f"Migrated from E-Boekhouden",
                f"Entry: {payment_info.get('entry_number', 'N/A')}",
                f"Type: {payment_info['bank_cash_type']} {payment_info['payment_type']}"
            ]
            if payment_info.get("description"):
                remarks.append(f"Description: {payment_info['description']}")
            
            pe.remarks = "\n".join(remarks)
            
            # Mode of payment
            pe.mode_of_payment = self._get_mode_of_payment(payment_info["bank_cash_type"])
            
            # Insert the payment entry
            pe.insert(ignore_permissions=True)
            
            # Log success
            frappe.log_error(
                f"Created payment entry {pe.name} for E-Boekhouden entry {payment_info.get('entry_number')}",
                "E-Boekhouden Migration Success"
            )
            
            return pe.name
            
        except Exception as e:
            frappe.log_error(
                f"Failed to create payment entry: {str(e)}\nInfo: {json.dumps(payment_info, indent=2)}",
                "E-Boekhouden Payment Creation Error"
            )
            raise
    
    def _create_journal_entry(self, trans_group):
        """Create journal entry for non-payment transactions"""
        
        try:
            je = frappe.new_doc("Journal Entry")
            je.posting_date = self._parse_date(trans_group[0].get("date"))
            je.company = self.settings.default_company
            
            # Build description
            descriptions = []
            entry_nums = set()
            
            for trans in trans_group:
                if trans.get("description"):
                    descriptions.append(trans["description"])
                if trans.get("entryNumber"):
                    entry_nums.add(trans["entryNumber"])
                    
            je.user_remark = " | ".join(descriptions) if descriptions else "Migrated from E-Boekhouden"
            if entry_nums:
                je.user_remark += f" (Entry: {', '.join(entry_nums)})"
            
            # Add accounts
            for trans in trans_group:
                ledger_id = str(trans.get("ledgerId", ""))
                account_info = self._account_cache.get(ledger_id)
                
                if not account_info:
                    continue
                
                amount = float(trans.get("amount", 0))
                if amount == 0:
                    continue
                
                # E-Boekhouden typically uses positive for debit, negative for credit
                je.append("accounts", {
                    "account": account_info["name"],
                    "debit_in_account_currency": amount if amount > 0 else 0,
                    "credit_in_account_currency": abs(amount) if amount < 0 else 0,
                    "user_remark": trans.get("description", ""),
                    "cost_center": self.settings.default_cost_center
                })
            
            # Only save if we have valid entries
            if len(je.accounts) >= 2:
                je.insert(ignore_permissions=True)
                return je.name
            else:
                self.stats["skipped"] += 1
                
        except Exception as e:
            frappe.log_error(
                f"Failed to create journal entry: {str(e)}",
                "E-Boekhouden Journal Creation Error"
            )
            raise
    
    def _parse_date(self, date_str):
        """Parse date from various formats"""
        if not date_str:
            return today()
            
        try:
            # ISO format with time
            if 'T' in date_str:
                return datetime.strptime(date_str.split('T')[0], '%Y-%m-%d').date()
            # Standard date format
            else:
                return datetime.strptime(date_str, '%Y-%m-%d').date()
        except:
            return today()
    
    def _get_mode_of_payment(self, payment_type):
        """Get or create appropriate mode of payment"""
        
        if payment_type == "Bank":
            mode_name = "Bank Transfer"
        else:
            mode_name = "Cash"
            
        # Check if mode exists
        if not frappe.db.exists("Mode of Payment", mode_name):
            # Create it
            mode = frappe.new_doc("Mode of Payment")
            mode.mode_of_payment = mode_name
            mode.type = payment_type
            mode.insert(ignore_permissions=True)
            
        return mode_name


@frappe.whitelist()
def analyze_account_structure():
    """
    Analyze E-Boekhouden account structure to identify bank accounts
    """
    
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        api = EBoekhoudenAPI()
        
        # Get all accounts
        result = api.get_chart_of_accounts()
        if not result["success"]:
            return {"success": False, "error": "Failed to get accounts"}
            
        accounts = json.loads(result["data"]).get("items", [])
        
        # Categorize accounts
        analysis = {
            "potential_bank_accounts": [],
            "potential_cash_accounts": [],
            "vat_accounts": [],
            "receivable_accounts": [],
            "payable_accounts": [],
            "other_accounts": []
        }
        
        # Analyze each account
        for account in accounts:
            code = account.get("code", "")
            name = account.get("description", "")
            
            try:
                code_num = int(code)
                
                # Check typical Dutch bank account ranges
                if 1000 <= code_num <= 1199:
                    analysis["potential_bank_accounts"].append({
                        "code": code,
                        "name": name,
                        "likely_type": "Bank account"
                    })
                elif 1600 <= code_num <= 1699:
                    analysis["potential_cash_accounts"].append({
                        "code": code,
                        "name": name,
                        "likely_type": "Cash account"
                    })
                elif 1500 <= code_num <= 1599:
                    analysis["vat_accounts"].append({
                        "code": code,
                        "name": name,
                        "likely_type": "VAT/BTW account"
                    })
                elif 1300 <= code_num <= 1399:
                    analysis["receivable_accounts"].append({
                        "code": code,
                        "name": name,
                        "likely_type": "Accounts Receivable"
                    })
                elif 4400 <= code_num <= 4499:
                    analysis["payable_accounts"].append({
                        "code": code,
                        "name": name,
                        "likely_type": "Accounts Payable"
                    })
                else:
                    analysis["other_accounts"].append({
                        "code": code,
                        "name": name
                    })
                    
            except ValueError:
                # Non-numeric codes
                analysis["other_accounts"].append({
                    "code": code,
                    "name": name
                })
        
        # Look for keyword matches in account names
        bank_keywords = ["bank", "ing", "rabo", "abn", "triodos", "bunq", "knab"]
        cash_keywords = ["kas", "cash", "contant"]
        
        for account in analysis["other_accounts"][:]:
            name_lower = account["name"].lower()
            
            if any(keyword in name_lower for keyword in bank_keywords):
                account["likely_type"] = "Bank account (by name)"
                analysis["potential_bank_accounts"].append(account)
                analysis["other_accounts"].remove(account)
            elif any(keyword in name_lower for keyword in cash_keywords):
                account["likely_type"] = "Cash account (by name)"
                analysis["potential_cash_accounts"].append(account)
                analysis["other_accounts"].remove(account)
        
        return {
            "success": True,
            "total_accounts": len(accounts),
            "analysis": analysis,
            "recommendations": {
                "likely_bank_accounts": len(analysis["potential_bank_accounts"]),
                "likely_cash_accounts": len(analysis["potential_cash_accounts"]),
                "message": "Review the potential bank and cash accounts to confirm which ones represent actual payment accounts"
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Account structure analysis error: {str(e)}")
        return {"success": False, "error": str(e)}