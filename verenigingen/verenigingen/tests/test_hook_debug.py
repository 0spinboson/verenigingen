import frappe


def test_hook_behavior():
    """Test the fee override hook behavior"""
    print("=" * 50)
    print("TESTING HOOK BEHAVIOR")
    print("=" * 50)
    
    try:
        # Get a test member
        member = frappe.get_doc('Member', 'Assoc-Member-2025-05-0009')
        
        print(f"Testing with member: {member.name}")
        print(f"Current fee override: {member.membership_fee_override}")
        print(f"Current fee change history entries: {len(member.fee_change_history)}")
        
        # Set a new fee override and save
        print(f"\nChanging fee override to 88.88...")
        old_fee = member.membership_fee_override
        member.membership_fee_override = 88.88
        member.fee_override_reason = "Hook test"
        
        # Check if validation sets _pending_fee_change
        print("Calling validate()...")
        member.validate()
        
        has_pending = hasattr(member, '_pending_fee_change')
        print(f"Has _pending_fee_change after validate: {has_pending}")
        
        if has_pending:
            print(f"Pending change data: {member._pending_fee_change}")
        
        # Save the member
        print("Saving member...")
        member.save()
        
        # Check if fee change history was recorded
        member.reload()
        print(f"Fee change history entries after save: {len(member.fee_change_history)}")
        
        for entry in member.fee_change_history:
            print(f"  - {entry.change_date}: {entry.old_amount} -> {entry.new_amount}")
            print(f"    Reason: {entry.reason}")
            print(f"    Changed by: {entry.changed_by}")
            print(f"    Subscription action: {entry.subscription_action}")
        
        # Manually test the hook function
        print(f"\nManually testing hook function...")
        from verenigingen.verenigingen.doctype.member.member import handle_fee_override_after_save
        
        # Set up a pending change manually
        member._pending_fee_change = {
            "old_amount": old_fee,
            "new_amount": 88.88,
            "reason": "Manual hook test",
            "change_date": frappe.utils.now(),
            "changed_by": frappe.session.user
        }
        
        print("Calling handle_fee_override_after_save manually...")
        handle_fee_override_after_save(member)
        
        # Check results
        member.reload()
        print(f"Fee change history entries after manual hook: {len(member.fee_change_history)}")
        
        # Test subscription update
        print(f"\nTesting subscription update...")
        result = member.update_active_subscriptions()
        print(f"Subscription update result: {result}")
        
        return {"success": True}
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    test_hook_behavior()