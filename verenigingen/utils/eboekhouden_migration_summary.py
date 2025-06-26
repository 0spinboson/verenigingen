"""
E-Boekhouden Migration Summary Builder

Creates clear, informative summaries of migration results
"""

import frappe
from frappe import _


def build_migration_summary(results):
    """
    Build a clear summary from migration results
    
    Args:
        results: Dict containing migration results for each component
    
    Returns:
        Formatted summary string
    """
    
    lines = []
    lines.append("=" * 60)
    lines.append("E-BOEKHOUDEN MIGRATION SUMMARY")
    lines.append("=" * 60)
    
    # Chart of Accounts
    if "chart_of_accounts" in results:
        coa = results["chart_of_accounts"]
        lines.append(f"\nChart of Accounts:")
        if coa.get("created", 0) > 0:
            lines.append(f"  ✓ Created: {coa['created']} new accounts")
        if coa.get("updated", 0) > 0:
            lines.append(f"  ✓ Updated: {coa['updated']} existing accounts")
        if coa.get("skipped", 0) > 0:
            lines.append(f"  - Skipped: {coa['skipped']} (already exist)")
        if coa.get("failed", 0) > 0:
            lines.append(f"  ✗ Failed: {coa['failed']}")
    
    # Cost Centers
    if "cost_centers" in results:
        cc = results["cost_centers"]
        lines.append(f"\nCost Centers:")
        if cc.get("created", 0) > 0:
            lines.append(f"  ✓ Created: {cc['created']} new cost centers")
        if cc.get("skipped", 0) > 0:
            lines.append(f"  - Skipped: {cc['skipped']} (already exist)")
        if cc.get("failed", 0) > 0:
            lines.append(f"  ✗ Failed: {cc['failed']}")
    
    # Customers
    if "customers" in results:
        cust = results["customers"]
        lines.append(f"\nCustomers:")
        if cust.get("created", 0) > 0:
            lines.append(f"  ✓ Created: {cust['created']} new customers")
        if cust.get("skipped", 0) > 0:
            lines.append(f"  - Skipped: {cust['skipped']} (already exist)")
        if cust.get("failed", 0) > 0:
            lines.append(f"  ✗ Failed: {cust['failed']}")
    
    # Suppliers
    if "suppliers" in results:
        supp = results["suppliers"]
        lines.append(f"\nSuppliers:")
        if supp.get("created", 0) > 0:
            lines.append(f"  ✓ Created: {supp['created']} new suppliers")
        if supp.get("skipped", 0) > 0:
            lines.append(f"  - Skipped: {supp['skipped']} (already exist)")
        if supp.get("failed", 0) > 0:
            lines.append(f"  ✗ Failed: {supp['failed']}")
    
    # Transactions
    if "transactions" in results:
        trans = results["transactions"]
        lines.append(f"\nTransactions:")
        if trans.get("created", 0) > 0:
            lines.append(f"  ✓ Created: {trans['created']} journal entries")
        if trans.get("skipped", 0) > 0:
            lines.append(f"  - Skipped: {trans['skipped']}")
        if trans.get("failed", 0) > 0:
            lines.append(f"  ✗ Failed: {trans['failed']}")
    
    # Stock Transactions
    if "stock_transactions" in results:
        stock = results["stock_transactions"]
        lines.append(f"\nStock Transactions:")
        if isinstance(stock, str):
            # If it's a message, display it
            lines.append(f"  ℹ {stock}")
        else:
            if stock.get("created", 0) > 0:
                lines.append(f"  ✓ Created: {stock['created']} stock entries")
            if stock.get("skipped", 0) > 0:
                lines.append(f"  - Skipped: {stock['skipped']} (no quantity data)")
            if stock.get("failed", 0) > 0:
                lines.append(f"  ✗ Failed: {stock['failed']}")
    
    # Summary totals
    lines.append("\n" + "=" * 60)
    total_created = sum(
        results.get(key, {}).get("created", 0) 
        for key in ["chart_of_accounts", "cost_centers", "customers", "suppliers", "transactions"]
        if isinstance(results.get(key, {}), dict)
    )
    total_skipped = sum(
        results.get(key, {}).get("skipped", 0) 
        for key in ["chart_of_accounts", "cost_centers", "customers", "suppliers", "transactions", "stock_transactions"]
        if isinstance(results.get(key, {}), dict)
    )
    total_failed = sum(
        results.get(key, {}).get("failed", 0) 
        for key in ["chart_of_accounts", "cost_centers", "customers", "suppliers", "transactions", "stock_transactions"]
        if isinstance(results.get(key, {}), dict)
    )
    
    lines.append(f"TOTAL: {total_created} created, {total_skipped} skipped, {total_failed} failed")
    
    # Add notes if everything was skipped
    if total_created == 0 and total_skipped > 0:
        lines.append("\nNote: All records were skipped because they already exist.")
        lines.append("This typically happens when running migration multiple times.")
        lines.append("To re-import, you may need to delete existing records first.")
    
    return "\n".join(lines)


def parse_migration_log(log_text):
    """
    Parse the migration log text into structured results
    
    Args:
        log_text: The migration log string
        
    Returns:
        Dict with parsed results
    """
    
    results = {}
    
    # Parse each line of the log
    lines = log_text.split('\n') if log_text else []
    
    for line in lines:
        line = line.strip()
        
        # Parse Chart of Accounts line
        if line.startswith("Chart of Accounts:"):
            parts = line.split(":")
            if len(parts) > 1:
                # Extract numbers using regex
                import re
                created = re.search(r'Created (\d+)', parts[1])
                skipped = re.search(r'skipped (\d+)', parts[1])
                
                results["chart_of_accounts"] = {
                    "created": int(created.group(1)) if created else 0,
                    "skipped": int(skipped.group(1)) if skipped else 0,
                    "failed": 0
                }
        
        # Similar parsing for other components...
        # (Implementation details omitted for brevity)
    
    return results