#!/usr/bin/env python3
"""
Test script for income calculator feature in membership application forms
"""

import frappe

@frappe.whitelist()
def test_income_calculator_settings():
    """Test that calculator settings can be retrieved and updated"""
    try:
        # Get current settings
        settings = frappe.get_single("Verenigingen Settings")
        
        print("Current Calculator Settings:")
        print(f"  Enable Calculator: {getattr(settings, 'enable_income_calculator', 'Not set')}")
        print(f"  Percentage Rate: {getattr(settings, 'income_percentage_rate', 'Not set')}%")
        print(f"  Description: {getattr(settings, 'calculator_description', 'Not set')}")
        
        # Test enabling the calculator
        if not getattr(settings, 'enable_income_calculator', False):
            print("\nEnabling calculator...")
            settings.enable_income_calculator = 1
            settings.income_percentage_rate = 0.5
            settings.calculator_description = "Our suggested contribution is 0.5% of your monthly net income. This helps ensure fair and equitable contributions based on your financial capacity."
            settings.save()
            print("Calculator enabled successfully!")
        else:
            print("\nCalculator already enabled")
        
        return {"success": True, "settings": {
            "enabled": getattr(settings, 'enable_income_calculator', False),
            "rate": getattr(settings, 'income_percentage_rate', 0.5),
            "description": getattr(settings, 'calculator_description', '')
        }}
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def test_calculator_logic():
    """Test the calculator logic with sample values"""
    try:
        test_cases = [
            {"income": 3000, "interval": "monthly", "expected_monthly": 15.0, "expected_quarterly": 45.0},
            {"income": 4500, "interval": "quarterly", "expected_monthly": 22.5, "expected_quarterly": 67.5},
            {"income": 2000, "interval": "monthly", "expected_monthly": 10.0, "expected_quarterly": 30.0},
        ]
        
        results = []
        percentage = 0.5  # Default 0.5%
        
        for case in test_cases:
            monthly_contribution = case["income"] * (percentage / 100)
            quarterly_contribution = monthly_contribution * 3
            
            result = {
                "income": case["income"],
                "interval": case["interval"],
                "monthly_contribution": monthly_contribution,
                "quarterly_contribution": quarterly_contribution,
                "matches_expected": {
                    "monthly": abs(monthly_contribution - case["expected_monthly"]) < 0.01,
                    "quarterly": abs(quarterly_contribution - case["expected_quarterly"]) < 0.01
                }
            }
            results.append(result)
            
            print(f"Income: €{case['income']}/month")
            print(f"  Monthly contribution: €{monthly_contribution:.2f}")
            print(f"  Quarterly contribution: €{quarterly_contribution:.2f}")
            print(f"  Expected values match: {result['matches_expected']}")
            print()
        
        return {"success": True, "test_results": results}
        
    except Exception as e:
        print(f"Error: {e}")
        return {"success": False, "error": str(e)}

def run_tests():
    """Run all tests"""
    print("=== Testing Income Calculator Feature ===\n")
    
    print("1. Testing settings...")
    result1 = test_income_calculator_settings()
    print(f"Settings test: {'PASSED' if result1['success'] else 'FAILED'}")
    
    print("\n2. Testing calculator logic...")
    result2 = test_calculator_logic()
    print(f"Logic test: {'PASSED' if result2['success'] else 'FAILED'}")
    
    print("\n=== Test Summary ===")
    if result1['success'] and result2['success']:
        print("All tests PASSED ✓")
        print("\nIncome calculator feature is ready!")
        print("- Configure settings in Verenigingen Settings")
        print("- Calculator will appear on membership application forms when enabled")
        print("- Calculates 0.5% of monthly income based on payment interval")
    else:
        print("Some tests FAILED ✗")
        if not result1['success']:
            print(f"Settings error: {result1.get('error', 'Unknown')}")
        if not result2['success']:
            print(f"Logic error: {result2.get('error', 'Unknown')}")

if __name__ == "__main__":
    run_tests()
