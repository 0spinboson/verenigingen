import frappe
from frappe import _


@frappe.whitelist()
def check_eboekhouden_accounts(company=None):
    """
    Check for E-Boekhouden accounts in the system.
    Returns accounts with eboekhouden_grootboek_nummer field set.
    """
    try:
        filters = {}
        if company:
            filters["company"] = company
            
        # Get all accounts with eboekhouden_grootboek_nummer
        filters["eboekhouden_grootboek_nummer"] = ["!=", ""]
        
        accounts = frappe.get_all("Account", 
            filters=filters,
            fields=[
                "name", 
                "account_name",
                "account_number",
                "eboekhouden_grootboek_nummer",
                "is_group",
                "parent_account",
                "company",
                "account_type",
                "root_type"
            ],
            order_by="lft")
        
        # Group accounts by type
        leaf_accounts = []
        group_accounts = []
        
        for account in accounts:
            if account.is_group:
                group_accounts.append(account)
            else:
                leaf_accounts.append(account)
        
        # Get additional statistics
        account_types = {}
        root_types = {}
        companies = {}
        
        for account in accounts:
            # Count by account type
            if account.account_type:
                account_types[account.account_type] = account_types.get(account.account_type, 0) + 1
            
            # Count by root type
            if account.root_type:
                root_types[account.root_type] = root_types.get(account.root_type, 0) + 1
                
            # Count by company
            if account.company:
                companies[account.company] = companies.get(account.company, 0) + 1
        
        return {
            "success": True,
            "total_accounts": len(accounts),
            "leaf_accounts_count": len(leaf_accounts),
            "group_accounts_count": len(group_accounts),
            "by_account_type": account_types,
            "by_root_type": root_types,
            "by_company": companies,
            "leaf_accounts": leaf_accounts[:10],  # Show first 10 leaf accounts
            "group_accounts": group_accounts[:10],  # Show first 10 group accounts
            "message": f"Found {len(accounts)} E-Boekhouden accounts in the system"
        }
        
    except Exception as e:
        frappe.log_error(f"Error checking E-Boekhouden accounts: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def debug_cleanup_eboekhouden_accounts(company, dry_run=True):
    """
    Debug and optionally clean up E-Boekhouden accounts.
    
    Args:
        company: Company name to clean up accounts for
        dry_run: If True, only simulate the cleanup without deleting
    """
    try:
        if not company:
            return {"success": False, "error": "Company is required"}
            
        # Get all accounts with eboekhouden_grootboek_nummer
        accounts = frappe.get_all("Account", 
            filters={
                "company": company,
                "eboekhouden_grootboek_nummer": ["!=", ""]
            },
            fields=["name", "is_group", "account_name", "eboekhouden_grootboek_nummer"])
        
        if not accounts:
            return {
                "success": True,
                "message": "No E-Boekhouden accounts found for cleanup",
                "total_accounts": 0
            }
        
        # Sort accounts - leaf accounts first, then parent accounts
        leaf_accounts = [a for a in accounts if not a.is_group]
        group_accounts = [a for a in accounts if a.is_group]
        
        result = {
            "success": True,
            "total_accounts": len(accounts),
            "leaf_accounts": len(leaf_accounts),
            "group_accounts": len(group_accounts),
            "dry_run": dry_run,
            "deleted_accounts": [],
            "failed_accounts": [],
            "accounts_deleted": 0
        }
        
        if dry_run:
            result["message"] = f"DRY RUN: Would delete {len(accounts)} E-Boekhouden accounts"
            result["accounts_to_delete"] = {
                "leaf_accounts": [{"name": a.name, "account_name": a.account_name} for a in leaf_accounts[:5]],
                "group_accounts": [{"name": a.name, "account_name": a.account_name} for a in group_accounts[:5]]
            }
            return result
        
        # Actual deletion
        # Delete leaf accounts first
        for account in leaf_accounts:
            try:
                # Check if account has any transactions
                has_transactions = frappe.db.exists("GL Entry", {"account": account.name})
                
                if has_transactions:
                    result["failed_accounts"].append({
                        "name": account.name,
                        "reason": "Has GL entries"
                    })
                    continue
                    
                frappe.delete_doc("Account", account.name, force=True)
                result["deleted_accounts"].append(account.name)
                result["accounts_deleted"] += 1
                
            except Exception as e:
                result["failed_accounts"].append({
                    "name": account.name,
                    "reason": str(e)
                })
                frappe.log_error(f"Failed to delete account {account.name}: {str(e)}")
        
        # Then delete group accounts
        for account in group_accounts:
            try:
                # Check if account has children
                has_children = frappe.db.exists("Account", {"parent_account": account.name})
                
                if has_children:
                    result["failed_accounts"].append({
                        "name": account.name,
                        "reason": "Has child accounts"
                    })
                    continue
                    
                frappe.delete_doc("Account", account.name, force=True)
                result["deleted_accounts"].append(account.name)
                result["accounts_deleted"] += 1
                
            except Exception as e:
                result["failed_accounts"].append({
                    "name": account.name,
                    "reason": str(e)
                })
                frappe.log_error(f"Failed to delete account {account.name}: {str(e)}")
        
        frappe.db.commit()
        
        result["message"] = f"Deleted {result['accounts_deleted']} out of {len(accounts)} E-Boekhouden accounts"
        
        return result
        
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(f"Error in cleanup E-Boekhouden accounts: {str(e)}")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def get_eboekhouden_account_details(account_name):
    """
    Get detailed information about a specific E-Boekhouden account.
    """
    try:
        if not account_name:
            return {"success": False, "error": "Account name is required"}
            
        account = frappe.get_doc("Account", account_name)
        
        # Check if it's an E-Boekhouden account
        if not account.get("eboekhouden_grootboek_nummer"):
            return {"success": False, "error": "Not an E-Boekhouden account"}
        
        # Get GL entries count
        gl_entries_count = frappe.db.count("GL Entry", {"account": account_name})
        
        # Get child accounts if it's a group
        child_accounts = []
        if account.is_group:
            child_accounts = frappe.get_all("Account",
                filters={"parent_account": account_name},
                fields=["name", "account_name", "eboekhouden_grootboek_nummer"])
        
        # Get recent GL entries
        recent_gl_entries = frappe.get_all("GL Entry",
            filters={"account": account_name},
            fields=["posting_date", "voucher_type", "voucher_no", "debit", "credit", "remarks"],
            order_by="posting_date desc",
            limit=5)
        
        return {
            "success": True,
            "account": {
                "name": account.name,
                "account_name": account.account_name,
                "account_number": account.get("account_number"),
                "eboekhouden_grootboek_nummer": account.eboekhouden_grootboek_nummer,
                "is_group": account.is_group,
                "parent_account": account.parent_account,
                "company": account.company,
                "account_type": account.account_type,
                "root_type": account.root_type,
                "disabled": account.disabled
            },
            "gl_entries_count": gl_entries_count,
            "child_accounts_count": len(child_accounts),
            "child_accounts": child_accounts,
            "recent_gl_entries": recent_gl_entries,
            "can_delete": gl_entries_count == 0 and len(child_accounts) == 0
        }
        
    except Exception as e:
        frappe.log_error(f"Error getting E-Boekhouden account details: {str(e)}")
        return {"success": False, "error": str(e)}