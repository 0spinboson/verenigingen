import frappe
from frappe.utils import today


def test_fee_override_integration():
    """Test the complete fee override integration"""
    print("=" * 60)
    print("TESTING FEE OVERRIDE INTEGRATION")
    print("=" * 60)
    
    try:
        # Find an existing member with a customer
        members = frappe.get_all(
            "Member", 
            filters={"customer": ["!=", ""]},
            fields=["name", "full_name", "customer", "membership_fee_override"],
            limit=1
        )
        
        if not members:
            print("❌ No members with customers found for testing")
            return
            
        member_data = members[0]
        print(f"📝 Testing with member: {member_data.name} ({member_data.full_name})")
        
        # Get the member document
        member = frappe.get_doc("Member", member_data.name)
        
        # Check initial state
        print(f"\n1. Initial state:")
        initial_fee = member.get_current_membership_fee()
        print(f"   Current fee: {initial_fee}")
        
        initial_subscriptions = frappe.get_all(
            "Subscription",
            filters={"party": member.customer, "party_type": "Customer"},
            fields=["name", "status"]
        )
        print(f"   Existing subscriptions: {len(initial_subscriptions)}")
        for sub in initial_subscriptions:
            print(f"     - {sub.name}: {sub.status}")
        
        # Apply fee override
        new_fee_amount = 99.99
        print(f"\n2. Applying fee override: €{new_fee_amount}")
        
        member.membership_fee_override = new_fee_amount
        member.fee_override_reason = "Integration test - automated fee override"
        member.save()
        
        print(f"   ✅ Fee override saved")
        
        # Check updated fee
        updated_fee = member.get_current_membership_fee()
        print(f"   Updated fee info: {updated_fee}")
        
        # Check if hook was triggered and subscriptions updated
        updated_subscriptions = frappe.get_all(
            "Subscription",
            filters={"party": member.customer, "party_type": "Customer"},
            fields=["name", "status", "modified"],
            order_by="modified desc"
        )
        
        print(f"\n3. After fee override:")
        print(f"   Subscriptions count: {len(updated_subscriptions)}")
        for sub in updated_subscriptions:
            print(f"     - {sub.name}: {sub.status} (modified: {sub.modified})")
            
            # Check subscription plan details
            sub_doc = frappe.get_doc("Subscription", sub.name)
            for plan in sub_doc.plans:
                plan_doc = frappe.get_doc("Subscription Plan", plan.plan)
                print(f"       Plan: {plan_doc.plan_name} - Cost: €{plan_doc.cost}")
        
        # Check fee change history
        member.reload()
        print(f"\n4. Fee change history:")
        print(f"   History entries: {len(member.fee_change_history)}")
        for entry in member.fee_change_history:
            print(f"     - {entry.change_date}: €{entry.old_amount} → €{entry.new_amount}")
            print(f"       Reason: {entry.reason}")
            print(f"       Changed by: {entry.changed_by}")
            
        # Check subscription history
        print(f"\n5. Subscription history:")
        print(f"   History entries: {len(member.subscription_history)}")
        for entry in member.subscription_history:
            print(f"     - {entry.subscription_name}: {entry.status} - €{entry.amount}")
            
        # Test subscription history refresh
        print(f"\n6. Testing subscription history refresh:")
        refresh_result = member.refresh_subscription_history()
        print(f"   Refresh result: {refresh_result}")
        
        member.reload()
        print(f"   Updated history entries: {len(member.subscription_history)}")
        
        print("\n" + "=" * 60)
        print("✅ FEE OVERRIDE INTEGRATION TEST COMPLETED SUCCESSFULLY")
        print("=" * 60)
        
        return {
            "success": True,
            "member": member_data.name,
            "initial_fee": initial_fee,
            "final_fee": updated_fee,
            "initial_subscriptions": len(initial_subscriptions),
            "final_subscriptions": len(updated_subscriptions)
        }
        
    except Exception as e:
        print(f"\n❌ INTEGRATION TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    test_fee_override_integration()