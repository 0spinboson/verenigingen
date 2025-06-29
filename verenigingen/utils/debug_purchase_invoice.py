"""
Debug purchase invoice creation
"""

import frappe
from frappe.utils import getdate, add_days

@frappe.whitelist()
def debug_pi_dates():
    """Debug the date handling in purchase invoice"""
    
    # Data from failed record
    date_str = "2025-04-03T00:00:00"
    payment_terms_str = "30"
    
    # Parse date like in migration
    if 'T' in date_str:
        posting_date = date_str.split('T')[0]  # "2025-04-03"
    else:
        posting_date = date_str
    
    # Calculate due date
    payment_terms_int = int(payment_terms_str)
    due_date = add_days(posting_date, max(0, payment_terms_int))
    
    # What ERPNext will do
    posting_getdate = getdate(posting_date)
    due_getdate = getdate(due_date)
    
    return {
        "original_date": date_str,
        "parsed_posting_date": posting_date,
        "payment_terms": payment_terms_int,
        "calculated_due_date": str(due_date),
        "posting_date_type": type(posting_date).__name__,
        "due_date_type": type(due_date).__name__,
        "getdate_posting": str(posting_getdate),
        "getdate_due": str(due_getdate),
        "comparison": due_getdate >= posting_getdate,
        "date_diff": (due_getdate - posting_getdate).days if posting_getdate and due_getdate else None
    }

if __name__ == "__main__":
    print(debug_pi_dates())