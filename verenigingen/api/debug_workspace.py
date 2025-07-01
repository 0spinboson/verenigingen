import frappe

@frappe.whitelist()
def check_workspace_issues():
    """Debug function to check for workspace issues causing menu problems"""
    
    # Get all workspace links that might have null values
    problematic_links = frappe.db.sql("""
        SELECT 
            parent as workspace_name, 
            label, 
            link_to,
            link_type,
            type,
            idx
        FROM `tabWorkspace Link`
        WHERE (label IS NULL OR label = '' OR link_to IS NULL OR link_to = '')
        ORDER BY parent, idx
    """, as_dict=True)
    
    # Get workspaces with potential issues
    workspaces_with_issues = frappe.db.sql("""
        SELECT 
            name,
            title,
            module
        FROM `tabWorkspace`
        WHERE title IS NULL OR title = ''
    """, as_dict=True)
    
    # Check for verenigingen-related workspaces
    verenigingen_workspaces = frappe.db.sql("""
        SELECT 
            name,
            title,
            module
        FROM `tabWorkspace`
        WHERE name LIKE '%verenigingen%' 
           OR module LIKE '%verenigingen%'
           OR module = 'Verenigingen'
    """, as_dict=True)
    
    return {
        "problematic_links": problematic_links,
        "workspaces_with_issues": workspaces_with_issues,
        "verenigingen_workspaces": verenigingen_workspaces,
        "total_workspaces": frappe.db.count("Workspace"),
        "total_workspace_links": frappe.db.count("Workspace Link")
    }

@frappe.whitelist()
def check_workspace_module_assignments():
    """Check workspace module assignments and E-Boekhouden configuration"""
    results = {}
    
    # Check all workspaces
    workspaces = frappe.get_all('Workspace', 
        fields=['name', 'label', 'module', 'is_hidden', 'title'],
        order_by='name')
    results['all_workspaces'] = workspaces
    
    # Check E-Boekhouden workspace
    if frappe.db.exists('Workspace', 'E-Boekhouden'):
        eb_workspace = frappe.get_doc('Workspace', 'E-Boekhouden')
        results['e_boekhouden'] = {
            'module': eb_workspace.module,
            'label': eb_workspace.label,
            'title': eb_workspace.title,
            'is_hidden': eb_workspace.is_hidden,
            'public': getattr(eb_workspace, 'public', None),
            'links_count': len(eb_workspace.links) if hasattr(eb_workspace, 'links') else 0
        }
        
        # Check first few links
        if hasattr(eb_workspace, 'links'):
            eb_links = []
            for link in eb_workspace.links[:5]:
                eb_links.append({
                    'label': link.label,
                    'link_to': getattr(link, 'link_to', None),
                    'link_type': link.link_type
                })
            results['e_boekhouden']['sample_links'] = eb_links
    
    # Check SEPA Management workspace
    if frappe.db.exists('Workspace', 'SEPA Management'):
        sepa_workspace = frappe.get_doc('Workspace', 'SEPA Management')
        results['sepa_management'] = {
            'module': sepa_workspace.module,
            'label': sepa_workspace.label,
            'title': sepa_workspace.title,
            'is_hidden': sepa_workspace.is_hidden,
            'public': getattr(sepa_workspace, 'public', None),
            'links_count': len(sepa_workspace.links) if hasattr(sepa_workspace, 'links') else 0
        }
    
    # Check for E-Boekhouden links in other workspaces
    eb_links_in_workspaces = frappe.db.sql("""
        SELECT wl.parent, wl.label, wl.link_to, wl.link_type
        FROM `tabWorkspace Link` wl
        WHERE wl.link_to LIKE '%Boekhouden%'
        AND wl.parent != 'E-Boekhouden'
    """, as_dict=True)
    
    results['e_boekhouden_links_elsewhere'] = eb_links_in_workspaces
    
    # Check module assignments
    module_workspaces = frappe.db.sql("""
        SELECT name, module, label, title
        FROM `tabWorkspace`
        WHERE module = 'Verenigingen'
        ORDER BY name
    """, as_dict=True)
    
    results['verenigingen_module_workspaces'] = module_workspaces
    
    # Check for broken DocType links
    broken_links = []
    all_workspace_links = frappe.db.sql("""
        SELECT parent, label, link_to, link_type
        FROM `tabWorkspace Link`
        WHERE parent IN ('E-Boekhouden', 'SEPA Management', 'Verenigingen')
        AND link_type = 'DocType'
    """, as_dict=True)
    
    for link in all_workspace_links:
        doctype_name = link.get('link_to')
        if doctype_name and not frappe.db.exists('DocType', doctype_name):
            broken_links.append(link)
    
    results['broken_links'] = broken_links
    
    # Check if E-Boekhouden doctypes exist
    eb_doctypes = [
        "E-Boekhouden Settings", 
        "E-Boekhouden Migration", 
        "E-Boekhouden Dashboard", 
        "E-Boekhouden Import Log"
    ]
    doctype_status = {}
    for dt in eb_doctypes:
        doctype_status[dt] = frappe.db.exists("DocType", dt)
    
    results['e_boekhouden_doctypes'] = doctype_status
    
    return results

