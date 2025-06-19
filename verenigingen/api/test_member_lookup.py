"""
Test member lookup
"""

import frappe

@frappe.whitelist()
def test_member_lookup():
    """Test member lookup functionality"""
    try:
        # Get some existing members
        members = frappe.get_all("Member", 
            fields=["name", "email", "first_name", "last_name"], 
            limit=5)
        
        # Also check for specific test users
        test_members = []
        test_emails = ["foppe@veganisme.net", "jantje.paasman@leden.rsp.nu", "Administrator"]
        
        for email in test_emails:
            member = frappe.db.get_value("Member", {"email": email}, ["name", "first_name", "last_name"])
            if member:
                test_members.append({
                    "email": email,
                    "name": member[0] if isinstance(member, tuple) else member,
                    "first_name": member[1] if isinstance(member, tuple) and len(member) > 1 else None,
                    "last_name": member[2] if isinstance(member, tuple) and len(member) > 2 else None
                })
        
        return {
            "success": True,
            "existing_members": members,
            "test_members": test_members,
            "member_count": len(members)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }