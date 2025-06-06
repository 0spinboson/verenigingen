#!/usr/bin/env python3

import frappe
import json

def update_workspace():
    """Update the Verenigingen workspace with missing doctypes"""
    
    try:
        # Get the workspace document
        workspace = frappe.get_doc('Workspace', 'Verenigingen')
        
        print(f"Current workspace has {len(workspace.links)} links")
        
        # Additional links to add
        new_links = [
            {
                "hidden": 0,
                "is_query_report": 0,
                "label": "Termination & Appeals",
                "link_count": 2,
                "link_type": "DocType",
                "onboard": 0,
                "type": "Card Break"
            },
            {
                "dependencies": "",
                "hidden": 0,
                "is_query_report": 0,
                "label": "Membership Termination Request",
                "link_count": 0,
                "link_to": "Membership Termination Request",
                "link_type": "DocType",
                "onboard": 0,
                "type": "Link"
            },
            {
                "dependencies": "",
                "hidden": 0,
                "is_query_report": 0,
                "label": "Termination Appeals Process",
                "link_count": 0,
                "link_to": "Termination Appeals Process",
                "link_type": "DocType",
                "onboard": 0,
                "type": "Link"
            },
            {
                "hidden": 0,
                "is_query_report": 0,
                "label": "Payment Management",
                "link_count": 3,
                "link_type": "DocType",
                "onboard": 0,
                "type": "Card Break"
            },
            {
                "dependencies": "",
                "hidden": 0,
                "is_query_report": 0,
                "label": "SEPA Mandate",
                "link_count": 0,
                "link_to": "SEPA Mandate",
                "link_type": "DocType",
                "onboard": 0,
                "type": "Link"
            },
            {
                "dependencies": "",
                "hidden": 0,
                "is_query_report": 0,
                "label": "Direct Debit Batch",
                "link_count": 0,
                "link_to": "Direct Debit Batch",
                "link_type": "DocType",
                "onboard": 0,
                "type": "Link"
            },
            {
                "dependencies": "",
                "hidden": 0,
                "is_query_report": 0,
                "label": "Member Payment History",
                "link_count": 0,
                "link_to": "Member Payment History",
                "link_type": "DocType",
                "onboard": 0,
                "type": "Link"
            }
        ]
        
        # Check if links already exist to avoid duplicates
        existing_links = [link.get('link_to') for link in workspace.links if link.get('link_to')]
        
        for new_link in new_links:
            if new_link.get('link_to') and new_link.get('link_to') not in existing_links:
                workspace.append('links', new_link)
                print(f"Added link: {new_link.get('label', new_link.get('link_to'))}")
            elif new_link.get('type') == 'Card Break':
                workspace.append('links', new_link)
                print(f"Added card break: {new_link.get('label')}")
        
        # Add new shortcuts
        new_shortcuts = [
            {
                "color": "Red",
                "label": "Termination Requests",
                "link_to": "Membership Termination Request",
                "type": "DocType"
            },
            {
                "color": "Blue",
                "label": "SEPA Mandates",
                "link_to": "SEPA Mandate",
                "type": "DocType"
            },
            {
                "color": "Green",
                "label": "Direct Debits",
                "link_to": "Direct Debit Batch",
                "type": "DocType"
            }
        ]
        
        existing_shortcuts = [shortcut.get('link_to') for shortcut in workspace.shortcuts if shortcut.get('link_to')]
        
        for shortcut in new_shortcuts:
            if shortcut.get('link_to') not in existing_shortcuts:
                workspace.append('shortcuts', shortcut)
                print(f"Added shortcut: {shortcut.get('label')}")
        
        # Update content to include new sections
        updated_content = [
            {"id":"NFcjh9I8BH","type":"header","data":{"text":"<span class=\"h4\"><b>Your Shortcuts</b></span>","col":12}},
            {"id":"sxzInK1PHL","type":"shortcut","data":{"shortcut_name":"Member","col":3}},
            {"id":"q6OM4R0OUa","type":"shortcut","data":{"shortcut_name":"Membership","col":3}},
            {"id":"Eic5oNDHuQ","type":"shortcut","data":{"shortcut_name":"Chapter","col":3}},
            {"id":"TermReqShort","type":"shortcut","data":{"shortcut_name":"Termination Requests","col":3}},
            {"id":"zGoLYG0xRM","type":"spacer","data":{"col":12}},
            {"id":"jMy1CTqEJS","type":"header","data":{"text":"<span class=\"h4\"><b>Core Modules</b></span>","col":12}},
            {"id":"oIk2CrSoAH","type":"card","data":{"card_name":"Memberships","col":4}},
            {"id":"2vHgUjgQcL","type":"card","data":{"card_name":"Volunteers","col":4}},
            {"id":"S8Mi0T41U7","type":"card","data":{"card_name":"Chapters","col":4}},
            {"id":"ZvroSYo9F3","type":"card","data":{"card_name":"Donations","col":4}},
            {"id":"XXEhdaTHF_","type":"card","data":{"card_name":"Teams and Commissions","col":4}},
            {"id":"RKkllDSemd","type":"card","data":{"card_name":"Module Settings","col":4}},
            {"id":"AdminModulesHdr","type":"header","data":{"text":"<span class=\"h4\"><b>Administrative Functions</b></span>","col":12}},
            {"id":"TerminationCard","type":"card","data":{"card_name":"Termination & Appeals","col":4}},
            {"id":"PaymentCard","type":"card","data":{"card_name":"Payment Management","col":4}},
            {"id":"7calAUIe4T","type":"header","data":{"text":"<span class=\"h4\"><b>Reports</b></span>","col":12}},
            {"id":"dvcuq-ItCp","type":"shortcut","data":{"shortcut_name":"Users by Team","col":3}}
        ]
        
        workspace.content = json.dumps(updated_content)
        
        # Save the workspace
        workspace.save()
        frappe.db.commit()
        
        print(f"Updated workspace now has {len(workspace.links)} links and {len(workspace.shortcuts)} shortcuts")
        print("Workspace updated successfully!")
        
    except Exception as e:
        print(f"Error updating workspace: {str(e)}")
        frappe.db.rollback()

update_workspace()