import frappe
from frappe.utils import getdate
from datetime import timedelta
import json

@frappe.whitelist()
def analyze_migration_count():
    """Analyze why migration shows 1621 records"""
    
    # Get the latest migration
    latest_migration = frappe.get_list(
        "E-Boekhouden Migration",
        fields=["name", "date_from", "date_to", "total_records", "imported_records", "failed_records"],
        order_by="creation desc",
        limit=1
    )[0]
    
    # Simulate what the grouped migration does
    from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenAPI(settings)
    
    # The grouped migration processes month by month
    all_mutations = []
    current_date = getdate(latest_migration.date_from)
    end_date = getdate(latest_migration.date_to)
    
    month_counts = {}
    
    while current_date <= end_date:
        # Calculate month end
        if current_date.month == 12:
            month_end = current_date.replace(year=current_date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = current_date.replace(month=current_date.month + 1, day=1) - timedelta(days=1)
        
        month_end = min(month_end, end_date)
        
        # Get mutations for this month
        params = {
            "dateFrom": current_date.strftime("%Y-%m-%d"),
            "dateTo": month_end.strftime("%Y-%m-%d")
        }
        
        # Log what we're requesting
        month_key = current_date.strftime("%Y-%m")
        
        result = api.get_mutations(params)
        if result["success"]:
            data = json.loads(result["data"])
            mutations = data.get("items", [])
            month_counts[month_key] = len(mutations)
            all_mutations.extend(mutations)
        
        # Move to next month
        if current_date.month == 12:
            current_date = current_date.replace(year=current_date.year + 1, month=1, day=1)
        else:
            current_date = current_date.replace(month=current_date.month + 1, day=1)
        
        # Stop after 3 months for debugging
        if len(month_counts) >= 3:
            break
    
    # Check for duplicates
    mutation_ids = [m.get("id") for m in all_mutations if m.get("id")]
    unique_ids = set(mutation_ids)
    
    return {
        "migration": latest_migration,
        "month_counts": month_counts,
        "total_fetched": len(all_mutations),
        "unique_mutations": len(unique_ids),
        "duplicates": len(mutation_ids) - len(unique_ids),
        "note": "The API returns ALL mutations regardless of date filter!",
        "explanation": "The 1621 might be the count after deduplication or filtering"
    }

if __name__ == "__main__":
    print(analyze_migration_count())