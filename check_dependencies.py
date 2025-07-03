#!/usr/bin/env python3
"""
Check for broken imports after cleanup
"""

import os
import re
import ast

def find_imports_in_file(filepath):
    """Extract all imports from a Python file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for alias in node.names:
                        imports.append(f"{node.module}.{alias.name}")
                        
        return imports
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
        return []

def get_moved_files():
    """Get list of all files that were moved to cleanup_temp"""
    moved_files = []
    cleanup_dir = '/home/frappe/frappe-bench/apps/verenigingen/cleanup_temp'
    
    for root, dirs, files in os.walk(cleanup_dir):
        for file in files:
            if file.endswith('.py'):
                # Get just the filename without .py extension
                module_name = file[:-3]
                moved_files.append(module_name)
    
    return set(moved_files)

def check_production_dependencies():
    """Check production files for imports of moved files"""
    production_dir = '/home/frappe/frappe-bench/apps/verenigingen'
    moved_modules = get_moved_files()
    broken_imports = []
    
    for root, dirs, files in os.walk(production_dir):
        # Skip cleanup_temp directory
        if 'cleanup_temp' in root:
            continue
            
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                imports = find_imports_in_file(filepath)
                
                for imp in imports:
                    # Check if any import references a moved module
                    for moved_module in moved_modules:
                        if moved_module in imp:
                            broken_imports.append({
                                'file': filepath,
                                'import': imp,
                                'moved_module': moved_module
                            })
    
    return broken_imports

if __name__ == "__main__":
    print("Checking for broken dependencies after cleanup...")
    
    broken = check_production_dependencies()
    
    if broken:
        print(f"\n❌ Found {len(broken)} broken imports:")
        for item in broken:
            print(f"  {item['file']}")
            print(f"    imports: {item['import']}")
            print(f"    (moved module: {item['moved_module']})")
            print()
    else:
        print("\n✅ No broken imports found!")