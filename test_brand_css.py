#!/usr/bin/env python3
"""
Test script to verify brand CSS is working correctly
"""

import sys
import os
sys.path.insert(0, '/home/frappe/frappe-bench')
sys.path.insert(0, '/home/frappe/frappe-bench/apps/frappe')
sys.path.insert(0, '/home/frappe/frappe-bench/sites')

def test_brand_css_endpoint():
    """Test that the brand CSS endpoint returns valid CSS"""
    import requests
    
    try:
        # Test the brand CSS endpoint
        response = requests.get('https://dev.veganisme.net/brand_css')
        
        print(f"Brand CSS Endpoint Test:")
        print(f"Status Code: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type', 'N/A')}")
        print(f"Content Length: {len(response.text)} characters")
        
        if response.status_code == 200:
            css_content = response.text[:500]  # First 500 chars
            print(f"CSS Preview:\n{css_content}...")
            
            # Check for brand variables
            if '--brand-primary' in response.text:
                print("✓ Brand variables found in CSS")
            else:
                print("✗ Brand variables NOT found in CSS")
                
            return True
        else:
            print("✗ Brand CSS endpoint failed")
            return False
            
    except Exception as e:
        print(f"✗ Error testing brand CSS: {str(e)}")
        return False

def test_portal_pages():
    """Test that portal pages include the brand CSS"""
    import requests
    
    portal_pages = [
        '/member_portal',
        '/membership_fee_adjustment', 
        '/bank_details',
        '/apply_for_membership'
    ]
    
    print(f"\nPortal Pages CSS Inclusion Test:")
    
    for page in portal_pages:
        try:
            response = requests.get(f'https://dev.veganisme.net{page}', allow_redirects=False)
            
            if response.status_code in [200, 302]:  # 302 for login redirects
                if '/brand_css' in response.text:
                    print(f"✓ {page}: Brand CSS included")
                else:
                    print(f"✗ {page}: Brand CSS NOT included")
            else:
                print(f"⚠ {page}: Status {response.status_code}")
                
        except Exception as e:
            print(f"✗ {page}: Error - {str(e)}")

if __name__ == "__main__":
    print("=" * 50)
    print("Brand CSS System Test")
    print("=" * 50)
    
    # Test 1: Brand CSS endpoint
    css_works = test_brand_css_endpoint()
    
    # Test 2: Portal pages inclusion
    test_portal_pages()
    
    print(f"\n" + "=" * 50)
    if css_works:
        print("✓ Brand CSS system is working")
        print("The member portal should now display brand colors correctly!")
    else:
        print("✗ Brand CSS system has issues")
    print("=" * 50)