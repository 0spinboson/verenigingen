import frappe
import unittest
import random
import string
import os
import xml.etree.ElementTree as ET
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today, nowdate, add_days

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
    
    def create_test_batch(self):
        """Create a test direct debit batch"""
        batch = frappe.new_doc("Direct Debit Batch")
        batch.batch_date = today()
        batch.batch_description = f"Test Batch {self.unique_id}"
        batch.batch_type = "RCUR"
        batch.currency = "EUR"
        
        # Add test invoice
        batch.append("invoices", {
            "invoice": f"SINV-TEST-{self.unique_id}",  # This is a dummy invoice ID
            "membership": f"MEMB-TEST-{self.unique_id}",  # This is a dummy membership ID
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
                frappe.delete_doc("Direct Debit Batch", b.name, force=True)
            except Exception as e:
                print(f"Error cleaning up batch {b.name}: {str(e)}")
        
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
        
        for i, amount in enumerate(amounts):
            batch.append("invoices", {
                "invoice": f"SINV-TEST-{self.unique_id}-{i}",
                "membership": f"MEMB-TEST-{self.unique_id}-{i}",
                "member": self.member.name,
                "member_name": self.member.full_name,
                "amount": amount,
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
            self.assertEqual(batch.total_amount, expected_total, "Total amount calculation incorrect")
            self.assertEqual(batch.entry_count, len(amounts), "Entry count calculation incorrect")
        finally:
            # Clean up
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
        
        # Add invoice missing mandate reference
        batch.append("invoices", {
            "invoice": f"SINV-TEST-{self.unique_id}",
            "membership": f"MEMB-TEST-{self.unique_id}",
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
