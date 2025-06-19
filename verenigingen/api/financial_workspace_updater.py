"""
Add financial and banking doctypes to the Verenigingen workspace
"""

import frappe

@frappe.whitelist()
def get_current_financial_links():
    """Check what financial links are currently in the workspace"""
    try:
        workspace = frappe.get_doc('Workspace', 'Verenigingen')
        
        financial_links = []
        for link in workspace.links:
            if link.link_to and any(term in link.link_to.lower() for term in ['bank', 'payment', 'invoice', 'financial', 'transaction', 'account', 'sepa', 'mandate']):
                financial_links.append({
                    "label": link.label,
                    "link_to": link.link_to,
                    "link_type": link.link_type,
                    "type": link.type
                })
        
        return {
            "success": True,
            "current_financial_links": financial_links,
            "total_links": len(workspace.links)
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def add_financial_and_banking_links():
    """Add all relevant financial and banking doctypes to the workspace"""
    try:
        workspace = frappe.get_doc('Workspace', 'Verenigingen')
        
        # Financial and Banking doctypes to add
        financial_doctypes = [
            # Banking & Transactions
            {"label": "Bank Transaction", "link_to": "Bank Transaction", "section": "Banking"},
            {"label": "Bank Reconciliation Tool", "link_to": "Bank Reconciliation Tool", "section": "Banking"},
            {"label": "Bank Statement Import", "link_to": "Bank Statement Import", "section": "Banking"}, 
            {"label": "Bank Account", "link_to": "Bank Account", "section": "Banking"},
            {"label": "Bank Guarantee", "link_to": "Bank Guarantee", "section": "Banking"},
            
            # SEPA & Direct Debit
            {"label": "Direct Debit Batch", "link_to": "Direct Debit Batch", "section": "SEPA"},
            {"label": "SEPA Mandate", "link_to": "SEPA Mandate", "section": "SEPA"},
            
            # Payments & Invoicing
            {"label": "Payment Entry", "link_to": "Payment Entry", "section": "Payments"},
            {"label": "Payment Request", "link_to": "Payment Request", "section": "Payments"},
            {"label": "Payment Order", "link_to": "Payment Order", "section": "Payments"},
            {"label": "Sales Invoice", "link_to": "Sales Invoice", "section": "Invoicing"},
            {"label": "Purchase Invoice", "link_to": "Purchase Invoice", "section": "Invoicing"},
            
            # Accounting
            {"label": "Journal Entry", "link_to": "Journal Entry", "section": "Accounting"},
            {"label": "Chart of Accounts", "link_to": "Chart of Accounts", "section": "Accounting"},
            {"label": "Account", "link_to": "Account", "section": "Accounting"},
            {"label": "Accounting Dimension", "link_to": "Accounting Dimension", "section": "Accounting"},
            
            # Financial Reports
            {"label": "General Ledger", "link_to": "General Ledger", "section": "Reports"},
            {"label": "Trial Balance", "link_to": "Trial Balance", "section": "Reports"},
            {"label": "Balance Sheet", "link_to": "Balance Sheet", "section": "Reports"},
            {"label": "Profit and Loss Statement", "link_to": "Profit and Loss Statement", "section": "Reports"},
            {"label": "Cash Flow", "link_to": "Cash Flow", "section": "Reports"},
            
            # Custom Association Specific
            {"label": "Subscription Override", "link_to": "Subscription Override", "section": "Membership"},
            {"label": "Membership Fee Override", "link_to": "Membership Fee Override", "section": "Membership"},
            
        ]
        
        added_links = []
        existing_links = []
        
        for doctype_info in financial_doctypes:
            # Check if link already exists
            link_exists = False
            for existing_link in workspace.links:
                if existing_link.link_to == doctype_info["link_to"]:
                    link_exists = True
                    existing_links.append(doctype_info["label"])
                    break
            
            # Add link if it doesn't exist and doctype exists in system
            if not link_exists:
                try:
                    # Handle different link types
                    if doctype_info["link_to"].startswith("/"):
                        # Web page link
                        workspace.append('links', {
                            'hidden': 0,
                            'is_query_report': 0,
                            'label': doctype_info["label"],
                            'link_count': 0,
                            'link_to': doctype_info["link_to"],
                            'link_type': 'Page',
                            'onboard': 0,
                            'type': 'Link'
                        })
                        added_links.append(doctype_info["label"])
                    elif frappe.db.exists("DocType", doctype_info["link_to"]):
                        # DocType link
                        workspace.append('links', {
                            'hidden': 0,
                            'is_query_report': 1 if doctype_info["section"] == "Reports" else 0,
                            'label': doctype_info["label"],
                            'link_count': 0,
                            'link_to': doctype_info["link_to"],
                            'link_type': 'Report' if doctype_info["section"] == "Reports" else 'DocType',
                            'onboard': 0,
                            'type': 'Link'
                        })
                        added_links.append(doctype_info["label"])
                except:
                    # Skip if doctype doesn't exist
                    pass
        
        # Save the workspace
        if added_links:
            workspace.save()
            frappe.db.commit()
        
        return {
            "success": True,
            "added_links": added_links,
            "existing_links": existing_links,
            "total_added": len(added_links),
            "message": f"Added {len(added_links)} financial links to workspace"
        }
        
    except Exception as e:
        frappe.log_error(f"Error adding financial links to workspace: {str(e)}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def add_financial_shortcuts():
    """Add useful financial shortcuts to workspace"""
    try:
        workspace = frappe.get_doc('Workspace', 'Verenigingen')
        
        # Key financial shortcuts for quick access
        financial_shortcuts = [
            {"label": "Bank Reconciliation", "link_to": "Bank Reconciliation Tool", "color": "Green", "type": "DocType"},
            {"label": "Bank Transactions", "link_to": "Bank Transaction", "color": "Purple", "type": "DocType"},
            {"label": "Payment Entries", "link_to": "Payment Entry", "color": "Orange", "type": "DocType"},
            {"label": "SEPA Mandates", "link_to": "SEPA Mandate", "color": "Red", "type": "DocType"},
            {"label": "Direct Debit Batches", "link_to": "Direct Debit Batch", "color": "Cyan", "type": "DocType"},
        ]
        
        added_shortcuts = []
        existing_shortcuts = []
        
        for shortcut_info in financial_shortcuts:
            # Check if shortcut already exists
            shortcut_exists = False
            for existing_shortcut in workspace.shortcuts:
                if existing_shortcut.link_to == shortcut_info["link_to"]:
                    shortcut_exists = True
                    existing_shortcuts.append(shortcut_info["label"])
                    break
            
            # Add shortcut if it doesn't exist
            if not shortcut_exists:
                try:
                    # Handle different shortcut types
                    if shortcut_info.get("type") == "Page" or shortcut_info["link_to"].startswith("/"):
                        # Web page shortcut
                        workspace.append('shortcuts', {
                            'color': shortcut_info["color"],
                            'doc_view': '',
                            'label': shortcut_info["label"],
                            'link_to': shortcut_info["link_to"],
                            'type': 'Page'
                        })
                        added_shortcuts.append(shortcut_info["label"])
                    elif frappe.db.exists("DocType", shortcut_info["link_to"]):
                        # DocType shortcut
                        workspace.append('shortcuts', {
                            'color': shortcut_info["color"],
                            'doc_view': '',
                            'label': shortcut_info["label"],
                            'link_to': shortcut_info["link_to"],
                            'type': 'DocType'
                        })
                        added_shortcuts.append(shortcut_info["label"])
                except:
                    pass
        
        # Save the workspace
        if added_shortcuts:
            workspace.save()
            frappe.db.commit()
        
        return {
            "success": True,
            "added_shortcuts": added_shortcuts,
            "existing_shortcuts": existing_shortcuts,
            "total_added": len(added_shortcuts),
            "message": f"Added {len(added_shortcuts)} financial shortcuts to workspace"
        }
        
    except Exception as e:
        frappe.log_error(f"Error adding financial shortcuts to workspace: {str(e)}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def setup_complete_financial_workspace():
    """Complete setup of financial section in workspace"""
    try:
        # Add all financial links
        links_result = add_financial_and_banking_links()
        
        # Add financial shortcuts  
        shortcuts_result = add_financial_shortcuts()
        
        return {
            "success": True,
            "links_result": links_result,
            "shortcuts_result": shortcuts_result,
            "message": "Complete financial workspace setup completed"
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}