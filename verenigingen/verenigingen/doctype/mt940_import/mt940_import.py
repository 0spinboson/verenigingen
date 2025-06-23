# Copyright (c) 2025, R.S.P. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import base64
import tempfile
import os

class MT940Import(Document):
	def before_save(self):
		"""Set company from bank account if not set"""
		if self.bank_account and not self.company:
			self.company = frappe.db.get_value("Bank Account", self.bank_account, "company")
		
		# Set status to pending if not set
		if not self.import_status:
			self.import_status = "Pending"
	
	def on_submit(self):
		"""Process the MT940 import when document is submitted"""
		try:
			self.import_status = "In Progress"
			self.save()
			
			# Process the import
			result = self.process_mt940_import()
			
			if result.get("success"):
				self.import_status = "Completed"
				self.import_summary = result.get("message", "Import completed successfully")
				self.transactions_created = result.get("transactions_created", 0)
				self.transactions_skipped = result.get("transactions_skipped", 0)
			else:
				self.import_status = "Failed"
				self.import_summary = result.get("message", "Import failed")
				self.error_log = str(result.get("errors", []))
			
			self.save()
			
		except Exception as e:
			self.import_status = "Failed"
			self.import_summary = f"Import failed with error: {str(e)}"
			self.error_log = frappe.get_traceback()
			self.save()
			raise
	
	def process_mt940_import(self):
		"""Process the MT940 file and create bank transactions"""
		try:
			# Get the file content
			if not self.mt940_file:
				return {"success": False, "message": "No MT940 file attached"}
			
			# Get file content from attachment
			file_doc = frappe.get_doc("File", {"file_url": self.mt940_file})
			file_path = file_doc.get_full_path()
			
			with open(file_path, 'r', encoding='utf-8') as f:
				mt940_content = f.read()
			
			# Encode as base64 for processing
			file_content_b64 = base64.b64encode(mt940_content.encode('utf-8')).decode('utf-8')
			
			# Use existing import function
			from verenigingen.api.member_management import import_mt940_improved
			result = import_mt940_improved(file_content_b64, self.bank_account, self.company)
			
			return result
			
		except Exception as e:
			frappe.logger().error(f"Error in MT940 import processing: {str(e)}")
			return {
				"success": False,
				"message": f"Processing failed: {str(e)}",
				"errors": [str(e)]
			}

@frappe.whitelist()
def debug_import(bank_account, file_url):
	"""Debug method for testing MT940 import"""
	try:
		# Get file content from attachment
		file_doc = frappe.get_doc("File", {"file_url": file_url})
		file_path = file_doc.get_full_path()
		
		with open(file_path, 'r', encoding='utf-8') as f:
			mt940_content = f.read()
		
		# Encode as base64 for processing
		file_content_b64 = base64.b64encode(mt940_content.encode('utf-8')).decode('utf-8')
		
		# Use existing debug function
		from verenigingen.api.member_management import debug_mt940_import_detailed
		company = frappe.db.get_value("Bank Account", bank_account, "company")
		result = debug_mt940_import_detailed(file_content_b64, bank_account, company)
		
		return result
		
	except Exception as e:
		return {
			"error": str(e),
			"traceback": frappe.get_traceback()
		}

@frappe.whitelist()
def debug_duplicates(bank_account, file_url):
	"""Debug method for analyzing duplicate detection logic"""
	try:
		# Get file content from attachment
		file_doc = frappe.get_doc("File", {"file_url": file_url})
		file_path = file_doc.get_full_path()
		
		with open(file_path, 'r', encoding='utf-8') as f:
			mt940_content = f.read()
		
		# Encode as base64 for processing
		file_content_b64 = base64.b64encode(mt940_content.encode('utf-8')).decode('utf-8')
		
		# Use duplicate detection debug function
		from verenigingen.api.member_management import debug_duplicate_detection
		company = frappe.db.get_value("Bank Account", bank_account, "company")
		result = debug_duplicate_detection(file_content_b64, bank_account, company)
		
		return result
		
	except Exception as e:
		return {
			"error": str(e),
			"traceback": frappe.get_traceback()
		}