# verenigingen/verenigingen/tests/test_setup.py

import frappe
from frappe.utils import today

def setup_test_environment():
    """Set up the test environment with required test records"""
    try:
        print("Setting up test environment...")
        setup_test_company()
        setup_test_accounts()
        setup_test_warehouses()
        print("Test environment setup complete.")
    return True
    except Exception as e:
        print(f"Error setting up test environment: {e}")
        return False

def setup_test_company():
    """Create _Test Company if it doesn't exist"""
    if not frappe.db.exists("Company", "_Test Company"):
        print("Creating _Test Company...")
        company = frappe.new_doc("Company")
        company.company_name = "_Test Company"
        company.abbr = "_TC"
        company.default_currency = "INR"
        company.country = "India"
        company.chart_of_accounts = "Standard"
        company.domain = "Manufacturing" 
        try:
            company.insert(ignore_permissions=True)
            frappe.db.commit()
            print("_Test Company created")
        except Exception as e:
            print(f"Error creating company: {e}")
    else:
        # Ensure company has proper abbreviation
        abbr = frappe.db.get_value("Company", "_Test Company", "abbr")
        if not abbr:
            frappe.db.set_value("Company", "_Test Company", "abbr", "_TC")
            frappe.db.commit()
            print("Updated _Test Company abbreviation")

def setup_test_accounts():
    """Set up test accounts including USD payable account"""
    # Create USD Currency if needed
    if not frappe.db.exists("Currency", "USD"):
        print("Creating USD currency...")
        currency = frappe.new_doc("Currency")
        currency.currency_name = "USD"
        currency.enabled = 1
        currency.symbol = "$"
        currency.fraction = "Cent"
        currency.fraction_units = 100
        try:
            currency.insert(ignore_permissions=True)
            frappe.db.commit()
            print("USD currency created")
        except Exception as e:
            print(f"Error creating currency: {e}")

    # Find the parent account for Payable
    payables_account = frappe.db.get_value("Account", 
        {"account_type": "Payable", "company": "_Test Company", "is_group": 1}, "name")

    if not payables_account:
        print("Payables parent account not found, getting Accounts Payable group")
        payables_account = frappe.db.get_value("Account", 
            {"account_name": "Accounts Payable", "company": "_Test Company"}, "name")

    # Create the missing USD payable account
    if payables_account and not frappe.db.exists("Account", "_Test Payable USD - _TC"):
        print(f"Creating USD Payable account under {payables_account}")
        account = frappe.new_doc("Account")
        account.account_name = "_Test Payable USD"
        account.account_type = "Payable"
        account.parent_account = payables_account
        account.company = "_Test Company"
        account.account_currency = "USD"
        try:
            account.insert(ignore_permissions=True)
            frappe.db.commit()
            print("USD Payable account created successfully")
        except Exception as e:
            frappe.db.rollback()
            print(f"Error creating account: {e}")

def setup_test_warehouses():
    """Set up test warehouses needed for tests"""
    if not frappe.db.exists("Warehouse", "_Test Warehouse - _TC"):
        print("Creating _Test Warehouse...")
        warehouse = frappe.new_doc("Warehouse")
        warehouse.warehouse_name = "_Test Warehouse"
        warehouse.company = "_Test Company"
        warehouse.warehouse_type = "Stores"
        try:
            # To avoid autoname issues, we'll set the name directly
            warehouse.name = "_Test Warehouse - _TC"
            warehouse.insert(ignore_permissions=True)
            frappe.db.commit()
            print("_Test Warehouse created")
        except Exception as e:
            frappe.db.rollback()
            print(f"Error creating warehouse: {e}")

# Function to disable automatic test record creation
def disable_test_record_creation():
    """Disable automatic test record creation"""
    frappe.flags.skip_test_records = True
    frappe.flags.make_test_records = False
    return True
