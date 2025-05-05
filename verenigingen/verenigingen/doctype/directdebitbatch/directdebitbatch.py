import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today, getdate, nowdate, nowtime, format_datetime, random_string
import xml.etree.ElementTree as ET
from datetime import datetime
import os

class DirectDebitBatch(Document):
    def validate(self):
        self.validate_invoices()
        self.calculate_totals()
    
    def validate_invoices(self):
        """Validate that all invoices are valid for direct debit"""
        if not self.invoices:
            frappe.throw(_("No invoices added to batch"))
            
        for invoice in self.invoices:
            # Check if invoice exists
            if not frappe.db.exists("Sales Invoice", invoice.invoice):
                frappe.throw(_("Invoice {0} does not exist").format(invoice.invoice))
                
            # Check if invoice is unpaid
            inv = frappe.get_doc("Sales Invoice", invoice.invoice)
            if inv.status not in ["Unpaid", "Overdue"]:
                frappe.throw(_("Invoice {0} is not unpaid").format(inv.name))
                
            # Check if membership exists
            if not frappe.db.exists("Membership", invoice.membership):
                frappe.throw(_("Membership {0} does not exist").format(invoice.membership))
                
            # Check bank details
            if not invoice.iban:
                frappe.throw(_("IBAN is required for invoice {0}").format(invoice.invoice))
                
            if not invoice.mandate_reference:
                frappe.throw(_("Mandate reference is required for invoice {0}").format(invoice.invoice))
    
    def calculate_totals(self):
        """Calculate batch totals"""
        self.total_amount = sum(invoice.amount for invoice in self.invoices)
        self.entry_count = len(self.invoices)
    
    def on_submit(self):
        """Generate SEPA file on submit if not already generated"""
        if not self.sepa_file_generated:
            self.generate_sepa_xml()
    
    def on_cancel(self):
        """Handle batch cancellation"""
        self.status = "Cancelled"
        self.add_to_batch_log(_("Batch cancelled"))
    
    def generate_sepa_xml(self):
        """Generate SEPA Direct Debit XML file"""
        try:
            # Generate IDs for SEPA message
            message_id = f"BATCH-{self.name}-{random_string(8)}"
            payment_info_id = f"PMT-{self.name}-{random_string(8)}"
            
            # Store IDs
            self.sepa_message_id = message_id
            self.sepa_payment_info_id = payment_info_id
            self.sepa_generation_date = f"{nowdate()} {nowtime()}"
            
            # Create XML structure
            root = create_sepa_xml_structure(
                message_id=message_id,
                payment_info_id=payment_info_id,
                batch_data=self,
                invoices=self.invoices
            )
            
            # Convert to string
            xml_string = ET.tostring(root, encoding='utf-8', method='xml')
            
            # Prettify XML
            import xml.dom.minidom
            xml_pretty = xml.dom.minidom.parseString(xml_string).toprettyxml()
            
            # Create temporary file
            temp_file_path = f"/tmp/sepa-{self.name}.xml"
            with open(temp_file_path, "w") as f:
                f.write(xml_pretty)
            
            # Attach to document
            self.sepa_file = self.attach_sepa_file(temp_file_path)
            self.sepa_file_generated = 1
            self.status = "Generated"
            
            # Update log
            self.add_to_batch_log(_("SEPA XML file generated successfully"))
            self.save()
            
            # Clean up
            os.remove(temp_file_path)
            
            return self.sepa_file
            
        except Exception as e:
            self.add_to_batch_log(_("Error generating SEPA file: {0}").format(str(e)))
            frappe.log_error(f"Error generating SEPA file for batch {self.name}: {str(e)}", 
                           "Direct Debit Batch Error")
            frappe.throw(_("Error generating SEPA file: {0}").format(str(e)))
    
    def attach_sepa_file(self, file_path):
        """Attach SEPA file to document"""
        file_name = os.path.basename(file_path)
        
        with open(file_path, "rb") as f:
            file_content = f.read()
            
        # Use Frappe's file API to attach the file
        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": file_name,
            "attached_to_doctype": self.doctype,
            "attached_to_name": self.name,
            "content": file_content,
            "is_private": 1
        })
        file_doc.insert()
        
        return file_doc.file_url
    
    def add_to_batch_log(self, message):
        """Add message to batch log"""
        timestamp = format_datetime(datetime.now())
        log_message = f"{timestamp}: {message}\n"
        
        if self.batch_log:
            self.batch_log += log_message
        else:
            self.batch_log = log_message
    
    def process_batch(self):
        """Process the batch - to be implemented based on bank requirements"""
        # This would typically involve sending the SEPA file to the bank
        # For now, we'll just update the status
        if not self.sepa_file_generated:
            frappe.throw(_("SEPA file must be generated before processing"))
            
        # Set status to submitted
        self.status = "Submitted"
        self.add_to_batch_log(_("Batch submitted for processing"))
        self.save()
        
        # Here you would add code to communicate with your bank's API
        
        return True
        
    def update_invoice_status(self, invoice_index, status, result_code=None, result_message=None):
        """Update status of a specific invoice in the batch"""
        if invoice_index < 0 or invoice_index >= len(self.invoices):
            frappe.throw(_("Invalid invoice index"))
            
        self.invoices[invoice_index].status = status
        
        if result_code:
            self.invoices[invoice_index].result_code = result_code
            
        if result_message:
            self.invoices[invoice_index].result_message = result_message
            
        self.save()
        
    def mark_invoices_as_paid(self):
        """Mark all invoices in the batch as paid"""
        success_count = 0
        
        for i, invoice_item in enumerate(self.invoices):
            try:
                # Get the invoice
                invoice = frappe.get_doc("Sales Invoice", invoice_item.invoice)
                
                # Create payment entry
                payment_entry = create_payment_entry_for_invoice(
                    invoice=invoice,
                    payment_type="Receive",
                    mode_of_payment="Direct Debit",
                    reference_no=self.name,
                    reference_date=self.batch_date
                )
                
                # Update batch invoice status
                self.update_invoice_status(
                    i, 
                    "Successful", 
                    "PDNG", 
                    f"Payment entry {payment_entry.name} created"
                )
                
                # Update membership
                update_membership_payment_status(invoice_item.membership)
                
                success_count += 1
                
            except Exception as e:
                self.update_invoice_status(
                    i, 
                    "Failed", 
                    "RJCT", 
                    f"Error: {str(e)}"
                )
                frappe.log_error(f"Error processing payment for invoice {invoice_item.invoice}: {str(e)}", 
                               "Direct Debit Payment Error")
        
        # Update batch status
        if success_count == len(self.invoices):
            self.status = "Processed"
        elif success_count > 0:
            self.status = "Partially Processed"
        else:
            self.status = "Failed"
            
        self.add_to_batch_log(_(f"Processed {success_count} of {len(self.invoices)} invoices"))
        self.save()
        
        return success_count

