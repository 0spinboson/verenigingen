"""
E-Boekhouden Full Migration

Comprehensive migration function that automatically determines date ranges
and migrates all data from E-Boekhouden to ERPNext
"""

import frappe
from frappe import _
import json
from datetime import datetime, timedelta


@frappe.whitelist()
def migrate_all_eboekhouden_data():
    """
    Comprehensive migration function that:
    1. Automatically determines the date range from E-Boekhouden
    2. Creates opening balance journal entry
    3. Migrates all transactions
    4. Creates payment entries where applicable
    5. Provides detailed migration report
    """
    
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        from verenigingen.utils.eboekhouden_migration import EBoekhoudenMigration
        from verenigingen.utils.eboekhouden_payment_migration import EBoekhoudenPaymentMigration
        from verenigingen.utils.eboekhouden_proper_opening_balance import create_opening_balance_journal_entry
        
        # Initialize API
        api = EBoekhoudenAPI()
        
        # Step 1: Determine date range by getting the oldest and newest transactions
        frappe.publish_progress(10, title="Determining date range...")
        date_range_result = _get_migration_date_range(api)
        
        if not date_range_result["success"]:
            return date_range_result
        
        start_date = date_range_result["start_date"]
        end_date = date_range_result["end_date"]
        opening_balance_date = date_range_result["opening_balance_date"]
        
        frappe.msgprint(f"Found transactions from {start_date} to {end_date}")
        
        # Step 2: Create opening balance if needed
        frappe.publish_progress(20, title="Creating opening balance...")
        opening_balance_result = _create_opening_balance_safe(opening_balance_date)
        
        # Step 3: Migrate chart of accounts
        frappe.publish_progress(30, title="Migrating chart of accounts...")
        migration = EBoekhoudenMigration()
        coa_result = migration.migrate_chart_of_accounts()
        
        if not coa_result["success"]:
            return {
                "success": False,
                "error": f"Failed to migrate chart of accounts: {coa_result.get('error')}",
                "opening_balance": opening_balance_result
            }
        
        # Step 4: Migrate all transactions
        frappe.publish_progress(50, title="Migrating transactions...")
        transaction_result = _migrate_all_transactions(migration, start_date, end_date)
        
        # Step 5: Create payment entries
        frappe.publish_progress(80, title="Creating payment entries...")
        payment_result = _create_payment_entries(start_date, end_date)
        
        # Step 6: Generate summary report
        frappe.publish_progress(90, title="Generating report...")
        summary = _generate_migration_summary(
            date_range_result,
            opening_balance_result,
            coa_result,
            transaction_result,
            payment_result
        )
        
        frappe.publish_progress(100, title="Migration complete!")
        
        return {
            "success": True,
            "summary": summary,
            "details": {
                "date_range": date_range_result,
                "opening_balance": opening_balance_result,
                "chart_of_accounts": coa_result,
                "transactions": transaction_result,
                "payment_entries": payment_result
            }
        }
        
    except Exception as e:
        import traceback
        frappe.log_error(traceback.format_exc(), "E-Boekhouden Full Migration Error")
        return {"success": False, "error": str(e)}


def _get_migration_date_range(api):
    """
    Automatically determine the date range for migration
    """
    try:
        # Get a sample of old and new transactions to find date range
        # First, try to get the oldest transactions
        oldest_params = {
            "pageSize": 10,
            "sortOrder": "asc"  # Oldest first
        }
        
        oldest_result = api.get_mutations(oldest_params)
        if not oldest_result["success"]:
            return {"success": False, "error": "Failed to get oldest transactions"}
        
        oldest_data = json.loads(oldest_result["data"])
        oldest_mutations = oldest_data.get("items", [])
        
        # Get the newest transactions
        newest_params = {
            "pageSize": 10,
            "sortOrder": "desc"  # Newest first
        }
        
        newest_result = api.get_mutations(newest_params)
        if not newest_result["success"]:
            return {"success": False, "error": "Failed to get newest transactions"}
        
        newest_data = json.loads(newest_result["data"])
        newest_mutations = newest_data.get("items", [])
        
        if not oldest_mutations or not newest_mutations:
            return {"success": False, "error": "No transactions found in E-Boekhouden"}
        
        # Extract dates
        oldest_date = oldest_mutations[0].get("date", "")
        newest_date = newest_mutations[0].get("date", "")
        
        # Parse dates
        oldest_datetime = datetime.strptime(oldest_date[:10], "%Y-%m-%d")
        newest_datetime = datetime.strptime(newest_date[:10], "%Y-%m-%d")
        
        # Determine opening balance date (start of the year of oldest transaction)
        opening_balance_year = oldest_datetime.year
        opening_balance_date = f"{opening_balance_year}-01-01"
        
        # The actual migration should start from the opening balance date
        migration_start_date = opening_balance_date
        migration_end_date = newest_date[:10]
        
        return {
            "success": True,
            "start_date": migration_start_date,
            "end_date": migration_end_date,
            "oldest_transaction_date": oldest_date[:10],
            "newest_transaction_date": newest_date[:10],
            "opening_balance_date": opening_balance_date,
            "years_covered": newest_datetime.year - oldest_datetime.year + 1,
            "total_days": (newest_datetime - oldest_datetime).days
        }
        
    except Exception as e:
        return {"success": False, "error": f"Error determining date range: {str(e)}"}


def _create_opening_balance_safe(opening_balance_date):
    """
    Safely create opening balance, checking if it already exists
    """
    try:
        # Check if opening balance already exists
        existing = frappe.db.exists("Journal Entry", {
            "posting_date": opening_balance_date,
            "user_remark": ["like", "%Opening Balance - E-Boekhouden%"]
        })
        
        if existing:
            return {
                "success": True,
                "skipped": True,
                "message": f"Opening balance already exists: {existing}",
                "journal_entry": existing
            }
        
        # Create opening balance
        result = create_opening_balance_journal_entry(opening_balance_date)
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error creating opening balance: {str(e)}"
        }


def _migrate_all_transactions(migration, start_date, end_date):
    """
    Migrate all transactions in batches
    """
    try:
        # Convert dates to datetime objects
        start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
        end_datetime = datetime.strptime(end_date, "%Y-%m-%d")
        
        # Process in monthly batches to avoid timeouts
        current_date = start_datetime
        total_created = 0
        total_errors = 0
        monthly_results = []
        
        while current_date <= end_datetime:
            # Calculate month end
            if current_date.month == 12:
                month_end = datetime(current_date.year + 1, 1, 1) - timedelta(days=1)
            else:
                month_end = datetime(current_date.year, current_date.month + 1, 1) - timedelta(days=1)
            
            # Don't go beyond end date
            if month_end > end_datetime:
                month_end = end_datetime
            
            month_start_str = current_date.strftime("%Y-%m-%d")
            month_end_str = month_end.strftime("%Y-%m-%d")
            
            frappe.msgprint(f"Processing {current_date.strftime('%B %Y')}...")
            
            # Migrate this month's transactions
            month_result = migration.migrate_transactions(
                from_date=month_start_str,
                to_date=month_end_str
            )
            
            if month_result["success"]:
                total_created += month_result["created"]
                total_errors += month_result["errors"]
                monthly_results.append({
                    "month": current_date.strftime("%B %Y"),
                    "created": month_result["created"],
                    "errors": month_result["errors"]
                })
            
            # Move to next month
            current_date = month_end + timedelta(days=1)
        
        return {
            "success": True,
            "total_created": total_created,
            "total_errors": total_errors,
            "monthly_breakdown": monthly_results
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error migrating transactions: {str(e)}"
        }


def _create_payment_entries(start_date, end_date):
    """
    Create payment entries for bank and cash transactions
    """
    try:
        payment_migration = EBoekhoudenPaymentMigration()
        
        # Process in monthly batches
        start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
        end_datetime = datetime.strptime(end_date, "%Y-%m-%d")
        
        current_date = start_datetime
        total_created = 0
        total_errors = 0
        monthly_results = []
        
        while current_date <= end_datetime:
            # Calculate month end
            if current_date.month == 12:
                month_end = datetime(current_date.year + 1, 1, 1) - timedelta(days=1)
            else:
                month_end = datetime(current_date.year, current_date.month + 1, 1) - timedelta(days=1)
            
            if month_end > end_datetime:
                month_end = end_datetime
            
            month_start_str = current_date.strftime("%Y-%m-%d")
            month_end_str = month_end.strftime("%Y-%m-%d")
            
            # Create payment entries for this month
            month_result = payment_migration.create_payment_entries_from_journal(
                from_date=month_start_str,
                to_date=month_end_str
            )
            
            if month_result["success"]:
                total_created += month_result.get("created", 0)
                total_errors += month_result.get("errors", 0)
                monthly_results.append({
                    "month": current_date.strftime("%B %Y"),
                    "created": month_result.get("created", 0),
                    "errors": month_result.get("errors", 0)
                })
            
            current_date = month_end + timedelta(days=1)
        
        return {
            "success": True,
            "total_created": total_created,
            "total_errors": total_errors,
            "monthly_breakdown": monthly_results
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error creating payment entries: {str(e)}"
        }


