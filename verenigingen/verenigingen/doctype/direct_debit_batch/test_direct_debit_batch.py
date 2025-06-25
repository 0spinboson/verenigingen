import frappe
import unittest
import random
import string
import os
import xml.etree.ElementTree as ET
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today, nowdate, add_days, flt
from verenigingen.verenigingen.tests.test_setup import setup_test_environment
from verenigingen.verenigingen.tests.patch_test_runner import patch_test_runner

class TestDirectDebitBatch(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        # Set up the test environment and patch the test runner
        setup_test_environment()
        patch_test_runner()
        super().setUpClass()
        
    def setUp(self):
        # Generate a unique identifier for test data
        self.unique_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        
        # Create test settings
        self.setup_verenigingen_settings()
        
        # Create test member with unique name
        self.member = self.create_test_member()
        
        # Create test mandate
        self.mandate = self.create_test_mandate()
        
        # Create test memberships and invoices
        self.memberships = []
        self.invoices = []
        self.create_test_membership_and_invoice(100.00)
    
    def tearDown(self):
        # Clean up test data
        self.cleanup_test_data()
    
    def setup_verenigingen_settings(self):
        """Set up or update Verenigingen Settings"""
        if not frappe.db.exists("Verenigingen Settings"):
            settings = frappe.new_doc("Verenigingen Settings")
            settings.company = "_Test Company"
            settings.company_iban = "NL43INGB0123456789"
            settings.company_bic = "INGBNL2A"
            settings.creditor_id = "NL13ZZZ123456780000"
            settings.save()
        else:
            settings = frappe.get_doc("Verenigingen Settings")
            settings.company = "_Test Company"
            settings.company_iban = "NL43INGB0123456789"
            settings.company_bic = "INGBNL2A"
            settings.creditor_id = "NL13ZZZ123456780000"
            settings.save()
            
        # Create test Item and Item Group for Membership if they don't exist
        if not frappe.db.exists("Item Group", "Membership"):
            item_group = frappe.new_doc("Item Group")
            item_group.item_group_name = "Membership"
            item_group.parent_item_group = "All Item Groups"
            item_group.insert()
        
        # Create test item for membership
        item_code = f"TEST-ITEM-{self.unique_id}"
        if not frappe.db.exists("Item", item_code):
            # Get the test warehouse
            test_warehouse = None
            if frappe.db.exists("Warehouse", "_Test Warehouse - _TC"):
                test_warehouse = "_Test Warehouse - _TC"
                
            item = frappe.new_doc("Item")
            item.item_code = item_code
            item.item_name = f"Test Membership Item {self.unique_id}"
            item.item_group = "Membership"
            item.is_stock_item = 0  # Non-stock item to avoid warehouse requirements
            item.include_item_in_manufacturing = 0
            item.is_service_item = 1
            
            # Only add item_defaults if we have a valid test warehouse
            if test_warehouse:
                item.append("item_defaults", {
                    "company": "_Test Company",
                    "default_warehouse": test_warehouse
                })
            
            # Set flags to bypass strict validation
            item.flags.ignore_mandatory = True
            item.insert(ignore_permissions=True)
            self.test_item = item.name
    
    def create_test_member(self):
        """Create a test member with unique name"""
        member_email = f"testsepa{self.unique_id}@example.com"
        if frappe.db.exists("Member", {"email": member_email}):
            return frappe.get_doc("Member", {"email": member_email})
            
        member = frappe.new_doc("Member")
        member.first_name = f"Test{self.unique_id}"
        member.last_name = "Member"
        member.email = member_email
        member.iban = "NL43INGB9876543210"
        member.bank_account_name = f"Test{self.unique_id} Member"
        member.insert()
        
        # Create a test customer for this member
        if not member.customer:
            member.create_customer()
            member.reload()
            
        return member
    
    def create_test_mandate(self):
        """Create a test SEPA mandate"""
        # Check if mandate already exists for this member
        existing_mandates = frappe.get_all("SEPA Mandate", 
            filters={"member": self.member.name},
            fields=["name"]
        )
        
        if existing_mandates:
            return frappe.get_doc("SEPA Mandate", existing_mandates[0].name)
            
        mandate = frappe.new_doc("SEPA Mandate")
        mandate.mandate_id = f"TEST-MANDATE-{self.unique_id}"
        mandate.member = self.member.name
        mandate.account_holder_name = self.member.full_name
        mandate.iban = self.member.iban
        mandate.sign_date = today()
        mandate.status = "Active"
        mandate.is_active = 1
        mandate.insert()
        return mandate
    
    def create_membership_type(self):
        """Create a test membership type"""
        type_name = f"Test Type {self.unique_id}"
        
        if frappe.db.exists("Membership Type", type_name):
            return frappe.get_doc("Membership Type", type_name)
            
        membership_type = frappe.new_doc("Membership Type")
        membership_type.membership_type_name = type_name
        membership_type.description = "Test membership type for unit tests"
        membership_type.subscription_period = "Annual"
        membership_type.amount = 120
        membership_type.currency = "EUR"
        membership_type.is_active = 1
        membership_type.insert()
        
        return membership_type
    
    def create_minimal_invoice(self, amount=100.00):
        """Create a minimal but real invoice for testing"""
        invoice_name = f"SINV-TEST-{frappe.utils.random_string(10)}"
        
        # Check if invoice exists
        if frappe.db.exists("Sales Invoice", invoice_name):
            return invoice_name
            
        # Create a new invoice with minimal required fields
        invoice = frappe.new_doc("Sales Invoice")
        invoice.name = invoice_name  # Set name explicitly
        invoice.customer = self.member.customer
        invoice.posting_date = today()
        invoice.due_date = add_days(today(), 30)
        invoice.company = "_Test Company"
        invoice.currency = "EUR"
        
        # Add at least one item
        invoice.append("items", {
            "item_code": self.test_item,
            "qty": 1,
            "rate": amount,
            "amount": amount
        })
        
        # Set flags to bypass validation
        invoice.flags.ignore_permissions = True
        invoice.flags.ignore_validate = True
        invoice.flags.ignore_mandatory = True
        
        # Insert directly to database
        invoice.db_insert()
        
        # Set status and docstatus directly
        frappe.db.set_value("Sales Invoice", invoice_name, "status", "Unpaid")
        frappe.db.set_value("Sales Invoice", invoice_name, "docstatus", 1)
        frappe.db.set_value("Sales Invoice", invoice_name, "grand_total", amount)
        frappe.db.set_value("Sales Invoice", invoice_name, "outstanding_amount", amount)
        
        return invoice_name
    
    def create_test_membership_and_invoice(self, amount=100.00):
        """Create a test membership and invoice for testing"""
        # Create membership type if needed
        membership_type = self.create_membership_type()
        
        # Create membership
        membership = frappe.new_doc("Membership")
        membership.member = self.member.name
        membership.membership_type = membership_type.name
        membership.start_date = today()
        membership.email = self.member.email
        
        # Set flags to bypass strict validation
        membership.flags.ignore_permissions = True
        membership.flags.ignore_mandatory = True
        membership.insert()
        
        # Create a real invoice with minimal setup
        invoice_name = self.create_minimal_invoice(amount)
        
        # Add to arrays for tracking
        self.memberships.append(membership.name)
        self.invoices.append(invoice_name)
        
        return membership.name, invoice_name
    
    def create_test_batch(self):
        """Create a test direct debit batch with invoices"""
        if not self.invoices or not self.memberships:
            # Create a membership and invoice if we don't have any
            self.create_test_membership_and_invoice()
        
        batch = frappe.new_doc("SEPA Direct Debit Batch")
        batch.batch_date = today()
        batch.batch_description = f"Test Batch {self.unique_id}"
        batch.batch_type = "RCUR"
        batch.currency = "EUR"
        
        # Add invoice reference
        batch.append("invoices", {
            "invoice": self.invoices[0],
            "membership": self.memberships[0],
            "member": self.member.name,
            "member_name": self.member.full_name,
            "amount": 100.00,
            "currency": "EUR",
            "bank_account": "",
            "iban": self.member.iban,
            "mandate_reference": self.mandate.mandate_id,
            "status": "Pending"
        })
        
        batch.insert()
        return batch
    
    def cleanup_test_data(self):
        """Clean up all test data"""
        # Clean up batches
        for b in frappe.get_all("SEPA Direct Debit Batch", 
                filters={"batch_description": ["like", f"Test Batch {self.unique_id}%"]}):
            try:
                batch_doc = frappe.get_doc("SEPA Direct Debit Batch", b.name)
                if batch_doc.docstatus == 1:
                    batch_doc.cancel()
                frappe.delete_doc("SEPA Direct Debit Batch", b.name, force=True)
            except Exception as e:
                print(f"Error cleaning up batch {b.name}: {str(e)}")
        
        # Clean up invoices
        for inv in self.invoices:
            try:
                # First check if the invoice exists and is submitted
                if frappe.db.exists("Sales Invoice", inv):
                    doc_status = frappe.db.get_value("Sales Invoice", inv, "docstatus")
                    if doc_status == 1:
                        # If it's a submitted doc, we need to cancel it first
                        frappe.db.set_value("Sales Invoice", inv, "docstatus", 2)
                    # Then delete it
                    frappe.db.delete("Sales Invoice", inv)
            except Exception as e:
                print(f"Error cleaning up invoice {inv}: {str(e)}")
        
        # Clean up memberships
        for mem in self.memberships:
            try:
                if frappe.db.exists("Membership", mem):
                    doc_status = frappe.db.get_value("Membership", mem, "docstatus")
                    if doc_status == 1:
                        # If it's a submitted doc, we need to cancel it first
                        frappe.db.set_value("Membership", mem, "docstatus", 2)
                    # Then delete it
                    frappe.delete_doc("Membership", mem, force=True)
            except Exception as e:
                print(f"Error cleaning up membership {mem}: {str(e)}")
        
        # Clean up mandates
        for m in frappe.get_all("SEPA Mandate", 
                filters={"mandate_id": ["like", f"TEST-MANDATE-{self.unique_id}"]}):
            try:
                frappe.delete_doc("SEPA Mandate", m.name, force=True)
            except Exception as e:
                print(f"Error cleaning up mandate {m.name}: {str(e)}")
        
        # Clean up members
        for m in frappe.get_all("Member", 
                filters={"email": ["like", f"testsepa{self.unique_id}@example.com"]}):
            try:
                frappe.delete_doc("Member", m.name, force=True)
            except Exception as e:
                print(f"Error cleaning up member {m.name}: {str(e)}")
        
        # Clean up membership types
        for mt in frappe.get_all("Membership Type", 
                filters={"membership_type_name": ["like", f"Test Type {self.unique_id}"]}):
            try:
                frappe.delete_doc("Membership Type", mt.name, force=True)
            except Exception as e:
                print(f"Error cleaning up membership type {mt.name}: {str(e)}")
                
        # Clean up test items
        if hasattr(self, 'test_item') and frappe.db.exists("Item", self.test_item):
            try:
                frappe.delete_doc("Item", self.test_item, force=True)
            except Exception as e:
                print(f"Error cleaning up item {self.test_item}: {str(e)}")
    
    def test_generate_sepa_xml(self):
        """Test the SEPA XML generation function"""
        # Create a test batch
        batch = self.create_test_batch()
        
        try:
            # Generate SEPA file
            xml_file = batch.generate_sepa_xml()
            
            # Verify file was created
            self.assertTrue(xml_file, "SEPA XML file was not generated")
            
            # Verify status was updated
            batch.reload()
            self.assertEqual(batch.status, "Generated", "Batch status not updated to Generated")
            self.assertTrue(batch.sepa_file_generated, "sepa_file_generated flag not set")
        finally:
            # Clean up
            if batch.docstatus == 1:
                batch.cancel()
            batch.delete()
    
    def test_batch_calculation(self):
        """Test batch total amount and entry count calculation"""
        # Create a batch with multiple invoices
        batch = frappe.new_doc("SEPA Direct Debit Batch")
        batch.batch_date = today()
        batch.batch_description = f"Test Batch {self.unique_id}"
        batch.batch_type = "RCUR"
        batch.currency = "EUR"
        
        # Add multiple invoices with different amounts
        amounts = [100.00, 75.50, 200.25]
        
        # Create mock memberships and invoices with various amounts
        invoice_data = []
        for amount in amounts:
            membership, invoice = self.create_test_membership_and_invoice(amount)
            invoice_data.append({
                "invoice": invoice,
                "membership": membership,
                "amount": amount
            })
        
        # Add invoices to batch
        for data in invoice_data:
            batch.append("invoices", {
                "invoice": data["invoice"],
                "membership": data["membership"],
                "member": self.member.name,
                "member_name": self.member.full_name,
                "amount": data["amount"],
                "currency": "EUR",
                "bank_account": "",
                "iban": self.member.iban,
                "mandate_reference": self.mandate.mandate_id,
                "status": "Pending"
            })
        
        try:
            batch.insert()
            
            # Verify calculation
            expected_total = sum(amounts)
            self.assertEqual(flt(batch.total_amount), flt(expected_total), "Total amount calculation incorrect")
            self.assertEqual(batch.entry_count, len(amounts), "Entry count calculation incorrect")
        finally:
            # Clean up
            if batch.docstatus == 1:
                batch.cancel()
            batch.delete()
    
    def test_submission_workflow(self):
        """Test batch submission workflow"""
        # Create a batch
        batch = self.create_test_batch()
        
        try:
            # Submit the batch
            batch.docstatus = 1
            batch.save()
            
            # Force reload to get the updated document
            frappe.db.commit()
            batch = frappe.get_doc("SEPA Direct Debit Batch", batch.name)
            
            # Verify sepa_file_generated flag set after submission
            self.assertTrue(batch.sepa_file_generated, "SEPA file not generated on submit")
            self.assertEqual(batch.status, "Generated", "Status not updated to Generated on submit")
        finally:
            # Cancel the batch - make sure to reload first
            if batch.docstatus == 1:
                # Get fresh copy of the document to prevent timestamp mismatch
                batch = frappe.get_doc("SEPA Direct Debit Batch", batch.name)
                batch.cancel()
            
            # Delete using frappe.delete_doc to properly clean up
            frappe.delete_doc("SEPA Direct Debit Batch", batch.name, force=True)
    
    def test_invoice_validation(self):
        """Test invoice validation"""
        # Create a batch without required fields
        batch = frappe.new_doc("SEPA Direct Debit Batch")
        batch.batch_date = today()
        batch.batch_description = f"Test Batch {self.unique_id}"
        batch.batch_type = "RCUR"
        batch.currency = "EUR"
        
        # Create a test membership and invoice
        membership, invoice = self.create_test_membership_and_invoice()
        
        # Add invoice missing mandate reference
        batch.append("invoices", {
            "invoice": invoice,
            "membership": membership,
            "member": self.member.name,
            "member_name": self.member.full_name,
            "amount": 100.00,
            "currency": "EUR",
            "bank_account": "",
            "iban": self.member.iban,
            # Deliberately missing mandate_reference
            "status": "Pending"
        })
        
        # Should raise validation error
        with self.assertRaises(frappe.exceptions.ValidationError):
            batch.insert()

if __name__ == '__main__':
    unittest.main()
