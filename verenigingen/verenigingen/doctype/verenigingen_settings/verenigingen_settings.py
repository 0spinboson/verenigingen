# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.document import Document

from payments.utils import get_payment_gateway_controller

class VerenigingenSettings(Document):
	@frappe.whitelist()
	def generate_webhook_secret(self, field="membership_webhook_secret"):
		key = frappe.generate_hash(length=20)
		self.set(field, key)
		self.save()

		secret_for = "Membership" if field == "membership_webhook_secret" else "Donation"

		frappe.msgprint(
			_("Here is your webhook secret for {0} API, this will be shown to you only once.").format(secret_for) + "<br><br>" + key,
			_("Webhook Secret")
		)

	@frappe.whitelist()
	def revoke_key(self, key):
		self.set(key, None)
		self.save()

	def get_webhook_secret(self, endpoint="Membership"):
		fieldname = "membership_webhook_secret" if endpoint == "Membership" else "donation_webhook_secret"
		return self.get_password(fieldname=fieldname, raise_exception=False)

@frappe.whitelist()
def get_plans_for_membership(*args, **kwargs):
	controller = get_payment_gateway_controller("Razorpay")
	plans = controller.get_plans()
	return [plan.get("item") for plan in plans.get("items")]
# Add this function to verenigingen/verenigingen/doctype/verenigingen_settings/verenigingen_settings.py

@frappe.whitelist()
def get_income_account_query(doctype, txt, searchfield, start, page_len, filters):
    """Filter for income accounts only"""
    company = filters.get('company') or frappe.defaults.get_global_default('company')
    
    return frappe.db.sql("""
        SELECT name, account_name
        FROM `tabAccount`
        WHERE company = %s
        AND account_type = 'Income Account'
        AND is_group = 0
        AND (name LIKE %s OR account_name LIKE %s)
        ORDER BY name
        LIMIT %s OFFSET %s
    """, (company, "%" + txt + "%", "%" + txt + "%", page_len, start))
