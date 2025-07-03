"""
E-Boekhouden REST API Client for Mutations
Handles only mutation-related endpoints to overcome SOAP's 500-record limitation
"""

import frappe
import requests
import json
from datetime import datetime
from typing import List, Dict, Optional, Any

class EBoekhoudenRESTClient:
    def __init__(self, settings=None):
        if not settings:
            settings = frappe.get_single("E-Boekhouden Settings")
        
        self.base_url = "https://api.e-boekhouden.nl/v1"
        self.api_key = settings.get_password('api_token') if hasattr(settings, 'api_token') else None
        
        if not self.api_key:
            raise ValueError("API token is required for REST API access")
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Cache for lookup data
        self._ledger_cache = None
        self._relation_cache = None
    
    def get_mutations(self, limit=2000, offset=0, date_from=None, date_to=None) -> Dict[str, Any]:
        """
        Get mutations with pagination support
        
        Args:
            limit: Number of records per page (max 2000)
            offset: Starting position for pagination
            date_from: Optional start date filter
            date_to: Optional end date filter
            
        Returns:
            Dict with success status, mutations list, and pagination info
        """
        try:
            url = f"{self.base_url}/mutation"
            params = {
                "limit": min(limit, 2000),  # API max is 2000
                "offset": offset
            }
            
            # Add date filters if provided
            if date_from:
                params["from"] = date_from
            if date_to:
                params["to"] = date_to
            
            response = requests.get(url, headers=self._get_headers(), params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                # Fetch detailed info for each mutation
                mutations = []
                for mutation in data:
                    detailed = self.get_mutation_detail(mutation.get("id"))
                    if detailed:
                        mutations.append(detailed)
                
                return {
                    "success": True,
                    "mutations": mutations,
                    "count": len(mutations),
                    "has_more": len(data) == limit,  # If we got full page, there might be more
                    "offset": offset,
                    "limit": limit
                }
            else:
                return {
                    "success": False,
                    "error": f"API request failed: {response.status_code} - {response.text}"
                }
                
        except Exception as e:
            frappe.log_error(f"REST API error: {str(e)}", "E-Boekhouden REST")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_mutation_detail(self, mutation_id: int) -> Optional[Dict[str, Any]]:
        """
        Get detailed information for a specific mutation
        
        Args:
            mutation_id: The mutation ID to fetch
            
        Returns:
            Detailed mutation data or None if failed
        """
        try:
            url = f"{self.base_url}/mutation/{mutation_id}"
            response = requests.get(url, headers=self._get_headers(), timeout=30)
            
            if response.status_code == 200:
                return response.json()
            else:
                frappe.log_error(
                    f"Failed to get mutation detail for ID {mutation_id}: {response.status_code}",
                    "E-Boekhouden REST"
                )
                return None
                
        except Exception as e:
            frappe.log_error(f"Error fetching mutation {mutation_id}: {str(e)}", "E-Boekhouden REST")
            return None
    
    def get_all_mutations(self, date_from=None, date_to=None) -> Dict[str, Any]:
        """
        Get all mutations using pagination
        
        Args:
            date_from: Optional start date filter
            date_to: Optional end date filter
            
        Returns:
            Dict with all mutations combined
        """
        all_mutations = []
        offset = 0
        limit = 2000  # Maximum allowed by API
        
        while True:
            result = self.get_mutations(
                limit=limit,
                offset=offset,
                date_from=date_from,
                date_to=date_to
            )
            
            if not result["success"]:
                return result
            
            all_mutations.extend(result["mutations"])
            
            # Check if there are more pages
            if not result.get("has_more", False):
                break
                
            offset += limit
            
            # Progress update
            frappe.publish_realtime(
                "eboekhouden_migration_progress",
                {
                    "message": f"Fetched {len(all_mutations)} mutations...",
                    "progress": len(all_mutations)
                }
            )
        
        return {
            "success": True,
            "mutations": all_mutations,
            "count": len(all_mutations)
        }
    
    def get_ledgers(self) -> Dict[str, Any]:
        """
        Get all ledger accounts for mapping
        
        Returns:
            Dict with ledger accounts
        """
        if self._ledger_cache is not None:
            return {
                "success": True,
                "ledgers": self._ledger_cache
            }
        
        try:
            url = f"{self.base_url}/ledger"
            all_ledgers = []
            offset = 0
            limit = 2000
            
            while True:
                params = {"limit": limit, "offset": offset}
                response = requests.get(url, headers=self._get_headers(), params=params, timeout=30)
                
                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Failed to get ledgers: {response.status_code}"
                    }
                
                data = response.json()
                if not data:
                    break
                    
                all_ledgers.extend(data)
                
                if len(data) < limit:
                    break
                    
                offset += limit
            
            # Cache the results
            self._ledger_cache = all_ledgers
            
            return {
                "success": True,
                "ledgers": all_ledgers,
                "count": len(all_ledgers)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_relations(self) -> Dict[str, Any]:
        """
        Get all relations for mapping
        
        Returns:
            Dict with relations
        """
        if self._relation_cache is not None:
            return {
                "success": True,
                "relations": self._relation_cache
            }
        
        try:
            url = f"{self.base_url}/relation"
            all_relations = []
            offset = 0
            limit = 2000
            
            while True:
                params = {"limit": limit, "offset": offset}
                response = requests.get(url, headers=self._get_headers(), params=params, timeout=30)
                
                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Failed to get relations: {response.status_code}"
                    }
                
                data = response.json()
                if not data:
                    break
                    
                all_relations.extend(data)
                
                if len(data) < limit:
                    break
                    
                offset += limit
            
            # Cache the results
            self._relation_cache = all_relations
            
            return {
                "success": True,
                "relations": all_relations,
                "count": len(all_relations)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


@frappe.whitelist()
def test_rest_mutations():
    """Test REST API mutation fetching"""
    try:
        client = EBoekhoudenRESTClient()
        
        # Test getting first 10 mutations
        result = client.get_mutations(limit=10)
        
        if result["success"]:
            return {
                "success": True,
                "message": f"Successfully fetched {result['count']} mutations",
                "sample": result["mutations"][0] if result["mutations"] else None,
                "has_more": result.get("has_more", False)
            }
        else:
            return result
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def count_all_mutations():
    """Count total mutations available via REST API"""
    try:
        client = EBoekhoudenRESTClient()
        
        # Get all mutations
        result = client.get_all_mutations()
        
        if result["success"]:
            # Group by type
            by_type = {}
            for mut in result["mutations"]:
                mut_type = mut.get("type", "Unknown")
                by_type[mut_type] = by_type.get(mut_type, 0) + 1
            
            return {
                "success": True,
                "total_count": result["count"],
                "by_type": by_type,
                "message": f"Found {result['count']} total mutations via REST API"
            }
        else:
            return result
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }