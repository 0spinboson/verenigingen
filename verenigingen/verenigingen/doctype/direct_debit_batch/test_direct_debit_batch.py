import frappe
import unittest
import random
import string
import os
import xml.etree.ElementTree as ET
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today, nowdate, add_days, flt

class TestDirectDebitBatch(FrappeTestCase):
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
            item = frappe.new_doc("Item")
            item.item_code = item_code
            item.item_name = f"Test Membership Item {self.unique_id}"
            item.item_group = "Membership"
            item.is_stock_item = 0
            item.include_item_in_manufacturing = 0
            item.is_service_item = 1
            item.is_subscription_item = 1
            
            # Default warehouse
            item.append("item_defaults", {
                "company": "_Test Company"
            })
            
            item.insert()
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
    
    def create_test_membership_and_invoice(self, amount=100.00):
        """Create a real test membership and invoice"""
        # Create membership type if needed
        membership_type = self.create_membership_type()
        
        # Create membership
        membership = frappe.new_doc("Membership")
        membership.member = self.member.name
        membership.membership_type = membership_type.name
        membership.start_date = today()
        membership.email = self.member.email
        membership.insert()
        
        # Create a sales invoice for this membership
        invoice = frappe.new_doc("Sales Invoice")
        invoice.customer = self.member.customer
        invoice.posting_date = today()
        invoice.due_date = add_days(today(), 30)
        invoice.membership = membership.name  # Link to membership
        
        # Add invoice item
        invoice.append("items", {
            "item_code": self.test_item,
            "qty": 1,
            "rate": amount,
            "amount": amount
        })
        
        # Add to arrays for tracking
        self.memberships.append(membership.name)
        
        # Set to unpaid
        invoice.set_missing_values()
        invoice.insert()
        
        # Save invoice reference
        self.invoices.append(invoice.name)
        
        return membership, invoice
    
    def create_test_batch(self):
        """Create a test direct debit batch with real invoices"""
        if not self.invoices or not self.memberships:
            # Create a real invoice and membership if we don't have any
            self.create_test_membership_and_invoice()
        
        batch = frappe.new_doc("Direct Debit Batch")
        batch.batch_date = today()
        batch.batch_description = f"Test Batch {self.unique_id}"
        batch.batch_type = "RCUR"
        batch.currency = "EUR"
        
        # Add real invoice reference
        batch.append("invoices", {
            "invoice": self.invoices[0],  # Use a real invoice
            "membership": self.memberships[0],  # Use a real membership
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
        for b in frappe.get_all("Direct Debit Batch", 
                filters={"batch_description": ["like", f"Test Batch {self.unique_id}%"]}):
            try:
                batch_doc = frappe.get_doc("Direct Debit Batch", b.name)
                if batch_doc.docstatus == 1:
                    batch_doc.cancel()
                frappe.delete_doc("Direct Debit Batch", b.name, force=True)
            except Exception as e:
                print(f"Error cleaning up batch {b.name}: {str(e)}")
        
        # Clean up invoices
        for inv in self.invoices:
            try:
                doc = frappe.get_doc("Sales Invoice", inv)
                if doc.docstatus == 1:
                    doc.cancel()
                frappe.delete_doc("Sales Invoice", inv, force=True)
            except Exception as e:
                print(f"Error cleaning up invoice {inv}: {str(e)}")
        
        # Clean up memberships
        for mem in self.memberships:
            try:
                doc = frappe.get_doc("Membership", mem)
                if doc.docstatus == 1:
                    doc.cancel()
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
        batch = frappe.new_doc("Direct Debit Batch")
        batch.batch_date = today()
        batch.batch_description = f"Test Batch {self.unique_id}"
        batch.batch_type = "RCUR"
        batch.currency = "EUR"
        
        # Add multiple invoices with different amounts
        amounts = [100.00, 75.50, 200.25]
        
        # Create real memberships and invoices with various amounts
        invoice_data = []
        for amount in amounts:
            membership, invoice = self.create_test_membership_and_invoice(amount)
            invoice_data.append({
                "invoice": invoice.name,
                "membership": membership.name,
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
            
            # Verify sepa_file_generated flag set after submission
            batch.reload()
            self.assertTrue(batch.sepa_file_generated, "SEPA file not generated on submit")
            self.assertEqual(batch.status, "Generated", "Status not updated to Generated on submit")
        finally:
            # Cancel the batch
            if batch.docstatus == 1:
                batch.cancel()
            batch.delete()
    
    def test_invoice_validation(self):
        """Test invoice validation"""
        # Create a batch without required fields
        batch = frappe.new_doc("Direct Debit Batch")
        batch.batch_date = today()
        batch.batch_description = f"Test Batch {self.unique_id}"
        batch.batch_type = "RCUR"
        batch.currency = "EUR"
        
        # Create a real membership and invoice
        membership, invoice = self.create_test_membership_and_invoice()
        
        # Add invoice missing mandate reference
        batch.append("invoices", {
            "invoice": invoice.name,
            "membership": membership.name,
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
