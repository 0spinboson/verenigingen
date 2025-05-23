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
        
        # Log the successful setup
        frappe.logger().info("Verenigingen setup completed successfully")
        print("Verenigingen app setup completed successfully")
        
    except Exception as e:
        frappe.logger().error(f"Error during Verenigingen setup: {str(e)}")
        print(f"Error during setup: {str(e)}")
        # Don't throw error to avoid installation failure

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