# Helper Functions

def create_sepa_xml_structure(message_id, payment_info_id, batch_data, invoices):
    """Create SEPA XML structure for direct debit"""
    # This is a simplified version - you'll need to adjust according to 
    # Dutch banking requirements for SEPA Direct Debit
    
    # Create root element
    root = ET.Element("Document")
    root.set("xmlns", "urn:iso:std:iso:20022:tech:xsd:pain.008.001.02")
    
    # Customer Direct Debit Initiation
    cstmr_drct_dbt_initn = ET.SubElement(root, "CstmrDrctDbtInitn")
    
    # Group Header
    grp_hdr = ET.SubElement(cstmr_drct_dbt_initn, "GrpHdr")
    ET.SubElement(grp_hdr, "MsgId").text = message_id
    ET.SubElement(grp_hdr, "CreDtTm").text = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    ET.SubElement(grp_hdr, "NbOfTxs").text = str(batch_data.entry_count)
    ET.SubElement(grp_hdr, "CtrlSum").text = str(batch_data.total_amount)
    
    # Get company info
    company = frappe.get_doc("Company", frappe.defaults.get_global_default('company'))
    
    # Payment Information
    pmt_inf = ET.SubElement(cstmr_drct_dbt_initn, "PmtInf")
    ET.SubElement(pmt_inf, "PmtInfId").text = payment_info_id
    ET.SubElement(pmt_inf, "PmtMtd").text = "DD"
    ET.SubElement(pmt_inf, "NbOfTxs").text = str(batch_data.entry_count)
    ET.SubElement(pmt_inf, "CtrlSum").text = str(batch_data.total_amount)
    
    # Payment Type Information
    pmt_tp_inf = ET.SubElement(pmt_inf, "PmtTpInf")
    ET.SubElement(pmt_tp_inf, "SvcLvl").append(ET.Element("Cd", text="SEPA"))
    ET.SubElement(pmt_tp_inf, "LclInstrm").append(ET.Element("Cd", text="CORE"))
    ET.SubElement(pmt_tp_inf, "SeqTp").text = "RCUR"  # Recurring
    
    # Requested Collection Date
    ET.SubElement(pmt_inf, "ReqdColltnDt").text = getdate(batch_data.batch_date).strftime("%Y-%m-%d")
    
    # Creditor Information
    ET.SubElement(pmt_inf, "Cdtr").append(ET.Element("Nm", text=company.name))
    
    # Creditor Account
    cdtr_acct = ET.SubElement(pmt_inf, "CdtrAcct")
    ET.SubElement(cdtr_acct, "Id").append(ET.Element("IBAN", text="NL43INGB0123456789"))  # Replace with actual IBAN
    
    # Creditor Agent
    cdtr_agt = ET.SubElement(pmt_inf, "CdtrAgt")
    fin_instn_id = ET.SubElement(cdtr_agt, "FinInstnId")
    ET.SubElement(fin_instn_id, "BIC").text = "INGBNL2A"  # Replace with actual BIC
    
    # Creditor Scheme ID
    cdtr_schme_id = ET.SubElement(pmt_inf, "CdtrSchmeId")
    ET.SubElement(cdtr_schme_id, "Id").append(
        ET.Element("PrvtId", {
            "Othr": {
                "Id": "NL43ZZZ123456780000",  # Replace with actual Creditor ID
                "SchmeNm": {"Prtry": "SEPA"}
            }
        })
    )
    
    # Add transactions
    for invoice in invoices:
        # Get invoice details
        inv = frappe.get_doc("Sales Invoice", invoice.invoice)
        
        # Transaction Information
        drct_dbt_tx_inf = ET.SubElement(pmt_inf, "DrctDbtTxInf")
        
        # Payment ID
        pmt_id = ET.SubElement(drct_dbt_tx_inf, "PmtId")
        ET.SubElement(pmt_id, "EndToEndId").text = f"END2END-{invoice.invoice}"
        
        # Amount
        instd_amt = ET.SubElement(drct_dbt_tx_inf, "InstdAmt")
        instd_amt.text = str(invoice.amount)
        instd_amt.set("Ccy", invoice.currency)
        
        # Mandate Related Information
        drct_dbt_tx = ET.SubElement(drct_dbt_tx_inf, "DrctDbtTx")
        mdt_rltd_inf = ET.SubElement(drct_dbt_tx, "MndtRltd_Inf")
        ET.SubElement(mdt_rltd_inf, "MndtId").text = invoice.mandate_reference
        ET.SubElement(mdt_rltd_inf, "DtOfSgntr").text = "2023-01-01"  # Replace with actual date
        
        # Debtor Agent
        dbtr_agt = ET.SubElement(drct_dbt_tx_inf, "DbtrAgt")
        fin_instn_id = ET.SubElement(dbtr_agt, "FinInstnId")
        ET.SubElement(fin_instn_id, "BIC").text = "INGBNL2A"  # This should be derived from IBAN
        
        # Debtor
        dbtr = ET.SubElement(drct_dbt_tx_inf, "Dbtr")
        ET.SubElement(dbtr, "Nm").text = invoice.member_name
        
        # Debtor Account
        dbtr_acct = ET.SubElement(drct_dbt_tx_inf, "DbtrAcct")
        ET.SubElement(dbtr_acct, "Id").append(ET.Element("IBAN", text=invoice.iban))
        
        # Remittance Information
        rmtInf = ET.SubElement(drct_dbt_tx_inf, "RmtInf")
        ET.SubElement(rmtInf, "Ustrd").text = f"Invoice {invoice.invoice} for {invoice.member_name}"
    
    return root

