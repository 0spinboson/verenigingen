import frappe
from frappe import _

@frappe.whitelist()
def should_remove_prepare_system_button():
    """
    Analysis of whether the 'Prepare System' button should be removed
    """
    
    return {
        "recommendation": "Transform, don't remove",
        "reasons": [
            "SOAP API now handles all account/customer/supplier creation dynamically",
            "Account type fixing is now intelligent and based on actual usage patterns",
            "No need to pre-create cost centers or parties - they're created as needed",
            "System preparation steps are now integrated into the migration process itself"
        ],
        "useful_features_to_keep": [
            "Date range detection - helps users understand their data scope",
            "Connection testing - validates API credentials",
            "Data statistics - shows what will be imported"
        ],
        "suggested_changes": {
            "rename_to": "Analyze E-Boekhouden Data",
            "new_functionality": [
                "Show date range of available transactions",
                "Display count of mutations by type",
                "Preview account usage patterns",
                "Identify potential issues before migration"
            ],
            "remove": [
                "Cost center creation",
                "Party creation",
                "Account type adjustments",
                "Manual system preparation steps"
            ]
        }
    }

@frappe.whitelist()
def analyze_eboekhouden_data():
    """
    Analyze E-Boekhouden data without making any system changes
    This replaces the old 'prepare_system' functionality
    """
    
    from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    
    try:
        settings = frappe.get_single("E-Boekhouden Settings")
        api = EBoekhoudenSOAPAPI(settings)
        
        # First try to get early mutations by number range to find the actual start date
        early_result = api.get_mutations(mutation_nr_from=1, mutation_nr_to=100)
        
        # Then get recent mutations for analysis
        today = frappe.utils.today()
        one_year_ago = frappe.utils.add_years(today, -1)
        
        result = api.get_mutations(date_from=one_year_ago, date_to=today)
        
        if not result["success"]:
            return {
                "success": False,
                "error": result.get("error")
            }
        
        mutations = result["mutations"]
        
        # Check if we got early mutations to find actual start date
        actual_earliest_date = None
        if early_result["success"] and early_result["mutations"]:
            for early_mut in early_result["mutations"]:
                date_str = early_mut.get("Datum", "")
                if date_str:
                    date = date_str.split("T")[0] if "T" in date_str else date_str
                    if not actual_earliest_date or date < actual_earliest_date:
                        actual_earliest_date = date
        
        # Analyze the data
        analysis = {
            "date_range": {
                "earliest_date": actual_earliest_date,
                "latest_date": None
            },
            "mutation_types": {},
            "account_usage": {
                "receivable_accounts": set(),
                "payable_accounts": set(),
                "bank_accounts": set(),
                "income_accounts": set(),
                "expense_accounts": set()
            },
            "entities": {
                "unique_customers": set(),
                "unique_suppliers": set()
            }
        }
        
        for mut in mutations:
            # Update date range (only update earliest if we don't have one from early mutations)
            date_str = mut.get("Datum", "")
            if date_str:
                date = date_str.split("T")[0] if "T" in date_str else date_str
                if not actual_earliest_date:
                    if not analysis["date_range"]["earliest_date"] or date < analysis["date_range"]["earliest_date"]:
                        analysis["date_range"]["earliest_date"] = date
                if not analysis["date_range"]["latest_date"] or date > analysis["date_range"]["latest_date"]:
                    analysis["date_range"]["latest_date"] = date
            
            # Count mutation types
            mutation_type = mut.get("Soort", "Unknown")
            analysis["mutation_types"][mutation_type] = analysis["mutation_types"].get(mutation_type, 0) + 1
            
            # Analyze account usage
            account_code = mut.get("Rekening")
            if account_code:
                if mutation_type == "FactuurVerstuurd":
                    analysis["account_usage"]["receivable_accounts"].add(account_code)
                elif mutation_type == "FactuurOntvangen":
                    analysis["account_usage"]["payable_accounts"].add(account_code)
                elif mutation_type in ["GeldOntvangen", "GeldUitgegeven"]:
                    analysis["account_usage"]["bank_accounts"].add(account_code)
            
            # Count entities
            relation_code = mut.get("RelatieCode")
            if relation_code:
                if mutation_type in ["FactuurVerstuurd", "FactuurbetalingOntvangen"]:
                    analysis["entities"]["unique_customers"].add(relation_code)
                elif mutation_type in ["FactuurOntvangen", "FactuurbetalingVerstuurd"]:
                    analysis["entities"]["unique_suppliers"].add(relation_code)
            
            # Analyze line items for account usage
            for regel in mut.get("MutatieRegels", []):
                account_code = regel.get("TegenrekeningCode")
                if account_code:
                    if mutation_type in ["FactuurVerstuurd", "GeldOntvangen"]:
                        analysis["account_usage"]["income_accounts"].add(account_code)
                    elif mutation_type in ["FactuurOntvangen", "GeldUitgegeven"]:
                        analysis["account_usage"]["expense_accounts"].add(account_code)
        
        # Also get the actual account counts from the system
        actual_receivable_count = 0
        if frappe.db.exists("Company", settings.default_company):
            actual_receivable_count = frappe.db.count("Account", {
                "company": settings.default_company,
                "account_type": "Receivable",
                "is_group": 0
            })
        
        # Try to estimate total mutations by checking a higher range
        total_estimate = None
        high_range_result = api.get_mutations(mutation_nr_from=10000, mutation_nr_to=10100)
        if high_range_result["success"] and len(high_range_result["mutations"]) > 0:
            # If we get results in the 10000 range, there are at least 10000+ mutations
            total_estimate = "10,000+"
        
        # Convert sets to counts for JSON serialization
        summary = {
            "success": True,
            "date_range": analysis["date_range"],
            "total_mutations": len(mutations),
            "total_estimate": total_estimate,
            "mutation_types": analysis["mutation_types"],
            "account_summary": {
                "receivable_accounts": len(analysis["account_usage"]["receivable_accounts"]),
                "payable_accounts": len(analysis["account_usage"]["payable_accounts"]),
                "bank_accounts": len(analysis["account_usage"]["bank_accounts"]),
                "income_accounts": len(analysis["account_usage"]["income_accounts"]),
                "expense_accounts": len(analysis["account_usage"]["expense_accounts"]),
                "actual_receivable_accounts": actual_receivable_count
            },
            "entity_summary": {
                "unique_customers": len(analysis["entities"]["unique_customers"]),
                "unique_suppliers": len(analysis["entities"]["unique_suppliers"])
            },
            "insights": generate_insights(analysis, len(mutations))
        }
        
        return summary
        
    except Exception as e:
        frappe.log_error(f"E-Boekhouden analysis error: {str(e)}", "E-Boekhouden Analysis")
        return {
            "success": False,
            "error": str(e)
        }

