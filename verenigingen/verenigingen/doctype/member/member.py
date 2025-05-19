import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today, add_days, date_diff, now

class Member(Document):
    def before_save(self):
        if not self.member_id:
            self.member_id = self.generate_member_id()

    def generate_member_id(self):
        settings = frappe.get_single("Verenigingen Settings")

        if not settings.last_member_id:
            settings.last_member_id = settings.member_id_start -1

        new_id = settings.last_member_id +1

        settings.last_member_id = new_id
        settings.save()

        return str(new_id)
    
    def validate(self):
        self.validate_name()
        self.update_full_name()
        self.update_membership_status()
        self.calculate_age()
        self.validate_payment_method()
        self.set_payment_reference()
        self.validate_bank_details()
        self.sync_payment_amount()

    def after_insert(self):
        """Create linked entities after member is created"""
        # Create customer if not already linked
        if not self.customer and self.email:
            self.create_customer()

    def calculate_age(self):
        """Calculate age based on birth_date field"""
        try:
            if self.birth_date:
                from datetime import datetime, date
                today = date.today()
                if isinstance(self.birth_date, str):
                    born = datetime.strptime(self.birth_date, '%Y-%m-%d').date()
                else:
                    born = self.birth_date
            # Calculate age
                age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
            # Set the age field
                self.age = age
            else:
                self.age = None
        except Exception as e:
            frappe.log_error(f"Error calculating age: {str(e)}", "Member Error")

    @frappe.whitelist()
    def load_payment_history(self):
        """
        Load payment history for this member with focus on invoices.
        Also include unreconciled payments, but maintain separation from the Donation system.
        Then save the document to persist the changes.
        """
        # Use the shared logic to load payment history
        self._load_payment_history_without_save()
        
        # Save the document to persist the payment history
        self.save(ignore_permissions=True)
        
        return True

    def on_load(self):
        """Load payment history when the document is loaded"""
        if self.customer:
            self._load_payment_history_without_save()

    def _load_payment_history_without_save(self):
        """Internal method to load payment history without saving"""
        if not self.customer:
            return
        
        # Clear existing payment history
        self.payment_history = []
        
        # 1. Get all submitted invoices for this customer
        invoices = frappe.get_all(
            "Sales Invoice",
            filters={
                "customer": self.customer,
                "docstatus": 1  # Submitted invoices
            },
            fields=[
                "name", "posting_date", "due_date", "grand_total", 
                "outstanding_amount", "status"
            ],
            order_by="posting_date desc"
        )
        
        # Track payments that are reconciled with invoices
        reconciled_payments = []
        
        # 2. Process each invoice and its payment status
        for invoice in invoices:
            invoice_doc = frappe.get_doc("Sales Invoice", invoice.name)
            
            # Determine reference documents for this invoice
            reference_doctype = None
            reference_name = None
            transaction_type = "Regular Invoice"
            
            # Check if invoice is linked to a membership
            if hasattr(invoice_doc, 'membership') and invoice_doc.membership:
                transaction_type = "Membership Invoice"
                reference_doctype = "Membership"
                reference_name = invoice_doc.membership
            
            # Find linked payment entries
            payment_entries = frappe.get_all(
                "Payment Entry Reference",
                filters={"reference_doctype": "Sales Invoice", "reference_name": invoice.name},
                fields=["parent", "allocated_amount"]
            )
            
            # Determine payment status and details
            payment_status = "Unpaid"
            payment_date = None
            payment_entry = None
            payment_method = None
            paid_amount = 0
            reconciled = 0
            
            if payment_entries:
                # Track these payments as reconciled
                for pe in payment_entries:
                    reconciled_payments.append(pe.parent)
                    paid_amount += float(pe.allocated_amount or 0)
                
                # Get the most recent payment entry for reference
                most_recent_payment = frappe.get_all(
                    "Payment Entry",
                    filters={"name": ["in", [pe.parent for pe in payment_entries]]},
                    fields=["name", "posting_date", "mode_of_payment", "paid_amount"],
                    order_by="posting_date desc"
                )
                
                if most_recent_payment:
                    payment_entry = most_recent_payment[0].name
                    payment_date = most_recent_payment[0].posting_date
                    payment_method = most_recent_payment[0].mode_of_payment
                    reconciled = 1
            
            # Set payment status based on invoice and payment data
            if invoice.status == "Paid":
                payment_status = "Paid"
            elif invoice.status == "Overdue":
                payment_status = "Overdue"
            elif invoice.status == "Cancelled":
                payment_status = "Cancelled"
            elif paid_amount > 0 and paid_amount < invoice.grand_total:
                payment_status = "Partially Paid"
            
            # Check for SEPA mandate
            has_mandate = 0
            sepa_mandate = None
            mandate_status = None
            mandate_reference = None
            
            # First check if there's a mandate linked to the membership
            if reference_doctype == "Membership" and reference_name:
                try:
                    membership_doc = frappe.get_doc("Membership", reference_name)
                    if hasattr(membership_doc, 'sepa_mandate') and membership_doc.sepa_mandate:
                        has_mandate = 1
                        sepa_mandate = membership_doc.sepa_mandate
                        mandate_doc = frappe.get_doc("SEPA Mandate", sepa_mandate)
                        mandate_status = mandate_doc.status
                        mandate_reference = mandate_doc.mandate_id
                except Exception as e:
                    frappe.log_error(f"Error checking membership mandate for invoice {invoice.name}: {str(e)}")
            
            # If no mandate found, check member's default mandate
            if not has_mandate:
                default_mandate = self.get_default_sepa_mandate()
                if default_mandate:
                    has_mandate = 1
                    sepa_mandate = default_mandate.name
                    mandate_status = default_mandate.status
                    mandate_reference = default_mandate.mandate_id
            
            # Add invoice to payment history
            self.append("payment_history", {
                "invoice": invoice.name,
                "posting_date": invoice.posting_date,
                "due_date": invoice.due_date,
                "transaction_type": transaction_type,
                "reference_doctype": reference_doctype,
                "reference_name": reference_name,
                "amount": invoice.grand_total,
                "outstanding_amount": invoice.outstanding_amount,
                "status": invoice.status,
                "payment_status": payment_status,
                "payment_date": payment_date,
                "payment_entry": payment_entry,
                "payment_method": payment_method,
                "paid_amount": paid_amount,
                "reconciled": reconciled,
                "has_mandate": has_mandate,
                "sepa_mandate": sepa_mandate,
                "mandate_status": mandate_status,
                "mandate_reference": mandate_reference
            })
        
        # 3. Now find payments that aren't reconciled with any invoice
        unreconciled_payments = frappe.get_all(
            "Payment Entry",
            filters={
                "party_type": "Customer",
                "party": self.customer,
                "docstatus": 1,
                "name": ["not in", reconciled_payments or [""] if reconciled_payments else [""]]
            },
            fields=["name", "posting_date", "paid_amount", "mode_of_payment", "status", "reference_no", "reference_date"],
            order_by="posting_date desc"
        )
        
        for payment in unreconciled_payments:
            # Check if this payment is linked to a Donation
            donation = None
            if payment.reference_no:
                donations = frappe.get_all(
                    "Donation",
                    filters={"payment_id": payment.reference_no},
                    fields=["name"]
                )
                if donations:
                    donation = donations[0].name
            
            transaction_type = "Unreconciled Payment"
            reference_doctype = None
            reference_name = None
            notes = "Payment without matching invoice"
            
            # If this payment is linked to a donation, update references
            if donation:
                transaction_type = "Donation Payment"
                reference_doctype = "Donation"
                reference_name = donation
                notes = "Payment linked to donation"
            
            # Create a record for unreconciled payment
            self.append("payment_history", {
                "invoice": None,  # No invoice
                "posting_date": payment.posting_date,
                "due_date": None,
                "transaction_type": transaction_type,
                "reference_doctype": reference_doctype,
                "reference_name": reference_name,
                "amount": payment.paid_amount,
                "outstanding_amount": 0,
                "status": "N/A",  # No invoice status
                "payment_status": "Paid",  # Payment exists
                "payment_date": payment.posting_date,
                "payment_entry": payment.name,
                "payment_method": payment.mode_of_payment,
                "paid_amount": payment.paid_amount,
                "reconciled": 0,  # Not reconciled
                "notes": notes
            })
            
    def validate_payment_method(self):
        """Validate payment method and related fields"""
        # Check if payment_method exists (it might be on Membership, not Member)
        if not hasattr(self, 'payment_method'):
            # payment_method field doesn't exist on Member doctype
            # Check if we need to validate payment methods from memberships instead
            memberships = frappe.get_all(
                "Membership",
                filters={"member": self.name, "status": ["!=", "Cancelled"]},
                fields=["name", "payment_method"]
            )
            
            # If there are memberships with Direct Debit, check for SEPA mandate
            for membership in memberships:
                if membership.payment_method == "Direct Debit":
                    # Check if member has SEPA mandate fields
                    default_mandate = self.get_default_sepa_mandate()
                    if not default_mandate:
                        frappe.msgprint(
                            _("Member {0} has a membership with Direct Debit payment method but no active SEPA mandate.")
                            .format(self.name),
                            indicator='yellow'
                        )
                    break
            
            return

    def validate_name(self):
        # Validate that name fields don't contain special characters
        for field in ['first_name', 'middle_name', 'last_name']:
            if not hasattr(self, field) or not getattr(self, field):
                continue
            if not getattr(self, field).isalnum() and not all(c.isalnum() or c.isspace() for c in getattr(self, field)):
                frappe.throw(_("{0} name should not contain special characters")
                    .format(field.replace('_', ' ').title()))
                    
    def update_full_name(self):
        # Update the full name based on first, middle and last name
        full_name = " ".join(filter(None, [self.first_name, self.middle_name, self.last_name]))
        if self.full_name != full_name:
            self.full_name = full_name
            
    def update_membership_status(self):
        # Update the membership status section
        active_membership = self.get_active_membership()
        
        if active_membership:
            self.current_membership_details = active_membership.name
            
            if active_membership.end_date:
                # Calculate time remaining until end date
                days_left = date_diff(active_membership.end_date, getdate(today()))
                
                # Don't set time_remaining directly if field doesn't exist
                # Instead, perhaps add it to notes or a custom field
                time_remaining_text = ""
                if days_left < 0:
                    time_remaining_text = _("Expired")
                elif days_left == 0:
                    time_remaining_text = _("Expires today")
                else:
                    # Format as days/months/years depending on length
                    if days_left < 30:
                        time_remaining_text = _("{0} days").format(days_left)
                    elif days_left < 365:
                        months = int(days_left / 30)
                        time_remaining_text = _("{0} months").format(months)
                    else:
                        years = round(days_left / 365, 1)
                        time_remaining_text = _("{0} years").format(years)
                        
                # Store this information in notes or a custom field if needed
                if hasattr(self, 'time_remaining'):
                    self.time_remaining = time_remaining_text
                elif hasattr(self, 'notes'):
                    # Optionally add to notes
                    if not self.notes:
                        self.notes = f"<p>Time remaining: {time_remaining_text}</p>"
                    # Otherwise, consider updating notes or custom fields
            
    def get_active_membership(self):
        """Get currently active membership for this member"""
        memberships = frappe.get_all(
            "Membership",
            filters={
                "member": self.name,
                "status": "Active",
                "docstatus": 1
            },
            fields=["name", "membership_type", "start_date", "end_date", "status"],
            order_by="start_date desc"
        )
        
        if memberships:
            return frappe.get_doc("Membership", memberships[0].name)
            
        return None

    # Add these methods to the Member class in member.py
    
    def get_active_sepa_mandates(self):
        """Get all active SEPA mandates for this member"""
        return frappe.get_all(
            "SEPA Mandate",
            filters={
                "member": self.name,
                "status": "Active",
                "is_active": 1
            },
            fields=["name", "mandate_id", "status", "expiry_date", "used_for_memberships", "used_for_donations"]
        )
    
    def get_default_sepa_mandate(self):
        """Get the default SEPA mandate for this member"""
        # First, check for a current mandate in the member's mandate links
        for link in self.sepa_mandates:
            if link.is_current and link.sepa_mandate:
                try:
                    mandate = frappe.get_doc("SEPA Mandate", link.sepa_mandate)
                    if mandate.status == "Active" and mandate.is_active:
                        return mandate
                except frappe.DoesNotExistError:
                    continue
        
        # If no current mandate, get the first active mandate
        active_mandates = self.get_active_sepa_mandates()
        if active_mandates:
            # Mark this as the current mandate
            for link in self.sepa_mandates:
                if link.sepa_mandate == active_mandates[0].name:
                    link.is_current = 1
                    # Don't save here to avoid recursive save operations
                    break
            
            return frappe.get_doc("SEPA Mandate", active_mandates[0].name)
        
        return None
    
    def has_active_sepa_mandate(self, purpose="memberships"):
        """Check if member has an active SEPA mandate for a specific purpose"""
        filters = {
            "member": self.name,
            "status": "Active",
            "is_active": 1
        }
        
        if purpose == "memberships":
            filters["used_for_memberships"] = 1
        elif purpose == "donations":
            filters["used_for_donations"] = 1
        
        return frappe.db.exists("SEPA Mandate", filters)
    
    def on_trash(self):
        # Check if member has any active memberships
        active_memberships = frappe.get_all("Membership", 
            filters={"member": self.name, "docstatus": 1, "status": ["!=", "Cancelled"]})
        
        if active_memberships:
            frappe.throw(_("Cannot delete member with active memberships. Please cancel all memberships first."))
            
    @frappe.whitelist()
    def create_customer(self):
        """Create a customer for this member in ERPNext"""
        # First check if a customer is already linked to this member
        if self.customer:
            frappe.msgprint(_("Customer {0} already exists for this member").format(self.customer))
            return self.customer
    
        # REMOVED: The check for customer with same email already exists
        # We want each member to have their own unique customer
    
        # For duplicate name detection, we need a more sophisticated approach
        if self.full_name:
            # Get all customers with similar names
            similar_name_customers = frappe.get_all(
                "Customer",
                filters=[
                    ["customer_name", "like", f"%{self.full_name}%"]
                ],
                fields=["name", "customer_name", "email_id", "mobile_no"]
            )
    
            # Check if any match by exact name
            exact_name_match = next((c for c in similar_name_customers if c.customer_name.lower() == self.full_name.lower()), None)
            if exact_name_match:
                # Don't automatically link - just inform the user
                customer_info = f"Name: {exact_name_match.name}, Email: {exact_name_match.email_id or 'N/A'}"
                frappe.msgprint(
                    _("Found existing customer with same name: {0}").format(customer_info) +
                    _("\nCreating a new customer for this member. If you want to link to the existing customer instead, please do so manually.")
                )
    
            # If no exact match but we have similar names, prompt the user
            elif similar_name_customers:
                # Log similar customers for review
                customer_list = "\n".join([f"- {c.customer_name} ({c.name})" for c in similar_name_customers[:5]])
                frappe.msgprint(
                    _("Found similar customer names. Please review:") + 
                    f"\n{customer_list}" +
                    (_("\n(Showing first 5 of {0} matches)").format(len(similar_name_customers)) if len(similar_name_customers) > 5 else "") +
                    _("\nCreating a new customer for this member.")
                )
        
        # Create new customer if no match found or if matches were found but we're proceeding with a new customer
        customer = frappe.new_doc("Customer")
        customer.customer_name = self.full_name
        customer.customer_type = "Individual"

        # Set contact details
        if self.email:
            customer.email_id = self.email
        if self.mobile_no:
            customer.mobile_no = self.mobile_no
        if self.phone:
            customer.phone = self.phone

        # Save customer
        customer.flags.ignore_mandatory = True
        customer.insert(ignore_permissions=True)

        # Link customer to member
        self.customer = customer.name
        self.save(ignore_permissions=True)

        frappe.msgprint(_("Customer {0} created successfully").format(customer.name))
        return customer.name   
        
    @frappe.whitelist()
    def create_user(self):
        """Create a user account for this member"""
        if self.user:
            frappe.msgprint(_("User {0} already exists for this member").format(self.user))
            return self.user
            
        if not self.email:
            frappe.throw(_("Email is required to create a user"))
            
        # Check if user already exists
        if frappe.db.exists("User", self.email):
            user = frappe.get_doc("User", self.email)
            self.user = user.name
            self.save()
            frappe.msgprint(_("Linked to existing user {0}").format(user.name))
            return user.name
            
        # Create new user
        user = frappe.new_doc("User")
        user.email = self.email
        user.first_name = self.first_name
        user.last_name = self.last_name
        user.send_welcome_email = 1
        user.user_type = "Website User"
        
        member_role = "Assocation Member"
        verenigingen_member_role = "Verenigingen Member"
    
        # Try to find a suitable role
        if frappe.db.exists("Role", member_role):
            user.append("roles", {"role": member_role})
        elif frappe.db.exists("Role", verenigingen_member_role):
            user.append("roles", {"role": verenigingen_member_role})
        else:
            # No appropriate role found, create a message but continue
            frappe.msgprint(_("Warning: Could not find Member role to assign to user. Creating user without roles."))
        
        user.flags.ignore_permissions = True
        user.insert(ignore_permissions=True)
        
        # Link user to member
        self.user = user.name
        self.save(ignore_permissions=True)
        
        frappe.msgprint(_("User {0} created successfully").format(user.name))
        return user.name
        
    def get_chapters(self):
        """Get all chapters this member belongs to"""
        # Check if chapter management is enabled
        if not is_chapter_management_enabled():
            return []
            
        chapters = []
        
        # Add primary chapter
        if self.primary_chapter:
            chapters.append({
                "chapter": self.primary_chapter,
                "is_primary": 1
            })
        
        # Add chapters where member is in the members list
        member_chapters = frappe.get_all(
            "Chapter Member", 
            filters={"user": self.user, "enabled": 1},
            fields=["parent as chapter"]
        )
        
        for mc in member_chapters:
            if mc.chapter != self.primary_chapter:
                chapters.append({
                    "chapter": mc.chapter,
                    "is_primary": 0
                })
        
        # Add chapters where member is on the board
        board_chapters = frappe.get_all(
            "Chapter Board Member",
            filters={"member": self.name, "is_active": 1},
            fields=["parent as chapter"]
        )
        
        for bc in board_chapters:
            if not any(c["chapter"] == bc.chapter for c in chapters):
                chapters.append({
                    "chapter": bc.chapter,
                    "is_primary": 0,
                    "is_board": 1
                })
        
        return chapters

    def is_board_member(self, chapter=None):
        """Check if member is a board member of any chapter or a specific chapter"""
        if not is_chapter_management_enabled():
            return False
            
        filters = {"member": self.name, "is_active": 1}
        
        if chapter:
            filters["parent"] = chapter
        
        return frappe.db.exists("Chapter Board Member", filters)
    
    def get_board_roles(self):
        """Get all board roles for this member"""
        if not is_chapter_management_enabled():
            return []
            
        board_roles = frappe.get_all(
            "Chapter Board Member",
            filters={"member": self.name, "is_active": 1},
            fields=["parent as chapter", "chapter_role as role"]
        )
        
        return board_roles
    
    def can_view_member_payments(self, view_member):
        """Check if this member can view another member's payment info"""
        # System managers can view all
        if "System Manager" in frappe.get_roles(self.user):
            return True
            
        # Can always view own payments
        if self.name == view_member:
            return True
        
        # If chapter management is disabled, only system managers can view others
        if not is_chapter_management_enabled():
            return False
        
        # Check if member is a board member with financial permissions
        member_obj = frappe.get_doc("Member", view_member)
        
        # If member has set visibility to public, anyone can view
        if member_obj.permission_category == "Public":
            return True
            
        # If set to Admin Only, only system managers can view (already checked)
        if member_obj.permission_category == "Admin Only":
            return False
        
        # For Board Only, check if this member is on board with financial permissions
        if member_obj.primary_chapter:
            chapter = frappe.get_doc("Chapter", member_obj.primary_chapter)
            return chapter.can_view_member_payments(self.name)
        
        return False
   
    def set_payment_reference(self):
        """Generate a unique payment reference for this membership"""
        if not self.payment_reference and self.name:
            # Generate reference: MEMB-YYYY-MM-XXXX
            self.payment_reference = self.name
    
    def validate_bank_details(self):
        """Validate bank details if payment method is Direct Debit"""
        if self.payment_method == "Direct Debit":
            # Find the current SEPA mandate
            current_mandate = None
            for mandate_link in self.sepa_mandates:
                if mandate_link.is_current and mandate_link.status == "Active":
                    try:
                        mandate = frappe.get_doc("SEPA Mandate", mandate_link.sepa_mandate)
                        if mandate.status == "Active" and mandate.is_active:
                            current_mandate = mandate
                            break
                    except frappe.DoesNotExistError:
                        continue
            
            # Use bank details from current mandate if available
            if current_mandate:
                self.iban = current_mandate.iban
                self.bic = current_mandate.bic
                self.bank_account_name = current_mandate.account_holder_name
            
            # Validate IBAN format
            if self.iban:
                self.iban = self.validate_iban_format(self.iban)
    
    def validate_iban_format(self, iban):
        """Basic IBAN validation and formatting"""
        if not iban:
            return None
        
        # Remove spaces and convert to uppercase
        iban = iban.replace(' ', '').upper()
        
        # Dutch IBAN should be 18 characters
        if len(iban) < 15 or len(iban) > 34:
            frappe.throw(_("Invalid IBAN length"))
        
        # Format with spaces for readability
        formatted_iban = ' '.join([iban[i:i+4] for i in range(0, len(iban), 4)])
        return formatted_iban
    
    def sync_payment_amount(self):
        """Sync payment amount from membership type"""
        if hasattr(self, 'payment_amount') and not self.payment_amount:
            # Get active membership
            active_membership = self.get_active_membership()
            if active_membership and active_membership.membership_type:
                membership_type = frappe.get_doc("Membership Type", active_membership.membership_type)
                self.payment_amount = membership_type.amount
    
    def create_payment_entry(self, payment_date=None, amount=None):
        """Create a payment entry for this membership"""
        if not payment_date:
            payment_date = today()
        
        if not amount:
            amount = self.payment_amount or 0
        
        # Get member's customer
        member = frappe.get_doc("Member", self.member)
        if not member.customer:
            frappe.throw(_("Member must have a linked customer for payment processing"))
        
        # Get payment settings
        settings = frappe.get_single("Verenigingen Settings")
        
        payment_entry = frappe.new_doc("Payment Entry")
        payment_entry.payment_type = "Receive"
        payment_entry.party_type = "Customer"
        payment_entry.party = member.customer
        payment_entry.posting_date = payment_date
        payment_entry.paid_from = settings.membership_debit_account
        payment_entry.paid_to = settings.membership_payment_account
        payment_entry.paid_amount = amount
        payment_entry.received_amount = amount
        payment_entry.reference_no = self.payment_reference
        payment_entry.reference_date = payment_date
        payment_entry.mode_of_payment = self.payment_method
        
        # Add reference to this membership
        payment_entry.append("references", {
            "reference_doctype": "Membership",
            "reference_name": self.name,
            "allocated_amount": amount
        })
        
        payment_entry.flags.ignore_mandatory = True
        payment_entry.insert(ignore_permissions=True)
        payment_entry.submit()
        
        # Update membership payment status
        self.payment_status = "Paid"
        self.payment_date = payment_date
        self.paid_amount = amount
        self.db_set('payment_status', 'Paid')
        self.db_set('payment_date', payment_date)
        self.db_set('paid_amount', amount)
        
        return payment_entry.name
    
    def process_payment(self, payment_method=None):
        """Process payment for this membership"""
        if payment_method:
            self.payment_method = payment_method
        
        if self.payment_method == "Direct Debit":
            # Add to direct debit batch
            batch = self.add_to_direct_debit_batch()
            self.payment_status = "Pending"
            self.db_set('payment_status', 'Pending')
            return batch
        else:
            # Create immediate payment entry
            payment_entry = self.create_payment_entry()
            return payment_entry
    
    def add_to_direct_debit_batch(self):
        """Add this membership to a direct debit batch"""
        # Check if there's an open batch
        open_batch = frappe.get_all(
            "Direct Debit Batch",
            filters={"status": "Draft", "docstatus": 0},
            limit=1
        )
        
        if open_batch:
            batch = frappe.get_doc("Direct Debit Batch", open_batch[0].name)
        else:
            # Create new batch
            batch = frappe.new_doc("Direct Debit Batch")
            batch.batch_date = today()
            batch.batch_description = f"Membership payments - {today()}"
            batch.batch_type = "RCUR"
            batch.currency = "EUR"
        
        # Add this membership
        batch.append("invoices", {
            "membership": self.name,
            "member": self.member,
            "member_name": self.member_name,
            "amount": self.payment_amount,
            "currency": "EUR",
            "iban": self.iban,
            "mandate_reference": self.mandate_reference or self.sepa_mandate,
            "status": "Pending"
        })
        
        batch.calculate_totals()
        batch.save()
        
        return batch.name
    
    @frappe.whitelist()
    def mark_as_paid(self, payment_date=None, amount=None):
        """Mark membership as paid"""
        if not payment_date:
            payment_date = today()
        
        if not amount:
            amount = self.payment_amount
        
        self.payment_status = "Paid"
        self.payment_date = payment_date
        self.paid_amount = amount
        
        self.save()
        
        # Create payment entry if configured
        settings = frappe.get_single("Verenigingen Settings")
        if settings.automate_membership_payment_entries:
            self.create_payment_entry(payment_date, amount)
        
        return True
    
    def check_payment_status(self):
        """Check and update payment status"""
        if self.payment_status == "Paid":
            return
        
        # Check if payment is overdue
        if self.payment_status == "Unpaid" and self.start_date:
            days_overdue = date_diff(today(), self.start_date)
            if days_overdue > 30:  # Configurable grace period
                self.payment_status = "Overdue"
                self.db_set('payment_status', 'Overdue')
                
    @frappe.whitelist()
    def create_sepa_mandate(self):
        """Create a new SEPA mandate for this member"""
        mandate = frappe.new_doc("SEPA Mandate")
        mandate.member = self.name
        mandate.member_name = self.full_name
        mandate.account_holder_name = self.full_name
        mandate.sign_date = frappe.utils.today()
        
        # Set default usage
        mandate.used_for_memberships = 1
        mandate.used_for_donations = 1
        
        mandate.insert()
        
        # Add to member's mandate links
        self.append("sepa_mandates", {
            "sepa_mandate": mandate.name,
            "is_current": 0  # Not current by default - user will need to fill in bank details
        })
        
        self.save()
        
        return mandate.name

