"""
E-Boekhouden Simplified Migration
Uses native transaction types instead of complex pattern matching
"""

import frappe
from frappe import _
from frappe.utils import getdate, flt
from .eboekhouden_transaction_type_mapper import simplify_migration_process, get_payment_entry_reference_type

class SimplifiedEBoekhoudenMigration:
    """Simplified migration using native E-Boekhouden transaction types"""
    
    def __init__(self, settings=None):
        self.settings = settings or frappe.get_single("E-Boekhouden Settings")
        self.stats = {
            "sales_invoices": 0,
            "purchase_invoices": 0,
            "payment_entries": 0,
            "journal_entries": 0,
            "skipped": 0,
            "errors": []
        }
    
    def process_mutation(self, mutation_data):
        """
        Process a single mutation using native transaction type
        
        Args:
            mutation_data: Dict containing mutation from E-Boekhouden with 'Soort' field
            
        Returns:
            Dict with processing result
        """
        try:
            # Get the simplified mapping
            mapping = simplify_migration_process(mutation_data)
            
            # Log the mapping decision
            frappe.logger().info(
                f"Mutation {mutation_data.get('MutatieNr')}: "
                f"{mapping['transaction_type']} → {mapping['document_type']}"
            )
            
            # Route to appropriate handler based on document type
            if mapping["document_type"] == "Sales Invoice":
                return self._create_sales_invoice(mutation_data)
            elif mapping["document_type"] == "Purchase Invoice":
                return self._create_purchase_invoice(mutation_data)
            elif mapping["document_type"] == "Payment Entry":
                return self._create_payment_entry(mutation_data, mapping)
            elif mapping["document_type"] == "Journal Entry":
                return self._create_journal_entry(mutation_data)
            else:
                self.stats["skipped"] += 1
                return {
                    "success": False,
                    "reason": f"Unknown document type: {mapping['document_type']}"
                }
                
        except Exception as e:
            self.stats["errors"].append({
                "mutation": mutation_data.get("MutatieNr"),
                "error": str(e)
            })
            return {
                "success": False,
                "error": str(e)
            }
    
    def _create_sales_invoice(self, mutation_data):
        """Create Sales Invoice from mutation"""
        try:
            # Extract relevant fields
            invoice_date = getdate(mutation_data.get("Datum"))
            customer_id = mutation_data.get("RelatieId")
            amount = flt(mutation_data.get("Bedrag", 0))
            invoice_number = mutation_data.get("FactuurNummer")
            description = mutation_data.get("Omschrijving", "")
            
            # Get or create customer
            customer = self._get_or_create_customer(customer_id)
            
            # Create sales invoice
            invoice = frappe.new_doc("Sales Invoice")
            invoice.customer = customer
            invoice.posting_date = invoice_date
            invoice.due_date = invoice_date  # Adjust based on payment terms
            invoice.company = self.settings.default_company
            
            # Add line item
            invoice.append("items", {
                "item_code": self._get_default_item("income"),
                "description": description,
                "qty": 1,
                "rate": amount
            })
            
            # Set E-Boekhouden reference
            invoice.eboekhouden_invoice_number = invoice_number
            invoice.eboekhouden_mutation_nr = mutation_data.get("MutatieNr")
            
            invoice.insert(ignore_permissions=True)
            invoice.submit()
            
            self.stats["sales_invoices"] += 1
            
            return {
                "success": True,
                "document": invoice.name,
                "doctype": "Sales Invoice"
            }
            
        except Exception as e:
            frappe.log_error(f"Failed to create sales invoice: {str(e)}")
            raise
    
    def _create_purchase_invoice(self, mutation_data):
        """Create Purchase Invoice from mutation"""
        try:
            # Extract relevant fields
            invoice_date = getdate(mutation_data.get("Datum"))
            supplier_id = mutation_data.get("RelatieId")
            amount = flt(mutation_data.get("Bedrag", 0))
            invoice_number = mutation_data.get("FactuurNummer")
            description = mutation_data.get("Omschrijving", "")
            
            # Get or create supplier
            supplier = self._get_or_create_supplier(supplier_id)
            
            # Create purchase invoice
            invoice = frappe.new_doc("Purchase Invoice")
            invoice.supplier = supplier
            invoice.posting_date = invoice_date
            invoice.due_date = invoice_date
            invoice.company = self.settings.default_company
            
            # Add line item
            invoice.append("items", {
                "item_code": self._get_default_item("expense"),
                "description": description,
                "qty": 1,
                "rate": amount
            })
            
            # Set E-Boekhouden reference
            invoice.eboekhouden_invoice_number = invoice_number
            invoice.eboekhouden_mutation_nr = mutation_data.get("MutatieNr")
            
            invoice.insert(ignore_permissions=True)
            invoice.submit()
            
            self.stats["purchase_invoices"] += 1
            
            return {
                "success": True,
                "document": invoice.name,
                "doctype": "Purchase Invoice"
            }
            
        except Exception as e:
            frappe.log_error(f"Failed to create purchase invoice: {str(e)}")
            raise
    
    def _create_payment_entry(self, mutation_data, mapping):
        """Create Payment Entry from mutation"""
        try:
            # Determine if this is payment for sales or purchase invoice
            reference_type = mapping.get("reference_type")
            
            if not reference_type:
                # Fallback to checking transaction type
                transaction_type = mutation_data.get("Soort", "").lower()
                if "ontvangen" in transaction_type:
                    reference_type = "Sales Invoice"
                else:
                    reference_type = "Purchase Invoice"
            
            # Extract fields
            payment_date = getdate(mutation_data.get("Datum"))
            party_id = mutation_data.get("RelatieId")
            amount = abs(flt(mutation_data.get("Bedrag", 0)))
            reference_no = mutation_data.get("FactuurNummer")
            
            # Create payment entry
            payment = frappe.new_doc("Payment Entry")
            payment.payment_type = "Receive" if reference_type == "Sales Invoice" else "Pay"
            payment.posting_date = payment_date
            payment.company = self.settings.default_company
            
            if reference_type == "Sales Invoice":
                payment.party_type = "Customer"
                payment.party = self._get_or_create_customer(party_id)
                payment.paid_from = self.settings.default_receivable_account
                payment.paid_to = self._get_bank_account(mutation_data)
            else:
                payment.party_type = "Supplier"
                payment.party = self._get_or_create_supplier(party_id)
                payment.paid_from = self._get_bank_account(mutation_data)
                payment.paid_to = self.settings.default_payable_account
            
            payment.paid_amount = amount
            payment.received_amount = amount
            
            # Try to link to invoice if reference number exists
            if reference_no:
                invoice = self._find_invoice_by_reference(reference_no, reference_type)
                if invoice:
                    payment.append("references", {
                        "reference_doctype": reference_type,
                        "reference_name": invoice,
                        "allocated_amount": amount
                    })
            
            # Set E-Boekhouden reference
            payment.eboekhouden_mutation_nr = mutation_data.get("MutatieNr")
            
            payment.insert(ignore_permissions=True)
            payment.submit()
            
            self.stats["payment_entries"] += 1
            
            return {
                "success": True,
                "document": payment.name,
                "doctype": "Payment Entry"
            }
            
        except Exception as e:
            frappe.log_error(f"Failed to create payment entry: {str(e)}")
            raise
    
    def _create_journal_entry(self, mutation_data):
        """Create Journal Entry from mutation"""
        try:
            # For now, create a simple journal entry
            # This would need more logic for complex entries
            
            entry_date = getdate(mutation_data.get("Datum"))
            amount = flt(mutation_data.get("Bedrag", 0))
            description = mutation_data.get("Omschrijving", "")
            
            journal = frappe.new_doc("Journal Entry")
            journal.posting_date = entry_date
            journal.company = self.settings.default_company
            journal.user_remark = description
            
            # Simple debit/credit based on amount sign
            if amount >= 0:
                journal.append("accounts", {
                    "account": self._get_default_account("misc_income"),
                    "debit_in_account_currency": amount
                })
                journal.append("accounts", {
                    "account": self._get_bank_account(mutation_data),
                    "credit_in_account_currency": amount
                })
            else:
                journal.append("accounts", {
                    "account": self._get_default_account("misc_expense"),
                    "credit_in_account_currency": abs(amount)
                })
                journal.append("accounts", {
                    "account": self._get_bank_account(mutation_data),
                    "debit_in_account_currency": abs(amount)
                })
            
            # Set E-Boekhouden reference
            journal.eboekhouden_mutation_nr = mutation_data.get("MutatieNr")
            
            journal.insert(ignore_permissions=True)
            journal.submit()
            
            self.stats["journal_entries"] += 1
            
            return {
                "success": True,
                "document": journal.name,
                "doctype": "Journal Entry"
            }
            
        except Exception as e:
            frappe.log_error(f"Failed to create journal entry: {str(e)}")
            raise
    
    # Helper methods would go here...
    def _get_or_create_customer(self, customer_id):
        # Implementation would fetch from cache or create
        return "Guest"
    
    def _get_or_create_supplier(self, supplier_id):
        # Implementation would fetch from cache or create
        return "Miscellaneous Supplier"
    
    def _get_bank_account(self, mutation_data):
        # Would map E-Boekhouden account to ERPNext account
        return self.settings.default_bank_account
    
    def _get_default_item(self, item_type):
        # Would return appropriate default item
        return "ITEM-001"
    
    def _find_invoice_by_reference(self, reference_no, doctype):
        # Would search for invoice by E-Boekhouden reference
        return None
    
    def _get_default_account(self, account_type):
        # Would return appropriate default account
        return "Miscellaneous"

@frappe.whitelist()
def migrate_with_native_types(start_date=None, end_date=None):
    """
    Run migration using native E-Boekhouden transaction types
    """
    from .eboekhouden_soap_api import EBoekhoudenSOAPAPI
    
    try:
        # Initialize
        migrator = SimplifiedEBoekhoudenMigration()
        api = EBoekhoudenSOAPAPI()
        
        # Fetch mutations
        result = api.get_mutations(date_from=start_date, date_to=end_date)
        
        if not result["success"]:
            return {"success": False, "error": result.get("error")}
        
        # Process each mutation
        for mutation in result["mutations"]:
            migrator.process_mutation(mutation)
        
        # Return statistics
        return {
            "success": True,
            "stats": migrator.stats,
            "message": f"Processed {len(result['mutations'])} mutations"
        }
        
    except Exception as e:
        frappe.log_error(f"Migration failed: {str(e)}", "E-Boekhouden Migration")
        return {"success": False, "error": str(e)}