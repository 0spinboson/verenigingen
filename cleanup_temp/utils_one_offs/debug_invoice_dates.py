"""
Debug invoice date issues
"""

import frappe
from frappe.utils import add_days, today, getdate
from datetime import datetime

@frappe.whitelist()
def debug_date_issue():
    """Debug the date issue with purchase invoices"""
    
    # Test case from failed record
    posting_date_str = "2025-04-03T00:00:00"
    payment_terms = "30"
    
    # Parse date
    if 'T' in posting_date_str:
        posting_date = datetime.strptime(posting_date_str.split('T')[0], '%Y-%m-%d').date()
    else:
        posting_date = datetime.strptime(posting_date_str, '%Y-%m-%d').date()
    
    # Calculate due date
    payment_terms_int = int(payment_terms)
    due_date = add_days(posting_date, max(0, payment_terms_int))
    
    # Check today's date
    today_date = today()
    
    return {
        "today": today_date,
        "posting_date": str(posting_date),
        "payment_terms": payment_terms_int,
        "calculated_due_date": str(due_date),
        "due_date_after_posting": due_date > posting_date,
        "posting_date_type": type(posting_date).__name__,
        "due_date_type": type(due_date).__name__
    }

if __name__ == "__main__":
    print(debug_date_issue())