@frappe.whitelist()
def is_chapter_management_enabled():
    """Check if chapter management is enabled in settings"""
    try:
        return frappe.db.get_single_value("Verenigingen Settings", "enable_chapter_management") == 1
    except:
        # Default to enabled if setting doesn't exist
        return True

@frappe.whitelist()
def get_board_memberships(member_name):
    """Get board memberships for a member with proper permission handling"""
    if not is_chapter_management_enabled():
        return []
        
    # Query directly using SQL to bypass permission checks
    board_memberships = frappe.db.sql("""
        SELECT cbm.parent, cbm.chapter_role 
        FROM `tabChapter Board Member` cbm
        WHERE cbm.member = %s AND cbm.is_active = 1
    """, (member_name,), as_dict=True)
    
    return board_memberships

@frappe.whitelist()
def check_sepa_mandate_status(member):
    """Check SEPA mandate status for dashboard indicators"""
    member_doc = frappe.get_doc("Member", member)
    active_mandates = member_doc.get_active_sepa_mandates()
    
    result = {
        "has_active_mandate": bool(active_mandates),
        "expiring_soon": False
    }
    
    # Check if any mandate is expiring within 30 days
    for mandate in active_mandates:
        if mandate.expiry_date:
            days_to_expiry = frappe.utils.date_diff(mandate.expiry_date, frappe.utils.today())
            if 0 < days_to_expiry <= 30:
                result["expiring_soon"] = True
                break
    
    return result

@frappe.whitelist()
def update_member_payment_history(doc, method=None):
    """Update payment history for member when a payment entry is modified"""
    if doc.party_type != "Customer":
        return
        
    # Find member linked to this customer
    members = frappe.get_all(
        "Member",
        filters={"customer": doc.party},
        fields=["name"]
    )
    
    # Update payment history for each member
    for member_doc in members:
        try:
            member = frappe.get_doc("Member", member_doc.name)
            member.load_payment_history()
            member.save(ignore_permissions=True)
        except Exception as e:
            frappe.log_error(f"Failed to update payment history for Member {member_doc.name}: {str(e)}")

def update_member_payment_history_from_invoice(doc, method=None):
    """Update payment history for member when an invoice is modified"""
    if doc.doctype != "Sales Invoice" or doc.customer is None:
        return
        
    # Find member linked to this customer
    members = frappe.get_all(
        "Member",
        filters={"customer": doc.customer},
        fields=["name"]
    )
    
    # Update payment history for each member
    for member_doc in members:
        try:
            member = frappe.get_doc("Member", member_doc.name)
            member.load_payment_history()
            member.save(ignore_permissions=True)
        except Exception as e:
            frappe.log_error(f"Failed to update payment history for Member {member_doc.name}: {str(e)}")

# Add a new method to manually add a payment/donation record
@frappe.whitelist()
def add_manual_payment_record(member, amount, payment_date=None, payment_method=None, notes=None):
    """
    Manually add a payment record (e.g., for cash donations)
    """
    if not member or not amount:
        frappe.throw(_("Member and amount are required"))
        
    member_doc = frappe.get_doc("Member", member)
    
    if not member_doc.customer:
        frappe.throw(_("Member must have a customer record"))
        
    # Create a Payment Entry
    payment = frappe.new_doc("Payment Entry")
    payment.payment_type = "Receive"
    payment.party_type = "Customer"
    payment.party = member_doc.customer
    payment.posting_date = payment_date or frappe.utils.today()
    payment.paid_amount = float(amount)
    payment.received_amount = float(amount)
    payment.mode_of_payment = payment_method or "Cash"
    
    # Set company from Verenigingen Settings
    settings = frappe.get_single("Verenigingen Settings")
    payment.company = settings.company or frappe.defaults.get_global_default('company')
    
    # Set accounts
    payment.paid_from = frappe.get_value("Company", payment.company, "default_receivable_account")
    payment.paid_to = settings.donation_payment_account or frappe.get_value("Company", payment.company, "default_cash_account")
    
    # Add remarks
    payment.remarks = notes or "Manual donation entry"
    
    # Save and submit
    payment.insert(ignore_permissions=True)
    payment.submit()
    
    # Refresh member's payment history
    member_doc.load_payment_history()
    member_doc.save(ignore_permissions=True)
    
    return payment.name

@frappe.whitelist()
def get_linked_donations(member):
    """
    Find linked donor record for a member to view donations
    """
    if not member:
        return {"success": False, "message": "No member specified"}
        
    # First try to find a donor with the same email as the member
    member_doc = frappe.get_doc("Member", member)
    if member_doc.email:
        donors = frappe.get_all(
            "Donor",
            filters={"donor_email": member_doc.email},
            fields=["name"]
        )
        
        if donors:
            return {"success": True, "donor": donors[0].name}
            
    # Then try to find by name
    if member_doc.full_name:
        donors = frappe.get_all(
            "Donor",
            filters={"donor_name": ["like", f"%{member_doc.full_name}%"]},
            fields=["name"]
        )
        
        if donors:
            return {"success": True, "donor": donors[0].name}
    
    # No donor found
    return {"success": False, "message": "No donor record found for this member"}

@frappe.whitelist()
def create_donor_from_member(member):
    """
    Create a donor record from a member for tracking donations
    """
    if not member:
        frappe.throw(_("No member specified"))
        
    member_doc = frappe.get_doc("Member", member)
    
    # Check if donor with same email already exists
    if member_doc.email:
        existing_donor = frappe.db.exists("Donor", {"donor_email": member_doc.email})
        if existing_donor:
            return existing_donor
    
    # Create new donor
    donor = frappe.new_doc("Donor")
    donor.donor_name = member_doc.full_name or member_doc.name
    donor.donor_type = "Individual"
    donor.donor_email = member_doc.email
    donor.contact_person = member_doc.full_name or member_doc.name
    donor.phone = member_doc.mobile_no or member_doc.phone
    
    # Set default donor category - get from settings if possible
    donor.donor_category = "Regular Donor"  # Default
    
    # Get preferred communication method based on member data
    if member_doc.email:
        donor.preferred_communication_method = "Email"
    elif member_doc.mobile_no:
        donor.preferred_communication_method = "Phone"
    
    # Save with ignore permissions to ensure it works for all users
    donor.insert(ignore_permissions=True)
    
    frappe.msgprint(_("Donor record {0} created from member").format(donor.name))
    return donor.name

@frappe.whitelist()
def create_sepa_mandate_from_bank_details(member, iban, bic=None, account_holder_name=None, mandate_type="RCUR", sign_date=None, used_for_memberships=1, used_for_donations=0):
    """
    Create a new SEPA mandate based on bank details already entered
    """
    if not member or not iban:
        frappe.throw(_("Member and IBAN are required"))
    
    if not sign_date:
        sign_date = frappe.utils.today()
    
    # Get member details if not provided
    member_doc = frappe.get_doc("Member", member)
    if not account_holder_name:
        account_holder_name = member_doc.full_name
    
    # Create mandate ID with timestamp to ensure uniqueness
    timestamp = frappe.utils.now().replace(' ', '').replace('-', '').replace(':', '')[:14]
    mandate_id = f"M-{member_doc.member_id}-{timestamp}"
    
    # Create new mandate
    mandate = frappe.new_doc("SEPA Mandate")
    mandate.mandate_id = mandate_id
    mandate.member = member
    mandate.member_name = member_doc.full_name
    mandate.account_holder_name = account_holder_name
    mandate.iban = iban
    if bic:
        mandate.bic = bic
    mandate.sign_date = sign_date
    mandate.mandate_type = mandate_type
    
    # Set usage flags
    mandate.used_for_memberships = 1 if used_for_memberships else 0
    mandate.used_for_donations = 1 if used_for_donations else 0
    
    # Set status to active
    mandate.status = "Active"
    mandate.is_active = 1
    
    mandate.insert(ignore_permissions=True)
    
    # Add to member's mandate links
    member_doc.append("sepa_mandates", {
        "sepa_mandate": mandate.name,
        "is_current": 1
    })
    
    # Save the member document
    member_doc.save(ignore_permissions=True)
    
    return mandate.name

@frappe.whitelist()
def get_member_form_settings():
    """Get settings for the member form based on system configuration"""
    settings = {
        "show_chapter_field": is_chapter_management_enabled(),
        "chapter_field_label": _("Chapter") if is_chapter_management_enabled() else ""
    }
    
    return settings

@frappe.whitelist()
def find_chapter_by_postal_code(postal_code):
    """Find chapters matching a postal code"""
    if not is_chapter_management_enabled():
        return {"success": False, "message": "Chapter management is disabled"}
        
    if not postal_code:
        return {"success": False, "message": "Postal code is required"}
    
    # Get all published chapters
    chapters = frappe.get_all(
        "Chapter",
        filters={"published": 1},
        fields=["name", "region", "postal_codes"]
    )
    
    matching_chapters = []
    
    for chapter in chapters:
        if not chapter.get("postal_codes"):
            continue
            
        # Create chapter object to use the matching method
        chapter_doc = frappe.get_doc("Chapter", chapter.name)
        if chapter_doc.matches_postal_code(postal_code):
            matching_chapters.append({
                "name": chapter.name,
                "region": chapter.region
            })
    
    return {
        "success": True,
        "matching_chapters": matching_chapters
    }

@frappe.whitelist()
def check_and_handle_sepa_mandate(member, iban):
    """Check if a mandate exists for this IBAN and handle accordingly"""
    member_doc = frappe.get_doc("Member", member)
    
    # Find any mandate with matching IBAN
    matching_mandates = frappe.get_all(
        "SEPA Mandate",
        filters={
            "member": member,
            "iban": iban,
            "status": "Active",
            "is_active": 1
        },
        fields=["name"]
    )
    
    if matching_mandates:
        # Found an active mandate with this IBAN
        mandate_doc = frappe.get_doc("SEPA Mandate", matching_mandates[0].name)
        
        # See if this mandate is already set as current
        is_current = False
        for mandate_link in member_doc.sepa_mandates:
            if mandate_link.sepa_mandate == mandate_doc.name and mandate_link.is_current:
                is_current = True
                break
        
        if not is_current:
            # Set this mandate as current
            for mandate_link in member_doc.sepa_mandates:
                if mandate_link.sepa_mandate == mandate_doc.name:
                    mandate_link.is_current = 1
                else:
                    mandate_link.is_current = 0
            
            member_doc.save(ignore_permissions=True)
            return {"action": "use_existing", "mandate": mandate_doc.name}
        else:
            # Already set as current
            return {"action": "none_needed"}
    else:
        # No matching mandate, need to create a new one
        return {"action": "create_new"}

@frappe.whitelist()
def need_new_mandate(member, iban):
    """Check if we need to create a new mandate for this IBAN"""
    # Find any mandate with matching IBAN
    matching_mandates = frappe.get_all(
        "SEPA Mandate",
        filters={
            "member": member,
            "iban": iban,
            "status": "Active",
            "is_active": 1
        },
        fields=["name"]
    )
    
    # If no matching mandates, we need a new one
    return {"need_new": not bool(matching_mandates)}

@frappe.whitelist()
def create_and_link_mandate(member, iban, bic=None, account_holder_name=None, 
                           mandate_type="RCUR", sign_date=None, 
                           used_for_memberships=1, used_for_donations=0):
    """Create a new mandate and link it to the member in one atomic operation"""
    if not member or not iban:
        frappe.throw(_("Member and IBAN are required"))
    
    if not sign_date:
        sign_date = frappe.utils.today()
    
    # Get member details if not provided
    member_doc = frappe.get_doc("Member", member)
    if not account_holder_name:
        account_holder_name = member_doc.full_name
    
    # Create mandate ID with timestamp to ensure uniqueness
    timestamp = frappe.utils.now().replace(' ', '').replace('-', '').replace(':', '')[:14]
    mandate_id = f"M-{member_doc.member_id}-{timestamp}"
    
    # Create new mandate
    mandate = frappe.new_doc("SEPA Mandate")
    mandate.mandate_id = mandate_id
    mandate.member = member
    mandate.member_name = member_doc.full_name
    mandate.account_holder_name = account_holder_name
    mandate.iban = iban
    if bic:
        mandate.bic = bic
    mandate.sign_date = sign_date
    mandate.mandate_type = mandate_type
    
    # Set usage flags
    mandate.used_for_memberships = 1 if used_for_memberships else 0
    mandate.used_for_donations = 1 if used_for_donations else 0
    
    # Set status to active
    mandate.status = "Active"
    mandate.is_active = 1
    
    mandate.insert(ignore_permissions=True)
    
    # Now link this mandate to the member using a direct database update
    # This avoids issues with document state management
    frappe.db.sql("""
        INSERT INTO `tabMember SEPA Mandate Link`
        (name, parent, parentfield, parenttype, sepa_mandate, is_current, mandate_reference, status, valid_from)
        VALUES (%s, %s, 'sepa_mandates', 'Member', %s, 1, %s, %s, %s)
    """, (frappe.generate_hash(), member, mandate.name, mandate.mandate_id, 'Active', mandate.sign_date))
    
    # Update any existing mandates to not be current
    frappe.db.sql("""
        UPDATE `tabMember SEPA Mandate Link`
        SET is_current = 0
        WHERE parent = %s AND sepa_mandate != %s
    """, (member, mandate.name))
    
    # Commit the transaction to ensure all changes are saved
    frappe.db.commit()
    
    return mandate.name
