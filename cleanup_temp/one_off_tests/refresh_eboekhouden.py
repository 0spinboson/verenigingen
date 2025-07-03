#!/usr/bin/env python3
import frappe

def main():
    frappe.init(site='dev.veganisme.net')
    frappe.connect()
    
    try:
        # Clear cache
        frappe.clear_cache()
        
        # Check if workspace exists
        workspace = frappe.get_doc("Workspace", "E-Boekhouden")
        print(f"Workspace found: {workspace.name}")
        print(f"Module: {workspace.module}")
        print(f"Is Hidden: {workspace.is_hidden}")
        print(f"Public: {workspace.public}")
        
        # Force save to refresh
        workspace.save()
        print("Workspace refreshed")
        
        # Check doctypes
        doctypes = ["E-Boekhouden Settings", "E-Boekhouden Migration", "E-Boekhouden Dashboard", "E-Boekhouden Import Log"]
        for dt in doctypes:
            if frappe.db.exists("DocType", dt):
                print(f"✓ {dt} exists")
            else:
                print(f"✗ {dt} missing")
        
        frappe.db.commit()
        print("\nWorkspace and doctypes verified. Please refresh your browser.")
        
    except Exception as e:
        print(f"Error: {e}")
        frappe.db.rollback()
    finally:
        frappe.destroy()

if __name__ == "__main__":
    main()