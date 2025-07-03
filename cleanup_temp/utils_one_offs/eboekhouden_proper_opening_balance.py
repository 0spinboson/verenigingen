"""
E-Boekhouden Proper Opening Balance

Create opening balance based on the actual Beginbalans (Opening Balance) structure
"""

import frappe
from frappe import _
import json


@frappe.whitelist()
def create_opening_balance_from_beginbalans():
    """
    Create opening balance journal entry based on E-Boekhouden Beginbalans
    
    The Beginbalans shows:
    - Activa (Assets/Debit side) 
    - Passiva (Liabilities & Equity/Credit side)
    - Total: €112,365.14 on each side
    """
    
    # Define the opening balance as per the Beginbalans screenshot
    # Date: 31-12-2018
    opening_balance_data = [
        # Activa (Debit side)
        {"code": "02400", "name": "Apparatuur en toebehoren", "debit": 400.00, "credit": 0},
        {"code": "10000", "name": "Kas", "debit": 154.70, "credit": 0},
        {"code": "10440", "name": "Triodos - 19.83.96.716 - Algemeen", "debit": 5206.77, "credit": 0},
        {"code": "10470", "name": "PayPal - info@veganisme.org", "debit": 479.15, "credit": 0},
        {"code": "10620", "name": "ASN - 97.88.80.455", "debit": 96941.41, "credit": 0},
        {"code": "13500", "name": "Te ontvangen contributies", "debit": 1150.58, "credit": 0},
        {"code": "13510", "name": "Te ontvangen donaties", "debit": 212.45, "credit": 0},
        {"code": "13600", "name": "Te ontvangen rente", "debit": 66.71, "credit": 0},
        {"code": "13900", "name": "Te ontvangen bedragen", "debit": 3142.47, "credit": 0},
        {"code": "14200", "name": "Vooruitbetaalde verzekeringen", "debit": 25.80, "credit": 0},
        {"code": "14500", "name": "Vooruitbetaalde bedragen", "debit": 2028.04, "credit": 0},
        {"code": "30000", "name": "Voorraden", "debit": 1971.79, "credit": 0},
        {"code": "30010", "name": "Postzegelvoorraad", "debit": 585.27, "credit": 0},
        
        # Passiva (Credit side)
        {"code": "05000", "name": "Vrij besteedbaar eigen vermogen", "debit": 0, "credit": 38848.55},
        {"code": "05292", "name": "Bestemmingsreserve Melk Je Kan Zonder", "debit": 0, "credit": 1037.28},
        {"code": "05310", "name": "Continuïteitsreserve", "debit": 0, "credit": 40000.00},
        {"code": "05320", "name": "Continuïteitsreserve Productie", "debit": 0, "credit": 20000.00},
        {"code": "14600", "name": "Vooruitontvangen bedragen", "debit": 0, "credit": 1127.98},
        {"code": "17100", "name": "Reservering vakantiegeld", "debit": 0, "credit": 1256.15},
        {"code": "18100", "name": "Te betalen sociale lasten", "debit": 0, "credit": 1110.00},
        {"code": "18200", "name": "Reservering sociale lasten vakantiegeld", "debit": 0, "credit": 540.15},
        {"code": "19290", "name": "Te betalen bedragen", "debit": 0, "credit": 8445.03},
    ]
    
    # Verify totals
    total_debit = sum(entry["debit"] for entry in opening_balance_data)
    total_credit = sum(entry["credit"] for entry in opening_balance_data)
    
    return {
        "success": True,
        "opening_balance_date": "2018-12-31",
        "entries": opening_balance_data,
        "summary": {
            "total_debit": round(total_debit, 2),
            "total_credit": round(total_credit, 2),
            "expected_total": 112365.14,
            "balanced": abs(total_debit - total_credit) < 0.01,
            "debit_matches": abs(total_debit - 112365.14) < 0.01,
            "credit_matches": abs(total_credit - 112365.14) < 0.01
        }
    }


@frappe.whitelist()
def create_opening_balance_journal_entry(posting_date="2019-01-01"):
    """
    Create the actual opening balance journal entry in ERPNext
    """
    
    try:
        # Get the opening balance data
        balance_data = create_opening_balance_from_beginbalans()
        
        if not balance_data["success"]:
            return balance_data
        
        # Check if opening balance already exists
        existing = frappe.db.exists("Journal Entry", {
            "posting_date": posting_date,
            "user_remark": ["like", "%Opening Balance - E-Boekhouden%"]
        })
        
        if existing:
            return {
                "success": False,
                "error": f"Opening balance journal entry already exists: {existing}"
            }
        
        # Get settings
        settings = frappe.get_single("E-Boekhouden Settings")
        company = settings.default_company
        
        if not company:
            return {
                "success": False,
                "error": "No default company set in E-Boekhouden Settings"
            }
        
        # Create journal entry
        je = frappe.new_doc("Journal Entry")
        je.posting_date = posting_date
        je.company = company
        je.user_remark = "Opening Balance - E-Boekhouden Beginbalans 31-12-2018"
        
        # Process each entry
        skipped_accounts = []
        
        for entry in balance_data["entries"]:
            # Find the ERPNext account
            account = frappe.db.get_value(
                "Account",
                {"account_number": entry["code"], "company": company},
                "name"
            )
            
            if not account:
                # Try without company filter
                account = frappe.db.get_value(
                    "Account",
                    {"account_number": entry["code"]},
                    "name"
                )
            
            if not account:
                skipped_accounts.append(f"{entry['code']} - {entry['name']}")
                continue
            
            # Add to journal entry
            je.append("accounts", {
                "account": account,
                "debit_in_account_currency": entry["debit"],
                "credit_in_account_currency": entry["credit"],
                "user_remark": f"Opening balance: {entry['name']}",
                "cost_center": settings.default_cost_center
            })
        
        # Verify the journal entry is balanced
        total_debit = sum(acc.debit_in_account_currency for acc in je.accounts)
        total_credit = sum(acc.credit_in_account_currency for acc in je.accounts)
        
        if abs(total_debit - total_credit) > 0.01:
            return {
                "success": False,
                "error": f"Journal entry is not balanced. Debit: {total_debit}, Credit: {total_credit}",
                "skipped_accounts": skipped_accounts
            }
        
        # Save the journal entry
        if len(je.accounts) >= 2:
            je.insert(ignore_permissions=True)
            je.submit()
            
            return {
                "success": True,
                "journal_entry": je.name,
                "message": f"Created opening balance journal entry {je.name}",
                "summary": {
                    "total_accounts": len(je.accounts),
                    "total_debit": round(total_debit, 2),
                    "total_credit": round(total_credit, 2),
                    "skipped_accounts": skipped_accounts
                }
            }
        else:
            return {
                "success": False,
                "error": "Not enough accounts found to create journal entry",
                "skipped_accounts": skipped_accounts
            }
            
    except Exception as e:
        import traceback
        frappe.log_error(traceback.format_exc(), "Opening Balance Creation Error")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def validate_opening_balance_accounts():
    """
    Check which accounts from the Beginbalans exist in ERPNext
    """
    
    balance_data = create_opening_balance_from_beginbalans()
    settings = frappe.get_single("E-Boekhouden Settings")
    company = settings.default_company
    
    validation_results = []
    
    for entry in balance_data["entries"]:
        # Check if account exists
        account = frappe.db.get_value(
            "Account",
            {"account_number": entry["code"], "company": company},
            ["name", "account_name", "account_type", "root_type"],
            as_dict=True
        )
        
        if not account:
            # Try without company filter
            account = frappe.db.get_value(
                "Account",
                {"account_number": entry["code"]},
                ["name", "account_name", "account_type", "root_type"],
                as_dict=True
            )
        
        validation_results.append({
            "code": entry["code"],
            "name": entry["name"],
            "debit": entry["debit"],
            "credit": entry["credit"],
            "exists": bool(account),
            "erpnext_account": account.name if account else None,
            "account_type": account.account_type if account else None,
            "root_type": account.root_type if account else None
        })
    
    existing_count = sum(1 for r in validation_results if r["exists"])
    
    return {
        "success": True,
        "validation_results": validation_results,
        "summary": {
            "total_accounts": len(validation_results),
            "existing_accounts": existing_count,
            "missing_accounts": len(validation_results) - existing_count,
            "ready_for_opening_balance": existing_count == len(validation_results)
        }
    }