def generate_insights(analysis, mutation_count=0):
    """Generate helpful insights from the analysis"""
    insights = []
    
    # Date range insight
    if analysis["date_range"]["earliest_date"] and analysis["date_range"]["latest_date"]:
        from datetime import datetime
        earliest = datetime.strptime(analysis["date_range"]["earliest_date"], "%Y-%m-%d")
        latest = datetime.strptime(analysis["date_range"]["latest_date"], "%Y-%m-%d")
        days = (latest - earliest).days
        insights.append(f"Your E-Boekhouden data spans {days} days ({days//365} years)")
    
    # Account type insights
    total_accounts = sum(len(accounts) for accounts in analysis["account_usage"].values())
    if total_accounts > 0:
        insights.append(f"Found {total_accounts} unique accounts in use across all transaction types")
    
    # Transaction volume insights
    total_mutations = sum(analysis["mutation_types"].values())
    if total_mutations > 100:
        insights.append("You have a substantial transaction history - migration may take several minutes")
    elif total_mutations < 10:
        insights.append("Light transaction volume detected - migration should be quick")
    
    # Entity insights
    customers = len(analysis["entities"]["unique_customers"])
    suppliers = len(analysis["entities"]["unique_suppliers"])
    if customers > 0 or suppliers > 0:
        insights.append(f"Will create {customers} customers and {suppliers} suppliers during migration")
    
    # Add warning about limited data
    if mutation_count == 500:
        insights.insert(0, "⚠️ Analysis limited to most recent 500 mutations. Full migration will process ALL historical data.")
    
    return insights