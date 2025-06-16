import frappe
from frappe import _, scrub
from frappe.utils.data import comma_or

from erpnext.accounts.doctype.invoice_discounting.invoice_discounting import \
	get_party_account_based_on_invoice_discounting
from erpnext.accounts.doctype.payment_entry.payment_entry import PaymentEntry


class PaymentEntry(PaymentEntry):
	"""Extended Payment Entry to support nonprofit operations with Donor party type"""
	
	def validate_reference_documents(self):
		"""Override to add support for Donor party type and Donation reference documents"""
		if self.party_type == "Student":
			valid_reference_doctypes = ("Fees", "Journal Entry")
		elif self.party_type == "Customer":
			valid_reference_doctypes = ("Sales Order", "Sales Invoice", "Journal Entry", "Dunning")
		elif self.party_type == "Supplier":
			valid_reference_doctypes = ("Purchase Order", "Purchase Invoice", "Journal Entry")
		elif self.party_type == "Employee":
			valid_reference_doctypes = ("Expense Claim", "Journal Entry", "Employee Advance")
		elif self.party_type == "Shareholder":
			valid_reference_doctypes = ("Journal Entry")
		elif self.party_type == "Donor":
			# Support for nonprofit Donor party type
			valid_reference_doctypes = ("Donation", "Journal Entry")
		else:
			# Fall back to parent validation for other party types
			return super().validate_reference_documents()

		for d in self.get("references"):
			if not d.allocated_amount:
				continue
			if d.reference_doctype not in valid_reference_doctypes:
				frappe.throw(_("Reference Doctype must be one of {0}")
					.format(comma_or(valid_reference_doctypes)))
			elif d.reference_name:
				if not frappe.db.exists(d.reference_doctype, d.reference_name):
					frappe.throw(_("{0} {1} does not exist").format(d.reference_doctype, d.reference_name))
				else:
					ref_doc = frappe.get_doc(d.reference_doctype, d.reference_name)
					if d.reference_doctype != "Journal Entry":
						if self.party != ref_doc.get(scrub(self.party_type)):
							frappe.throw(_("{0} {1} is not associated with {2} {3}")
								.format(d.reference_doctype, d.reference_name, self.party_type, self.party))
					else:
						self.validate_journal_entry()
					if d.reference_doctype in ("Sales Invoice", "Purchase Invoice", "Expense Claim", "Fees"):
						if self.party_type == "Customer":
							ref_party_account = get_party_account_based_on_invoice_discounting(d.reference_name) or ref_doc.debit_to
						elif self.party_type == "Student":
							ref_party_account = ref_doc.receivable_account
						elif self.party_type=="Supplier":
							ref_party_account = ref_doc.credit_to
						elif self.party_type=="Employee":
							ref_party_account = ref_doc.payable_account
						if ref_party_account != self.party_account:
								frappe.throw(_("{0} {1} is associated with {2}, but Party Account is {3}")
									.format(d.reference_doctype, d.reference_name, ref_party_account, self.party_account))
					if ref_doc.docstatus != 1:
						frappe.throw(_("{0} {1} must be submitted")
							.format(d.reference_doctype, d.reference_name))

	def set_missing_ref_details(
		self,
		force: bool = False,
		update_ref_details_only_for: list | None = None,
		reference_exchange_details: dict | None = None,
	) -> None:
		"""Override to support custom reference details for nonprofit doctypes"""
		# Import here to avoid circular imports
		from verenigingen.utils.payment_utils import get_payment_reference_details
		
		for d in self.get("references"):
			if d.allocated_amount:
				if (
					update_ref_details_only_for
					and (d.reference_doctype, d.reference_name) not in update_ref_details_only_for
				):
					continue

				ref_details = get_payment_reference_details(d.reference_doctype, d.reference_name, self.party_account_currency,
															self.party_type, self.party)

				# Only update exchange rate when the reference is Journal Entry
				if (
					reference_exchange_details
					and d.reference_doctype == reference_exchange_details.reference_doctype
					and d.reference_name == reference_exchange_details.reference_name
				):
					ref_details.update({"exchange_rate": reference_exchange_details.exchange_rate})

				for field, value in ref_details.items():
					if d.exchange_gain_loss:
						# for cases where gain/loss is booked into invoice
						# exchange_gain_loss is calculated from invoice & populated
						# and row.exchange_rate is already set to payment entry's exchange rate
						# refer -> `update_reference_in_payment_entry()` in utils.py
						continue

					if field == 'exchange_rate' or not d.get(field) or force:
						d.db_set(field, value)