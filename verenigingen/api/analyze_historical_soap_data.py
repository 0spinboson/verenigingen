"""
Analyze E-Boekhouden SOAP API historical data from 2018
"""

import frappe
from frappe import _
from datetime import datetime

@frappe.whitelist()
def analyze_historical_mutations():
    """
    Analyze mutations from the full historical range starting from 2018
    """
    try:
        from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
        
        settings = frappe.get_single("E-Boekhouden Settings")
        api = EBoekhoudenSOAPAPI(settings)
        
        # Get mutations from the historical start date
        date_from = "2018-12-31"  # User mentioned transactions start from December 31, 2018
        date_to = frappe.utils.today()
        
        result = api.get_mutations(date_from=date_from, date_to=date_to)
        
        if not result["success"]:
            return {
                "success": False,
                "error": result.get("error"),
                "date_range": f"{date_from} to {date_to}"
            }
        
        mutations = result["mutations"]
        
        # Analyze the data
        analysis = {
            "total_mutations": len(mutations),
            "date_range": f"{date_from} to {date_to}",
            "earliest_date": None,
            "latest_date": None,
            "mutations_by_year": {},
            "mutations_by_type": {},
            "sample_mutations": []
        }
        
        # Process mutations
        for mut in mutations:
            # Get date
            datum = mut.get("Datum", "")
            if datum:
                try:
                    # Parse date (assuming format YYYY-MM-DD or similar)
                    date_str = datum[:10] if len(datum) >= 10 else datum
                    year = date_str[:4]
                    
                    # Track earliest and latest
                    if not analysis["earliest_date"] or date_str < analysis["earliest_date"]:
                        analysis["earliest_date"] = date_str
                    if not analysis["latest_date"] or date_str > analysis["latest_date"]:
                        analysis["latest_date"] = date_str
                    
                    # Count by year
                    if year not in analysis["mutations_by_year"]:
                        analysis["mutations_by_year"][year] = 0
                    analysis["mutations_by_year"][year] += 1
                except:
                    pass
            
            # Count by type
            soort = mut.get("Soort", "Unknown")
            if soort not in analysis["mutations_by_type"]:
                analysis["mutations_by_type"][soort] = 0
            analysis["mutations_by_type"][soort] += 1
            
            # Collect samples (first 10)
            if len(analysis["sample_mutations"]) < 10:
                analysis["sample_mutations"].append({
                    "MutatieNr": mut.get("MutatieNr"),
                    "Datum": mut.get("Datum", "")[:10] if mut.get("Datum") else "",
                    "Omschrijving": mut.get("Omschrijving", "")[:100],
                    "Soort": soort,
                    "Factuurnummer": mut.get("Factuurnummer"),
                    "RelatieCode": mut.get("RelatieCode"),
                    "Rekening": mut.get("Rekening"),
                    "MutatieRegels": len(mut.get("MutatieRegels", []))
                })
        
        return {
            "success": True,
            "analysis": analysis,
            "message": f"Successfully analyzed {len(mutations)} mutations from {date_from} to {date_to}"
        }
        
    except Exception as e:
        frappe.log_error(f"Historical mutation analysis error: {str(e)}", "E-Boekhouden SOAP")
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def analyze_date_range_limits():
    """
    Test different date ranges to understand API limits
    """
    try:
        from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
        
        settings = frappe.get_single("E-Boekhouden Settings")
        api = EBoekhoudenSOAPAPI(settings)
        
        test_ranges = [
            ("2018-12-31", "2019-01-31", "First month from start"),
            ("2019-01-01", "2019-12-31", "Year 2019"),
            ("2020-01-01", "2020-12-31", "Year 2020"),
            ("2021-01-01", "2021-12-31", "Year 2021"),
            ("2022-01-01", "2022-12-31", "Year 2022"),
            ("2023-01-01", "2023-12-31", "Year 2023"),
            ("2024-01-01", "2024-12-31", "Year 2024"),
            ("2025-01-01", frappe.utils.today(), "Year 2025 to today"),
            (None, None, "No date filter"),
        ]
        
        results = []
        
        for date_from, date_to, label in test_ranges:
            try:
                result = api.get_mutations(date_from=date_from, date_to=date_to)
                
                if result["success"]:
                    mutations = result["mutations"]
                    
                    # Get actual date range from data
                    actual_earliest = None
                    actual_latest = None
                    
                    for mut in mutations:
                        datum = mut.get("Datum", "")[:10] if mut.get("Datum") else ""
                        if datum:
                            if not actual_earliest or datum < actual_earliest:
                                actual_earliest = datum
                            if not actual_latest or datum > actual_latest:
                                actual_latest = datum
                    
                    results.append({
                        "label": label,
                        "requested_from": date_from,
                        "requested_to": date_to,
                        "count": len(mutations),
                        "actual_earliest": actual_earliest,
                        "actual_latest": actual_latest,
                        "success": True
                    })
                else:
                    results.append({
                        "label": label,
                        "requested_from": date_from,
                        "requested_to": date_to,
                        "error": result.get("error"),
                        "success": False
                    })
            except Exception as e:
                results.append({
                    "label": label,
                    "requested_from": date_from,
                    "requested_to": date_to,
                    "error": str(e),
                    "success": False
                })
        
        return {
            "success": True,
            "results": results,
            "summary": "Tested various date ranges to understand API behavior"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def get_earliest_mutation():
    """
    Find the earliest mutation by testing different years
    """
    try:
        from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
        
        settings = frappe.get_single("E-Boekhouden Settings")
        api = EBoekhoudenSOAPAPI(settings)
        
        # Start from current year and work backwards
        current_year = datetime.now().year
        earliest_found = None
        
        for year in range(current_year, 2015, -1):  # Go back to 2015
            date_from = f"{year}-01-01"
            date_to = f"{year}-12-31"
            
            result = api.get_mutations(date_from=date_from, date_to=date_to)
            
            if result["success"] and result["mutations"]:
                # Find earliest in this year
                for mut in result["mutations"]:
                    datum = mut.get("Datum", "")[:10] if mut.get("Datum") else ""
                    if datum:
                        if not earliest_found or datum < earliest_found["date"]:
                            earliest_found = {
                                "date": datum,
                                "mutation": {
                                    "MutatieNr": mut.get("MutatieNr"),
                                    "Omschrijving": mut.get("Omschrijving", "")[:100],
                                    "Soort": mut.get("Soort"),
                                    "year_checked": year
                                }
                            }
        
        return {
            "success": True,
            "earliest_found": earliest_found,
            "message": f"Checked years from {current_year} back to 2016"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def check_2018_data():
    """
    Specifically check for 2018 data
    """
    try:
        from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
        
        settings = frappe.get_single("E-Boekhouden Settings")
        api = EBoekhoudenSOAPAPI(settings)
        
        # Check December 2018
        result = api.get_mutations(date_from="2018-12-01", date_to="2018-12-31")
        
        if result["success"]:
            mutations = result["mutations"]
            
            # Find mutations from Dec 31, 2018
            dec_31_mutations = []
            for mut in mutations:
                datum = mut.get("Datum", "")
                if "2018-12-31" in datum:
                    dec_31_mutations.append({
                        "MutatieNr": mut.get("MutatieNr"),
                        "Datum": datum[:10],
                        "Omschrijving": mut.get("Omschrijving", "")[:100],
                        "Soort": mut.get("Soort")
                    })
            
            return {
                "success": True,
                "total_december_2018": len(mutations),
                "dec_31_mutations": len(dec_31_mutations),
                "samples": dec_31_mutations[:5],
                "message": f"Found {len(mutations)} mutations in December 2018"
            }
        else:
            return {
                "success": False,
                "error": result.get("error")
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def search_by_mutation_number():
    """
    Try to find older mutations by mutation number
    """
    try:
        from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
        
        settings = frappe.get_single("E-Boekhouden Settings")
        api = EBoekhoudenSOAPAPI(settings)
        
        # The earliest mutation we found was 1297 from 2019-01-05
        # Let's try to find earlier mutation numbers
        test_ranges = [
            (1, 100, "First 100 mutations"),
            (100, 500, "Mutations 100-500"),
            (500, 1000, "Mutations 500-1000"),
            (1000, 1296, "Mutations 1000-1296"),
            (1200, 1300, "Around mutation 1297")
        ]
        
        results = []
        
        for nr_from, nr_to, label in test_ranges:
            try:
                result = api.get_mutations(mutation_nr_from=nr_from, mutation_nr_to=nr_to)
                
                if result["success"] and result["mutations"]:
                    # Get date range
                    dates = []
                    for mut in result["mutations"]:
                        datum = mut.get("Datum", "")[:10] if mut.get("Datum") else ""
                        if datum:
                            dates.append(datum)
                    
                    dates.sort()
                    
                    results.append({
                        "label": label,
                        "nr_from": nr_from,
                        "nr_to": nr_to,
                        "count": len(result["mutations"]),
                        "earliest_date": dates[0] if dates else None,
                        "latest_date": dates[-1] if dates else None,
                        "success": True
                    })
                else:
                    results.append({
                        "label": label,
                        "nr_from": nr_from,
                        "nr_to": nr_to,
                        "count": 0,
                        "success": False,
                        "error": result.get("error", "No mutations found")
                    })
            except Exception as e:
                results.append({
                    "label": label,
                    "nr_from": nr_from,
                    "nr_to": nr_to,
                    "error": str(e),
                    "success": False
                })
        
        return {
            "success": True,
            "results": results,
            "message": "Searched for mutations by mutation number ranges"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }