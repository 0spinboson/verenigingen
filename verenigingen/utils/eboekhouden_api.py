"""
E-Boekhouden API Integration Utilities

This module provides utilities for integrating with the e-Boekhouden.nl API
for migrating accounting data to ERPNext.
"""

import frappe
import requests
import xml.etree.ElementTree as ET
from frappe.utils import getdate, today
import json


class EBoekhoudenAPI:
    """E-Boekhouden API client"""
    
    def __init__(self, settings=None):
        """Initialize API client with settings"""
        if not settings:
            settings = frappe.get_single("E-Boekhouden Settings")
        
        self.settings = settings
        self.base_url = settings.api_url
        self.username = settings.username
        self.security_code1 = settings.get_password('security_code1')
        self.security_code2 = settings.get_password('security_code2')
        self.source = settings.source_application or 'Verenigingen ERPNext'
    
    def make_request(self, mode, additional_params=None):
        """Make API request to e-Boekhouden"""
        try:
            data = {
                'UserName': self.username,
                'SecurityCode1': self.security_code1,
                'SecurityCode2': self.security_code2,
                'Source': self.source
            }
            
            if additional_params:
                data.update(additional_params)
            
            url = f"{self.base_url}?mode={mode}"
            
            response = requests.post(url, data=data, timeout=120)
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "data": response.text,
                    "status_code": response.status_code
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text[:500]}",
                    "status_code": response.status_code
                }
                
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Request timeout - API call took too long"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_chart_of_accounts(self):
        """Get Chart of Accounts (Grootboekrekeningen)"""
        return self.make_request("Grootboekrekeningen")
    
    def get_customers(self):
        """Get Customers (Relations with type C)"""
        return self.make_request("Relaties", {"Type": "C"})
    
    def get_suppliers(self):
        """Get Suppliers (Relations with type L)"""
        return self.make_request("Relaties", {"Type": "L"})
    
    def get_transactions(self, date_from, date_to):
        """Get Transactions (Mutaties) for date range"""
        return self.make_request("Mutaties", {
            "OpenDat": date_from.strftime("%d-%m-%Y"),
            "SluitDat": date_to.strftime("%d-%m-%Y")
        })
    
    def get_vat_codes(self):
        """Get VAT codes (BtwCodes)"""
        return self.make_request("BtwCodes")


