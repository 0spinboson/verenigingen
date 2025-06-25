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
        self.base_url = settings.api_url.rstrip('/')  # Remove trailing slash
        self.api_token = settings.get_password('api_token')
        self.source = settings.source_application or 'Verenigingen ERPNext'
    
    def get_session_token(self):
        """Get session token using API token"""
        try:
            session_url = f"{self.base_url}/v1/session"
            session_data = {
                "accessToken": self.api_token,
                "source": self.source
            }
            
            response = requests.post(session_url, json=session_data, timeout=30)
            
            if response.status_code == 200:
                session_response = response.json()
                return session_response.get("token")
            else:
                frappe.log_error(f"Session token request failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            frappe.log_error(f"Error getting session token: {str(e)}")
            return None
    
    def make_request(self, endpoint, method="GET", params=None):
        """Make API request to e-Boekhouden"""
        try:
            # Get session token first
            session_token = self.get_session_token()
            if not session_token:
                return {
                    "success": False,
                    "error": "Failed to get session token"
                }
            
            headers = {
                'Authorization': session_token,
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            url = f"{self.base_url}/{endpoint}"
            
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=120)
            else:
                response = requests.post(url, headers=headers, json=params, timeout=120)
            
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
        """Get Chart of Accounts (Ledgers)"""
        return self.make_request("v1/ledger")
    
    def get_cost_centers(self):
        """Get Cost Centers"""
        return self.make_request("v1/costcenter")
    
    def get_invoices(self, params=None):
        """Get Invoices"""
        return self.make_request("v1/invoice", params=params)
    
    def get_invoice_templates(self):
        """Get Invoice Templates"""
        return self.make_request("v1/invoicetemplate")
    
    def get_email_templates(self):
        """Get Email Templates"""
        return self.make_request("v1/emailtemplate")
    
    def get_administrations(self):
        """Get Administrations"""
        return self.make_request("v1/administration")
    
    def get_linked_administrations(self):
        """Get Linked Administrations"""
        return self.make_request("v1/administration/linked")


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
def debug_settings():
    """Debug E-Boekhouden Settings"""
    try:
        settings = frappe.get_single("E-Boekhouden Settings")
        
        # Check basic fields
        result = {
            "settings_exists": True,
            "api_url": settings.api_url,
            "source_application": settings.source_application,
            "api_token_field_populated": bool(settings.get("api_token")),
        }
        
        # Try to get the password
        try:
            token = settings.get_password('api_token')
            result["api_token_password_accessible"] = bool(token)
            if token:
                result["token_length"] = len(token)
        except Exception as e:
            result["password_error"] = str(e)
        
        # Check raw database value
        raw_token = frappe.db.get_value("E-Boekhouden Settings", "E-Boekhouden Settings", "api_token")
        result["raw_token_exists"] = bool(raw_token)
        
        return result
        
    except Exception as e:
        return {
            "error": str(e),
            "settings_exists": False
        }

@frappe.whitelist()
def update_api_url():
    """Update API URL to the correct modern endpoint"""
    try:
        settings = frappe.get_single("E-Boekhouden Settings")
        settings.api_url = "https://api.e-boekhouden.nl"
        settings.source_application = "ERPNext"  # Standard source format
        settings.save()
        
        return {
            "success": True,
            "message": "API URL and source updated",
            "new_url": settings.api_url,
            "new_source": settings.source_application
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def test_session_token_only():
    """Test just the session token creation with detailed logging"""
    try:
        settings = frappe.get_single("E-Boekhouden Settings")
        
        session_url = f"{settings.api_url}/v1/session"
        session_data = {
            "accessToken": settings.get_password("api_token"),
            "source": settings.source_application or "ERPNext"
        }
        
        frappe.log_error(f"Testing session token with URL: {session_url}")
        frappe.log_error(f"Session data: {{'accessToken': '***', 'source': '{session_data['source']}'}}")
        
        response = requests.post(session_url, json=session_data, timeout=30)
        
        result = {
            "url": session_url,
            "source": session_data["source"],
            "status_code": response.status_code,
            "response_text": response.text[:1000],  # First 1000 chars
            "headers": dict(response.headers)
        }
        
        if response.status_code == 200:
            try:
                json_response = response.json()
                result["session_token_received"] = bool(json_response.get("sessionToken"))
                result["success"] = True
            except:
                result["json_parse_error"] = True
                result["success"] = False
        else:
            result["success"] = False
        
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "exception_type": type(e).__name__
        }

@frappe.whitelist()
def discover_api_structure():
    """Try to discover the API structure by testing various approaches"""
    try:
        api = EBoekhoudenAPI()
        
        # Test basic endpoints and root paths
        discovery_tests = [
            ("", "Root"),
            ("v1", "Version 1 root"),
            ("api", "API root"),
            ("api/v1", "API v1 root"),
            ("swagger.json", "Swagger spec"),
            ("swagger/v1/swagger.json", "Swagger v1 spec"),
            ("docs", "Documentation"),
            ("health", "Health check"),
            ("status", "Status check")
        ]
        
        results = {}
        
        for endpoint, description in discovery_tests:
            result = api.make_request(endpoint)
            results[endpoint] = {
                "description": description,
                "success": result["success"],
                "status_code": result.get("status_code"),
                "error": result.get("error"),
                "response_preview": result.get("data", "")[:500] if result["success"] else None
            }
        
        return {
            "success": True,
            "message": "API discovery completed",
            "results": results
        }
            
    except Exception as e:
        frappe.log_error(f"Error discovering API structure: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def test_raw_request():
    """Test a raw HTTP request to understand the API better"""
    try:
        settings = frappe.get_single("E-Boekhouden Settings")
        
        # Get session token
        session_url = f"{settings.api_url}/v1/session"
        session_data = {
            "accessToken": settings.get_password("api_token"),
            "source": settings.source_application or "ERPNext"
        }
        
        session_response = requests.post(session_url, json=session_data, timeout=30)
        
        if session_response.status_code != 200:
            return {
                "success": False,
                "error": f"Session token failed: {session_response.status_code} - {session_response.text}"
            }
        
        token = session_response.json().get("token")
        
        # Try a simple GET to the base API URL with the token
        headers = {
            'Authorization': token,
            'Accept': 'application/json'
        }
        
        # Test different base URLs
        test_urls = [
            f"{settings.api_url}/",
            f"{settings.api_url}/v1/",
            f"{settings.api_url}/api/",
            f"{settings.api_url}/swagger.json"
        ]
        
        results = {}
        
        for test_url in test_urls:
            try:
                response = requests.get(test_url, headers=headers, timeout=15)
                results[test_url] = {
                    "status_code": response.status_code,
                    "content_type": response.headers.get("content-type", ""),
                    "content_length": len(response.text),
                    "response_preview": response.text[:500],
                    "success": response.status_code == 200
                }
            except Exception as e:
                results[test_url] = {
                    "error": str(e),
                    "success": False
                }
        
        return {
            "success": True,
            "token_obtained": bool(token),
            "test_results": results
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def test_correct_endpoints():
    """Test the correct API endpoints from Swagger documentation"""
    try:
        api = EBoekhoudenAPI()
        
        # Test all available endpoints
        endpoint_tests = [
            ("v1/administration", "Administrations"),
            ("v1/ledger", "Chart of Accounts"),
            ("v1/costcenter", "Cost Centers"),
            ("v1/invoice", "Invoices"),
            ("v1/invoicetemplate", "Invoice Templates"),
            ("v1/emailtemplate", "Email Templates")
        ]
        
        results = {}
        
        for endpoint, description in endpoint_tests:
            result = api.make_request(endpoint)
            results[endpoint] = {
                "description": description,
                "success": result["success"],
                "status_code": result.get("status_code"),
                "error": result.get("error"),
                "data_preview": result.get("data", "")[:300] if result["success"] else None
            }
        
        return {
            "success": True,
            "message": "Endpoint testing completed with correct endpoints",
            "results": results
        }
            
    except Exception as e:
        frappe.log_error(f"Error testing correct endpoints: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def test_api_connection():
    """Test API connection and return sample data"""
    try:
        api = EBoekhoudenAPI()
        
        # Test with Chart of Accounts using correct endpoint
        result = api.get_chart_of_accounts()
        
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
            # Parse JSON response instead of XML
            try:
                data = json.loads(result["data"])
                accounts = data.get("items", [])
                
                # Convert to simplified format
                simplified_accounts = []
                for account in accounts[:10]:  # First 10 for preview
                    simplified_accounts.append({
                        'id': account.get('id'),
                        'code': account.get('code'),
                        'description': account.get('description'),
                        'category': account.get('category'),
                        'group': account.get('group', '')
                    })
                
                return {
                    "success": True,
                    "message": f"Found {len(accounts)} accounts",
                    "accounts": simplified_accounts,
                    "total_count": len(accounts)
                }
            except json.JSONDecodeError as e:
                return {
                    "success": False,
                    "error": f"Failed to parse API response: {str(e)}"
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
def test_chart_of_accounts_migration():
    """Test Chart of Accounts migration in dry-run mode"""
    try:
        # Create a temporary migration document for testing
        migration = frappe.new_doc("E-Boekhouden Migration")
        migration.migration_name = f"Test Migration {frappe.utils.now_datetime()}"
        migration.migrate_accounts = 1
        migration.migrate_cost_centers = 0
        migration.migrate_customers = 0
        migration.migrate_suppliers = 0
        migration.migrate_transactions = 0
        migration.dry_run = 1
        
        # Get settings
        settings = frappe.get_single("E-Boekhouden Settings")
        
        # Run migration test
        result = migration.migrate_chart_of_accounts(settings)
        
        return {
            "success": True,
            "message": "Chart of Accounts migration test completed",
            "result": result,
            "imported_records": getattr(migration, 'imported_records', 0),
            "failed_records": getattr(migration, 'failed_records', 0),
            "total_records": getattr(migration, 'total_records', 0)
        }
        
    except Exception as e:
        frappe.log_error(f"Error testing Chart of Accounts migration: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def test_cost_center_migration():
    """Test Cost Center migration in dry-run mode"""
    try:
        # Create a temporary migration document for testing
        migration = frappe.new_doc("E-Boekhouden Migration")
        migration.migration_name = f"Test Cost Center Migration {frappe.utils.now_datetime()}"
        migration.migrate_accounts = 0
        migration.migrate_cost_centers = 1
        migration.migrate_customers = 0
        migration.migrate_suppliers = 0
        migration.migrate_transactions = 0
        migration.dry_run = 1
        
        # Get settings
        settings = frappe.get_single("E-Boekhouden Settings")
        
        # Run migration test
        result = migration.migrate_cost_centers(settings)
        
        return {
            "success": True,
            "message": "Cost Center migration test completed",
            "result": result,
            "imported_records": getattr(migration, 'imported_records', 0),
            "failed_records": getattr(migration, 'failed_records', 0),
            "total_records": getattr(migration, 'total_records', 0)
        }
        
    except Exception as e:
        frappe.log_error(f"Error testing Cost Center migration: {str(e)}")
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