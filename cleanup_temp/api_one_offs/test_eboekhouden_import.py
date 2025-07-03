#!/usr/bin/env python
"""Test E-Boekhouden account import functionality"""

import frappe
from frappe import _

@frappe.whitelist()
def test_create_sample_eboekhouden_accounts():
    """Create some sample E-Boekhouden accounts for testing"""
    
    # Get default company
    settings = frappe.get_single("E-Boekhouden Settings")
    company = settings.default_company if settings else None
    
    if not company:
        return {"error": "No default company configured"}
    
    # Get root accounts
    root_income = frappe.db.get_value("Account", {"company": company, "root_type": "Income", "is_group": 1}, "name")
    root_expense = frappe.db.get_value("Account", {"company": company, "root_type": "Expense", "is_group": 1}, "name")
    root_asset = frappe.db.get_value("Account", {"company": company, "root_type": "Asset", "is_group": 1}, "name")
    root_liability = frappe.db.get_value("Account", {"company": company, "root_type": "Liability", "is_group": 1}, "name")
    
    # Find or use default parent accounts
    current_assets = frappe.db.get_value("Account", {"company": company, "account_name": "Current Assets", "is_group": 1}, "name") or root_asset
    current_liabilities = frappe.db.get_value("Account", {"company": company, "account_name": "Current Liabilities", "is_group": 1}, "name") or root_liability
    
    # Sample accounts to create
    sample_accounts = [
        {"account_code": "1000", "account_name": "Kas", "account_type": "Cash", "parent_account": current_assets},
        {"account_code": "1100", "account_name": "Bank rekening", "account_type": "Bank", "parent_account": current_assets},
        {"account_code": "1300", "account_name": "Debiteuren", "account_type": "Receivable", "parent_account": current_assets},
        {"account_code": "1600", "account_name": "Crediteuren", "account_type": "Payable", "parent_account": current_liabilities},
        {"account_code": "4000", "account_name": "Omzet", "account_type": "Income Account", "parent_account": root_income},
        {"account_code": "7000", "account_name": "Algemene kosten", "account_type": "Expense Account", "parent_account": root_expense},
        {"account_code": "1200", "account_name": "Voorraad", "account_type": "Stock", "parent_account": current_assets},
        {"account_code": "2100", "account_name": "BTW te betalen", "account_type": "Tax", "parent_account": current_liabilities},
        {"account_code": "0800", "account_name": "Eigen vermogen", "account_type": "Equity", "parent_account": root_liability},
    ]
    
    created_accounts = []
    errors = []
    
    for account_data in sample_accounts:
        try:
            # Check if account already exists
            existing = frappe.db.exists("Account", {
                "company": company,
                "account_name": account_data["account_name"]
            })
            
            if existing:
                # Update the E-Boekhouden number if needed
                account = frappe.get_doc("Account", existing)
                if not account.eboekhouden_grootboek_nummer:
                    account.eboekhouden_grootboek_nummer = account_data["account_code"]
                    account.save()
                    created_accounts.append(f"Updated: {account_data['account_name']}")
            else:
                # Create new account
                account = frappe.new_doc("Account")
                account.account_name = account_data["account_name"]
                account.company = company
                account.parent_account = account_data["parent_account"]
                account.account_type = account_data["account_type"]
                account.eboekhouden_grootboek_nummer = account_data["account_code"]
                account.insert()
                created_accounts.append(f"Created: {account_data['account_name']}")
                
        except Exception as e:
            errors.append(f"Error with {account_data['account_name']}: {str(e)}")
    
    frappe.db.commit()
    
    # Count total E-Boekhouden accounts
    total_accounts = frappe.db.count("Account", {
        "company": company,
        "eboekhouden_grootboek_nummer": ["!=", ""]
    })
    
    return {
        "success": True,
        "created_accounts": created_accounts,
        "errors": errors,
        "total_eboekhouden_accounts": total_accounts
    }


@frappe.whitelist()
def test_cleanup_and_status():
    """Test cleanup function and check status"""
    from verenigingen.verenigingen.doctype.e_boekhouden_migration.e_boekhouden_migration import cleanup_chart_of_accounts
    
    # Get default company
    settings = frappe.get_single("E-Boekhouden Settings")
    company = settings.default_company if settings else None
    
    if not company:
        return {"error": "No default company configured"}
    
    # Count before cleanup
    count_before = frappe.db.count("Account", {
        "company": company,
        "eboekhouden_grootboek_nummer": ["!=", ""]
    })
    
    # Run cleanup
    cleanup_result = cleanup_chart_of_accounts(company)
    
    # Count after cleanup
    count_after = frappe.db.count("Account", {
        "company": company,
        "eboekhouden_grootboek_nummer": ["!=", ""]
    })
    
    return {
        "count_before": count_before,
        "cleanup_result": cleanup_result,
        "count_after": count_after
    }


if __name__ == "__main__":
    # Test creating sample accounts
    print("Creating sample E-Boekhouden accounts...")
    result = test_create_sample_eboekhouden_accounts()
    print(f"Result: {result}")
    
    # Test cleanup
    print("\nTesting cleanup...")
    cleanup_result = test_cleanup_and_status()
    print(f"Cleanup result: {cleanup_result}")