"""
E-Boekhouden Fix Receivable and Payable Accounts

Post-migration function to update receivable and payable accounts to proper type
based on E-Boekhouden category information
"""

import frappe
from frappe import _
import json


@frappe.whitelist()
def fix_receivable_payable_accounts():
    """
    Update accounts to 'Receivable' or 'Payable' type based on E-Boekhouden categories
    
    This is done post-migration because during migration, journal entries
    don't have party information which would cause failures with Receivable/Payable accounts
    
    E-Boekhouden categories:
    - DEB (Debiteuren) -> Receivable accounts
    - CRED (Crediteuren) -> Payable accounts
    """
    
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        api = EBoekhoudenAPI()
        
        # Get chart of accounts with category information
        accounts_result = api.get_chart_of_accounts()
        if not accounts_result["success"]:
            return {"success": False, "error": "Failed to get chart of accounts"}
        
        accounts_data = json.loads(accounts_result["data"])
        accounts = accounts_data.get("items", [])
        
        results = {
            "updated_receivables": [],
            "updated_payables": [],
            "not_found": [],
            "already_correct": [],
            "errors": []
        }
        
        # Process accounts by category
        for account_data in accounts:
            account_code = account_data.get("code", "")
            category = account_data.get("category", "")
            description = account_data.get("description", "")
            
            # Skip if no category
            if not category:
                continue
            
            # Determine target account type based on category
            target_type = None
            if category == "DEB":  # Debiteuren
                target_type = "Receivable"
            elif category == "CRED":  # Crediteuren
                target_type = "Payable"
            else:
                continue  # Skip other categories
            
            # Find the account in ERPNext
            account_name = frappe.db.get_value(
                "Account",
                {"account_number": account_code},
                ["name", "account_type"],
                as_dict=True
            )
            
            if not account_name:
                results["not_found"].append(f"{account_code} - {description} ({category})")
                continue
            
            # Check if update needed
            if account_name.account_type == target_type:
                results["already_correct"].append(f"{account_code} - {description} already {target_type}")
                continue
            
            # Update the account
            try:
                account = frappe.get_doc("Account", account_name.name)
                old_type = account.account_type
                account.account_type = target_type
                
                # Ensure correct root type
                if target_type == "Receivable":
                    account.root_type = "Asset"
                elif target_type == "Payable":
                    account.root_type = "Liability"
                
                account.save(ignore_permissions=True)
                
                if target_type == "Receivable":
                    results["updated_receivables"].append(
                        f"{account_code} - {account.account_name} (was {old_type})"
                    )
                else:
                    results["updated_payables"].append(
                        f"{account_code} - {account.account_name} (was {old_type})"
                    )
                
                frappe.msgprint(
                    f"Updated {account_code} - {account.account_name} to {target_type} type",
                    indicator="green"
                )
                
            except Exception as e:
                results["errors"].append(f"{account_code}: {str(e)}")
                frappe.log_error(
                    f"Error updating account {account_code}: {str(e)}",
                    "Fix Account Types"
                )
        
        # Commit changes
        frappe.db.commit()
        
        # Set default receivable account if we updated any
        if results["updated_receivables"]:
            # Try to set 13900 as default if it was updated
            set_default_receivable_account("13900")
        
        return {
            "success": len(results["errors"]) == 0,
            "results": results,
            "summary": {
                "receivables_updated": len(results["updated_receivables"]),
                "payables_updated": len(results["updated_payables"]),
                "already_correct": len(results["already_correct"]),
                "not_found": len(results["not_found"]),
                "errors": len(results["errors"])
            }
        }
        
    except Exception as e:
        import traceback
        frappe.log_error(traceback.format_exc(), "Fix Account Types Error")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def fix_receivable_accounts():
    """
    Update specific receivable accounts to 'Receivable' type after migration
    
    This is done post-migration because during migration, journal entries
    don't have party information which would cause failures with Receivable accounts
    """
    
    # Define the specific receivable accounts that need to be updated
    receivable_accounts = {
        "13500": "Te ontvangen contributies",
        "13510": "Te ontvangen donaties", 
        "13600": "Te ontvangen rente",
        "13900": "Te ontvangen bedragen"
    }
    
    results = {
        "updated": [],
        "not_found": [],
        "errors": []
    }
    
    for account_code, expected_name in receivable_accounts.items():
        try:
            # Find the account
            account_name = frappe.db.get_value(
                "Account",
                {"account_number": account_code},
                "name"
            )
            
            if not account_name:
                results["not_found"].append(f"{account_code} - {expected_name}")
                continue
            
            # Update the account type
            account = frappe.get_doc("Account", account_name)
            
            if account.account_type != "Receivable":
                account.account_type = "Receivable"
                # Ensure root type is Asset (should already be)
                if account.root_type != "Asset":
                    account.root_type = "Asset"
                
                account.save(ignore_permissions=True)
                results["updated"].append(f"{account_code} - {account.account_name}")
                
                frappe.msgprint(
                    f"Updated {account_code} - {account.account_name} to Receivable type",
                    indicator="green"
                )
            else:
                frappe.msgprint(
                    f"{account_code} - {account.account_name} is already Receivable type",
                    indicator="blue"
                )
                
        except Exception as e:
            results["errors"].append(f"{account_code}: {str(e)}")
            frappe.log_error(
                f"Error updating account {account_code}: {str(e)}",
                "Fix Receivable Accounts"
            )
    
    # Commit changes
    frappe.db.commit()
    
    return {
        "success": len(results["errors"]) == 0,
        "results": results,
        "message": f"Updated {len(results['updated'])} accounts to Receivable type"
    }


@frappe.whitelist()
def set_default_receivable_account(account_code="13900"):
    """
    Set the default receivable account for the company
    
    This ensures new members/customers will use the correct receivable account
    """
    
    try:
        # Get the account
        account_name = frappe.db.get_value(
            "Account",
            {"account_number": account_code},
            "name"
        )
        
        if not account_name:
            return {
                "success": False,
                "error": f"Account {account_code} not found"
            }
        
        # Get the company from account
        account = frappe.get_doc("Account", account_name)
        company = account.company
        
        if not company:
            return {
                "success": False,
                "error": "No company found for account"
            }
        
        # Update company's default receivable account
        company_doc = frappe.get_doc("Company", company)
        company_doc.default_receivable_account = account_name
        company_doc.save(ignore_permissions=True)
        
        frappe.db.commit()
        
        return {
            "success": True,
            "message": f"Set {account_name} as default receivable account for {company}"
        }
        
    except Exception as e:
        frappe.log_error(
            f"Error setting default receivable account: {str(e)}",
            "Set Default Receivable"
        )
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def check_receivable_accounts_status():
    """
    Check the current status of receivable accounts
    """
    
    receivable_accounts = {
        "13500": "Te ontvangen contributies",
        "13510": "Te ontvangen donaties", 
        "13600": "Te ontvangen rente",
        "13900": "Te ontvangen bedragen"
    }
    
    status = []
    
    for account_code, expected_name in receivable_accounts.items():
        account_name = frappe.db.get_value(
            "Account",
            {"account_number": account_code},
            ["name", "account_name", "account_type", "root_type"],
            as_dict=True
        )
        
        if account_name:
            status.append({
                "account_code": account_code,
                "account_name": account_name.account_name,
                "current_type": account_name.account_type,
                "root_type": account_name.root_type,
                "is_receivable": account_name.account_type == "Receivable",
                "exists": True
            })
        else:
            status.append({
                "account_code": account_code,
                "expected_name": expected_name,
                "exists": False
            })
    
    # Check default receivable account
    companies = frappe.get_all("Company", fields=["name", "default_receivable_account"])
    
    return {
        "accounts": status,
        "companies": companies
    }