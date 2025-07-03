#!/usr/bin/env python3

import frappe
import sys
import os

# Add the apps directory to Python path
sys.path.insert(0, '/home/frappe/frappe-bench/apps/verenigingen')

# Initialize Frappe
frappe.init(site='dev.veganisme.net')
frappe.connect()

try:
    # Test the settings
    settings = frappe.get_single("E-Boekhouden Settings")
    print(f"API URL: {settings.api_url}")
    print(f"Source: {settings.source_application}")
    
    # Test token retrieval
    token = settings.get_password('api_token')
    print(f"Token available: {bool(token)}")
    print(f"Token length: {len(token) if token else 0}")
    
    # Test API class initialization
    from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
    api = EBoekhoudenAPI(settings)
    print(f"API initialized successfully")
    
    # Test session token
    session_token = api.get_session_token()
    print(f"Session token obtained: {bool(session_token)}")
    
    if session_token:
        print(f"Session token length: {len(session_token)}")
        
        # Test a simple API call
        result = api.make_request("v1/ledger", "GET", {"limit": 1})
        print(f"Test API call result: {result['success']}")
        if not result['success']:
            print(f"Error: {result['error']}")
    else:
        print("Failed to get session token")
        
except Exception as e:
    print(f"Error: {str(e)}")
    import traceback
    traceback.print_exc()

finally:
    frappe.destroy()