def create_payment_entry_for_invoice(invoice, payment_type, mode_of_payment, reference_no, reference_date):
    """Create a payment entry for an invoice"""
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
    
    # Get the payment entry
    payment_entry = get_payment_entry(
        dt="Sales Invoice",
        dn=invoice.name,
        party_amount=invoice.outstanding_amount
    )
    
    # Set payment details
    payment_entry.payment_type = payment_type
    payment_entry.mode_of_payment = mode_of_payment
    payment_entry.reference_no = reference_no
    payment_entry.reference_date = reference_date
    
    # Save and submit
    payment_entry.insert(ignore_permissions=True)
    payment_entry.submit()
    
    return payment_entry

def update_membership_payment_status(membership_name):
    """Update payment status on membership"""
    membership = frappe.get_doc("Membership", membership_name)
    membership.payment_status = "Paid"
    membership.payment_date = today()
    
    # If membership is in Pending status, change to Active
    if membership.status == "Pending":
        membership.status = "Active"
        
    membership.flags.ignore_validate_update_after_submit = True
    membership.save()
    
    return membership

@frappe.whitelist()
def generate_direct_debit_batch(date=None):
    """
    Create a direct debit batch for unpaid membership invoices
    This can be called via JS or scheduled jobs
    """
    from verenigingen.verenigingen.doctype.membership.enhanced_subscription import create_direct_debit_batch
    
    batch = create_direct_debit_batch(date)
    
    if batch:
        frappe.msgprint(_("Direct Debit Batch {0} created with {1} entries").format(
            batch.name, batch.entry_count))
        return batch.name
    else:
        frappe.msgprint(_("No eligible invoices found for direct debit"))
        return None

@frappe.whitelist()
def process_batch(batch_name):
    """Process a direct debit batch"""
    batch = frappe.get_doc("Direct Debit Batch", batch_name)
    
    if batch.docstatus != 1:
        frappe.throw(_("Batch must be submitted before processing"))
        
    if not batch.sepa_file_generated:
        batch.generate_sepa_xml()
        
    result = batch.process_batch()
    
    return result

@frappe.whitelist()
def mark_invoices_as_paid(batch_name):
    """Mark all invoices in a batch as paid"""
    batch = frappe.get_doc("Direct Debit Batch", batch_name)
    
    if batch.docstatus != 1:
        frappe.throw(_("Batch must be submitted before marking invoices as paid"))
        
    success_count = batch.mark_invoices_as_paid()
    
    return success_count
