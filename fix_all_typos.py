#!/usr/bin/env python3
"""
Fix all instances of 'verenigingen' and 'vereinigen' typos to 'verenigingen'
"""

import os
import re

def fix_typos_in_file(filepath):
    """Fix typos in a single file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Count occurrences of both typos
        count1 = len(re.findall(r'verenigingen', content))
        count2 = len(re.findall(r'vereinigen\.', content))  # vereinigen followed by dot
        
        total_count = count1 + count2
        
        if total_count > 0:
            # Replace both typos
            fixed_content = content.replace('verenigingen', 'verenigingen')
            fixed_content = fixed_content.replace('verenigingen.', 'verenigingen.')
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(fixed_content)
            
            details = []
            if count1 > 0:
                details.append(f"{count1} 'verenigingen'")
            if count2 > 0:
                details.append(f"{count2} 'verenigingen.'")
            
            print(f"Fixed {' and '.join(details)} in: {filepath}")
            return total_count
        
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
            if file.endswith(('.py', '.js', '.json', '.md', '.html')):
                filepath = os.path.join(root, file)
                fixed = fix_typos_in_file(filepath)
                if fixed > 0:
                    total_fixed += fixed
                    files_fixed += 1
    
    print(f"\nSummary: Fixed {total_fixed} occurrences across {files_fixed} files")

if __name__ == "__main__":
    main()