import frappe
from frappe.desk.page.setup_wizard.setup_wizard import make_records
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def make_custom_records():
	records = [
		{'doctype': "Party Type", "party_type": "Member", "account_type": "Receivable"},
		{'doctype': "Party Type", "party_type": "Donor", "account_type": "Receivable"},
	]
	make_records(records)
def create_sales_invoice_custom_fields():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    
    custom_fields = {
        "Sales Invoice": [
            {
                "fieldname": "exempt_from_tax",
                "label": "Exempt from Tax",
                "fieldtype": "Check",
                "insert_after": "tax_category",
                "translatable": 0
            }
        ]
    }
    
    create_custom_fields(custom_fields)

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
	custom_fields = {
		'Company': [
			dict(fieldname='verenigingen_section', label='Verenigingen Settings',
				 fieldtype='Section Break', insert_after='asset_received_but_not_billed', collapsible=1)
		]
	}
	return custom_fields

def execute_after_install():
    """
    Function executed after the app is installed
    Sets up necessary configurations for the Verenigingen app
    """
    try:
        # Execute the setup function from the root setup.py
        setup_verenigingen()
        
        # Log the successful setup
        frappe.logger().info("Verenigingen setup completed successfully")
        
    except Exception as e:
        frappe.logger().error(f"Error during Verenigingen setup: {str(e)}")
        frappe.throw(_("Error during setup: {0}").format(str(e)))
