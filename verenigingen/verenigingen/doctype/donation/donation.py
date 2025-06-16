# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_link_to_form, getdate


class Donation(Document):
	def validate(self):
		if not self.donor or not frappe.db.exists('Donor', self.donor):
			# for web forms
			user_type = frappe.db.get_value('User', frappe.session.user, 'user_type')
			if user_type == 'Website User':
				self.create_donor_for_website_user()
			else:
				frappe.throw(_('Please select a Donor'))
		
		# Set default donation type if not provided
		if not self.donation_type:
			default_donation_type = frappe.db.get_single_value('Verenigingen Settings', 'default_donation_type')
			if default_donation_type:
				self.donation_type = default_donation_type
		
		# Validate payment method dependencies
		self.validate_payment_method()
		
		# Validate ANBI agreement requirements
		self.validate_anbi_agreement()
		
		# Validate donation purpose fields
		self.validate_donation_purpose()

	def create_donor_for_website_user(self):
		donor_name = frappe.get_value('Donor', dict(email=frappe.session.user))

		if not donor_name:
			user = frappe.get_doc('User', frappe.session.user)
			donor = frappe.get_doc(dict(
				doctype='Donor',
				donor_type=self.get('donor_type'),
				email=frappe.session.user,
				member_name=user.get_fullname()
			)).insert(ignore_permissions=True)
			donor_name = donor.name

		if self.get('__islocal'):
			self.donor = donor_name

	def on_payment_authorized(self, *args, **kwargs):
		self.db_set("paid", 1)
		self.load_from_db()
		self.create_payment_entry()
	
	def validate_payment_method(self):
		"""Validate payment method specific requirements"""
		if self.payment_method == 'SEPA Direct Debit' and self.donation_status in ['Promised', 'Recurring']:
			if not getattr(self, 'sepa_mandate', None):
				frappe.msgprint(_('SEPA mandate is recommended for recurring donations'), indicator='yellow')
		
		if self.payment_method == 'Bank Transfer' and not getattr(self, 'bank_reference', None):
			if self.paid:
				frappe.msgprint(_('Bank reference is recommended for tracking bank transfers'), indicator='yellow')
	
	def validate_anbi_agreement(self):
		"""Validate ANBI agreement fields"""
		anbi_number = getattr(self, 'anbi_agreement_number', None)
		anbi_date = getattr(self, 'anbi_agreement_date', None)
		
		if anbi_number and not anbi_date:
			frappe.throw(_('ANBI Agreement Date is required when ANBI Agreement Number is provided'))
		
		if anbi_date and not anbi_number:
			frappe.throw(_('ANBI Agreement Number is required when ANBI Agreement Date is provided'))
		
		# Auto-set belastingdienst_reportable for larger donations
		settings = frappe.get_single('Verenigingen Settings')
		min_amount = flt(getattr(settings, 'anbi_minimum_reportable_amount', 500))
		if self.amount and flt(self.amount) >= min_amount and anbi_number:
			self.belastingdienst_reportable = 1
	
	def generate_anbi_report_data(self):
		"""Generate data for ANBI reporting to Belastingdienst"""
		if not self.belastingdienst_reportable or not self.anbi_agreement_number:
			return None
		
		donor_doc = frappe.get_doc('Donor', self.donor)
		return {
			'donation_id': self.name,
			'anbi_agreement_number': self.anbi_agreement_number,
			'anbi_agreement_date': self.anbi_agreement_date,
			'donation_date': self.date,
			'amount': self.amount,
			'donor_name': donor_doc.donor_name,
			'donor_email': getattr(donor_doc, 'donor_email', ''),
			'donation_type': self.donation_type
		}
	
	def validate_donation_purpose(self):
		"""Validate donation purpose and earmarking fields"""
		purpose_type = getattr(self, 'donation_purpose_type', 'General')
		campaign_ref = getattr(self, 'campaign_reference', None)
		chapter_ref = getattr(self, 'chapter_reference', None)
		goal_desc = getattr(self, 'specific_goal_description', None)
		
		if purpose_type == 'Campaign' and not campaign_ref:
			frappe.throw(_('Campaign Reference is required when Purpose Type is Campaign'))
		
		if purpose_type == 'Chapter' and not chapter_ref:
			frappe.throw(_('Chapter is required when Purpose Type is Chapter'))
		
		if purpose_type == 'Specific Goal' and not goal_desc:
			frappe.throw(_('Specific Goal Description is required when Purpose Type is Specific Goal'))
		
		# Validate chapter exists if specified
		if chapter_ref and not frappe.db.exists('Chapter', chapter_ref):
			frappe.throw(_('Invalid Chapter reference: {0}').format(chapter_ref))
	
	def get_earmarking_summary(self):
		"""Get a summary of how this donation is earmarked"""
		if self.donation_purpose_type == 'General':
			return 'General Fund'
		elif self.donation_purpose_type == 'Campaign':
			return f'Campaign: {self.campaign_reference}'
		elif self.donation_purpose_type == 'Chapter':
			chapter_name = frappe.db.get_value('Chapter', self.chapter_reference, 'chapter_name')
			return f'Chapter: {chapter_name or self.chapter_reference}'
		elif self.donation_purpose_type == 'Specific Goal':
			return f'Specific Goal: {self.specific_goal_description[:50]}...' if len(self.specific_goal_description) > 50 else f'Specific Goal: {self.specific_goal_description}'
		else:
			return self.donation_category or 'Unspecified'

	def create_payment_entry(self, date=None):
		settings = frappe.get_doc('Verenigingen Settings')
		if not settings.automate_donation_payment_entries:
			return

		if not settings.donation_payment_account:
			frappe.throw(_('You need to set <b>Payment Account</b> for Donation in {0}').format(
				get_link_to_form('Verenigingen Settings', 'Verenigingen Settings')))

		from verenigingen.utils.payment_utils import get_donation_payment_entry

		frappe.flags.ignore_account_permission = True
		pe = get_donation_payment_entry(dt=self.doctype, dn=self.name)
		frappe.flags.ignore_account_permission = False
		
		# Use purpose-specific account mapping
		debit_account, credit_account = self.get_accounting_accounts()
		pe.paid_from = debit_account
		pe.paid_to = credit_account
		
		pe.posting_date = date or getdate()
		pe.reference_no = self.name
		pe.reference_date = date or getdate()
		pe.flags.ignore_mandatory = True
		pe.insert()
		pe.submit()
		
		# Create additional journal entry for earmarked donations if needed
		self.create_earmarking_journal_entry(date)
	
	def get_accounting_accounts(self):
		"""Get appropriate debit and credit accounts based on donation purpose"""
		settings = frappe.get_doc('Verenigingen Settings')
		
		# Default accounts
		debit_account = settings.donation_debit_account
		credit_account = settings.donation_payment_account
		
		# Override based on donation purpose
		if self.donation_purpose_type == 'Chapter' and self.chapter_reference:
			# Check if chapter has specific accounts
			chapter_account = frappe.db.get_value('Chapter', self.chapter_reference, 'donation_account')
			if chapter_account:
				credit_account = chapter_account
		
		elif self.donation_purpose_type == 'Campaign' and self.campaign_reference:
			# For campaigns, use a campaign-specific account if configured
			# This could be expanded to link to a Campaign doctype with accounts
			pass
			
		return debit_account, credit_account
	
	def create_earmarking_journal_entry(self, date=None):
		"""Create journal entry to move earmarked donations to specific funds"""
		if self.donation_purpose_type == 'General':
			return  # No earmarking needed for general donations
		
		# Only create earmarking entry for substantial amounts to avoid clutter
		if not self.amount or flt(self.amount) < 100:
			return
			
		from_account, to_account = self.get_earmarking_accounts()
		if not from_account or not to_account or from_account == to_account:
			return
		
		# Create journal entry for fund earmarking
		je = frappe.new_doc('Journal Entry')
		je.voucher_type = 'Journal Entry'
		je.company = self.company
		je.posting_date = date or getdate()
		je.user_remark = f'Earmarking donation {self.name} for {self.get_earmarking_summary()}'
		
		# Credit general donation account
		je.append('accounts', {
			'account': from_account,
			'credit_in_account_currency': self.amount,
			'reference_type': 'Donation',
			'reference_name': self.name
		})
		
		# Debit specific purpose account
		je.append('accounts', {
			'account': to_account,
			'debit_in_account_currency': self.amount,
			'reference_type': 'Donation',
			'reference_name': self.name
		})
		
		je.insert(ignore_permissions=True)
		je.submit()
		
		return je.name
	
	def get_earmarking_accounts(self):
		"""Get accounts for earmarking journal entries"""
		settings = frappe.get_doc('Verenigingen Settings')
		from_account = settings.donation_payment_account  # General donation account
		to_account = None
		
		if self.donation_purpose_type == 'Chapter' and self.chapter_reference:
			to_account = frappe.db.get_value('Chapter', self.chapter_reference, 'donation_account')
			
		elif self.donation_purpose_type == 'Campaign':
			# Could be expanded to use campaign-specific accounts
			to_account = frappe.db.get_single_value('Verenigingen Settings', 'campaign_donation_account')
			
		elif self.donation_purpose_type == 'Specific Goal':
			# Use a general "restricted funds" account
			to_account = frappe.db.get_single_value('Verenigingen Settings', 'restricted_donation_account')
		
		return from_account, to_account

	def on_submit(self):
		"""Called when donation is submitted"""
		# Send confirmation email
		from verenigingen.utils.donation_emails import send_donation_confirmation
		frappe.enqueue(
			send_donation_confirmation,
			donation_id=self.name,
			queue="short",
			timeout=300
		)
	
	def on_update_after_submit(self):
		"""Called when submitted donation is updated"""
		# Send payment confirmation if marked as paid
		if self.paid and self.has_value_changed("paid"):
			from verenigingen.utils.donation_emails import send_payment_confirmation
			frappe.enqueue(
				send_payment_confirmation,
				donation_id=self.name,
				queue="short",
				timeout=300
			)

	def on_cancel(self):
		self.ignore_linked_doctypes = (
			"GL Entry",
			"Stock Ledger Entry",
			"Payment Ledger Entry",
			"Repost Payment Ledger",
			"Repost Payment Ledger Items",
			"Repost Accounting Ledger",
			"Repost Accounting Ledger Items",
			"Unreconcile Payment",
			"Unreconcile Payment Entries",
		)


@frappe.whitelist()
def create_donation_from_bank_transfer(donor, amount, date, bank_reference, donation_type=None):
	"""Create donation from bank transfer details"""
	if not donation_type:
		donation_type = frappe.db.get_single_value('Verenigingen Settings', 'default_donation_type')
	
	company = get_company_for_donations()
	donation = frappe.get_doc({
		'doctype': 'Donation',
		'company': company,
		'donor': donor,
		'date': getdate(date),
		'amount': flt(amount),
		'payment_method': 'Bank Transfer',
		'bank_reference': bank_reference,
		'donation_type': donation_type,
		'paid': 1
	}).insert()

	donation.submit()
	donation.create_payment_entry()
	return donation


def get_donor_by_email(email):
	"""Get donor by email address"""
	donors = frappe.get_all('Donor',
		filters={'donor_email': email},
		order_by='creation desc')

	try:
		return frappe.get_doc('Donor', donors[0]['name'])
	except Exception:
		return None


@frappe.whitelist()
def create_donor_from_donation(donor_name, email, phone=None, donor_type=None):
	"""Create a new donor from donation information"""
	if not donor_type:
		donor_type = frappe.db.get_single_value('Verenigingen Settings', 'default_donor_type')

	donor = frappe.new_doc('Donor')
	donor.update({
		'donor_name': donor_name,
		'donor_type': donor_type,
		'donor_email': email,
		'phone': phone or ''
	})

	donor.insert()
	return donor


