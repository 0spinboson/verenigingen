"""
E-Boekhouden Date Range Analyzer
Analyzes actual transaction dates by fetching sample mutations
"""

import frappe
from frappe.utils import formatdate
from datetime import datetime


@frappe.whitelist()
def get_actual_date_range():
    """
    Get the actual date range of transactions in E-Boekhouden
    by fetching early and recent mutations
    """
    from .eboekhouden_soap_api import EBoekhoudenSOAPAPI
    
    # Get settings
    settings = frappe.get_single("E-Boekhouden Settings")
    if not settings:
        frappe.throw("E-Boekhouden Settings not configured")
    
    # Initialize API
    api = EBoekhoudenSOAPAPI(settings)
    
    # Get the highest mutation number first
    highest_result = api.get_highest_mutation_number()
    if not highest_result["success"]:
        frappe.throw(f"Failed to get mutation range: {highest_result.get('error')}")
    
    highest_mutation_nr = highest_result["highest_mutation_number"]
    if highest_mutation_nr == 0:
        return {
            "success": False,
            "error": "No mutations found in E-Boekhouden"
        }
    
    # Get early mutations (1-100) to find earliest date
    early_result = api.get_mutations(mutation_nr_from=1, mutation_nr_to=min(100, highest_mutation_nr))
    
    if not early_result["success"]:
        frappe.throw(f"Failed to fetch early mutations: {early_result.get('error')}")
    
    # Get recent mutations (last 100) to find latest date
    start_recent = max(1, highest_mutation_nr - 99)
    recent_result = api.get_mutations(mutation_nr_from=start_recent, mutation_nr_to=highest_mutation_nr)
    
    if not recent_result["success"]:
        frappe.throw(f"Failed to fetch recent mutations: {recent_result.get('error')}")
    
    # Find earliest and latest dates
    all_mutations = early_result["mutations"] + recent_result["mutations"]
    
    if not all_mutations:
        return {
            "success": False,
            "error": "No mutations found"
        }
    
    dates = []
    for mut in all_mutations:
        date_str = mut.get("Datum")
        if date_str:
            # Parse date - handle T format
            if 'T' in date_str:
                date_str = date_str.split('T')[0]
            try:
                dates.append(datetime.strptime(date_str, "%Y-%m-%d").date())
            except:
                pass
    
    if not dates:
        return {
            "success": False,
            "error": "No valid dates found in mutations"
        }
    
    earliest_date = min(dates)
    latest_date = max(dates)
    
    # Save to settings or cache
    save_date_range_to_settings(earliest_date, latest_date)
    
    return {
        "success": True,
        "earliest_date": str(earliest_date),
        "latest_date": str(latest_date),
        "earliest_formatted": formatdate(str(earliest_date)),
        "latest_formatted": formatdate(str(latest_date)),
        "total_mutations": highest_mutation_nr,
        "samples_analyzed": len(all_mutations)
    }


def save_date_range_to_settings(earliest_date, latest_date):
    """Save the date range to E-Boekhouden Settings for reuse"""
    try:
        settings = frappe.get_single("E-Boekhouden Settings")
        
        # Check if fields exist, if not add them via custom fields
        if not hasattr(settings, 'data_earliest_date'):
            # Add custom fields to store date range
            if not frappe.db.has_column("E-Boekhouden Settings", "data_earliest_date"):
                frappe.get_doc({
                    "doctype": "Custom Field",
                    "dt": "E-Boekhouden Settings",
                    "fieldname": "data_earliest_date",
                    "fieldtype": "Date",
                    "label": "Data Earliest Date",
                    "read_only": 1,
                    "insert_after": "default_fiscal_year"
                }).insert(ignore_permissions=True)
            
            if not frappe.db.has_column("E-Boekhouden Settings", "data_latest_date"):
                frappe.get_doc({
                    "doctype": "Custom Field",
                    "dt": "E-Boekhouden Settings",
                    "fieldname": "data_latest_date",
                    "fieldtype": "Date",
                    "label": "Data Latest Date",
                    "read_only": 1,
                    "insert_after": "data_earliest_date"
                }).insert(ignore_permissions=True)
            
            if not frappe.db.has_column("E-Boekhouden Settings", "date_range_last_updated"):
                frappe.get_doc({
                    "doctype": "Custom Field",
                    "dt": "E-Boekhouden Settings",
                    "fieldname": "date_range_last_updated",
                    "fieldtype": "Datetime",
                    "label": "Date Range Last Updated",
                    "read_only": 1,
                    "insert_after": "data_latest_date"
                }).insert(ignore_permissions=True)
            
            # Reload the document
            settings.reload()
        
        # Update the values
        frappe.db.set_value("E-Boekhouden Settings", settings.name, {
            "data_earliest_date": earliest_date,
            "data_latest_date": latest_date,
            "date_range_last_updated": frappe.utils.now()
        })
        
        frappe.db.commit()
        
    except Exception as e:
        frappe.log_error(f"Failed to save date range: {str(e)}", "E-Boekhouden Date Range")


@frappe.whitelist()
def get_cached_date_range():
    """Get cached date range from settings"""
    settings = frappe.get_single("E-Boekhouden Settings")
    
    # Check if we have cached values
    if hasattr(settings, 'data_earliest_date') and settings.data_earliest_date:
        return {
            "success": True,
            "cached": True,
            "earliest_date": str(settings.data_earliest_date),
            "latest_date": str(settings.data_latest_date),
            "earliest_formatted": formatdate(str(settings.data_earliest_date)),
            "latest_formatted": formatdate(str(settings.data_latest_date)),
            "last_updated": settings.date_range_last_updated
        }
    
    # No cached data, need to analyze
    return {
        "success": False,
        "cached": False,
        "message": "No cached date range found. Please analyze the data."
    }


@frappe.whitelist()
def analyze_date_distribution(sample_size=1000):
    """
    Analyze the distribution of transaction dates
    Useful for understanding data patterns
    """
    from .eboekhouden_soap_api import EBoekhoudenSOAPAPI
    from collections import defaultdict
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenSOAPAPI(settings)
    
    # Get a sample of mutations
    highest_result = api.get_highest_mutation_number()
    if not highest_result["success"]:
        return {"success": False, "error": "Failed to get mutation range"}
    
    highest_mutation_nr = highest_result["highest_mutation_number"]
    
    # Get evenly distributed sample
    sample_interval = max(1, highest_mutation_nr // sample_size)
    
    year_month_counts = defaultdict(int)
    year_counts = defaultdict(int)
    
    for i in range(0, min(sample_size, highest_mutation_nr), 1):
        mutation_nr = min(i * sample_interval + 1, highest_mutation_nr)
        
        result = api.get_mutations_by_number_range(mutation_nr, mutation_nr)
        if result["success"] and result["mutations"]:
            mut = result["mutations"][0]
            date_str = mut.get("Datum")
            if date_str:
                if 'T' in date_str:
                    date_str = date_str.split('T')[0]
                try:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                    year_month = f"{date_obj.year}-{date_obj.month:02d}"
                    year = str(date_obj.year)
                    
                    year_month_counts[year_month] += 1
                    year_counts[year] += 1
                except:
                    pass
    
    # Sort by date
    sorted_year_months = sorted(year_month_counts.items())
    sorted_years = sorted(year_counts.items())
    
    return {
        "success": True,
        "year_month_distribution": sorted_year_months,
        "year_distribution": sorted_years,
        "samples_analyzed": sum(year_month_counts.values()),
        "earliest_year_month": sorted_year_months[0][0] if sorted_year_months else None,
        "latest_year_month": sorted_year_months[-1][0] if sorted_year_months else None
    }