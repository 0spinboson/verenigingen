#!/usr/bin/env python3
import subprocess
import sys
import os

# Change to bench directory
os.chdir('/home/frappe/frappe-bench')

# Run the test using bench execute
try:
    result = subprocess.run([
        'bench', 'execute', 
        'verenigingen.test_approval_now.test_approval_fix'
    ], capture_output=True, text=True, cwd='/home/frappe/frappe-bench')
    
    print("STDOUT:")
    print(result.stdout)
    
    if result.stderr:
        print("STDERR:")
        print(result.stderr)
        
    print(f"Return code: {result.returncode}")
    
except Exception as e:
    print(f"Error running test: {e}")