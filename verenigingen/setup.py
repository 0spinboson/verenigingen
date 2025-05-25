import frappe
from frappe import _
from frappe.desk.page.setup_wizard.setup_wizard import make_records
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def make_custom_records():
    records = [
        {'doctype': "Party Type", "party_type": "Member", "account_type": "Receivable"},
        {'doctype': "Party Type", "party_type": "Donor", "account_type": "Receivable"},
    ]
    make_records(records)

def setup_verenigingen():
    make_custom_records()
    make_custom_fields()

    has_domain = frappe.get_doc({
        'doctype': 'Has Domain',
        'parent': 'Domain Settings',
        'parentfield': 'active_domains',
        'parenttype': 'Domain Settings',
        'domain': 'Verenigingen',
    })
    has_domain.save()

    domain = frappe.get_doc('Domain', 'Verenigingen')
    domain.setup_domain()

    domain_settings = frappe.get_single('Domain Settings')
    domain_settings.append('active_domains', dict(domain=domain))
    frappe.clear_cache()


data = {
    'on_setup': 'verenigingen.setup.setup_verenigingen'
}


def make_custom_fields(update=True):
    custom_fields = get_custom_fields()
    create_custom_fields(custom_fields, update=update)


def get_custom_fields():
    # Constants for Dutch BTW Codes
    BTW_CODES = {
        "EXEMPT_NONPROFIT": "BTW Vrijgesteld - Art. 11-1-f Wet OB",
        "EXEMPT_MEMBERSHIP": "BTW Vrijgesteld - Art. 11-1-l Wet OB",
        "EXEMPT_FUNDRAISING": "BTW Vrijgesteld - Art. 11-1-v Wet OB",
        "EXEMPT_SMALL_BUSINESS": "BTW Vrijgesteld - KOR",
        "OUTSIDE_SCOPE": "Buiten reikwijdte BTW",
        "EXEMPT_WITH_INPUT": "BTW Vrijgesteld met recht op aftrek",
        "EXEMPT_NO_INPUT": "BTW Vrijgesteld zonder recht op aftrek"
    }
    
    custom_fields = {
        'Company': [
            dict(fieldname='verenigingen_section', label='Verenigingen Settings',
                 fieldtype='Section Break', insert_after='asset_received_but_not_billed', collapsible=1)
        ],
        'Sales Invoice': [
            dict(
                fieldname='exempt_from_tax',
                label='Exempt from Tax',
                fieldtype='Check',
                insert_after='tax_category',
                translatable=0
            ),
            # BTW fields that were missing and causing the error
            {
                "fieldname": "btw_exemption_type",
                "label": "BTW Exemption Type",
                "fieldtype": "Select",
                "options": "\n" + "\n".join(BTW_CODES.keys()),
                "insert_after": "exempt_from_tax",
                "translatable": 0
            },
            {
                "fieldname": "btw_exemption_reason",
                "label": "BTW Exemption Reason",
                "fieldtype": "Small Text",
                "insert_after": "btw_exemption_type",
                "translatable": 0,
                "depends_on": "eval:doc.btw_exemption_type"
            },
            {
                "fieldname": "btw_reporting_category",
                "label": "BTW Reporting Category",
                "fieldtype": "Data",
                "insert_after": "btw_exemption_reason",
                "translatable": 0,
                "read_only": 1,
                "depends_on": "eval:doc.btw_exemption_type"
            }
        ],
        'Membership': [
            {
                "fieldname": "btw_exemption_type",
                "label": "BTW Exemption Type",
                "fieldtype": "Select",
                "options": "\n" + "\n".join(BTW_CODES.keys()),
                "insert_after": "membership_type",
                "default": "EXEMPT_MEMBERSHIP",
                "translatable": 0
            }
        ]
    }
    
    # Add Donation fields if Donation doctype exists
    if frappe.db.exists("DocType", "Donation"):
        custom_fields['Donation'] = [
            {
                "fieldname": "btw_exemption_type",
                "label": "BTW Exemption Type",
                "fieldtype": "Select", 
                "options": "\n" + "\n".join(BTW_CODES.keys()),
                "insert_after": "donation_category",
                "default": "EXEMPT_FUNDRAISING",
                "translatable": 0
            }
        ]
    
    return custom_fields

def execute_after_install():
    """
    Function executed after the app is installed
    Sets up necessary configurations for the Verenigingen app
    """
    try:
        # Execute the setup function from this file
        setup_verenigingen()
        
        # Set up tax exemption templates if enabled
        setup_tax_exemption_on_install()

        # NEW: Set up termination system
        setup_termination_system_integration()
        
        # Log the successful setup
        frappe.logger().info("Verenigingen setup completed successfully")
        print("Verenigingen app setup completed successfully")
        
    except Exception as e:  # <-- This except has no matching try!
        frappe.logger().error(f"Error during Verenigingen setup: {str(e)}")
        print(f"Error during setup: {str(e)}")

def setup_tax_exemption_on_install():
    """Set up tax exemption during installation if enabled"""
    try:
        settings = frappe.get_single("Verenigingen Settings")
        if settings.get("tax_exempt_for_contributions"):
            # Import and run the tax setup
            from verenigingen.utils import setup_dutch_tax_exemption
            setup_dutch_tax_exemption()
            print("Tax exemption templates set up during installation")
    except Exception as e:
        frappe.logger().error(f"Error setting up tax exemption during install: {str(e)}")
        print(f"Warning: Could not set up tax exemption during install: {str(e)}")

@frappe.whitelist()
def install_missing_btw_fields():
    """Install BTW custom fields that were missing"""
    try:
        make_custom_fields(update=True)
        frappe.msgprint(_("BTW custom fields installed successfully. Please refresh to see changes."))
        return True
    except Exception as e:
        frappe.msgprint(_("Error installing BTW fields: {0}").format(str(e)))
        frappe.log_error(f"Error installing BTW fields: {str(e)}", "BTW Field Installation Error")
        return False

@frappe.whitelist()
def verify_btw_installation():
    """Verify that BTW fields are properly installed"""
    missing_fields = []
    
    # Check required BTW fields
    required_fields = [
        ("Sales Invoice", "btw_exemption_type"),
        ("Sales Invoice", "btw_exemption_reason"),
        ("Sales Invoice", "btw_reporting_category"),
        ("Membership", "btw_exemption_type")
    ]
    
    for doctype, fieldname in required_fields:
        if not frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": fieldname}):
            missing_fields.append(f"{doctype}.{fieldname}")
    
    if missing_fields:
        return {
            "status": "Missing Fields",
            "missing_fields": missing_fields,
            "message": f"Missing {len(missing_fields)} BTW custom fields"
        }
    else:
        return {
            "status": "All Good",
            "message": "All BTW custom fields are installed"
        }

@frappe.whitelist()
def fix_btw_installation():
    """Fix BTW installation issues"""
    try:
        # Reinstall custom fields
        install_missing_btw_fields()
        
        # Set up tax templates if needed
        settings = frappe.get_single("Verenigingen Settings")
        if settings.get("tax_exempt_for_contributions"):
            from verenigingen.utils import setup_dutch_tax_exemption
            setup_dutch_tax_exemption()
        
        frappe.msgprint(_("BTW installation fixed successfully"))
        return True
        
    except Exception as e:
        frappe.msgprint(_("Error fixing BTW installation: {0}").format(str(e)))
        return False

def setup_termination_system_integration():
    """Setup the termination system as part of app installation"""
    try:
        print("🔧 Setting up termination system...")
        
        # Step 1: Setup termination-specific settings
        setup_termination_settings()
        
        # Step 2: Setup workflows using simplified approach
        from verenigingen.simplified_workflow_setup import setup_workflows_simplified
        workflow_success = setup_workflows_simplified()
        
        if workflow_success:
            print("✅ Workflows created successfully")
        else:
            print("⚠️ Workflow creation had issues")
        
        # Step 3: Setup roles and permissions
        setup_termination_roles_and_permissions()
        
        print("✅ Termination system setup completed")
        
    except Exception as e:
        frappe.log_error(f"Termination system setup error: {str(e)}", "Termination Setup Error")
        print(f"⚠️ Termination system setup failed: {str(e)}")

def setup_termination_settings():
    """Setup termination system settings"""
    
    try:
        # Get or create Verenigingen Settings
        if not frappe.db.exists("Verenigingen Settings", "Verenigingen Settings"):
            # This should already be created by the main setup, but just in case
            return
        
        settings = frappe.get_single("Verenigingen Settings")
        
        # Add termination system settings if they don't exist
        termination_defaults = {
            'enable_termination_system': 1,
            'require_secondary_approval': 1,
            'appeal_deadline_days': 30,
            'appeal_review_days': 60,
            'termination_grace_period_days': 30,
            'auto_cancel_sepa_mandates': 1,
            'auto_end_board_positions': 1,
            'send_termination_notifications': 1
        }
        
        settings_updated = False
        for field, default_value in termination_defaults.items():
            if hasattr(settings, field):
                if not getattr(settings, field):
                    setattr(settings, field, default_value)
                    settings_updated = True
        
        if settings_updated:
            settings.save(ignore_permissions=True)
            frappe.db.commit()
            print("   ✓ Termination settings configured")
        else:
            print("   ✓ Termination settings already configured")
            
    except Exception as e:
        print(f"   ⚠️ Could not setup termination settings: {str(e)}")