@frappe.whitelist()
def fix_workspace_module_assignments():
    """Fix workspace module assignments"""
    fixes_applied = []
    
    # 1. Fix E-Boekhouden workspace module
    if frappe.db.exists('Workspace', 'E-Boekhouden'):
        frappe.db.set_value('Workspace', 'E-Boekhouden', 'module', 'Verenigingen')
        fixes_applied.append("Set E-Boekhouden workspace module to 'Verenigingen'")
    
    # 2. Fix SEPA Management workspace module
    if frappe.db.exists('Workspace', 'SEPA Management'):
        frappe.db.set_value('Workspace', 'SEPA Management', 'module', 'Verenigingen')
        fixes_applied.append("Set SEPA Management workspace module to 'Verenigingen'")
    
    # 3. Remove E-Boekhouden links from SEPA Management
    eb_links_in_sepa = frappe.db.sql("""
        SELECT name
        FROM `tabWorkspace Link`
        WHERE parent = 'SEPA Management'
        AND link_to LIKE '%Boekhouden%'
    """, pluck='name')
    
    if eb_links_in_sepa:
        for link_name in eb_links_in_sepa:
            frappe.delete_doc('Workspace Link', link_name, ignore_permissions=True)
        fixes_applied.append(f"Removed {len(eb_links_in_sepa)} E-Boekhouden links from SEPA Management")
    
    # 4. Ensure E-Boekhouden workspace is not hidden
    if frappe.db.exists('Workspace', 'E-Boekhouden'):
        frappe.db.set_value('Workspace', 'E-Boekhouden', 'is_hidden', 0)
        fixes_applied.append("Made E-Boekhouden workspace visible")
    
    # 5. Ensure titles are set
    if frappe.db.exists('Workspace', 'E-Boekhouden'):
        frappe.db.set_value('Workspace', 'E-Boekhouden', 'title', 'E-Boekhouden')
    
    if frappe.db.exists('Workspace', 'SEPA Management'):
        frappe.db.set_value('Workspace', 'SEPA Management', 'title', 'SEPA Management')
    
    # Commit changes
    frappe.db.commit()
    
    # Clear cache
    frappe.clear_cache()
    
    return {
        "success": True,
        "fixes_applied": fixes_applied,
        "message": "Workspace module assignments fixed. Please refresh your browser."
    }

@frappe.whitelist()
def fix_eboekhouden_workspace_links():
    """Fix E-Boekhouden workspace links that have null link_to values"""
    
    if not frappe.db.exists('Workspace', 'E-Boekhouden'):
        return {"success": False, "message": "E-Boekhouden workspace not found"}
    
    # Use SQL to directly update the workspace links
    # First, delete existing links with null link_to
    frappe.db.sql("""
        DELETE FROM `tabWorkspace Link`
        WHERE parent = 'E-Boekhouden'
        AND (link_to IS NULL OR link_to = '')
    """)
    
    # Get the workspace to update module
    frappe.db.set_value('Workspace', 'E-Boekhouden', {
        'module': 'Verenigingen',
        'is_hidden': 0
    })
    
    # Check if links exist, if not create them
    existing_links = frappe.db.sql("""
        SELECT link_to FROM `tabWorkspace Link`
        WHERE parent = 'E-Boekhouden'
    """, pluck='link_to')
    
    links_to_add = [
        {
            'label': 'Migration Dashboard',
            'link_to': 'E-Boekhouden Dashboard',
            'link_type': 'DocType'
        },
        {
            'label': 'Migrations',
            'link_to': 'E-Boekhouden Migration',
            'link_type': 'DocType'
        },
        {
            'label': 'Settings',
            'link_to': 'E-Boekhouden Settings',
            'link_type': 'DocType'
        },
        {
            'label': 'Import Logs',
            'link_to': 'E-Boekhouden Import Log',
            'link_type': 'DocType'
        }
    ]
    
    workspace = frappe.get_doc('Workspace', 'E-Boekhouden')
    
    # Add missing links
    for link_data in links_to_add:
        if link_data['link_to'] not in existing_links:
            workspace.append('links', {
                'hidden': 0,
                'is_query_report': 0,
                'label': link_data['label'],
                'link_to': link_data['link_to'],
                'link_type': link_data['link_type'],
                'onboard': 0,
                'type': 'Link'
            })
    
    # Save workspace if we added new links
    if len(workspace.links) > len(existing_links):
        workspace.flags.ignore_validate = True
        workspace.save(ignore_permissions=True)
    
    frappe.db.commit()
    
    # Clear cache
    frappe.clear_cache()
    
    return {
        "success": True,
        "message": "E-Boekhouden workspace links fixed. Please refresh your browser."
    }