def get_company_for_donations():
	company = frappe.db.get_single_value('Verenigingen Settings', 'donation_company')
	if not company:
		from verenigingen.verenigingen.utils import get_company
		company = get_company()
	return company


@frappe.whitelist()
def create_sepa_donation(donor, amount, date, sepa_mandate, donation_type=None, recurring_frequency=None):
	"""Create donation for SEPA direct debit"""
	if not donation_type:
		donation_type = frappe.db.get_single_value('Verenigingen Settings', 'default_donation_type')
	
	company = get_company_for_donations()
	donation_status = 'Recurring' if recurring_frequency else 'Promised'
	
	donation = frappe.get_doc({
		'doctype': 'Donation',
		'company': company,
		'donor': donor,
		'date': getdate(date),
		'amount': flt(amount),
		'payment_method': 'SEPA Direct Debit',
		'donation_type': donation_type,
		'donation_status': donation_status,
		'sepa_mandate': sepa_mandate,
		'recurring_frequency': recurring_frequency,
		'paid': 0  # Will be marked paid when SEPA batch is processed
	}).insert()

	return donation


def create_mode_of_payment(method):
	"""Create mode of payment if it doesn't exist"""
	if not frappe.db.exists('Mode of Payment', method):
		frappe.get_doc({
			'doctype': 'Mode of Payment',
			'mode_of_payment': method
		}).insert(ignore_mandatory=True)


@frappe.whitelist()
def get_anbi_donations_for_reporting(from_date, to_date):
	"""Get all ANBI donations requiring Belastingdienst reporting"""
	donations = frappe.get_all('Donation',
		filters={
			'belastingdienst_reportable': 1,
			'date': ['between', [from_date, to_date]],
			'docstatus': 1
		},
		fields=['name', 'donor', 'date', 'amount', 'anbi_agreement_number', 'anbi_agreement_date']
	)
	
	report_data = []
	for donation in donations:
		donation_doc = frappe.get_doc('Donation', donation.name)
		report_data.append(donation_doc.generate_anbi_report_data())
	
	return [data for data in report_data if data]  # Filter out None values


@frappe.whitelist()
def generate_anbi_agreement_number():
	"""Generate next ANBI agreement number"""
	# Get the latest ANBI agreement number
	latest = frappe.db.sql("""
		SELECT anbi_agreement_number 
		FROM `tabDonation` 
		WHERE anbi_agreement_number IS NOT NULL 
		ORDER BY creation DESC 
		LIMIT 1
	""")
	
	if latest and latest[0][0]:
		try:
			# Extract number from format like "ANBI-2024-001"
			parts = latest[0][0].split('-')
			if len(parts) >= 3:
				year = parts[1]
				num = int(parts[2]) + 1
			else:
				year = str(getdate().year)
				num = 1
		except:
			year = str(getdate().year)
			num = 1
	else:
		year = str(getdate().year)
		num = 1
	
	return f"ANBI-{year}-{num:03d}"


@frappe.whitelist()
def get_donations_by_chapter(chapter, from_date=None, to_date=None):
	"""Get all donations earmarked for a specific chapter"""
	filters = {
		'chapter_reference': chapter,
		'donation_purpose_type': 'Chapter',
		'docstatus': 1
	}
	
	if from_date and to_date:
		filters['date'] = ['between', [from_date, to_date]]
	
	donations = frappe.get_all('Donation',
		filters=filters,
		fields=['name', 'donor', 'date', 'amount', 'donation_type', 'paid'],
		order_by='date desc'
	)
	
	total_amount = sum(d.amount for d in donations if d.amount)
	paid_amount = sum(d.amount for d in donations if d.amount and d.paid)
	
	return {
		'donations': donations,
		'total_amount': total_amount,
		'paid_amount': paid_amount,
		'outstanding_amount': total_amount - paid_amount,
		'count': len(donations)
	}


@frappe.whitelist()
def get_donations_by_campaign(campaign_reference, from_date=None, to_date=None):
	"""Get all donations for a specific campaign"""
	filters = {
		'campaign_reference': campaign_reference,
		'donation_purpose_type': 'Campaign',
		'docstatus': 1
	}
	
	if from_date and to_date:
		filters['date'] = ['between', [from_date, to_date]]
	
	donations = frappe.get_all('Donation',
		filters=filters,
		fields=['name', 'donor', 'date', 'amount', 'donation_type', 'paid'],
		order_by='date desc'
	)
	
	total_amount = sum(d.amount for d in donations if d.amount)
	paid_amount = sum(d.amount for d in donations if d.amount and d.paid)
	
	return {
		'donations': donations,
		'total_amount': total_amount,
		'paid_amount': paid_amount,
		'outstanding_amount': total_amount - paid_amount,
		'count': len(donations)
	}


@frappe.whitelist()
def get_donation_summary_by_purpose(from_date=None, to_date=None):
	"""Get donation summary grouped by purpose type"""
	filters = {'docstatus': 1}
	
	if from_date and to_date:
		filters['date'] = ['between', [from_date, to_date]]
	
	donations = frappe.get_all('Donation',
		filters=filters,
		fields=['donation_purpose_type', 'amount', 'paid', 'chapter_reference', 'campaign_reference'],
	)
	
	summary = {
		'General': {'total': 0, 'paid': 0, 'count': 0},
		'Campaign': {'total': 0, 'paid': 0, 'count': 0, 'campaigns': {}},
		'Chapter': {'total': 0, 'paid': 0, 'count': 0, 'chapters': {}},
		'Specific Goal': {'total': 0, 'paid': 0, 'count': 0}
	}
	
	for donation in donations:
		purpose = donation.donation_purpose_type or 'General'
		amount = donation.amount or 0
		
		if purpose in summary:
			summary[purpose]['total'] += amount
			summary[purpose]['count'] += 1
			if donation.paid:
				summary[purpose]['paid'] += amount
			
			# Track individual campaigns and chapters
			if purpose == 'Campaign' and donation.campaign_reference:
				if donation.campaign_reference not in summary['Campaign']['campaigns']:
					summary['Campaign']['campaigns'][donation.campaign_reference] = {'total': 0, 'paid': 0, 'count': 0}
				summary['Campaign']['campaigns'][donation.campaign_reference]['total'] += amount
				summary['Campaign']['campaigns'][donation.campaign_reference]['count'] += 1
				if donation.paid:
					summary['Campaign']['campaigns'][donation.campaign_reference]['paid'] += amount
			
			elif purpose == 'Chapter' and donation.chapter_reference:
				if donation.chapter_reference not in summary['Chapter']['chapters']:
					summary['Chapter']['chapters'][donation.chapter_reference] = {'total': 0, 'paid': 0, 'count': 0}
				summary['Chapter']['chapters'][donation.chapter_reference]['total'] += amount
				summary['Chapter']['chapters'][donation.chapter_reference]['count'] += 1
				if donation.paid:
					summary['Chapter']['chapters'][donation.chapter_reference]['paid'] += amount
	
	return summary


@frappe.whitelist()
def create_chapter_donation(donor, amount, chapter, date=None, donation_type=None, notes=None):
	"""Create a donation earmarked for a specific chapter"""
	if not frappe.db.exists('Chapter', chapter):
		frappe.throw(_('Chapter {0} does not exist').format(chapter))
	
	if not donation_type:
		donation_type = frappe.db.get_single_value('Verenigingen Settings', 'default_donation_type')
	
	company = get_company_for_donations()
	donation = frappe.get_doc({
		'doctype': 'Donation',
		'company': company,
		'donor': donor,
		'date': getdate(date) if date else getdate(),
		'amount': flt(amount),
		'donation_type': donation_type,
		'donation_purpose_type': 'Chapter',
		'chapter_reference': chapter,
		'donation_notes': notes or f'Donation earmarked for {chapter}'
	}).insert()

	return donation


@frappe.whitelist()
def get_donation_accounting_summary(from_date=None, to_date=None):
	"""Get donation accounting summary with GL account details"""
	filters = {'docstatus': 1, 'paid': 1}
	
	if from_date and to_date:
		filters['date'] = ['between', [from_date, to_date]]
	
	donations = frappe.get_all('Donation',
		filters=filters,
		fields=['name', 'amount', 'donation_purpose_type', 'chapter_reference', 'campaign_reference', 'company']
	)
	
	accounting_summary = {
		'total_donations': 0,
		'by_purpose': {},
		'gl_entries': []
	}
	
	for donation in donations:
		amount = flt(donation.amount)
		accounting_summary['total_donations'] += amount
		
		purpose = donation.donation_purpose_type or 'General'
		if purpose not in accounting_summary['by_purpose']:
			accounting_summary['by_purpose'][purpose] = 0
		accounting_summary['by_purpose'][purpose] += amount
		
		# Get related GL entries for this donation
		gl_entries = frappe.get_all('GL Entry',
			filters={'voucher_no': donation.name, 'voucher_type': 'Payment Entry'},
			fields=['account', 'debit', 'credit', 'posting_date']
		)
		
		for gl in gl_entries:
			gl['donation'] = donation.name
			gl['purpose'] = purpose
			accounting_summary['gl_entries'].append(gl)
	
	return accounting_summary


@frappe.whitelist()
def reconcile_donation_accounts():
	"""Reconcile donation amounts with GL entries"""
	# Get all paid donations
	donations = frappe.get_all('Donation',
		filters={'paid': 1, 'docstatus': 1},
		fields=['name', 'amount', 'date', 'company']
	)
	
	reconciliation_report = {
		'total_donations': 0,
		'total_gl_credits': 0,
		'discrepancies': [],
		'summary': {}
	}
	
	for donation in donations:
		amount = flt(donation.amount)
		reconciliation_report['total_donations'] += amount
		
		# Get GL entries for this donation
		gl_credits = frappe.db.sql("""
			SELECT SUM(credit) as total_credit
			FROM `tabGL Entry`
			WHERE reference_name = %s AND reference_type = 'Donation'
		""", donation.name, as_dict=True)
		
		gl_credit_amount = flt(gl_credits[0].total_credit) if gl_credits and gl_credits[0].total_credit else 0
		reconciliation_report['total_gl_credits'] += gl_credit_amount
		
		# Check for discrepancies
		if abs(amount - gl_credit_amount) > 0.01:  # Allow for minor rounding
			reconciliation_report['discrepancies'].append({
				'donation': donation.name,
				'donation_amount': amount,
				'gl_amount': gl_credit_amount,
				'difference': amount - gl_credit_amount,
				'date': donation.date
			})
	
	reconciliation_report['summary'] = {
		'total_difference': reconciliation_report['total_donations'] - reconciliation_report['total_gl_credits'],
		'discrepancy_count': len(reconciliation_report['discrepancies']),
		'reconciliation_status': 'Clean' if len(reconciliation_report['discrepancies']) == 0 else 'Needs Review'
	}
	
	return reconciliation_report


@frappe.whitelist()
def create_donation_allocation_report(chapter=None, from_date=None, to_date=None):
	"""Create detailed allocation report for chapter or overall donations"""
	filters = {'docstatus': 1}
	
	if chapter:
		filters['chapter_reference'] = chapter
		filters['donation_purpose_type'] = 'Chapter'
	
	if from_date and to_date:
		filters['date'] = ['between', [from_date, to_date]]
	
	donations = frappe.get_all('Donation',
		filters=filters,
		fields=['name', 'donor', 'date', 'amount', 'paid', 'donation_purpose_type', 
		        'chapter_reference', 'campaign_reference', 'specific_goal_description']
	)
	
	# Get donor details
	for donation in donations:
		if donation.donor:
			donor_doc = frappe.get_doc('Donor', donation.donor)
			donation['donor_name'] = getattr(donor_doc, 'donor_name', '')
			donation['donor_email'] = getattr(donor_doc, 'donor_email', '')
	
	report = {
		'donations': donations,
		'summary': {
			'total_amount': sum(d.amount for d in donations if d.amount),
			'paid_amount': sum(d.amount for d in donations if d.amount and d.paid),
			'outstanding_amount': sum(d.amount for d in donations if d.amount and not d.paid),
			'count': len(donations)
		},
		'filters_applied': {
			'chapter': chapter,
			'from_date': from_date,
			'to_date': to_date
		}
	}
	
	return report
