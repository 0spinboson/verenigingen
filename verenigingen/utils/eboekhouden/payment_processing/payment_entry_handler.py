"""
Enhanced payment entry handler for E-Boekhouden payment import.

This module handles the creation of Payment Entries from E-Boekhouden mutations,
including proper bank account mapping and multi-invoice reconciliation support.
"""

import json
from typing import Dict, List, Optional, Tuple

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate


class PaymentEntryHandler:
    """
    Handles creation of Payment Entries from E-Boekhouden mutations.

    Key capabilities:
    - Parses comma-separated invoice numbers
    - Maps rows to specific invoices
    - Handles both single and multi-invoice payments
    - Intelligent bank account determination from ledger mappings
    - Comprehensive error handling and logging
    """

    def __init__(self, company: str, cost_center: str = None):
        self.company = company
        self.cost_center = cost_center or frappe.db.get_value("Company", company, "cost_center")
        self.debug_log = []
        self._ledger_cache = {}  # Cache for ledger mappings

    def process_payment_mutation(self, mutation: Dict) -> Optional[str]:
        """
        Process a payment mutation (types 3 & 4) and create Payment Entry.

        Args:
            mutation: E-Boekhouden mutation data

        Returns:
            Payment Entry name if successful, None otherwise
        """
        try:
            mutation_id = mutation.get("id")
            self._log(f"Processing payment mutation {mutation_id}")

            # Validate mutation type
            mutation_type = mutation.get("type")
            if mutation_type not in [3, 4]:
                self._log(f"ERROR: Invalid mutation type {mutation_type} for payment processing")
                return None

            # Parse invoice numbers
            invoice_numbers = self._parse_invoice_numbers(mutation.get("invoiceNumber"))
            self._log(f"Found {len(invoice_numbers)} invoice(s): {invoice_numbers}")

            # Determine payment type and party
            payment_type = "Receive" if mutation_type == 3 else "Pay"
            party_type = "Customer" if payment_type == "Receive" else "Supplier"

            # Get or create party
            party = self._get_or_create_party(
                mutation.get("relationId"), party_type, mutation.get("description", "")
            )

            if not party:
                self._log(f"ERROR: Could not determine party for mutation {mutation_id}")
                return None

            # Determine bank account from ledger
            bank_account = self._determine_bank_account(
                mutation.get("ledgerId"), payment_type, mutation.get("description")
            )

            if not bank_account:
                self._log(f"ERROR: Could not determine bank account for mutation {mutation_id}")
                return None

            # Create payment entry
            pe = self._create_payment_entry(
                mutation=mutation,
                payment_type=payment_type,
                party_type=party_type,
                party=party,
                bank_account=bank_account,
            )

            # Handle invoice allocations
            if invoice_numbers:
                if mutation.get("rows"):
                    self._allocate_to_invoices(pe, invoice_numbers, mutation["rows"], party_type)
                else:
                    # Single invoice or no rows - simple allocation
                    self._simple_invoice_allocation(pe, invoice_numbers, party_type)

            # Save and submit
            pe.insert(ignore_permissions=True)
            self._log(f"Created Payment Entry {pe.name}")

            pe.submit()
            self._log(f"Submitted Payment Entry {pe.name}")

            return pe.name

        except Exception as e:
            self._log(f"ERROR processing mutation {mutation.get('id')}: {str(e)}")
            frappe.log_error(
                f"Payment mutation processing failed: {str(e)}\nMutation: {json.dumps(mutation, indent=2)}",
                "E-Boekhouden Payment Import",
            )
            return None

    def _parse_invoice_numbers(self, invoice_str: str) -> List[str]:
        """Parse comma-separated invoice numbers."""
        if not invoice_str:
            return []

        # Split by comma and clean up
        invoices = [inv.strip() for inv in str(invoice_str).split(",")]
        return [inv for inv in invoices if inv]

    def _determine_bank_account(
        self, ledger_id: int, payment_type: str, description: str = None
    ) -> Optional[str]:
        """
        Determine bank account from ledger mapping.

        Priority:
        1. Direct ledger mapping to bank/cash account
        2. Payment configuration based on ledger code
        3. Pattern matching from description
        4. Intelligent defaults
        """
        if not ledger_id:
            self._log("WARNING: No ledger ID provided, using defaults")
            return self._get_default_bank_account(payment_type)

        # Check cache first
        cache_key = f"{ledger_id}:{payment_type}"
        if cache_key in self._ledger_cache:
            return self._ledger_cache[cache_key]

        # Try direct mapping
        mapping = frappe.db.get_value(
            "E-Boekhouden Ledger Mapping",
            {"ledger_id": ledger_id},
            ["erpnext_account", "ledger_code", "ledger_name"],
            as_dict=True,
        )

        if mapping and mapping.get("erpnext_account"):
            # Verify it's a bank/cash account
            account_type = frappe.db.get_value("Account", mapping["erpnext_account"], "account_type")

            if account_type in ["Bank", "Cash"]:
                self._log(
                    f"Mapped ledger {ledger_id} ({mapping.get('ledger_name')}) to {mapping['erpnext_account']}"
                )
                self._ledger_cache[cache_key] = mapping["erpnext_account"]
                return mapping["erpnext_account"]
            else:
                self._log(f"WARNING: Ledger {ledger_id} maps to {account_type} account, not Bank/Cash")

        # Try payment configuration based on ledger code
        if mapping and mapping.get("ledger_code"):
            from verenigingen.utils.eboekhouden.eboekhouden_migration_config import get_payment_account_info

            account_info = get_payment_account_info(mapping["ledger_code"], self.company)
            if account_info and account_info.get("erpnext_account"):
                self._log(f"Found bank account via payment config: {account_info['erpnext_account']}")
                self._ledger_cache[cache_key] = account_info["erpnext_account"]
                return account_info["erpnext_account"]

        # Try pattern matching on description
        if description:
            bank_account = self._get_account_from_pattern(description, payment_type)
            if bank_account:
                self._log(f"Found bank account via pattern matching: {bank_account}")
                self._ledger_cache[cache_key] = bank_account
                return bank_account

        # Fallback to defaults
        default_account = self._get_default_bank_account(payment_type)
        self._log(f"Using default bank account: {default_account}")
        self._ledger_cache[cache_key] = default_account
        return default_account

    def _get_account_from_pattern(self, description: str, payment_type: str) -> Optional[str]:
        """Match bank account based on description patterns."""
        patterns = {
            "triodos": "10440 - Triodos - 19.83.96.716 - Algemeen - NVV",
            "paypal": "10470 - PayPal - info@veganisme.org - NVV",
            "asn": "10620 - ASN - 97.88.80.455 - NVV",
            "kas": "10000 - Kas - NVV",
            "cash": "10000 - Kas - NVV",
        }

        description_lower = description.lower()
        for pattern, account in patterns.items():
            if pattern in description_lower:
                # Verify account exists
                if frappe.db.exists("Account", {"name": account, "company": self.company}):
                    return account

        return None

    def _get_default_bank_account(self, payment_type: str) -> str:
        """Get intelligent default account based on payment type."""
        if payment_type == "Receive":
            # Customer payments typically go to main bank account
            # Try Triodos first as it's the main account
            triodos = frappe.db.get_value(
                "Account", {"account_number": "10440", "company": self.company, "disabled": 0}, "name"
            )
            if triodos:
                return triodos

        # Fallback to any active bank account
        bank_account = frappe.db.get_value(
            "Account", {"account_type": "Bank", "company": self.company, "is_group": 0, "disabled": 0}, "name"
        )

        if bank_account:
            return bank_account

        # Last resort - cash account
        return (
            frappe.db.get_value("Account", {"account_number": "10000", "company": self.company}, "name")
            or "10000 - Kas - NVV"
        )

    def _get_or_create_party(self, relation_id: str, party_type: str, description: str) -> Optional[str]:
        """Get existing party or create new one."""
        if not relation_id:
            return None

        # Try to use existing system first, fall back to simple handler if it fails
        try:
            if party_type == "Customer":
                from verenigingen.utils.eboekhouden.eboekhouden_rest_full_migration import (
                    _get_or_create_customer,
                )

                return _get_or_create_customer(relation_id, self.debug_log)
            else:
                from verenigingen.utils.eboekhouden.eboekhouden_rest_full_migration import (
                    _get_or_create_supplier,
                )

                return _get_or_create_supplier(relation_id, description, self.debug_log)
        except Exception as e:
            self._log(f"Error with standard party creation: {str(e)}, using simple handler")

            # Fall back to simple handler
            from verenigingen.utils.eboekhouden.simple_party_handler import (
                get_or_create_customer_simple,
                get_or_create_supplier_simple,
            )

            if party_type == "Customer":
                return get_or_create_customer_simple(relation_id, self.debug_log)
            else:
                return get_or_create_supplier_simple(relation_id, description, self.debug_log)

    def _create_payment_entry(
        self, mutation: Dict, payment_type: str, party_type: str, party: str, bank_account: str
    ) -> frappe._dict:
        """Create the payment entry document."""
        pe = frappe.new_doc("Payment Entry")
        pe.company = self.company
        pe.cost_center = self.cost_center
        pe.posting_date = getdate(mutation.get("date"))
        pe.payment_type = payment_type

        # Set amounts
        amount = abs(flt(mutation.get("amount", 0), 2))
        if payment_type == "Receive":
            pe.received_amount = amount
            pe.paid_amount = amount
        else:
            pe.paid_amount = amount
            pe.received_amount = amount

        # Set party details
        if party:
            pe.party_type = party_type
            pe.party = party

        # Set accounts based on payment type
        if payment_type == "Receive":
            pe.paid_to = bank_account
            if party:
                pe.paid_from = frappe.db.get_value(
                    "Account", {"account_type": "Receivable", "company": self.company}, "name"
                )
        else:
            pe.paid_from = bank_account
            if party:
                pe.paid_to = frappe.db.get_value(
                    "Account", {"account_type": "Payable", "company": self.company}, "name"
                )

        # Set reference details
        invoice_number = mutation.get("invoiceNumber")
        pe.reference_no = invoice_number if invoice_number else f"EB-{mutation.get('id')}"
        pe.reference_date = pe.posting_date

        # Store E-Boekhouden references
        if hasattr(pe, "eboekhouden_mutation_nr"):
            pe.eboekhouden_mutation_nr = str(mutation.get("id"))
        if hasattr(pe, "eboekhouden_mutation_type"):
            pe.eboekhouden_mutation_type = str(mutation.get("type"))

        # Enhanced naming and remarks
        from verenigingen.utils.eboekhouden.eboekhouden_payment_naming import (
            enhance_payment_entry_fields,
            get_payment_entry_title,
        )

        pe.title = get_payment_entry_title(mutation, party, payment_type)
        enhance_payment_entry_fields(pe, mutation)

        # Add detailed remarks
        pe.remarks = self._generate_remarks(mutation, bank_account, party)

        return pe

    def _allocate_to_invoices(
        self, payment_entry: frappe._dict, invoice_numbers: List[str], rows: List[Dict], party_type: str
    ):
        """
        Allocate payment to multiple invoices based on row data.

        Strategy:
        1. If row count matches invoice count - 1:1 mapping
        2. Otherwise, use FIFO allocation
        """
        invoice_doctype = "Sales Invoice" if party_type == "Customer" else "Purchase Invoice"

        # Get invoice details
        invoices = self._find_invoices(invoice_numbers, invoice_doctype, payment_entry.party)

        if not invoices:
            self._log("WARNING: No matching invoices found for allocation")
            return

        # Prepare row amounts (absolute values)
        row_amounts = [abs(flt(row.get("amount", 0))) for row in rows]

        # Log allocation strategy
        self._log(f"Allocating {len(row_amounts)} row(s) to {len(invoices)} invoice(s)")

        # Allocate based on strategy
        if len(invoices) == len(rows) and len(invoices) > 1:
            # 1:1 mapping
            self._log("Using 1:1 row-to-invoice mapping")
            self._allocate_one_to_one(payment_entry, invoices, row_amounts)
        else:
            # FIFO allocation
            self._log("Using FIFO allocation strategy")
            self._allocate_fifo(payment_entry, invoices, row_amounts)

    def _allocate_one_to_one(
        self, payment_entry: frappe._dict, invoices: List[Dict], row_amounts: List[float]
    ):
        """Allocate with 1:1 mapping between rows and invoices."""
        for invoice, amount in zip(invoices, row_amounts):
            allocation = min(amount, invoice["outstanding_amount"])

            payment_entry.append(
                "references",
                {
                    "reference_doctype": invoice["doctype"],
                    "reference_name": invoice["name"],
                    "total_amount": invoice["grand_total"],
                    "outstanding_amount": invoice["outstanding_amount"],
                    "allocated_amount": allocation,
                },
            )

            self._log(f"Allocated {allocation} to {invoice['name']} (1:1 mapping)")

    def _allocate_fifo(self, payment_entry: frappe._dict, invoices: List[Dict], row_amounts: List[float]):
        """Allocate using FIFO strategy."""
        total_to_allocate = (
            sum(row_amounts) if row_amounts else payment_entry.paid_amount or payment_entry.received_amount
        )

        for invoice in invoices:
            if total_to_allocate <= 0:
                break

            allocation = min(total_to_allocate, invoice["outstanding_amount"])

            payment_entry.append(
                "references",
                {
                    "reference_doctype": invoice["doctype"],
                    "reference_name": invoice["name"],
                    "total_amount": invoice["grand_total"],
                    "outstanding_amount": invoice["outstanding_amount"],
                    "allocated_amount": allocation,
                },
            )

            total_to_allocate -= allocation
            self._log(f"Allocated {allocation} to {invoice['name']} (FIFO)")

        if total_to_allocate > 0:
            self._log(f"WARNING: {total_to_allocate} remains unallocated")

    def _simple_invoice_allocation(
        self, payment_entry: frappe._dict, invoice_numbers: List[str], party_type: str
    ):
        """Simple allocation for payments without row details."""
        invoice_doctype = "Sales Invoice" if party_type == "Customer" else "Purchase Invoice"
        invoices = self._find_invoices(invoice_numbers, invoice_doctype, payment_entry.party)

        if invoices:
            # Use FIFO allocation with total payment amount
            self._allocate_fifo(payment_entry, invoices, [])

    def _find_invoices(self, invoice_numbers: List[str], doctype: str, party: str) -> List[Dict]:
        """Find invoices matching the given numbers."""
        invoices = []
        party_field = "customer" if doctype == "Sales Invoice" else "supplier"

        for invoice_num in invoice_numbers:
            # Try multiple matching strategies
            matches = self._find_invoice_by_number(invoice_num, doctype, party_field, party)
            invoices.extend(matches)

        # Remove duplicates and sort by date for FIFO
        seen = set()
        unique_invoices = []
        for inv in invoices:
            if inv["name"] not in seen:
                seen.add(inv["name"])
                unique_invoices.append(inv)

        unique_invoices.sort(key=lambda x: x.get("posting_date", ""))

        return unique_invoices

    def _find_invoice_by_number(
        self, invoice_num: str, doctype: str, party_field: str, party: str
    ) -> List[Dict]:
        """Find invoice using multiple strategies."""
        # Strategy 1: E-Boekhouden invoice number field
        if frappe.db.has_column(doctype, "eboekhouden_invoice_number"):
            invoices = frappe.get_all(
                doctype,
                filters={
                    party_field: party,
                    "eboekhouden_invoice_number": invoice_num,
                    "docstatus": 1,
                    "outstanding_amount": [">", 0],
                },
                fields=["name", "grand_total", "outstanding_amount", "posting_date"],
            )

            if invoices:
                for inv in invoices:
                    inv["doctype"] = doctype
                self._log(f"Found invoice {invoices[0]['name']} via eboekhouden_invoice_number")
                return invoices

        # Strategy 2: Exact name match
        invoices = frappe.get_all(
            doctype,
            filters={party_field: party, "name": invoice_num, "docstatus": 1, "outstanding_amount": [">", 0]},
            fields=["name", "grand_total", "outstanding_amount", "posting_date"],
        )

        if invoices:
            for inv in invoices:
                inv["doctype"] = doctype
            self._log(f"Found invoice {invoices[0]['name']} via exact name match")
            return invoices

        # Strategy 3: Partial match (last resort)
        invoices = frappe.get_all(
            doctype,
            filters={
                party_field: party,
                "name": ["like", f"%{invoice_num}%"],
                "docstatus": 1,
                "outstanding_amount": [">", 0],
            },
            fields=["name", "grand_total", "outstanding_amount", "posting_date"],
            limit=1,
        )

        if invoices:
            for inv in invoices:
                inv["doctype"] = doctype
            self._log(f"Found invoice {invoices[0]['name']} via partial match")
            return invoices

        self._log(f"No invoice found for number: {invoice_num}")
        return []

    def _generate_remarks(self, mutation: Dict, bank_account: str, party: str) -> str:
        """Generate detailed remarks for audit trail."""
        remarks = []

        remarks.append(f"E-Boekhouden Import - Mutation {mutation.get('id')}")
        remarks.append(f"Type: {'Customer Payment' if mutation.get('type') == 3 else 'Supplier Payment'}")
        remarks.append(f"Bank Account: {bank_account}")

        if party:
            remarks.append(f"Party: {party} (Relation ID: {mutation.get('relationId')})")

        if mutation.get("invoiceNumber"):
            remarks.append(f"Invoice(s): {mutation.get('invoiceNumber')}")

        if mutation.get("description"):
            remarks.append(f"Description: {mutation.get('description')}")

        if mutation.get("rows"):
            remarks.append(f"Row count: {len(mutation.get('rows'))}")

        remarks.append(f"Original Ledger ID: {mutation.get('ledgerId')}")

        return "\n".join(remarks)

    def _log(self, message: str):
        """Add to debug log."""
        timestamp = nowdate()
        self.debug_log.append(f"{timestamp} {message}")
        frappe.logger().info(f"PaymentHandler: {message}")

    def get_debug_log(self) -> List[str]:
        """Get the debug log for inspection."""
        return self.debug_log
