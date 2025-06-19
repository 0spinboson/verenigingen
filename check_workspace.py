#!/usr/bin/env python3

def check_workspace_and_onboarding():
    """Check workspace configuration and onboarding setup"""
    import frappe
    
    frappe.init(site='dev.veganisme.net')
    frappe.connect()
    
    try:
        # Check if Verenigingen workspace exists
        workspaces = frappe.get_all('Workspace', fields=['name', 'title', 'module'])
        print("Available Workspaces:")
        for ws in workspaces:
            print(f"  - {ws.name}: {ws.title} (Module: {ws.module})")
        
        # Check specifically for Verenigingen workspace
        verenigingen_workspace = None
        for ws in workspaces:
            if 'verenigingen' in ws.name.lower() or 'verenigingen' in ws.title.lower():
                verenigingen_workspace = ws
                break
        
        if verenigingen_workspace:
            print(f"\n✅ Found Verenigingen workspace: {verenigingen_workspace.name}")
            
            # Get detailed workspace info
            workspace_doc = frappe.get_doc('Workspace', verenigingen_workspace.name)
            print(f"   Title: {workspace_doc.title}")
            print(f"   Module: {workspace_doc.module}")
            print(f"   Public: {workspace_doc.public}")
            print(f"   Number of links: {len(workspace_doc.links)}")
            print(f"   Number of shortcuts: {len(workspace_doc.shortcuts)}")
            
            # Check for onboarding-related content
            print("\n📋 Links in workspace:")
            for link in workspace_doc.links:
                if link.type == "Link":
                    print(f"  - {link.label} -> {link.link_to} ({link.link_type})")
            
            print("\n🚀 Shortcuts in workspace:")
            for shortcut in workspace_doc.shortcuts:
                print(f"  - {shortcut.label} -> {shortcut.link_to} ({shortcut.type})")
                
        else:
            print("\n❌ No Verenigingen workspace found")
        
        # Check for onboarding doctypes
        print("\n🎯 Checking for onboarding-related doctypes:")
        onboarding_doctypes = [
            'Module Onboarding',
            'Onboarding Permission',
            'Onboarding Step',
            'Workspace Onboarding'
        ]
        
        for doctype in onboarding_doctypes:
            if frappe.db.exists('DocType', doctype):
                count = frappe.db.count(doctype)
                print(f"  ✅ {doctype}: {count} records")
                
                if doctype == 'Module Onboarding':
                    # Check for Verenigingen-specific onboarding
                    verenigingen_onboarding = frappe.get_all(doctype, 
                        filters={'module': 'Verenigingen'}, 
                        fields=['name', 'title', 'is_complete'])
                    
                    if verenigingen_onboarding:
                        print("     📌 Verenigingen Module Onboarding found:")
                        for ob in verenigingen_onboarding:
                            print(f"       - {ob.name}: {ob.title} (Complete: {ob.is_complete})")
                    else:
                        print("     ⚠️  No Verenigingen Module Onboarding found")
                        
            else:
                print(f"  ❌ {doctype}: Not found")
        
        # Check if onboarding files exist in the app
        import os
        app_path = frappe.get_app_path('verenigingen')
        onboarding_path = os.path.join(app_path, 'onboarding')
        
        print(f"\n📁 Checking onboarding files in: {onboarding_path}")
        if os.path.exists(onboarding_path):
            files = os.listdir(onboarding_path)
            print(f"  ✅ Onboarding directory exists with {len(files)} files:")
            for file in files:
                print(f"    - {file}")
        else:
            print("  ❌ No onboarding directory found")
            
        # Check fixtures/install data
        fixtures_path = os.path.join(app_path, '..', 'fixtures')
        print(f"\n📦 Checking fixtures in: {fixtures_path}")
        if os.path.exists(fixtures_path):
            files = os.listdir(fixtures_path)
            onboarding_files = [f for f in files if 'onboard' in f.lower()]
            if onboarding_files:
                print(f"  ✅ Found onboarding fixtures: {onboarding_files}")
            else:
                print(f"  ⚠️  No onboarding fixtures found in {len(files)} files")
        else:
            print("  ❌ No fixtures directory found")
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        frappe.destroy()

if __name__ == '__main__':
    check_workspace_and_onboarding()