class EBoekhoudenXMLParser:
    """XML parser for e-Boekhouden API responses"""
    
    @staticmethod
    def parse_grootboekrekeningen(xml_data):
        """Parse Chart of Accounts XML"""
        try:
            accounts = []
            
            # Handle both direct XML and response wrapper
            if '<?xml' in xml_data:
                root = ET.fromstring(xml_data)
            else:
                # Wrap in root element if needed
                xml_data = f"<root>{xml_data}</root>"
                root = ET.fromstring(xml_data)
            
            # Find all Grootboekrekening elements
            for account_elem in root.findall('.//Grootboekrekening'):
                account = {}
                for child in account_elem:
                    account[child.tag] = child.text
                
                accounts.append({
                    'code': account.get('Code', ''),
                    'name': account.get('Omschrijving', ''),
                    'category': account.get('Categorie', ''),
                    'group': account.get('Groep', ''),
                    'eb_data': account
                })
            
            return accounts
            
        except ET.ParseError as e:
            frappe.log_error(f"XML Parse Error in grootboekrekeningen: {str(e)}")
            return []
        except Exception as e:
            frappe.log_error(f"Error parsing grootboekrekeningen: {str(e)}")
            return []
    
    @staticmethod
    def parse_relaties(xml_data):
        """Parse Relations (Customers/Suppliers) XML"""
        try:
            relations = []
            
            if '<?xml' in xml_data:
                root = ET.fromstring(xml_data)
            else:
                xml_data = f"<root>{xml_data}</root>"
                root = ET.fromstring(xml_data)
            
            for relation_elem in root.findall('.//Relatie'):
                relation = {}
                for child in relation_elem:
                    relation[child.tag] = child.text
                
                relations.append({
                    'code': relation.get('Code', ''),
                    'company_name': relation.get('Bedrijf', ''),
                    'contact_name': relation.get('Contactpersoon', ''),
                    'address': relation.get('Adres', ''),
                    'postcode': relation.get('Postcode', ''),
                    'city': relation.get('Plaats', ''),
                    'country': relation.get('Land', ''),
                    'phone': relation.get('Telefoon', ''),
                    'email': relation.get('Email', ''),
                    'website': relation.get('Website', ''),
                    'vat_number': relation.get('BtwNummer', ''),
                    'eb_data': relation
                })
            
            return relations
            
        except ET.ParseError as e:
            frappe.log_error(f"XML Parse Error in relaties: {str(e)}")
            return []
        except Exception as e:
            frappe.log_error(f"Error parsing relaties: {str(e)}")
            return []
    
    @staticmethod
    def parse_mutaties(xml_data):
        """Parse Transactions (Mutaties) XML"""
        try:
            transactions = []
            
            if '<?xml' in xml_data:
                root = ET.fromstring(xml_data)
            else:
                xml_data = f"<root>{xml_data}</root>"
                root = ET.fromstring(xml_data)
            
            for mutatie_elem in root.findall('.//Mutatie'):
                mutatie = {}
                for child in mutatie_elem:
                    mutatie[child.tag] = child.text
                
                transactions.append({
                    'number': mutatie.get('MutatieNr', ''),
                    'date': mutatie.get('Datum', ''),
                    'account_code': mutatie.get('Rekening', ''),
                    'account_name': mutatie.get('RekeningOmschrijving', ''),
                    'description': mutatie.get('Omschrijving', ''),
                    'debit': float(mutatie.get('Debet', 0) or 0),
                    'credit': float(mutatie.get('Credit', 0) or 0),
                    'invoice_number': mutatie.get('Factuurnummer', ''),
                    'relation_code': mutatie.get('RelatieCode', ''),
                    'eb_data': mutatie
                })
            
            return transactions
            
        except ET.ParseError as e:
            frappe.log_error(f"XML Parse Error in mutaties: {str(e)}")
            return []
        except Exception as e:
            frappe.log_error(f"Error parsing mutaties: {str(e)}")
            return []


@frappe.whitelist()
def test_api_connection():
    """Test API connection and return sample data"""
    try:
        api = EBoekhoudenAPI()
        
        # Test with VAT codes (simplest API call)
        result = api.get_vat_codes()
        
        if result["success"]:
            return {
                "success": True,
                "message": "API connection successful",
                "sample_data": result["data"][:500] + "..." if len(result["data"]) > 500 else result["data"]
            }
        else:
            return {
                "success": False,
                "error": result["error"]
            }
            
    except Exception as e:
        frappe.log_error(f"Error testing API connection: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def preview_chart_of_accounts():
    """Preview Chart of Accounts data"""
    try:
        api = EBoekhoudenAPI()
        result = api.get_chart_of_accounts()
        
        if result["success"]:
            accounts = EBoekhoudenXMLParser.parse_grootboekrekeningen(result["data"])
            
            return {
                "success": True,
                "message": f"Found {len(accounts)} accounts",
                "accounts": accounts[:10],  # First 10 for preview
                "total_count": len(accounts)
            }
        else:
            return {
                "success": False,
                "error": result["error"]
            }
            
    except Exception as e:
        frappe.log_error(f"Error previewing Chart of Accounts: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def preview_customers():
    """Preview Customers data"""
    try:
        api = EBoekhoudenAPI()
        result = api.get_customers()
        
        if result["success"]:
            customers = EBoekhoudenXMLParser.parse_relaties(result["data"])
            
            return {
                "success": True,
                "message": f"Found {len(customers)} customers",
                "customers": customers[:10],  # First 10 for preview
                "total_count": len(customers)
            }
        else:
            return {
                "success": False,
                "error": result["error"]
            }
            
    except Exception as e:
        frappe.log_error(f"Error previewing Customers: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }