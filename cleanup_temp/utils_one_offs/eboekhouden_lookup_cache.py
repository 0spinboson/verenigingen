"""
E-Boekhouden Lookup Cache
Maps REST API IDs to SOAP account codes and relation codes
"""

import frappe
from typing import Dict, Optional, Any

class EBoekhoudenLookupCache:
    def __init__(self):
        self._ledger_map = {}  # ledger_id -> account_code
        self._relation_map = {}  # relation_id -> relation_code
        self._account_types = {}  # account_code -> account_type
        self._initialized = False
    
    def initialize(self, soap_api=None, rest_client=None):
        """
        Initialize cache by loading data from both APIs
        
        Args:
            soap_api: EBoekhoudenSOAPAPI instance
            rest_client: EBoekhoudenRESTClient instance
        """
        if self._initialized:
            return
        
        try:
            # Load from SOAP (has account codes)
            if soap_api:
                self._load_soap_accounts(soap_api)
                self._load_soap_relations(soap_api)
            
            # Load from REST (to map IDs)
            if rest_client:
                self._load_rest_mappings(rest_client)
            
            self._initialized = True
            
        except Exception as e:
            frappe.log_error(f"Failed to initialize lookup cache: {str(e)}", "E-Boekhouden Cache")
            raise
    
    def _load_soap_accounts(self, soap_api):
        """Load account data from SOAP API"""
        result = soap_api.get_grootboekrekeningen()
        
        if not result["success"]:
            raise Exception(f"Failed to load accounts: {result.get('error')}")
        
        for account in result["accounts"]:
            code = account.get("Code")
            if code:
                # Determine account type based on code ranges (Dutch accounting standards)
                account_type = self._determine_account_type(code)
                self._account_types[code] = account_type
    
    def _load_soap_relations(self, soap_api):
        """Load relation data from SOAP API"""
        result = soap_api.get_relaties()
        
        if not result["success"]:
            raise Exception(f"Failed to load relations: {result.get('error')}")
        
        # Relations are already loaded with their codes
        # We'll map them when we get REST data
    
    def _load_rest_mappings(self, rest_client):
        """Load and map REST API data to SOAP codes"""
        # Load ledgers
        ledger_result = rest_client.get_ledgers()
        if ledger_result["success"]:
            for ledger in ledger_result["ledgers"]:
                ledger_id = ledger.get("id")
                ledger_code = ledger.get("code")
                if ledger_id and ledger_code:
                    self._ledger_map[str(ledger_id)] = ledger_code
        
        # Load relations
        relation_result = rest_client.get_relations()
        if relation_result["success"]:
            for relation in relation_result["relations"]:
                relation_id = relation.get("id")
                relation_code = relation.get("code")
                if relation_id and relation_code:
                    self._relation_map[str(relation_id)] = relation_code
    
    def _determine_account_type(self, account_code: str) -> str:
        """
        Determine account type based on Dutch accounting standards
        
        0xxx = Fixed assets (Vaste activa)
        1xxx = Current assets (Vlottende activa)
        2xxx = Equity (Eigen vermogen)
        3xxx = Provisions (Voorzieningen)
        4xxx = Long-term liabilities (Langlopende schulden)
        5xxx = Short-term liabilities (Kortlopende schulden)
        6xxx = Other liabilities
        7xxx = Revenue accounts (Omzet)
        8xxx = Cost of goods sold (Kostprijs omzet)
        9xxx = Operating expenses (Bedrijfskosten)
        """
        if not account_code or not account_code.isdigit():
            return "unknown"
        
        first_digit = account_code[0]
        
        if first_digit in ["0", "1"]:
            return "asset"
        elif first_digit == "2":
            return "equity"
        elif first_digit in ["3", "4", "5", "6"]:
            return "liability"
        elif first_digit == "7":
            return "income"
        elif first_digit in ["8", "9"]:
            return "expense"
        else:
            return "unknown"
    
    def get_account_code(self, ledger_id: str) -> Optional[str]:
        """Get account code from ledger ID"""
        return self._ledger_map.get(str(ledger_id))
    
    def get_relation_code(self, relation_id: str) -> Optional[str]:
        """Get relation code from relation ID"""
        return self._relation_map.get(str(relation_id))
    
    def get_account_type(self, account_code: str) -> str:
        """Get account type for a given account code"""
        return self._account_types.get(account_code, "unknown")
    
    def convert_rest_to_soap_format(self, rest_mutation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert REST mutation format to SOAP-like format for compatibility
        
        Args:
            rest_mutation: Mutation data from REST API
            
        Returns:
            SOAP-compatible mutation dict
        """
        # Map basic fields
        soap_mutation = {
            "MutatieNr": str(rest_mutation.get("id", "")),
            "Datum": rest_mutation.get("date", ""),
            "Omschrijving": rest_mutation.get("description", ""),
            "Factuurnummer": rest_mutation.get("invoiceNumber", ""),
            "Boekstuk": rest_mutation.get("entryNumber", ""),
            "Soort": self._map_mutation_type(rest_mutation.get("type", ""))
        }
        
        # Map ledger ID to account code
        ledger_id = rest_mutation.get("ledgerId")
        if ledger_id:
            account_code = self.get_account_code(ledger_id)
            if account_code:
                soap_mutation["Rekening"] = account_code
        
        # Map relation ID to relation code
        relation_id = rest_mutation.get("relationId")
        if relation_id:
            relation_code = self.get_relation_code(relation_id)
            if relation_code:
                soap_mutation["RelatieCode"] = relation_code
        
        # Convert amount to debit/credit
        amount = float(rest_mutation.get("amount", 0))
        account_type = self.get_account_type(soap_mutation.get("Rekening", ""))
        
        debit, credit = self._convert_amount_to_debit_credit(
            amount, 
            account_type,
            soap_mutation["Soort"]
        )
        
        soap_mutation["BedragDebet"] = str(debit) if debit else ""
        soap_mutation["BedragCredit"] = str(credit) if credit else ""
        
        # Process mutation lines
        mutation_lines = []
        rows = rest_mutation.get("rows", [])
        
        for row in rows:
            line = {
                "BedragInvoer": str(row.get("amount", 0)),
                "Omschrijving": row.get("description", ""),
                "BTWCode": row.get("vatCode", ""),
                "BTWPercentage": str(row.get("vatPercentage", 0)),
                "TegenrekeningCode": ""
            }
            
            # Get counter account code
            counter_ledger_id = row.get("ledgerId")
            if counter_ledger_id:
                counter_code = self.get_account_code(counter_ledger_id)
                if counter_code:
                    line["TegenrekeningCode"] = counter_code
            
            mutation_lines.append(line)
        
        soap_mutation["MutatieRegels"] = mutation_lines
        
        return soap_mutation
    
    def _map_mutation_type(self, rest_type: str) -> str:
        """Map REST mutation type to SOAP mutation type"""
        type_mapping = {
            "sales_invoice": "FactuurVerstuurd",
            "purchase_invoice": "FactuurOntvangen",
            "sales_payment": "FactuurbetalingOntvangen",
            "purchase_payment": "FactuurbetalingVerstuurd",
            "bank_payment_received": "GeldOntvangen",
            "bank_payment_sent": "GeldUitgegeven",
            "memorial": "Memoriaal",
            "opening_balance": "BeginBalans"
        }
        
        return type_mapping.get(rest_type, rest_type)
    
    def _convert_amount_to_debit_credit(
        self, 
        amount: float, 
        account_type: str,
        mutation_type: str
    ) -> tuple[float, float]:
        """
        Convert single amount to debit/credit based on account type and context
        
        Args:
            amount: The amount from REST API
            account_type: Type of account (asset, liability, income, expense)
            mutation_type: Type of mutation
            
        Returns:
            Tuple of (debit, credit)
        """
        debit = 0.0
        credit = 0.0
        
        # For invoice and payment types, use standard rules
        if "Factuur" in mutation_type:
            if amount > 0:
                if account_type in ["asset", "expense"]:
                    debit = abs(amount)
                else:
                    credit = abs(amount)
            else:
                if account_type in ["asset", "expense"]:
                    credit = abs(amount)
                else:
                    debit = abs(amount)
        
        # For bank transactions
        elif "Geld" in mutation_type:
            if "Ontvangen" in mutation_type:  # Money received
                debit = abs(amount)  # Bank account increases
            else:  # Money sent
                credit = abs(amount)  # Bank account decreases
        
        # For other types, use general rules
        else:
            if amount > 0:
                if account_type in ["asset", "expense"]:
                    debit = abs(amount)
                else:
                    credit = abs(amount)
            else:
                if account_type in ["asset", "expense"]:
                    credit = abs(amount)
                else:
                    debit = abs(amount)
        
        return debit, credit


@frappe.whitelist()
def test_lookup_cache():
    """Test the lookup cache functionality"""
    from .eboekhouden_soap_api import EBoekhoudenSOAPAPI
    from .eboekhouden_rest_client import EBoekhoudenRESTClient
    
    try:
        # Initialize APIs
        soap_api = EBoekhoudenSOAPAPI()
        rest_client = EBoekhoudenRESTClient()
        
        # Initialize cache
        cache = EBoekhoudenLookupCache()
        cache.initialize(soap_api, rest_client)
        
        # Test with a sample mutation
        result = rest_client.get_mutations(limit=1)
        
        if result["success"] and result["mutations"]:
            rest_mutation = result["mutations"][0]
            soap_format = cache.convert_rest_to_soap_format(rest_mutation)
            
            return {
                "success": True,
                "rest_format": rest_mutation,
                "soap_format": soap_format,
                "message": "Successfully converted REST to SOAP format"
            }
        else:
            return {
                "success": False,
                "error": "No mutations found to test"
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }