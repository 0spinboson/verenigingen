#!/usr/bin/env python3
"""
Fix all instances of 'verenigingen' typo to 'verenigingen'
"""

import os
import re

def fix_typo_in_file(filepath):
    """Fix typo in a single file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Count occurrences
        count = len(re.findall(r'verenigingen', content))
        
        if count > 0:
            # Replace the typo
            fixed_content = content.replace('verenigingen', 'verenigingen')
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(fixed_content)
            
            print(f"Fixed {count} occurrences in: {filepath}")
            return count
        
        return 0
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return 0

def main():
    """Find and fix all typos"""
    total_fixed = 0
    files_fixed = 0
    
    # Walk through all files
    for root, dirs, files in os.walk('.'):
        # Skip certain directories
        if any(skip in root for skip in ['.git', '/env/', '__pycache__', '.egg-info']):
            continue
        
        for file in files:
            # Only process code files
            if file.endswith(('.py', '.js', '.json', '.md')):
                filepath = os.path.join(root, file)
                fixed = fix_typo_in_file(filepath)
                if fixed > 0:
                    total_fixed += fixed
                    files_fixed += 1
    
    print(f"\nSummary: Fixed {total_fixed} occurrences across {files_fixed} files")

if __name__ == "__main__":
    main()