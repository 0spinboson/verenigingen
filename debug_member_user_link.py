#!/usr/bin/env python3

import frappe

@frappe.whitelist()
def debug_member_user_link():
    frappe.init(site='dev.veganisme.net')
    frappe.connect()
    frappe.set_user("Administrator")
    
    member_name = 'Assoc-Member-2025-07-0030'
    
    try:
        member = frappe.get_doc('Member', member_name)
        print(f'Member: {member.full_name}')
        print(f'Member email: {member.email}')
        print(f'User field value: "{member.user}"')
        print(f'User field type: {type(member.user)}')
        print(f'User field is empty: {not member.user}')
        
        if member.user:
            # Check if the user record exists
            user_exists = frappe.db.exists('User', member.user)
            print(f'User record exists: {user_exists}')
            
            if user_exists:
                user_doc = frappe.get_doc('User', member.user)
                print(f'User email: {user_doc.email}')
                print(f'User enabled: {user_doc.enabled}')
            else:
                print('User record does not exist in database')
        else:
            print('No user linked to this member')
            
            # Check if there's a user with the same email
            if member.email:
                users_with_email = frappe.get_all('User', 
                    filters={'email': member.email}, 
                    fields=['name', 'email', 'enabled'])
                print(f'Users with same email ({member.email}): {users_with_email}')
    
    except Exception as e:
        print(f'Error: {str(e)}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_member_user_link()