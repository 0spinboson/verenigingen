"""
API endpoint to check and fix missing subscription plans for membership types
"""

import frappe
from frappe import _

@frappe.whitelist()
def check_membership_subscription_plans():
    """Check which membership types are missing subscription plans"""
    membership_types = frappe.get_all('Membership Type', 
        fields=['name', 'membership_type_name', 'amount', 'billing_interval', 'subscription_plan'],
        order_by='name'
    )
    
    subscription_plans = frappe.get_all('Subscription Plan', 
        fields=['name', 'plan_name', 'cost', 'billing_interval'],
        order_by='name'
    )
    
    missing_plans = [mt for mt in membership_types if not mt.subscription_plan]
    
    return {
        "membership_types": membership_types,
        "subscription_plans": subscription_plans,
        "missing_plans": missing_plans,
        "missing_count": len(missing_plans)
    }

@frappe.whitelist()
def create_missing_subscription_plans():
    """Create subscription plans for membership types that don't have them"""
    membership_types = frappe.get_all('Membership Type', 
        fields=['name', 'membership_type_name', 'subscription_plan'],
        filters={'subscription_plan': ['is', 'not set']}
    )
    
    results = []
    errors = []
    
    for mt in membership_types:
        try:
            membership_type_doc = frappe.get_doc("Membership Type", mt.name)
            plan_name = membership_type_doc.create_subscription_plan()
            results.append({
                "membership_type": mt.name,
                "subscription_plan": plan_name,
                "success": True
            })
        except Exception as e:
            errors.append({
                "membership_type": mt.name,
                "error": str(e),
                "success": False
            })
    
    if results:
        frappe.db.commit()
    
    return {
        "success": len(errors) == 0,
        "created_plans": results,
        "errors": errors,
        "total_created": len(results)
    }

@frappe.whitelist()
def create_subscription_plan_for_membership_type(membership_type_name):
    """Create a subscription plan for a specific membership type"""
    try:
        membership_type_doc = frappe.get_doc("Membership Type", membership_type_name)
        plan_name = membership_type_doc.create_subscription_plan()
        frappe.db.commit()
        
        return {
            "success": True,
            "membership_type": membership_type_name,
            "subscription_plan": plan_name,
            "message": f"Subscription plan '{plan_name}' created successfully"
        }
    except Exception as e:
        return {
            "success": False,
            "membership_type": membership_type_name,
            "error": str(e),
            "message": f"Failed to create subscription plan: {str(e)}"
        }