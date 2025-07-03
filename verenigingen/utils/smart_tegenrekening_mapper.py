import frappe

class SmartTegenrekeningMapper:
    """Smart mapping system for E-Boekhouden tegenrekening codes to ERPNext items"""
    
    def __init__(self, company="Ned Ver Vegan"):
        self.company = company
        self._ledger_mapping_cache = None
        self._account_cache = {}
    
    def get_item_for_tegenrekening(self, account_code, description="", transaction_type="purchase", amount=0):
        """
        Get appropriate ERPNext item for an E-Boekhouden tegenrekening code
        
        Args:
            account_code: E-Boekhouden account code (e.g., "80001", "42200")
            description: Transaction description (for fallback mapping)
            transaction_type: "purchase" or "sales" 
            amount: Transaction amount (for validation)
        
        Returns:
            dict: {
                'item_code': ERPNext item code,
                'item_name': Item name,
                'account': ERPNext account for this transaction,
                'item_group': Item group
            }
        """
        
        if not account_code:
            return self._get_fallback_item(transaction_type, description)
        
        # Strategy 1: Use pre-created smart items
        smart_item = self._get_smart_item(account_code)
        if smart_item:
            return smart_item
        
        # Strategy 2: Dynamic item creation based on account
        dynamic_item = self._create_dynamic_item(account_code, description, transaction_type)
        if dynamic_item:
            return dynamic_item
        
        # Strategy 3: Fallback to generic item
        return self._get_fallback_item(transaction_type, description)
    
    def _get_smart_item(self, account_code):
        """Get pre-created smart item for account code"""
        item_code = f"EB-{account_code}"
        
        item_data = frappe.db.get_value("Item", item_code, [
            "name", "item_name", "item_group"
        ], as_dict=True)
        
        if item_data:
            # Get account from E-Boekhouden mapping
            account = self._get_account_by_code(account_code)
            
            return {
                'item_code': item_data.name,
                'item_name': item_data.item_name,
                'account': account,
                'item_group': item_data.item_group,
                'source': 'smart_mapping'
            }
        
        return None
    
    def _create_dynamic_item(self, account_code, description, transaction_type):
        """Create item dynamically if account exists but item doesn't"""
        
        # Check if we have an ERPNext account for this code
        erpnext_account = self._get_account_by_code(account_code)
        if not erpnext_account:
            return None
        
        # Get account details
        account_details = frappe.db.get_value("Account", erpnext_account, [
            "account_name", "account_type", "root_type"
        ], as_dict=True)
        
        if not account_details:
            return None
        
        # Generate item name and properties
        item_code = f"EB-{account_code}"
        item_name = self._generate_item_name(account_details.account_name, account_code)
        
        # Determine item properties
        is_sales_item = 0
        is_purchase_item = 0
        item_group = "E-Boekhouden Import"
        
        if account_details.account_type == "Income Account":
            is_sales_item = 1
            item_group = "Revenue Items"
        elif account_details.account_type == "Expense Account":
            is_purchase_item = 1  
            item_group = "Expense Items"
        elif transaction_type == "sales":
            is_sales_item = 1
            item_group = "Revenue Items"
        else:
            is_purchase_item = 1
            item_group = "Expense Items"
        
        try:
            # Create the item
            item = frappe.new_doc("Item")
            item.item_code = item_code
            item.item_name = item_name
            item.item_group = item_group
            item.stock_uom = "Nos"
            item.is_stock_item = 0
            item.is_sales_item = is_sales_item
            item.is_purchase_item = is_purchase_item
            
            # Note: ERPNext Items don't have default account fields
            # Account mapping is handled during invoice creation
            
            # Note: Item will be linked to account via item_code pattern EB-{account_code}
            
            item.insert(ignore_permissions=True)
            
            return {
                'item_code': item_code,
                'item_name': item_name,
                'account': erpnext_account,
                'item_group': item_group,
                'source': 'dynamic_creation'
            }
            
        except Exception as e:
            frappe.log_error(f"Failed to create dynamic item for account {account_code}: {str(e)}")
            return None
    
    def _get_account_by_code(self, account_code):
        """Get ERPNext account by E-Boekhouden code"""
        if account_code in self._account_cache:
            return self._account_cache[account_code]
        
        # Try by eboekhouden_grootboek_nummer field
        account = frappe.db.get_value("Account", {
            "company": self.company,
            "eboekhouden_grootboek_nummer": account_code
        }, "name")
        
        if not account:
            # Try by account_number field
            account = frappe.db.get_value("Account", {
                "company": self.company,
                "account_number": account_code
            }, "name")
        
        self._account_cache[account_code] = account
        return account
    
    def _generate_item_name(self, account_name, account_code):
        """Generate meaningful item name from account name"""
        # Clean up account name
        item_name = account_name
        item_name = item_name.replace(f' - {self.company}', '')
        item_name = item_name.replace(f'{account_code} - ', '')
        
        # Limit length
        if len(item_name) > 60:
            item_name = item_name[:57] + "..."
        
        return item_name
    
    def _get_fallback_item(self, transaction_type, description):
        """Get fallback generic item"""
        if transaction_type == "sales":
            item_code = "EB-GENERIC-INCOME"
            item_name = "Generic Income Item"
            item_group = "Revenue Items"
            account_type = "Income Account"
        else:
            item_code = "EB-GENERIC-EXPENSE"
            item_name = "Generic Expense Item"
            item_group = "Expense Items"
            account_type = "Expense Account"
        
        # Ensure fallback item exists
        if not frappe.db.exists("Item", item_code):
            self._create_fallback_item(item_code, item_name, item_group, transaction_type)
        
        # Get appropriate account
        account = frappe.db.get_value("Account", {
            "company": self.company,
            "account_type": account_type,
            "is_group": 0
        }, "name")
        
        return {
            'item_code': item_code,
            'item_name': item_name,
            'account': account,
            'item_group': item_group,
            'source': 'fallback'
        }
    
    def _create_fallback_item(self, item_code, item_name, item_group, transaction_type):
        """Create fallback generic item"""
        try:
            item = frappe.new_doc("Item")
            item.item_code = item_code
            item.item_name = item_name
            item.item_group = item_group
            item.stock_uom = "Nos"
            item.is_stock_item = 0
            item.is_sales_item = 1 if transaction_type == "sales" else 0
            item.is_purchase_item = 1 if transaction_type == "purchase" else 0
            item.insert(ignore_permissions=True)
        except:
            pass  # Ignore if already exists


# Helper functions for migration scripts
def get_item_for_purchase_transaction(tegenrekening_code, description="", amount=0):
    """Helper for purchase transactions (invoices, payments)"""
    mapper = SmartTegenrekeningMapper()
    return mapper.get_item_for_tegenrekening(
        tegenrekening_code, description, "purchase", amount
    )

def get_item_for_sales_transaction(tegenrekening_code, description="", amount=0):
    """Helper for sales transactions (invoices, receipts)"""
    mapper = SmartTegenrekeningMapper()
    return mapper.get_item_for_tegenrekening(
        tegenrekening_code, description, "sales", amount
    )

def create_invoice_line_for_tegenrekening(tegenrekening_code, amount, description="", transaction_type="purchase"):
    """Create complete invoice line dict for a tegenrekening"""
    mapper = SmartTegenrekeningMapper()
    item_mapping = mapper.get_item_for_tegenrekening(
        tegenrekening_code, description, transaction_type, amount
    )
    
    # Check if mapping was successful
    if not item_mapping or not isinstance(item_mapping, dict):
        frappe.log_error(f"Smart mapping failed for tegenrekening {tegenrekening_code}: {item_mapping}")
        return None
    
    # Get cost center
    cost_center = frappe.db.get_value("Cost Center", {
        "company": mapper.company,
        "is_group": 0
    }, "name")
    
    line_dict = {
        "item_code": item_mapping.get('item_code'),
        "item_name": item_mapping.get('item_name'),
        "description": description or item_mapping.get('item_name', 'Unknown item'),
        "qty": 1,
        "rate": abs(float(amount)),
        "amount": abs(float(amount)),
        "cost_center": cost_center
    }
    
    # Add account field based on transaction type
    if transaction_type == "sales":
        line_dict["income_account"] = item_mapping.get('account')
    else:
        line_dict["expense_account"] = item_mapping.get('account')
    
    return line_dict


@frappe.whitelist()
def test_tegenrekening_mapping():
    """Test the smart tegenrekening mapping system"""
    try:
        response = []
        response.append("=== TESTING SMART TEGENREKENING MAPPING ===")
        
        mapper = SmartTegenrekeningMapper()
        
        # Test cases from real E-Boekhouden accounts
        test_cases = [
            ("80001", "Membership contribution", "sales", 50.0),
            ("42200", "Campaign advertising", "purchase", 250.0),
            ("83250", "Event ticket sales", "sales", 25.0),
            ("44007", "Insurance payment", "purchase", 150.0),
            ("99999", "Unknown account", "purchase", 100.0),  # Should create dynamic or fallback
        ]
        
        for account_code, description, transaction_type, amount in test_cases:
            mapping = mapper.get_item_for_tegenrekening(
                account_code, description, transaction_type, amount
            )
            
            response.append(f"\nAccount: {account_code} ({transaction_type})")
            response.append(f"  Description: {description}")
            response.append(f"  → Item: {mapping['item_code']}")
            response.append(f"  → Name: {mapping['item_name']}")
            response.append(f"  → Account: {mapping['account']}")
            response.append(f"  → Source: {mapping['source']}")
            
            # Test invoice line creation
            invoice_line = create_invoice_line_for_tegenrekening(
                account_code, amount, description, transaction_type
            )
            response.append(f"  → Invoice line: {invoice_line['item_code']} - €{invoice_line['rate']}")
        
        return "\n".join(response)
        
    except Exception as e:
        return f"Error: {e}\n{frappe.get_traceback()}"