# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.utils import getdate


def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	return columns, data

def get_columns(filters):
	return [
			_("Membership Type") + ":Link/Membership Type:100", _("Membership ID") + ":Link/Membership:140",
			_("Member ID") + ":Link/Member:140",  _("Member Name") + ":Data:140", _("Email") + ":Data:140",
	 		_("Expiring On") + ":Date:120"
	]

def get_data(filters):
	month_name = filters.get("month", "Jan")
	month_number = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"].index(month_name) + 1
	
	# Extract year from fiscal year if it's in format like "2024-2025"
	fiscal_year = filters.get("fiscal_year", "")
	if "-" in fiscal_year:
		year = int(fiscal_year.split("-")[0])
	else:
		try:
			year = int(fiscal_year)
		except (ValueError, TypeError):
			year = getdate().year

	return frappe.db.sql("""
		select ms.membership_type, ms.name, m.name, m.full_name, m.email, ms.expiry_date
		from `tabMember` m
		inner join (
			select 
				name, 
				membership_type, 
				member,
				COALESCE(next_billing_date, renewal_date) as expiry_date
			from `tabMembership`
			where status in ('Active', 'Pending')
			  and COALESCE(next_billing_date, renewal_date) is not null
		) ms on m.name = ms.member
		where month(ms.expiry_date) = %(month)s and year(ms.expiry_date) = %(year)s
		order by ms.expiry_date asc
		""", {'month': month_number, 'year': year}, as_dict=1)