@frappe.whitelist()
def fix_workspace_sql():
    """Fix workspace issues using direct SQL"""
    try:
        # 1. Fix E-Boekhouden workspace module
        frappe.db.sql("""
            UPDATE `tabWorkspace`
            SET module = 'Verenigingen', is_hidden = 0
            WHERE name = 'E-Boekhouden'
        """)
        
        # 2. Delete broken links
        frappe.db.sql("""
            DELETE FROM `tabWorkspace Link`
            WHERE parent = 'E-Boekhouden'
            AND (link_to IS NULL OR link_to = '')
        """)
        
        # 3. Fix existing links by updating link_to from link_name
        frappe.db.sql("""
            UPDATE `tabWorkspace Link` wl
            INNER JOIN (
                SELECT name, 
                       CASE label
                           WHEN 'Migration Dashboard' THEN 'E-Boekhouden Dashboard'
                           WHEN 'Migrations' THEN 'E-Boekhouden Migration'
                           WHEN 'Settings' THEN 'E-Boekhouden Settings'
                           WHEN 'Import Logs' THEN 'E-Boekhouden Import Log'
                           ELSE NULL
                       END as new_link_to
                FROM `tabWorkspace Link`
                WHERE parent = 'E-Boekhouden'
            ) AS fix_table ON wl.name = fix_table.name
            SET wl.link_to = fix_table.new_link_to
            WHERE fix_table.new_link_to IS NOT NULL
        """)
        
        # 4. Insert missing links
        links_to_ensure = [
            ('Migration Dashboard', 'E-Boekhouden Dashboard'),
            ('Migrations', 'E-Boekhouden Migration'),
            ('Settings', 'E-Boekhouden Settings'),
            ('Import Logs', 'E-Boekhouden Import Log')
        ]
        
        for idx, (label, link_to) in enumerate(links_to_ensure, 1):
            # Check if link exists
            existing = frappe.db.sql("""
                SELECT COUNT(*) FROM `tabWorkspace Link`
                WHERE parent = 'E-Boekhouden' AND link_to = %s
            """, link_to)[0][0]
            
            if not existing:
                frappe.db.sql("""
                    INSERT INTO `tabWorkspace Link` 
                    (name, creation, modified, modified_by, owner, docstatus, idx, 
                     type, label, link_type, link_to, onboard, is_query_report, hidden, 
                     parent, parentfield, parenttype)
                    VALUES 
                    (%s, NOW(), NOW(), 'Administrator', 'Administrator', 0, %s,
                     'Link', %s, 'DocType', %s, 0, 0, 0, 'E-Boekhouden', 'links', 'Workspace')
                """, (frappe.generate_hash(length=10), idx, label, link_to))
        
        # 5. Fix SEPA Management workspace module
        frappe.db.sql("""
            UPDATE `tabWorkspace`
            SET module = 'Verenigingen'
            WHERE name = 'SEPA Management'
        """)
        
        # 6. Remove any E-Boekhouden links from SEPA Management
        frappe.db.sql("""
            DELETE FROM `tabWorkspace Link`
            WHERE parent = 'SEPA Management'
            AND link_to LIKE '%Boekhouden%'
        """)
        
        frappe.db.commit()
        frappe.clear_cache()
        
        return {
            "success": True,
            "message": "Workspace issues fixed using SQL. Please refresh your browser."
        }
    except Exception as e:
        frappe.db.rollback()
        return {
            "success": False,
            "message": f"Error fixing workspace: {str(e)}"
        }