def _generate_migration_summary(date_range, opening_balance, coa, transactions, payments):
    """
    Generate a comprehensive migration summary
    """
    summary = {
        "migration_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "date_range": {
            "from": date_range.get("start_date"),
            "to": date_range.get("end_date"),
            "years": date_range.get("years_covered"),
            "days": date_range.get("total_days")
        },
        "results": {
            "opening_balance": {
                "created": opening_balance.get("success", False) and not opening_balance.get("skipped", False),
                "journal_entry": opening_balance.get("journal_entry"),
                "message": opening_balance.get("message", opening_balance.get("error"))
            },
            "chart_of_accounts": {
                "success": coa.get("success", False),
                "accounts_created": coa.get("created", 0),
                "accounts_updated": coa.get("updated", 0),
                "total_accounts": coa.get("total", 0)
            },
            "transactions": {
                "success": transactions.get("success", False),
                "journal_entries_created": transactions.get("total_created", 0),
                "errors": transactions.get("total_errors", 0),
                "monthly_breakdown": transactions.get("monthly_breakdown", [])
            },
            "payment_entries": {
                "success": payments.get("success", False),
                "payment_entries_created": payments.get("total_created", 0),
                "errors": payments.get("total_errors", 0),
                "monthly_breakdown": payments.get("monthly_breakdown", [])
            }
        },
        "totals": {
            "total_accounts": coa.get("total", 0),
            "total_journal_entries": transactions.get("total_created", 0),
            "total_payment_entries": payments.get("total_created", 0),
            "total_errors": (
                transactions.get("total_errors", 0) + 
                payments.get("total_errors", 0)
            )
        }
    }
    
    return summary


@frappe.whitelist()
def get_migration_status():
    """
    Check the current migration status
    """
    try:
        status = {
            "has_opening_balance": False,
            "opening_balance_date": None,
            "opening_balance_entry": None,
            "journal_entries_count": 0,
            "payment_entries_count": 0,
            "earliest_transaction": None,
            "latest_transaction": None,
            "eboekhouden_accounts": 0,
            "migration_complete": False
        }
        
        # Check for opening balance
        opening_balance = frappe.db.get_value(
            "Journal Entry",
            {"user_remark": ["like", "%Opening Balance - E-Boekhouden%"]},
            ["name", "posting_date"],
            as_dict=True
        )
        
        if opening_balance:
            status["has_opening_balance"] = True
            status["opening_balance_date"] = str(opening_balance.posting_date)
            status["opening_balance_entry"] = opening_balance.name
        
        # Count E-Boekhouden migrated entries
        je_count = frappe.db.count(
            "Journal Entry",
            {"user_remark": ["like", "%E-Boekhouden%"]}
        )
        status["journal_entries_count"] = je_count
        
        # Count payment entries
        pe_count = frappe.db.count(
            "Payment Entry",
            {"remarks": ["like", "%E-Boekhouden%"]}
        )
        status["payment_entries_count"] = pe_count
        
        # Get date range of migrated transactions
        earliest = frappe.db.sql("""
            SELECT MIN(posting_date) as earliest
            FROM `tabJournal Entry`
            WHERE user_remark LIKE '%E-Boekhouden%'
            AND user_remark NOT LIKE '%Opening Balance%'
        """, as_dict=True)
        
        latest = frappe.db.sql("""
            SELECT MAX(posting_date) as latest
            FROM `tabJournal Entry`
            WHERE user_remark LIKE '%E-Boekhouden%'
        """, as_dict=True)
        
        if earliest and earliest[0].earliest:
            status["earliest_transaction"] = str(earliest[0].earliest)
        
        if latest and latest[0].latest:
            status["latest_transaction"] = str(latest[0].latest)
        
        # Count E-Boekhouden accounts
        account_count = frappe.db.count(
            "Account",
            {"account_number": ["like", "%"]}
        )
        status["eboekhouden_accounts"] = account_count
        
        # Simple check if migration seems complete
        status["migration_complete"] = (
            status["has_opening_balance"] and 
            status["journal_entries_count"] > 0 and
            status["eboekhouden_accounts"] > 0
        )
        
        return {"success": True, "status": status}
        
    except Exception as e:
        frappe.log_error(f"Error checking migration status: {str(e)}", "Migration Status Check")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def cleanup_failed_migration():
    """
    Cleanup function to remove failed or test migration data
    
    WARNING: This will delete all E-Boekhouden migrated data!
    Use with caution.
    """
    try:
        if not frappe.conf.developer_mode:
            return {
                "success": False,
                "error": "This function can only be run in developer mode for safety"
            }
        
        deleted_counts = {}
        
        # Delete E-Boekhouden journal entries
        je_list = frappe.get_all(
            "Journal Entry",
            filters={"user_remark": ["like", "%E-Boekhouden%"]},
            fields=["name"]
        )
        
        for je in je_list:
            doc = frappe.get_doc("Journal Entry", je.name)
            if doc.docstatus == 1:
                doc.cancel()
            doc.delete()
        
        deleted_counts["journal_entries"] = len(je_list)
        
        # Delete E-Boekhouden payment entries
        pe_list = frappe.get_all(
            "Payment Entry",
            filters={"remarks": ["like", "%E-Boekhouden%"]},
            fields=["name"]
        )
        
        for pe in pe_list:
            doc = frappe.get_doc("Payment Entry", pe.name)
            if doc.docstatus == 1:
                doc.cancel()
            doc.delete()
        
        deleted_counts["payment_entries"] = len(pe_list)
        
        frappe.db.commit()
        
        return {
            "success": True,
            "message": "Migration data cleaned up",
            "deleted": deleted_counts
        }
        
    except Exception as e:
        frappe.db.rollback()
        return {"success": False, "error": str(e)}