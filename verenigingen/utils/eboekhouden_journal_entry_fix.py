"""
Enhanced journal entry creation for E-Boekhouden migration
Handles receivable/payable accounts properly
"""

import frappe
from frappe import _
import json

def create_journal_entry_enhanced(transaction_data, company, cost_center=None):
    """
    Create journal entry with proper party handling for receivable/payable accounts
    """
    try:
        # First check if this mutation already exists
        mutation_id = transaction_data.get("number")
        if mutation_id:
            existing = frappe.db.exists("Journal Entry", {
                "eboekhouden_mutation_id": mutation_id
            })
            if existing:
                return {
                    "success": False,
                    "reason": "duplicate",
                    "message": f"Mutation {mutation_id} already exists"
                }
        
        # Get the account details
        account_code = transaction_data.get("account_code")
        account = frappe.db.get_value("Account", {
            "company": company,
            "account_number": account_code
        }, ["name", "account_type", "root_type"], as_dict=True)
        
        if not account:
            return {
                "success": False,
                "reason": "account_not_found",
                "message": f"Account {account_code} not found"
            }
        
        # Prepare journal entry
        je = frappe.new_doc("Journal Entry")
        je.company = company
        je.posting_date = transaction_data.get("date")
        je.user_remark = transaction_data.get("description", "")
        
        # Store mutation ID to prevent duplicates
        if mutation_id:
            je.eboekhouden_mutation_id = mutation_id
        
        # Determine if we need party information
        needs_party = account.account_type in ["Receivable", "Payable"]
        party_type = None
        party = None
        
        if needs_party:
            # Try to determine party from relation code or description
            relation_code = transaction_data.get("relation_code")
            
            if relation_code:
                # Check if it's a customer or supplier
                customer = frappe.db.get_value("Customer", {"customer_code": relation_code}, "name")
                supplier = frappe.db.get_value("Supplier", {"supplier_code": relation_code}, "name")
                
                if account.account_type == "Receivable":
                    party_type = "Customer"
                    party = customer or "E-Boekhouden Import"
                else:  # Payable
                    party_type = "Supplier"
                    party = supplier or "E-Boekhouden Import"
            else:
                # Use default party
                if account.account_type == "Receivable":
                    party_type = "Customer"
                    party = "E-Boekhouden Import"
                else:
                    party_type = "Supplier"
                    party = "E-Boekhouden Import"
        
        # Add the main account entry
        je.append("accounts", {
            "account": account.name,
            "debit_in_account_currency": transaction_data.get("debit", 0),
            "credit_in_account_currency": transaction_data.get("credit", 0),
            "cost_center": cost_center,
            "party_type": party_type,
            "party": party
        })
        
        # Determine contra account based on account type
        if account.root_type in ["Asset", "Expense"]:
            if transaction_data.get("debit", 0) > 0:
                # Debit to asset/expense, credit from where?
                contra_account = get_default_credit_account(company, transaction_data)
            else:
                # Credit to asset/expense, debit from where?
                contra_account = get_default_debit_account(company, transaction_data)
        else:  # Liability, Income, Equity
            if transaction_data.get("credit", 0) > 0:
                # Credit to liability/income, debit from where?
                contra_account = get_default_debit_account(company, transaction_data)
            else:
                # Debit to liability/income, credit from where?
                contra_account = get_default_credit_account(company, transaction_data)
        
        # Add contra entry
        je.append("accounts", {
            "account": contra_account,
            "debit_in_account_currency": transaction_data.get("credit", 0),
            "credit_in_account_currency": transaction_data.get("debit", 0),
            "cost_center": cost_center
        })
        
        # Save the entry
        je.flags.ignore_mandatory = True
        je.insert(ignore_permissions=True)
        
        return {
            "success": True,
            "journal_entry": je.name
        }
        
    except Exception as e:
        return {
            "success": False,
            "reason": "error",
            "message": str(e)[:100]  # Truncate to avoid long error messages
        }

def get_default_debit_account(company, transaction_data):
    """Get appropriate debit account based on transaction context"""
    # Check for common patterns
    desc = (transaction_data.get("description", "") or "").lower()
    
    if "bank" in desc or "triodos" in desc or "asn" in desc:
        # Bank transaction
        return frappe.db.get_value("Account", {
            "company": company,
            "account_type": "Bank",
            "is_group": 0
        }, "name") or get_suspense_account(company)
    elif "kas" in desc or "cash" in desc:
        # Cash transaction
        return frappe.db.get_value("Account", {
            "company": company,
            "account_type": "Cash",
            "is_group": 0
        }, "name") or get_suspense_account(company)
    else:
        return get_suspense_account(company)

def get_default_credit_account(company, transaction_data):
    """Get appropriate credit account based on transaction context"""
    # Similar logic but for credit side
    return get_default_debit_account(company, transaction_data)

def get_suspense_account(company):
    """Get or create a suspense account for unclear transactions"""
    suspense = frappe.db.get_value("Account", {
        "company": company,
        "account_name": "E-Boekhouden Suspense"
    }, "name")
    
    if not suspense:
        # Create suspense account
        parent = frappe.db.get_value("Account", {
            "company": company,
            "root_type": "Asset",
            "is_group": 1
        }, "name")
        
        acc = frappe.new_doc("Account")
        acc.account_name = "E-Boekhouden Suspense"
        acc.company = company
        acc.parent_account = parent
        acc.account_type = "Temporary"
        acc.root_type = "Asset"
        acc.insert(ignore_permissions=True)
        suspense = acc.name
    
    return suspense

@frappe.whitelist()
def prepare_migration_defaults():
    """
    Ensure default parties and accounts exist
    """
    from verenigingen.utils.fix_migration_issues import create_default_parties, fix_cost_center_structure
    
    results = []
    
    # Create default parties
    party_result = create_default_parties()
    results.append(party_result)
    
    # Fix cost centers
    cc_result = fix_cost_center_structure()
    results.append(cc_result)
    
    # Create suspense account
    company = frappe.db.get_single_value("E-Boekhouden Settings", "default_company")
    if company:
        suspense = get_suspense_account(company)
        results.append({
            "success": True,
            "suspense_account": suspense
        })
    
    return {
        "success": all(r.get("success") for r in results),
        "results": results
    }