def setup_termination_workflows_and_templates():
    """Setup workflows and email templates for termination system"""
    
    try:
        # Try to import and run the workflow setup
        from verenigingen.workflow_states import setup_with_debug
        
        success = setup_with_debug()
        
        if success:
            print("   ✓ Termination workflows and templates setup completed")
        else:
            print("   ⚠️ Termination workflows setup had some issues")
            
    except ImportError:
        print("   ⚠️ Could not import workflow setup - termination workflows not created")
    except Exception as e:
        print(f"   ⚠️ Workflow setup failed: {str(e)}")

def setup_termination_roles_and_permissions():
    """Setup roles and basic permissions for termination system"""
    
    try:
        # Create required roles
        required_roles = [
            {
                "role_name": "Association Manager",
                "desk_access": 1,
                "is_custom": 1
            }
        ]
        
        for role_config in required_roles:
            role_name = role_config["role_name"]
            if not frappe.db.exists("Role", role_name):
                try:
                    role = frappe.get_doc({
                        "doctype": "Role",
                        **role_config
                    })
                    role.insert(ignore_permissions=True)
                    print(f"   ✓ Created role: {role_name}")
                except Exception as e:
                    print(f"   ⚠️ Could not create role {role_name}: {str(e)}")
            else:
                print(f"   ✓ Role already exists: {role_name}")
        
        frappe.db.commit()
        
    except Exception as e:
        print(f"   ⚠️ Role setup failed: {str(e)}")

# Add these API endpoints to your existing setup.py file

@frappe.whitelist()
def setup_termination_system_manual():
    """Manual setup endpoint for termination system"""
    try:
        setup_termination_system_integration()
        return {"success": True, "message": "Termination system setup completed"}
    except Exception as e:
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def check_termination_system_status():
    """Check the status of termination system setup"""
    
    status = {
        "settings_configured": False,
        "workflows_exist": False,
        "roles_exist": False,
        "system_enabled": False
    }
    
    try:
        # Check settings
        if frappe.db.exists("Verenigingen Settings", "Verenigingen Settings"):
            settings = frappe.get_single("Verenigingen Settings")
            if hasattr(settings, 'enable_termination_system'):
                status["settings_configured"] = True
                status["system_enabled"] = bool(settings.enable_termination_system)
        
        # Check workflows
        workflows = ["Membership Termination Workflow", "Termination Appeals Workflow"]
        workflow_count = 0
        for workflow in workflows:
            if frappe.db.exists("Workflow", workflow):
                workflow_count += 1
        status["workflows_exist"] = workflow_count > 0
        
        # Check roles
        status["roles_exist"] = frappe.db.exists("Role", "Association Manager")
        
        return {"success": True, "status": status}
        
    except Exception as e:
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def run_termination_diagnostics():
    """Run diagnostics on termination system"""
    
    print("🔍 TERMINATION SYSTEM DIAGNOSTICS")
    print("=" * 40)
    
    all_good = True
    
    # 1. Check required doctypes
    print("\n1. DOCTYPE CHECK")
    print("-" * 15)
    
    required_doctypes = [
        "Membership Termination Request",
        "Termination Appeals Process", 
        "Expulsion Report Entry"
    ]
    
    for doctype in required_doctypes:
        if frappe.db.exists("DocType", doctype):
            print(f"   ✅ {doctype}")
        else:
            print(f"   ❌ {doctype} - MISSING")
            all_good = False
    
    # 2. Check roles
    print("\n2. ROLE CHECK")
    print("-" * 12)
    
    if frappe.db.exists("Role", "Association Manager"):
        print("   ✅ Association Manager")
    else:
        print("   ❌ Association Manager - MISSING")
        all_good = False
    
    # 3. Check workflows
    print("\n3. WORKFLOW CHECK")
    print("-" * 15)
    
    workflows = ["Membership Termination Workflow", "Termination Appeals Workflow"]
    for workflow in workflows:
        if frappe.db.exists("Workflow", workflow):
            print(f"   ✅ {workflow}")
        else:
            print(f"   ❌ {workflow} - MISSING")
            all_good = False
    
    # Summary
    print("\n" + "=" * 40)
    if all_good:
        print("✅ ALL DIAGNOSTICS PASSED")
    else:
        print("⚠️ SOME ISSUES FOUND")
    print("=" * 40)
    
    return {"success": True, "diagnostics_passed": all_good}
