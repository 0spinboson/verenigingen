import frappe
import unittest
from frappe.utils import today, now


def run_subscription_debug():
    """Debug subscription creation and management directly"""
    print("=" * 60)
    print("DEBUGGING SUBSCRIPTION CREATION LOGIC")
    print("=" * 60)
    
    try:
        # Test 1: Check if required doctypes exist
        print("\n1. Checking required doctypes...")
        required_doctypes = ["Member", "Customer", "Subscription", "Subscription Plan", "Item"]
        for dt in required_doctypes:
            exists = frappe.db.exists("DocType", dt)
            print(f"   {dt}: {'✓' if exists else '✗'}")
            
        # Test 2: Check Member class methods
        print("\n2. Checking Member class methods...")
        from verenigingen.verenigingen.doctype.member.member import Member
        
        test_methods = [
            "get_current_membership_fee",
            "update_active_subscriptions", 
            "get_or_create_subscription_for_membership",
            "get_or_create_subscription_plan",
            "refresh_subscription_history"
        ]
        
        for method in test_methods:
            exists = hasattr(Member, method)
            print(f"   {method}: {'✓' if exists else '✗'}")
            
        # Test 3: Try to find an existing member to test with
        print("\n3. Looking for existing members...")
        existing_members = frappe.get_all(
            "Member", 
            filters={"customer": ["!=", ""]},
            fields=["name", "full_name", "customer"],
            limit=3
        )
        
        if existing_members:
            print(f"   Found {len(existing_members)} members with customers:")
            for member in existing_members:
                print(f"     - {member.name} ({member.full_name}) -> Customer: {member.customer}")
                
                # Test fee override methods on actual member
                try:
                    member_doc = frappe.get_doc("Member", member.name)
                    fee_info = member_doc.get_current_membership_fee()
                    print(f"       Current fee: {fee_info}")
                    
                    # Test subscription history refresh
                    result = member_doc.refresh_subscription_history()
                    print(f"       Subscription history refresh: {result}")
                    
                    # Check existing subscriptions
                    subscriptions = frappe.get_all(
                        "Subscription",
                        filters={"party": member.customer, "party_type": "Customer"},
                        fields=["name", "status", "start_date"]
                    )
                    print(f"       Existing subscriptions: {len(subscriptions)}")
                    for sub in subscriptions:
                        print(f"         - {sub.name}: {sub.status}")
                        
                except Exception as e:
                    print(f"       Error testing member {member.name}: {str(e)}")
                    
                # Only test first member to avoid spam
                break
        else:
            print("   No members with customers found")
            
        # Test 4: Test subscription plan creation
        print("\n4. Testing subscription plan creation...")
        try:
            # Check if we can create an item first
            test_item_code = "TEST-MEMBERSHIP-FEE"
            existing_item = frappe.db.exists("Item", test_item_code)
            
            if not existing_item:
                print("   Creating test item...")
                item = frappe.get_doc({
                    "doctype": "Item",
                    "item_code": test_item_code,
                    "item_name": "Test Membership Fee",
                    "item_group": "Services",
                    "is_service_item": 1,
                    "maintain_stock": 0,
                    "is_sales_item": 1
                })
                item.insert(ignore_permissions=True)
                print(f"     ✓ Created item: {item.name}")
            else:
                print(f"     ✓ Item already exists: {test_item_code}")
                
            # Now try to create a subscription plan
            test_plan_name = "Test Fee Plan - 150.00"
            existing_plan = frappe.db.exists("Subscription Plan", {"plan_name": test_plan_name})
            
            if not existing_plan:
                print("   Creating test subscription plan...")
                plan = frappe.get_doc({
                    "doctype": "Subscription Plan",
                    "plan_name": test_plan_name,
                    "item": test_item_code,
                    "price_determination": "Fixed Rate",
                    "cost": 150.00,
                    "billing_interval": "Month",
                    "enabled": 1
                })
                plan.insert(ignore_permissions=True)
                print(f"     ✓ Created subscription plan: {plan.name}")
            else:
                print(f"     ✓ Subscription plan already exists: {test_plan_name}")
                
        except Exception as e:
            print(f"   ✗ Error creating subscription plan: {str(e)}")
            import traceback
            traceback.print_exc()
            
        # Test 5: Test actual subscription creation
        if existing_members:
            print("\n5. Testing subscription creation...")
            member = existing_members[0]
            try:
                member_doc = frappe.get_doc("Member", member.name)
                
                # Test the update_active_subscriptions method
                print("   Testing update_active_subscriptions...")
                result = member_doc.update_active_subscriptions()
                print(f"     Result: {result}")
                
            except Exception as e:
                print(f"   ✗ Error testing subscription creation: {str(e)}")
                import traceback
                traceback.print_exc()
                
        # Test 6: Check hook configuration
        print("\n6. Checking hook configuration...")
        try:
            from verenigingen.hooks import doc_events
            member_hooks = doc_events.get("Member", {})
            print(f"   Member hooks configured: {list(member_hooks.keys())}")
            
            if "after_save" in member_hooks:
                after_save_hooks = member_hooks["after_save"]
                print(f"   After save hooks: {after_save_hooks}")
            else:
                print("   ✗ No after_save hooks configured for Member")
                
        except Exception as e:
            print(f"   ✗ Error checking hooks: {str(e)}")
            
        print("\n" + "=" * 60)
        print("DEBUG COMPLETED")
        print("=" * 60)
        
    except Exception as e:
        print(f"FATAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_subscription_debug()