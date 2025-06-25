# Copyright (c) 2025, R.S.P. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import requests
import json
from frappe.utils import now_datetime


class EBoekhoudenSettings(Document):
	def test_connection(self):
		"""Test connection to e-Boekhouden API"""
		try:
			# Prepare API request
			data = {
				'UserName': self.username,
				'SecurityCode1': self.get_password('security_code1'),
				'SecurityCode2': self.get_password('security_code2'),
				'Source': self.source_application or 'Verenigingen ERPNext'
			}
			
			# Test with a simple API call to get VAT codes
			url = f"{self.api_url}?mode=BtwCodes"
			
			response = requests.post(url, data=data, timeout=30)
			
			if response.status_code == 200:
				# Check if response contains valid XML/data
				if 'BtwCode' in response.text or 'BTW' in response.text:
					self.connection_status = "✅ Connection Successful"
					self.last_tested = now_datetime()
					frappe.msgprint("Connection test successful!", indicator="green")
					return True
				else:
					error_msg = "Invalid response from API"
					if 'error' in response.text.lower():
						error_msg = f"API Error: {response.text[:200]}"
					
					self.connection_status = f"❌ {error_msg}"
					self.last_tested = now_datetime()
					frappe.msgprint(f"Connection failed: {error_msg}", indicator="red")
					return False
			else:
				error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
				self.connection_status = f"❌ {error_msg}"
				self.last_tested = now_datetime()
				frappe.msgprint(f"Connection failed: {error_msg}", indicator="red")
				return False
				
		except requests.exceptions.Timeout:
			error_msg = "Connection timeout"
			self.connection_status = f"❌ {error_msg}"
			self.last_tested = now_datetime()
			frappe.msgprint(f"Connection failed: {error_msg}", indicator="red")
			return False
			
		except Exception as e:
			error_msg = str(e)
			self.connection_status = f"❌ {error_msg}"
			self.last_tested = now_datetime()
			frappe.msgprint(f"Connection failed: {error_msg}", indicator="red")
			return False
	
	def get_api_data(self, mode, additional_params=None):
		"""Generic method to call e-Boekhouden API"""
		try:
			data = {
				'UserName': self.username,
				'SecurityCode1': self.get_password('security_code1'),
				'SecurityCode2': self.get_password('security_code2'),
				'Source': self.source_application or 'Verenigingen ERPNext'
			}
			
			# Add additional parameters if provided
			if additional_params:
				data.update(additional_params)
			
			url = f"{self.api_url}?mode={mode}"
			
			response = requests.post(url, data=data, timeout=60)
			
			if response.status_code == 200:
				return {
					"success": True,
					"data": response.text,
					"raw_response": response
				}
			else:
				return {
					"success": False,
					"error": f"HTTP {response.status_code}: {response.text[:500]}"
				}
				
		except Exception as e:
			return {
				"success": False,
				"error": str(e)
			}


@frappe.whitelist()
def test_connection():
	"""API method to test connection"""
	try:
		settings = frappe.get_single("E-Boekhouden Settings")
		result = settings.test_connection()
		settings.save()
		return {"success": result}
	except Exception as e:
		frappe.log_error(f"Error testing e-Boekhouden connection: {str(e)}")
		return {"success": False, "error": str(e)}


@frappe.whitelist()
def get_grootboekrekeningen():
	"""Test method to fetch Chart of Accounts from e-Boekhouden"""
	try:
		settings = frappe.get_single("E-Boekhouden Settings")
		result = settings.get_api_data("Grootboekrekeningen")
		
		if result["success"]:
			return {
				"success": True,
				"message": "Successfully fetched Chart of Accounts",
				"data_preview": result["data"][:1000] + "..." if len(result["data"]) > 1000 else result["data"]
			}
		else:
			return result
			
	except Exception as e:
		frappe.log_error(f"Error fetching Chart of Accounts: {str(e)}")
		return {"success": False, "error": str(e)}