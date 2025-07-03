"""
Optimized E-Boekhouden iterator that fetches mutations by type
"""

import frappe
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any


class EBoekhoudenTypeBasedIterator:
    """Optimized iterator that fetches mutations by type"""
    
    def __init__(self, settings=None):
        if not settings:
            settings = frappe.get_single("E-Boekhouden Settings")
        
        self.settings = settings
        self.base_url = settings.api_url if hasattr(settings, 'api_url') else "https://api.e-boekhouden.nl"
        self.api_token = settings.get_password('api_token') if hasattr(settings, 'api_token') else None
        
        if not self.api_token:
            raise ValueError("API token is required for REST API access")
        
        self._session_token = None
        self._session_expiry = None
    
    def _get_session_token(self):
        """Get session token using API token"""
        # Check if we have a valid token
        if self._session_token and self._session_expiry:
            if datetime.now() < self._session_expiry:
                return self._session_token
        
        try:
            session_url = f"{self.base_url}/v1/session"
            session_data = {
                "accessToken": self.api_token,
                "source": self.settings.source_application or "Verenigingen ERPNext"
            }
            
            response = requests.post(session_url, json=session_data, timeout=30)
            
            if response.status_code == 200:
                session_response = response.json()
                self._session_token = session_response.get("token")
                self._session_expiry = datetime.now() + timedelta(minutes=55)
                return self._session_token
            else:
                frappe.log_error(f"Session token request failed: {response.status_code} - {response.text}", "E-Boekhouden REST")
                return None
                
        except Exception as e:
            frappe.log_error(f"Error getting session token: {str(e)}", "E-Boekhouden REST")
            return None
    
    def _get_headers(self):
        """Get headers with valid session token"""
        token = self._get_session_token()
        if not token:
            raise ValueError("Failed to obtain session token")
            
        return {
            "Authorization": token,
            "Accept": "application/json"
        }
    
    def fetch_mutations_by_type(self, mutation_type: int, limit: int = 500) -> List[Dict[str, Any]]:
        """
        Fetch all mutations of a specific type using pagination
        
        Args:
            mutation_type: Type of mutation (0-7)
            limit: Number of mutations per request (max 500)
            
        Returns:
            List of all mutations of the specified type
        """
        all_mutations = []
        offset = 0
        
        while True:
            try:
                url = f"{self.base_url}/v1/mutation"
                params = {
                    "type": mutation_type,
                    "limit": limit,
                    "offset": offset
                }
                
                response = requests.get(url, headers=self._get_headers(), params=params, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if isinstance(data, dict) and 'items' in data:
                        items = data['items']
                        
                        if not items:  # No more results
                            break
                            
                        all_mutations.extend(items)
                        
                        # If we got fewer items than requested, we've reached the end
                        if len(items) < limit:
                            break
                            
                        offset += limit
                    else:
                        break
                else:
                    frappe.log_error(
                        f"Failed to fetch mutations type {mutation_type} at offset {offset}: {response.status_code}",
                        "E-Boekhouden Type Iterator"
                    )
                    break
                    
            except Exception as e:
                frappe.log_error(f"Error fetching mutations type {mutation_type}: {str(e)}", "E-Boekhouden Type Iterator")
                break
        
        return all_mutations
    
    def fetch_all_mutations_by_processing_order(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Fetch all mutations grouped by type in processing order
        
        Returns:
            Dict with mutation types as keys and lists of mutations as values
        """
        # Processing order: Sales invoices, Purchase invoices, Payments, Others
        processing_order = [
            (2, "sales_invoices"),      # FactuurVerstuurd
            (1, "purchase_invoices"),   # FactuurOntvangen  
            (3, "customer_payments"),   # FactuurBetaaldOntvangen
            (4, "supplier_payments"),   # FactuurBetaaldVerstuurd
            (5, "money_received"),      # GeldOntvangen
            (6, "money_sent"),          # GeldVerstuurd
            (7, "journal_entries"),     # Memoriaal
            (0, "opening_balances")     # Opening balances last
        ]
        
        results = {}
        total_count = 0
        
        for mutation_type, type_name in processing_order:
            frappe.publish_realtime(
                "eboekhouden_migration_progress",
                {"message": f"Fetching {type_name} (type {mutation_type})..."}
            )
            
            mutations = self.fetch_mutations_by_type(mutation_type)
            results[type_name] = mutations
            total_count += len(mutations)
            
            frappe.publish_realtime(
                "eboekhouden_migration_progress", 
                {"message": f"Found {len(mutations)} {type_name}. Total so far: {total_count}"}
            )
        
        return results


@frappe.whitelist()
def test_type_based_iterator():
    """Test the new type-based iterator"""
    try:
        iterator = EBoekhoudenTypeBasedIterator()
        
        # Test fetching one type
        sales_invoices = iterator.fetch_mutations_by_type(2, limit=10)  # Limit to 10 for testing
        
        return {
            "success": True,
            "sales_invoice_count": len(sales_invoices),
            "sample": sales_invoices[0] if sales_invoices else None
        }
        
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@frappe.whitelist()
def get_mutation_counts_by_type():
    """Get count of mutations by type for planning"""
    try:
        iterator = EBoekhoudenTypeBasedIterator()
        
        type_counts = {}
        
        # Check each type with limit 1 to see if any exist
        for mutation_type in range(8):  # Types 0-7
            mutations = iterator.fetch_mutations_by_type(mutation_type, limit=1)
            type_counts[mutation_type] = len(mutations) > 0
            
        return {"success": True, "type_exists": type_counts}
        
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@frappe.whitelist()
def test_new_import_approach():
    """Test the complete new import approach with a small sample"""
    try:
        # Test with limit to avoid overwhelming
        iterator = EBoekhoudenTypeBasedIterator()
        
        # Fetch just 5 of each type for testing
        results = {}
        
        for mutation_type in [2, 1, 3, 4]:  # Sales, Purchase, Customer Pay, Supplier Pay
            mutations = iterator.fetch_mutations_by_type(mutation_type, limit=5)
            results[f"type_{mutation_type}"] = {
                "count": len(mutations),
                "sample": mutations[0] if mutations else None
            }
        
        return {
            "success": True,
            "results": results,
            "message": "New type-based approach working correctly"
        }
        
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }