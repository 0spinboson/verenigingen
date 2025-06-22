#!/usr/bin/env python3
"""
Test runner for recent code changes tests
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def run_tests():
    """Run tests for recent code changes"""
    print("Running tests for recent code changes...")
    
    try:
        # Try to run with bench if available
        import subprocess
        result = subprocess.run([
            'bench', '--site', 'dev.veganisme.net', 'run-tests', 
            '--app', 'verenigingen', 
            '--module', 'verenigingen.tests.test_recent_code_changes',
            '--verbose'
        ], capture_output=True, text=True, cwd='/home/frappe/frappe-bench')
        
        if result.returncode == 0:
            print("✅ Recent code changes tests passed!")
            print(result.stdout)
        else:
            print("❌ Recent code changes tests failed!")
            print(result.stderr)
            print(result.stdout)
            
        # Also run the updated expense integration tests
        result2 = subprocess.run([
            'bench', '--site', 'dev.veganisme.net', 'run-tests',
            '--app', 'verenigingen',
            '--module', 'verenigingen.tests.test_erpnext_expense_integration',
            '--verbose'
        ], capture_output=True, text=True, cwd='/home/frappe/frappe-bench')
        
        if result2.returncode == 0:
            print("✅ Updated expense integration tests passed!")
            print(result2.stdout)
        else:
            print("❌ Updated expense integration tests failed!")
            print(result2.stderr) 
            print(result2.stdout)
            
        return result.returncode == 0 and result2.returncode == 0
        
    except Exception as e:
        print(f"Error running tests: {e}")
        return False

if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)