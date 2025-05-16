# verenigingen/verenigingen/doctype/direct_debit_batch/test_direct_debit_batch.py

from frappe.tests.utils import FrappeTestCase
import frappe
import os
import xml.etree.ElementTree as ET

class TestDirectDebitBatch(FrappeTestCase):
    def setUp(self):
        # Create test settings
        if not frappe.db.exists("Verenigingen Settings"):
            settings = frappe.new_doc("Verenigingen Settings")
            settings.company = "_Test Company"
            settings.company_iban = "NL43INGB0123456789"
            settings.company_bic = "INGBNL2A"
            settings.creditor_id = "NL13ZZZ123456780000"
            settings.save()
        
        # Create test member
        if not frappe.db.exists("Member", {"email": "test_sepa@example.com"}):
            member = frappe.new_doc("Member")
            member.first_name = "Test"
            member.last_name = "Member"
            member.full_name = "Test Member"
            member.email = "test_sepa@example.com"
            member.iban = "NL43INGB9876543210"
            member.bank_account_name = "Test Member"
            member.insert()
        
        # Create test mandate
        if not frappe.db.exists("SEPA Mandate", {"member": member.name}):
            mandate = frappe.new_doc("SEPA Mandate")
            mandate.mandate_id = f"TEST-MANDATE-{frappe.utils.random_string(8)}"
            mandate.member = member.name
            mandate.account_holder_name = member.full_name
            mandate.iban = member.iban
            mandate.sign_date = frappe.utils.today()
            mandate.status = "Active"
            mandate.is_active = 1
            mandate.insert()
    
    def test_generate_sepa_xml(self):
        """Test the SEPA XML generation function"""
        # Create a test batch
        batch = frappe.new_doc("Direct Debit Batch")
        batch.batch_date = frappe.utils.today()
        batch.batch_description = "Test Batch"
        batch.batch_type = "RCUR"
        batch.currency = "EUR"
        
        # Add test invoice
        member = frappe.get_doc("Member", {"email": "test_sepa@example.com"})
        mandate = frappe.get_all("SEPA Mandate", filters={"member": member.name})[0]
        
        batch.append("invoices", {
            "invoice": "SINV-00001",  # This is a dummy invoice ID
            "membership": "MEMB-001",  # This is a dummy membership ID
            "member": member.name,
            "member_name": member.full_name,
            "amount": 100.00,
            "currency": "EUR",
            "bank_account": "",
            "iban": member.iban,
            "mandate_reference": mandate.mandate_id
        })
        
        batch.insert()
        
        # Generate SEPA file
        xml_file = batch.generate_sepa_xml()
        
        # Verify file was created
        self.assertTrue(xml_file, "SEPA XML file was not generated")
        
        # Clean up
        batch.delete()
