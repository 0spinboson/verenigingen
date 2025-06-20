import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today, add_days, date_diff, now
import random

from verenigingen.verenigingen.doctype.member.member_id_manager import (
    generate_member_id, 
    validate_member_id_change, 
    MemberIDManager
)
from verenigingen.verenigingen.doctype.member.mixins.payment_mixin import PaymentMixin
from verenigingen.verenigingen.doctype.member.mixins.sepa_mixin import SEPAMandateMixin
from verenigingen.verenigingen.doctype.member.mixins.chapter_mixin import ChapterMixin
from verenigingen.verenigingen.doctype.member.mixins.termination_mixin import TerminationMixin



class Member(Document, PaymentMixin, SEPAMandateMixin, ChapterMixin, TerminationMixin):
    """
    Member doctype with refactored structure using mixins for better organization
    """
    
    def before_save(self):
        """Execute before saving the document with optimized performance"""
        # Only generate member ID for approved members or non-application members
        if not self.member_id:
            if self.should_have_member_id():
                frappe.logger().info(f"Generating member ID for {self.name} - application_status: {getattr(self, 'application_status', 'None')}, is_application: {self.is_application_member()}")
                self.member_id = self.generate_member_id()
                frappe.logger().info(f"Generated member ID: {self.member_id} for {self.name}")
            elif self.is_application_member() and not self.application_id:
                self.application_id = self.generate_application_id()
        else:
            frappe.logger().debug(f"Member {self.name} already has member_id: {self.member_id}")
        
        # Only update chapter display if chapter-related fields have changed
        if self._should_update_chapter_display():
            self.update_current_chapter_display()
        
        if hasattr(self, 'reset_counter_to') and self.reset_counter_to:
            self.reset_counter_to = None
        
        # Set appropriate defaults for application_status
        self.set_application_status_defaults()
    
    def _should_update_chapter_display(self):
        """Check if chapter display needs updating to avoid unnecessary processing"""
        if self.is_new():
            return True  # Always update for new records
        
        # Check if chapter-related fields have changed
        chapter_related_fields = ['pincode', 'city', 'state']
        for field in chapter_related_fields:
            if hasattr(self, 'has_value_changed') and self.has_value_changed(field):
                return True
        
        # Check if this is being called from chapter assignment process
        if hasattr(self, '_chapter_assignment_in_progress'):
            return True
            
        return False
    
    def validate_fee_override_permissions(self):
        """Validate that only authorized users can set fee overrides"""
        # Skip validation for new documents or if no override is set
        if self.is_new() or not self.membership_fee_override:
            return
        
        # Check if fee override value has changed
        if self.name:
            old_amount = frappe.db.get_value("Member", self.name, "membership_fee_override")
            if old_amount == self.membership_fee_override:
                return  # No change, no validation needed
        
        # Check user permissions for fee override
        user_roles = frappe.get_roles(frappe.session.user)
        authorized_roles = ["System Manager", "Membership Manager", "Verenigingen Administrator"]
        
        if not any(role in user_roles for role in authorized_roles):
            frappe.throw(
                _("You do not have permission to override membership fees. Only administrators can modify membership fees."),
                frappe.PermissionError
            )
        
        # Log the fee override action for audit purposes
        frappe.logger().info(
            f"Fee override set by {frappe.session.user} for member {self.name}: "
            f"Amount: {self.membership_fee_override}, Reason: {self.fee_override_reason}"
        )

    def before_insert(self):
        """Execute before inserting new document"""
        # Member ID generation is now handled in before_save based on application status
        pass
    
    def after_save(self):
        """Execute after saving the document"""
        # Create user account for manually created members (non-application members)
        # Application members get user accounts created during the approval process
        if not self.is_application_member() and not self.user and self.email:
            # Only create user account if member doesn't have one and has an email
            self.create_user_account_if_needed()
    
    def create_user_account_if_needed(self):
        """Create user account for member if conditions are met"""
        try:
            # Don't create user for application members (handled in approval process)
            if self.is_application_member():
                return
            
            # Don't create if user already exists
            if self.user:
                return
            
            # Must have email to create user
            if not self.email:
                return
            
            # Only create for active members
            if getattr(self, 'status', '') not in ['Active', '']:
                return
            
            # Create user account
            result = create_member_user_account(self.name, send_welcome_email=False)
            
            if result.get("success"):
                frappe.logger().info(f"Auto-created user account for manually created member {self.name}")
            else:
                frappe.logger().warning(f"Could not auto-create user account for member {self.name}: {result.get('error', 'Unknown error')}")
        
        except Exception as e:
            frappe.log_error(f"Error in create_user_account_if_needed for member {self.name}: {str(e)}")
            # Don't raise exception to avoid blocking member save
    
    def onload(self):
        """Execute when document is loaded"""
        # Update chapter display when form loads
        if not self.get("__islocal"):
            self.update_current_chapter_display()

    def is_application_member(self):
        """Check if this member was created through the application process"""
        return bool(getattr(self, 'application_id', None))
    
    def should_have_member_id(self):
        """Check if this member should have a member ID assigned"""
        # Non-application members should get member ID immediately
        if not self.is_application_member():
            return True
        
        # Application members only get member ID when approved
        return getattr(self, 'application_status', '') == 'Approved'
    
    def generate_application_id(self):
        """Generate a unique applicant ID for applications"""
        if frappe.session.user == "Guest":
            return None
        
        try:
            settings = frappe.get_single("Verenigingen Settings")
            
            # Check if the field exists
            if not hasattr(settings, 'last_applicant_id'):
                # Initialize applicant ID starting from 1000
                start_id = getattr(settings, 'applicant_id_start', 1000)
                settings.last_applicant_id = start_id - 1
                settings.save()

            new_id = int(getattr(settings, 'last_applicant_id', 999)) + 1
            settings.last_applicant_id = new_id
            settings.save()

            return f"APP-{new_id:05d}"  # Format: APP-01000, APP-01001, etc.
        except Exception as e:
            # Fallback to timestamp-based ID
            import time
            return f"APP-{str(int(time.time() * 1000))[-8:]}"

    def generate_member_id(self):
        """Generate a unique member ID"""
        if frappe.session.user == "Guest":
            return None
        
        try:
            settings = frappe.get_single("Verenigingen Settings")
            
            # Check if the field exists
            if not hasattr(settings, 'last_member_id'):
                # Use a simple timestamp-based ID if settings field doesn't exist
                import time
                return str(int(time.time() * 1000))[-8:]  # Last 8 digits of timestamp
            
            if not settings.last_member_id:
                start_id = getattr(settings, 'member_id_start', 10000)
                settings.last_member_id = start_id - 1

            new_id = int(settings.last_member_id) + 1

            settings.last_member_id = new_id
            settings.save()

            return str(new_id)
        except Exception as e:
            # Fallback to simple ID generation
            import time
            return str(int(time.time() * 1000))[-8:]
    
    @frappe.whitelist()
    def ensure_member_id(self):
        """Ensure this member has a member ID if they should have one"""
        if not self.member_id and self.should_have_member_id():
            self.member_id = self.generate_member_id()
            self.save()
            return {"success": True, "message": _("Member ID assigned successfully")}
        return {"success": False, "message": _("Member already has an ID or doesn't qualify for one")}
    
    @frappe.whitelist()
    def force_assign_member_id(self):
        """Force assign a member ID regardless of normal rules (admin only)"""
        # Check if user has permission
        if not frappe.has_permission("Member", "write") or "System Manager" not in frappe.get_roles():
            frappe.throw(_("Only System Managers can force assign member IDs"))
        
        if self.member_id:
            return {"success": False, "message": _("Member already has a member ID: {0}").format(self.member_id)}
        
        self.member_id = self.generate_member_id()
        self.save()
        return {"success": True, "message": _("Member ID force assigned successfully: {0}").format(self.member_id)}
            
    def approve_application(self):
        """Approve this application and assign member ID"""
        if not self.is_application_member():
            frappe.throw(_("This is not an application member"))
        
        if self.application_status == 'Approved':
            frappe.throw(_("Application is already approved"))
        
        # Assign member ID
        if not self.member_id:
            self.member_id = self.generate_member_id()
        
        # Update status
        self.application_status = 'Approved'
        self.status = 'Active'
        self.reviewed_by = frappe.session.user
        self.review_date = now_datetime()
        
        # Save the member
        self.save()
        
        # Create membership - this should trigger the subscription logic
        return self.create_membership_on_approval()
    
    def create_membership_on_approval(self):
        """Create membership record when application is approved"""
        try:
            # Get membership type
            if not self.selected_membership_type:
                frappe.throw(_("No membership type selected for this application"))
            
            membership_type = frappe.get_doc("Membership Type", self.selected_membership_type)
            
            # Create membership record
            membership = frappe.get_doc({
                "doctype": "Membership",
                "member": self.name,
                "membership_type": self.selected_membership_type,
                "start_date": today(),
                "status": "Pending",  # Will become Active after payment
                "auto_renew": 1
            })
            membership.insert()
            
            # Generate invoice with member's custom fee if applicable
            from verenigingen.utils.application_payments import create_membership_invoice
            current_fee = self.get_current_membership_fee()
            invoice = create_membership_invoice(self, membership, membership_type, current_fee["amount"])
            
            # Update member with invoice reference
            self.application_invoice = invoice.name
            self.application_payment_status = "Pending"
            self.save()
            
            return membership
            
        except Exception as e:
            frappe.log_error(f"Error creating membership on approval: {str(e)}")
            frappe.throw(_("Error creating membership: {0}").format(str(e)))
    
    def validate(self):
        """Validate document data"""
        self.validate_name()
        self.update_full_name()
        self.update_membership_status()
        self.calculate_age()
        self.calculate_cumulative_membership_duration()
        self.validate_payment_method()
        self.set_payment_reference()
        self.validate_bank_details()
        self.sync_payment_amount()
        self.validate_member_id_change()
        self.handle_fee_override_changes()
        self.sync_status_fields()
        
    
    def set_application_status_defaults(self):
        """Set appropriate defaults for application_status based on member type"""
        # Check if application_status is not set
        if not hasattr(self, 'application_status') or not self.application_status:
            # Check if this member was created through application process
            is_application_member = bool(getattr(self, 'application_id', None))
            
            if is_application_member:
                # Application members start as Pending
                self.application_status = "Pending"
            else:
                # Backend-created members are considered approved
                self.application_status = "Approved"
    
    def sync_status_fields(self):
        """Ensure status and application_status fields are synchronized"""
        # Check if this member was created through application process
        is_application_member = bool(getattr(self, 'application_id', None))
        
        if is_application_member:
            # Handle application-created members
            if hasattr(self, 'application_status') and self.application_status:
                if self.application_status == "Approved" and self.status != "Active":
                    self.status = "Active"
                    # Set member_since date when application becomes approved
                    if not self.member_since:
                        self.member_since = today()
                elif self.application_status == "Rejected" and self.status != "Rejected":
                    self.status = "Rejected"
                elif self.application_status == "Pending" and self.status not in ["Pending", "Active"]:
                    # For pending applications, default to Pending unless already Active
                    if self.status != "Active":
                        self.status = "Pending"
        else:
            # Handle backend-created members (no application process)
            if not hasattr(self, 'application_status') or not self.application_status:
                # Set application_status to Approved for backend-created members
                self.application_status = "Approved"
            
            # Ensure backend-created members are Active by default unless explicitly set
            if not self.status or self.status == "Pending":
                self.status = "Active"

    def after_insert(self):
        """Execute after document is inserted"""
        if not self.customer and self.email:
            self.create_customer()

    def calculate_age(self):
        """Calculate age based on birth_date field"""
        try:
            if self.birth_date:
                from datetime import datetime, date
                today_date = date.today()
                if isinstance(self.birth_date, str):
                    born = datetime.strptime(self.birth_date, '%Y-%m-%d').date()
                else:
                    born = self.birth_date
                age = today_date.year - born.year - ((today_date.month, today_date.day) < (born.month, born.day))
                self.age = age
            else:
                self.age = None
        except Exception as e:
            frappe.log_error(f"Error calculating age: {str(e)}", "Member Error")

    def calculate_cumulative_membership_duration(self):
        """Calculate the human-readable duration from total_membership_days field"""
        try:
            total_days = getattr(self, 'total_membership_days', 0) or 0
            
            if total_days == 0:
                self.cumulative_membership_duration = "0 years, 0 months"
                return
            
            # Convert total days to human-readable format
            years = total_days // 365
            remaining_days = total_days % 365
            months = remaining_days // 30
            remaining_days = remaining_days % 30
            
            # Build duration string
            duration_parts = []
            if years > 0:
                duration_parts.append(f"{years} year{'s' if years != 1 else ''}")
            if months > 0:
                duration_parts.append(f"{months} month{'s' if months != 1 else ''}")
            if remaining_days > 0 and years == 0:  # Only show days if less than a year
                duration_parts.append(f"{remaining_days} day{'s' if remaining_days != 1 else ''}")
            
            if duration_parts:
                self.cumulative_membership_duration = ", ".join(duration_parts)
            else:
                self.cumulative_membership_duration = "Less than 1 day"
                
        except Exception as e:
            frappe.log_error(f"Error calculating cumulative membership duration: {str(e)}", "Member Error")
            self.cumulative_membership_duration = "Error calculating duration"

    def calculate_total_membership_days(self):
        """Calculate total membership days from all active membership periods"""
        try:
            if not self.name or not frappe.db.exists("Member", self.name):
                # For new records, can't calculate duration yet
                return 0
            
            # Get all memberships for this member, ordered by start date
            memberships = frappe.get_all(
                "Membership",
                filters={"member": self.name, "docstatus": 1},
                fields=["name", "start_date", "renewal_date", "status", "cancellation_date"],
                order_by="start_date asc"
            )
            
            if not memberships:
                return 0
            
            total_days = 0
            today_date = getdate(today())
            
            for membership in memberships:
                start_date = getdate(membership.start_date)
                
                # Determine end date for this membership period
                if membership.status in ["Cancelled", "Expired"]:
                    # Use cancellation date if available, otherwise renewal date
                    end_date = getdate(membership.cancellation_date) if membership.cancellation_date else getdate(membership.renewal_date)
                elif membership.status == "Active":
                    # For active memberships, use today or renewal date (whichever is earlier)
                    renewal_date = getdate(membership.renewal_date) if membership.renewal_date else today_date
                    end_date = min(today_date, renewal_date)
                else:
                    # For other statuses, use renewal date if available
                    end_date = getdate(membership.renewal_date) if membership.renewal_date else start_date
                
                # Calculate days for this membership period
                if end_date >= start_date:
                    period_days = date_diff(end_date, start_date) + 1  # +1 to include both start and end dates
                    total_days += period_days
            
            return total_days
                    
        except Exception as e:
            frappe.log_error(f"Error calculating total membership days: {str(e)}", "Member Error")
            return 0

    @frappe.whitelist()
    def update_membership_duration(self):
        """Update the total membership days and human-readable duration"""
        try:
            # Calculate the raw days
            total_days = self.calculate_total_membership_days()
            
            # Update the fields
            self.total_membership_days = total_days
            self.last_duration_update = now()
            
            # Calculate human-readable format
            self.calculate_cumulative_membership_duration()
            
            # Save the record
            self.save(ignore_permissions=True)
            
            return {
                "success": True,
                "total_days": total_days,
                "duration": self.cumulative_membership_duration,
                "updated": self.last_duration_update
            }
            
        except Exception as e:
            frappe.log_error(f"Error updating membership duration for {self.name}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def generate_application_id(self):
        """Generate unique application ID"""
        year = frappe.utils.today()[:4]
        random_part = str(random.randint(1000, 9999))
        app_id = f"APP-{year}-{random_part}"
        
        while frappe.db.exists("Member", {"application_id": app_id}):
            random_part = str(random.randint(1000, 9999))
            app_id = f"APP-{year}-{random_part}"
        
        return app_id

    def validate_name(self):
        """Validate that name fields don't contain special characters"""
        for field in ['first_name', 'middle_name', 'last_name']:
            if not hasattr(self, field) or not getattr(self, field):
                continue
            if not getattr(self, field).isalnum() and not all(c.isalnum() or c.isspace() for c in getattr(self, field)):
                frappe.throw(_("{0} name should not contain special characters")
                    .format(field.replace('_', ' ').title()))
                    
    def update_full_name(self):
        """Update the full name based on first names, name particles (tussenvoegsels), and last name"""
        # Build full name with proper handling of name particles
        name_parts = []
        
        if self.first_name:
            name_parts.append(self.first_name.strip())
        
        # Handle name particles (tussenvoegsels) - these should be lowercase when in the middle
        if self.middle_name:
            particles = self.middle_name.strip()
            # Ensure particles are lowercase when between first and last name
            if particles:
                name_parts.append(particles.lower())
        
        if self.last_name:
            name_parts.append(self.last_name.strip())
        
        full_name = " ".join(name_parts)
        if self.full_name != full_name:
            self.full_name = full_name
            
    def update_membership_status(self):
        """Update the membership status section"""
        if not self.name or not frappe.db.exists("Member", self.name):
            return
            
        active_membership = self.get_active_membership()
        
        if active_membership:
            self.current_membership_details = active_membership.name
            
            if hasattr(active_membership, 'renewal_date') and active_membership.renewal_date:
                days_left = date_diff(active_membership.renewal_date, getdate(today()))
                
                time_remaining_text = ""
                if days_left < 0:
                    time_remaining_text = _("Expired")
                elif days_left == 0:
                    time_remaining_text = _("Expires today")
                else:
                    if days_left < 30:
                        time_remaining_text = _("{0} days").format(days_left)
                    elif days_left < 365:
                        months = int(days_left / 30)
                        time_remaining_text = _("{0} months").format(months)
                    else:
                        years = round(days_left / 365, 1)
                        time_remaining_text = _("{0} years").format(years)
                        
                if hasattr(self, 'time_remaining'):
                    self.time_remaining = time_remaining_text
                elif hasattr(self, 'notes'):
                    if not self.notes:
                        self.notes = f"<p>Time remaining: {time_remaining_text}</p>"
            
    def get_active_membership(self):
        """Get currently active membership for this member"""
        memberships = frappe.get_all(
            "Membership",
            filters={
                "member": self.name,
                "status": "Active",
                "docstatus": 1
            },
            fields=["name", "membership_type", "start_date", "renewal_date", "status"],
            order_by="start_date desc"
        )
        
        if memberships:
            return frappe.get_doc("Membership", memberships[0].name)
            
        return None
    
    def validate_member_id_change(self):
        """Validate member ID changes using the ID manager"""
        validate_member_id_change(self)
    
    def on_trash(self):
        """Check constraints before deletion"""
        active_memberships = frappe.get_all("Membership", 
            filters={"member": self.name, "docstatus": 1, "status": ["!=", "Cancelled"]})
        
        if active_memberships:
            frappe.throw(_("Cannot delete member with active memberships. Please cancel all memberships first."))
            
    @frappe.whitelist()
    def create_customer(self):
        """Create a customer for this member in ERPNext"""
        if self.customer:
            frappe.msgprint(_("Customer {0} already exists for this member").format(self.customer))
            return self.customer
    
        if self.full_name:
            similar_name_customers = frappe.get_all(
                "Customer",
                filters=[
                    ["customer_name", "like", f"%{self.full_name}%"]
                ],
                fields=["name", "customer_name", "email_id", "mobile_no"]
            )
    
            exact_name_match = next((c for c in similar_name_customers if c.customer_name.lower() == self.full_name.lower()), None)
            if exact_name_match:
                customer_info = f"Name: {exact_name_match.name}, Email: {exact_name_match.email_id or 'N/A'}"
                frappe.msgprint(
                    _("Found existing customer with same name: {0}").format(customer_info) +
                    _("\nCreating a new customer for this member. If you want to link to the existing customer instead, please do so manually.")
                )
    
            elif similar_name_customers:
                customer_list = "\n".join([f"- {c.customer_name} ({c.name})" for c in similar_name_customers[:5]])
                frappe.msgprint(
                    _("Found similar customer names. Please review:") + 
                    f"\n{customer_list}" +
                    (_("\n(Showing first 5 of {0} matches)").format(len(similar_name_customers)) if len(similar_name_customers) > 5 else "") +
                    _("\nCreating a new customer for this member.")
                )
        
        customer = frappe.new_doc("Customer")
        customer.customer_name = self.full_name
        customer.customer_type = "Individual"

        if self.email:
            customer.email_id = self.email
        if hasattr(self, 'contact_number') and self.contact_number:
            customer.mobile_no = self.contact_number
        elif hasattr(self, 'mobile_no') and self.mobile_no:
            customer.mobile_no = self.mobile_no
        if hasattr(self, 'phone') and self.phone:
            customer.phone = self.phone

        customer.flags.ignore_mandatory = True
        customer.insert(ignore_permissions=True)

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
            
        if frappe.db.exists("User", self.email):
            user = frappe.get_doc("User", self.email)
            self.user = user.name
            self.save()
            frappe.msgprint(_("Linked to existing user {0}").format(user.name))
            return user.name
            
        user = frappe.new_doc("User")
        user.email = self.email
        user.first_name = self.first_name
        user.last_name = self.last_name
        user.send_welcome_email = 1
        user.user_type = "System User"
        
        member_role = "Assocation Member"
        verenigingen_member_role = "Verenigingen Member"
    
        if frappe.db.exists("Role", member_role):
            user.append("roles", {"role": member_role})
        elif frappe.db.exists("Role", verenigingen_member_role):
            user.append("roles", {"role": verenigingen_member_role})
        else:
            frappe.msgprint(_("Warning: Could not find Member role to assign to user. Creating user without roles."))
        
        user.flags.ignore_permissions = True
        user.insert(ignore_permissions=True)
        
        # Set allowed modules for member users
        set_member_user_modules(user.name)
        
        self.user = user.name
        self.save(ignore_permissions=True)
        
        frappe.msgprint(_("User {0} created successfully").format(user.name))
        return user.name
    
    @frappe.whitelist()
    def get_active_sepa_mandate(self):
        """Get the active SEPA mandate for this member - exposed for JavaScript calls"""
        return self.get_default_sepa_mandate()
    
    @frappe.whitelist() 
    def get_linked_donations(self):
        """Get linked donations for this member"""
        from verenigingen.verenigingen.doctype.member.member_utils import get_linked_donations
        return get_linked_donations(self.name)
    
    def handle_fee_override_changes(self):
        """Handle changes to membership fee override using amendment system with better atomicity"""
        # Check permissions for fee override changes
        self.validate_fee_override_permissions()
        
        # Skip fee override change tracking for new member applications
        # Applications should set initial fee amounts without triggering change tracking
        if not self.name or self.is_new():
            # For new documents, validate and set audit fields but no change tracking
            if self.membership_fee_override:
                if self.membership_fee_override <= 0:
                    frappe.throw(_("Membership fee override must be greater than 0"))
                if not self.fee_override_reason:
                    frappe.throw(_("Please provide a reason for the fee override"))
                    
                # Set audit fields for new members (but no change tracking)
                if not self.fee_override_date:
                    self.fee_override_date = today()
                if not self.fee_override_by:
                    self.fee_override_by = frappe.session.user
            return
        
        # Get current and old values for existing documents with better error handling
        new_amount = self.membership_fee_override
        old_amount = None
        
        try:
            # Use database lock to prevent concurrent modifications
            with frappe.db.transaction():
                # Get current value from database with row lock
                db_result = frappe.db.sql("""
                    SELECT membership_fee_override 
                    FROM `tabMember` 
                    WHERE name = %s 
                    FOR UPDATE
                """, (self.name,), as_dict=True)
                
                if db_result:
                    old_amount = db_result[0].membership_fee_override
                
                # Check if values are actually different
                if old_amount == new_amount:
                    return  # No change detected
                
                # If we reach here, there's an actual change to process
                frappe.logger().info(f"Processing fee override change for member {self.name}: {old_amount} -> {new_amount}")
                
                # Set audit fields when adding or changing override
                if new_amount and not old_amount:
                    self.fee_override_date = today()
                    self.fee_override_by = frappe.session.user
                    
                # Validate fee override
                if new_amount:
                    if new_amount <= 0:
                        frappe.throw(_("Membership fee override must be greater than 0"))
                    if not self.fee_override_reason:
                        frappe.throw(_("Please provide a reason for the fee override"))
                
                # Store change data for deferred processing to avoid save recursion
                self._pending_fee_change = {
                    "old_amount": old_amount,
                    "new_amount": new_amount,
                    "reason": self.fee_override_reason or "No reason provided",
                    "change_date": now(),
                    "changed_by": frappe.session.user
                }
                
                frappe.logger().info(f"Queued fee override change for member {self.name}")
                
        except Exception as e:
            frappe.logger().error(f"Error processing fee override change for member {self.name}: {str(e)}")
            # Don't fail the save operation, just log the error
            return
    
    
    def record_fee_change(self, change_data):
        """Record fee change in history"""
        self.append("fee_change_history", {
            "change_date": change_data["change_date"],
            "old_amount": change_data["old_amount"],
            "new_amount": change_data["new_amount"],
            "reason": change_data["reason"],
            "changed_by": change_data["changed_by"],
            "subscription_action": change_data.get("subscription_action", "Pending subscription update")
        })
        # Note: Don't save here to avoid recursive save during validation
    
    @frappe.whitelist()
    def get_current_membership_fee(self):
        """Get current effective membership fee for this member"""
        if self.membership_fee_override:
            return {
                "amount": self.membership_fee_override,
                "source": "custom_override",
                "reason": self.fee_override_reason
            }
        
        # Get from active membership
        active_membership = self.get_active_membership()
        if active_membership and active_membership.membership_type:
            membership_type = frappe.get_doc("Membership Type", active_membership.membership_type)
            return {
                "amount": membership_type.amount,
                "source": "membership_type",
                "membership_type": membership_type.membership_type_name
            }
        
        return {"amount": 0, "source": "none"}
    
    @frappe.whitelist()
    def get_display_membership_fee(self):
        """Get membership fee for display with amendment status"""
        current_fee = self.get_current_membership_fee()
        
        # Check for pending amendments
        pending_amendments = frappe.get_all(
            "Contribution Amendment Request",
            filters={
                "member": self.name,
                "status": ["in", ["Draft", "Pending Approval", "Approved"]],
                "amendment_type": "Fee Change"
            },
            fields=["name", "status", "requested_amount", "effective_date", "reason"],
            order_by="creation desc",
            limit=1
        )
        
        if pending_amendments:
            amendment = pending_amendments[0]
            return {
                "current_amount": current_fee["amount"],
                "display_amount": amendment["requested_amount"],
                "status": f"Pending - Effective {frappe.format_date(amendment['effective_date']) if amendment['effective_date'] else 'TBD'}",
                "amendment_status": amendment["status"],
                "amendment_id": amendment["name"],
                "reason": amendment["reason"],
                "source": "amendment_pending"
            }
        
        # No pending amendments, return current fee
        return {
            "current_amount": current_fee["amount"],
            "display_amount": current_fee["amount"],
            "status": "Current",
            "source": current_fee["source"],
            "reason": current_fee.get("reason")
        }
    
    @frappe.whitelist()
    def get_current_subscription_details(self):
        """Get current active subscription details including billing interval"""
        if not self.customer:
            return {"error": "No customer linked to this member"}
        
        try:
            # Get active subscriptions for this customer
            active_subscriptions = frappe.get_all(
                "Subscription",
                filters={
                    "party": self.customer,
                    "party_type": "Customer",
                    "status": "Active",
                    "docstatus": 1
                },
                fields=["name", "start_date", "end_date", "status"]
            )
            
            if not active_subscriptions:
                return {
                    "has_subscription": False,
                    "message": "No active subscriptions found"
                }
            
            subscription_details = []
            for sub_data in active_subscriptions:
                try:
                    subscription = frappe.get_doc("Subscription", sub_data.name)
                    
                    # Get subscription plan details
                    plan_details = []
                    total_amount = 0
                    
                    for plan in subscription.plans:
                        plan_doc = frappe.get_doc("Subscription Plan", plan.plan)
                        # Get price from subscription plan, multiply by quantity
                        plan_price = plan_doc.cost * plan.qty
                        plan_details.append({
                            "plan_name": plan_doc.plan_name,
                            "price": plan_price,
                            "quantity": plan.qty,
                            "billing_interval": plan_doc.billing_interval,
                            "billing_interval_count": plan_doc.billing_interval_count,
                            "currency": plan_doc.currency
                        })
                        total_amount += plan_price
                    
                    subscription_details.append({
                        "name": subscription.name,
                        "status": subscription.status,
                        "start_date": subscription.start_date,
                        "end_date": subscription.end_date,
                        "current_invoice_start": subscription.current_invoice_start,
                        "current_invoice_end": subscription.current_invoice_end,
                        "total_amount": total_amount,
                        "plans": plan_details
                    })
                    
                except Exception as e:
                    frappe.log_error(f"Error getting subscription details for {sub_data.name}: {str(e)}")
                    continue
            
            return {
                "has_subscription": True,
                "subscriptions": subscription_details,
                "count": len(subscription_details)
            }
            
        except Exception as e:
            frappe.log_error(f"Error getting subscription details for member {self.name}: {str(e)}")
            return {"error": str(e)}
    
    @frappe.whitelist()
    def refresh_subscription_history(self):
        """Refresh the subscription history table with current data"""
        if not self.customer:
            return {"message": "No customer linked to this member"}
        
        # Clear existing history
        self.subscription_history = []
        
        # Get all subscriptions for this customer
        subscriptions = frappe.get_all(
            "Subscription",
            filters={"party": self.customer, "party_type": "Customer"},
            fields=["name", "status", "start_date", "end_date", "modified"],
            order_by="start_date desc"
        )
        
        for sub_data in subscriptions:
            try:
                subscription = frappe.get_doc("Subscription", sub_data.name)
                
                # Calculate total amount from plans
                total_amount = 0
                plan_details = []
                for plan in subscription.plans:
                    plan_doc = frappe.get_doc("Subscription Plan", plan.plan)
                    amount = plan_doc.cost * plan.qty
                    total_amount += amount
                    plan_details.append(f"{plan_doc.plan_name}: {frappe.format_value(amount, 'Currency')} x {plan.qty}")
                
                # Add to history
                self.append("subscription_history", {
                    "subscription_name": sub_data.name,
                    "status": sub_data.status,
                    "amount": total_amount,
                    "start_date": sub_data.start_date,
                    "end_date": sub_data.end_date,
                    "last_update": sub_data.modified,
                    "plan_details": "; ".join(plan_details),
                    "cancellation_reason": ""  # Will need to check subscription doc for this field
                })
                
            except Exception as e:
                frappe.log_error(f"Error processing subscription {sub_data.name}: {str(e)}")
                continue
        
        self.save(ignore_permissions=True)
        return {"message": f"Refreshed {len(self.subscription_history)} subscription records"}
    
    def update_subscription_history_entry(self, subscription_name, action="updated"):
        """Update or add a specific subscription to the history"""
        if not self.customer:
            return
            
        try:
            subscription = frappe.get_doc("Subscription", subscription_name)
            
            # Calculate total amount from plans
            total_amount = 0
            plan_details = []
            for plan in subscription.plans:
                plan_doc = frappe.get_doc("Subscription Plan", plan.plan)
                amount = plan_doc.cost * plan.qty
                total_amount += amount
                plan_details.append(f"{plan_doc.plan_name}: {frappe.format_value(amount, 'Currency')} x {plan.qty}")
            
            # Find existing entry or create new one
            existing_entry = None
            for entry in self.subscription_history:
                if entry.subscription_name == subscription_name:
                    existing_entry = entry
                    break
            
            if existing_entry:
                # Update existing entry
                existing_entry.status = subscription.status
                existing_entry.amount = total_amount
                existing_entry.end_date = subscription.end_date
                existing_entry.last_update = subscription.modified
                existing_entry.plan_details = "; ".join(plan_details)
                existing_entry.cancellation_reason = ""
            else:
                # Add new entry
                self.append("subscription_history", {
                    "subscription_name": subscription_name,
                    "status": subscription.status,
                    "amount": total_amount,
                    "start_date": subscription.start_date,
                    "end_date": subscription.end_date,
                    "last_update": subscription.modified,
                    "plan_details": "; ".join(plan_details),
                    "cancellation_reason": ""
                })
            
            self.save(ignore_permissions=True)
            
        except Exception as e:
            frappe.log_error(f"Error updating subscription history for {subscription_name}: {str(e)}")
    
    def update_active_subscriptions(self):
        """Update existing subscription plans based on current fee override with better atomicity"""
        if not self.customer:
            return {"message": "No customer linked to member"}
        
        try:
            # Use database transaction for atomicity
            with frappe.db.transaction():
                current_fee = self.get_current_membership_fee()
                
                if current_fee["amount"] <= 0:
                    return {"message": "No fee amount set, skipping subscription update"}
                
                # Find existing active subscriptions with row lock
                active_subscriptions = frappe.db.sql("""
                    SELECT name, status 
                    FROM `tabSubscription` 
                    WHERE party = %s 
                    AND party_type = 'Customer' 
                    AND status = 'Active' 
                    AND docstatus = 1
                    FOR UPDATE
                """, (self.customer,), as_dict=True)
                
                updated_subscriptions = []
                
                # Process each subscription atomically
                for sub_data in active_subscriptions:
                    try:
                        subscription = frappe.get_doc("Subscription", sub_data.name)
                        
                        # Cancel the existing subscription
                        subscription.cancel()
                        frappe.logger().info(f"Cancelled subscription {subscription.name}")
                        
                        # Create a new subscription with the updated fee
                        active_membership = self.get_active_membership()
                        if active_membership:
                            new_subscription = self.get_or_create_subscription_for_membership(
                                active_membership, current_fee["amount"]
                            )
                            if new_subscription:
                                updated_subscriptions.append(new_subscription.name)
                                frappe.logger().info(f"Created new subscription {new_subscription.name} with fee {current_fee['amount']}")
                                
                                # Update subscription history
                                self.update_subscription_history_entry(new_subscription.name, "created")
                        
                    except Exception as e:
                        frappe.logger().error(f"Error replacing subscription {sub_data.name}: {str(e)}")
                        # Continue with other subscriptions
                        continue
                
                # If no active subscriptions exist, create one
                if not active_subscriptions:
                    active_membership = self.get_active_membership()
                    if active_membership:
                        new_subscription = self.get_or_create_subscription_for_membership(
                            active_membership, current_fee["amount"]
                        )
                        
                        if new_subscription:
                            updated_subscriptions.append(new_subscription.name)
                            self.update_subscription_history_entry(new_subscription.name, "created")
                            return {
                                "message": f"Created new subscription {new_subscription.name}",
                                "updated_subscriptions": updated_subscriptions
                            }
                
                # Commit the transaction
                frappe.db.commit()
                
                return {
                    "message": f"Updated {len(updated_subscriptions)} subscription(s)",
                    "updated_subscriptions": updated_subscriptions
                }
                    
        except Exception as e:
            frappe.logger().error(f"Error in update_active_subscriptions for member {self.name}: {str(e)}")
            frappe.db.rollback()
            return {"error": str(e)}
    
    def get_or_create_subscription_for_membership(self, membership, fee_amount):
        """Get or create a subscription for the given membership"""
        if not self.customer:
            return None
            
        try:
            # Get or create subscription plan for this fee amount
            plan = self.get_or_create_subscription_plan(fee_amount)
            if not plan:
                return None
            
            # Create new subscription
            subscription = frappe.get_doc({
                "doctype": "Subscription",
                "party_type": "Customer",
                "party": self.customer,
                "start_date": membership.start_date or today(),
                "end_date": membership.renewal_date,
                "plans": [{
                    "plan": plan.name,
                    "qty": 1
                }]
            })
            
            subscription.insert(ignore_permissions=True)
            subscription.submit()
            
            frappe.log_error(f"Created subscription {subscription.name} for member {self.name}")
            return subscription
            
        except Exception as e:
            frappe.log_error(f"Error creating subscription for member {self.name}: {str(e)}")
            return None
    
    def get_or_create_subscription_plan(self, fee_amount):
        """Get or create a subscription plan for the given fee amount"""
        try:
            # Look for existing plan with this amount
            plan_name = f"Membership Fee - {frappe.format_value(fee_amount, 'Currency')}"
            
            existing_plan = frappe.db.exists("Subscription Plan", {"plan_name": plan_name})
            if existing_plan:
                return frappe.get_doc("Subscription Plan", existing_plan)
            
            # Get or create membership fee item
            item = self.get_or_create_membership_item()
            if not item:
                return None
            
            # Create new subscription plan
            plan = frappe.get_doc({
                "doctype": "Subscription Plan",
                "plan_name": plan_name,
                "item": item.name,
                "price_determination": "Fixed Rate",
                "cost": fee_amount,
                "billing_interval": "Month",
                "enabled": 1
            })
            
            plan.insert(ignore_permissions=True)
            frappe.log_error(f"Created subscription plan {plan.name}")
            return plan
            
        except Exception as e:
            frappe.log_error(f"Error creating subscription plan: {str(e)}")
            return None
    
    def get_or_create_membership_item(self):
        """Get or create the membership fee item"""
        try:
            item_code = "MEMBERSHIP-FEE"
            
            existing_item = frappe.db.exists("Item", item_code)
            if existing_item:
                return frappe.get_doc("Item", existing_item)
            
            # Create membership fee item
            item = frappe.get_doc({
                "doctype": "Item",
                "item_code": item_code,
                "item_name": "Membership Fee",
                "item_group": frappe.db.get_single_value("Item", "item_group") or "Services",
                "is_service_item": 1,
                "maintain_stock": 0,
                "include_item_in_manufacturing": 0,
                "is_purchase_item": 0,
                "is_sales_item": 1
            })
            
            item.insert(ignore_permissions=True)
            frappe.log_error(f"Created membership item {item.name}")
            return item
            
        except Exception as e:
            frappe.log_error(f"Error creating membership item: {str(e)}")
            return None

    @frappe.whitelist()
    def force_update_chapter_display(self):
        """Force update chapter display - useful for fixing display issues"""
        self._chapter_assignment_in_progress = True
        self.update_current_chapter_display()
        self.save(ignore_permissions=True)
        return {
            "success": True,
            "message": "Chapter display updated",
            "current_chapter_display": getattr(self, 'current_chapter_display', 'Not set')
        }

    @frappe.whitelist()
    def debug_chapter_assignment(self):
        """Debug chapter assignment for this member"""
        # Check chapter memberships in Chapter Member table
        chapter_members = frappe.get_all(
            "Chapter Member",
            filters={"member": self.name, "enabled": 1},
            fields=["parent as chapter", "chapter_join_date", "enabled"],
            order_by="chapter_join_date desc"
        )
        
        # Check board memberships
        board_members = frappe.get_all(
            "Chapter Board Member", 
            filters={"member": self.name, "is_active": 1},
            fields=["parent as chapter", "chapter_role", "is_active"]
        )
        
        # Check current chapter display
        current_chapter_display = getattr(self, 'current_chapter_display', 'Not set')
        
        # Get optimized chapters
        try:
            optimized_chapters = self.get_current_chapters_optimized()
        except Exception as e:
            optimized_chapters = f"Error: {str(e)}"
        
        return {
            "member_name": self.full_name,
            "member_id": self.name,
            "chapter_members": chapter_members,
            "board_members": board_members,
            "current_chapter_display": current_chapter_display,
            "optimized_chapters": optimized_chapters,
            "chapter_management_enabled": frappe.db.get_single_value("Verenigingen Settings", "enable_chapter_management")
        }

    def update_current_chapter_display(self):
        """Update the current chapter display field based on Chapter Member relationships with optimized queries"""
        try:
            chapters = self.get_current_chapters_optimized()
            
            if not chapters:
                # Use the custom field until the main field is fixed
                field_name = 'current_chapter_display_temp' if hasattr(self, 'current_chapter_display_temp') else 'current_chapter_display'
                setattr(self, field_name, '<p style="color: #888;"><em>No chapter assignment</em></p>')
                return
            
            # Build HTML using more efficient string operations
            html_items = ['<div class="member-chapters">']
            
            for chapter in chapters:
                chapter_display = chapter['chapter']
                if chapter.get('region'):
                    chapter_display += f" ({chapter['region']})"
                
                status_badges = []
                if chapter.get('is_primary'):
                    status_badges.append('<span class="badge badge-success">Primary</span>')
                if chapter.get('is_board'):
                    status_badges.append('<span class="badge badge-info">Board Member</span>')
                if chapter.get('chapter_join_date'):
                    status_badges.append(f'<span class="badge badge-light">Joined: {chapter["chapter_join_date"]}</span>')
                
                badges_html = ' '.join(status_badges) if status_badges else ''
                
                html_items.append(f'''
                    <div class="chapter-item" style="margin-bottom: 8px; padding: 8px; border-left: 3px solid #007bff; background-color: #f8f9fa;">
                        <strong>{chapter_display}</strong>
                        {f'<br>{badges_html}' if badges_html else ''}
                    </div>
                ''')
            
            html_items.append('</div>')
            
            # Use the custom field until the main field is fixed
            field_name = 'current_chapter_display_temp' if hasattr(self, 'current_chapter_display_temp') else 'current_chapter_display'
            setattr(self, field_name, ''.join(html_items))
            
        except Exception as e:
            frappe.log_error(f"Error updating chapter display: {str(e)}", "Member Chapter Display")
            self.current_chapter_display = '<p style="color: #dc3545;">Error loading chapter information</p>'

    def get_current_chapters_optimized(self):
        """Get current chapter memberships with optimized single query"""
        if not self.name:
            return []
        
        try:
            # Single optimized query to get all chapter information at once
            chapters_data = frappe.db.sql("""
                SELECT 
                    cm.parent as chapter,
                    cm.chapter_join_date,
                    c.region,
                    cbm.volunteer as board_volunteer,
                    cbm.is_active as is_board_member
                FROM `tabChapter Member` cm
                LEFT JOIN `tabChapter` c ON cm.parent = c.name
                LEFT JOIN `tabVolunteer` v ON v.member = %s
                LEFT JOIN `tabChapter Board Member` cbm ON cbm.parent = cm.parent AND cbm.volunteer = v.name AND cbm.is_active = 1
                WHERE cm.member = %s AND cm.enabled = 1
                ORDER BY cm.chapter_join_date DESC
            """, (self.name, self.name), as_dict=True)
            
            chapters = []
            for idx, chapter_data in enumerate(chapters_data):
                chapters.append({
                    "chapter": chapter_data.chapter,
                    "chapter_join_date": chapter_data.chapter_join_date,
                    "region": chapter_data.region,
                    "is_primary": idx == 0,  # First one is primary
                    "is_board": bool(chapter_data.is_board_member)
                })
            
            return chapters
            
        except Exception as e:
            frappe.log_error(f"Error getting current chapters optimized: {str(e)}", "Member Chapter Query")
            # Fallback to original method
            return self.get_current_chapters()
    
    def get_current_chapters(self):
        """Get current chapter memberships from Chapter Member child table (fallback method)"""
        if not self.name:
            return []
        
        try:
            # Get chapters where this member is listed in the Chapter Member child table
            # Use ignore_permissions since this is called within member doc context
            chapter_members = frappe.get_all(
                "Chapter Member",
                filters={
                    "member": self.name,
                    "enabled": 1
                },
                fields=["parent", "chapter_join_date"],
                order_by="chapter_join_date desc",
                ignore_permissions=True
            )
            
            chapters = []
            for cm in chapter_members:
                chapters.append({
                    "chapter": cm.parent,
                    "chapter_join_date": cm.chapter_join_date,
                    "is_primary": len(chapters) == 0,  # First one is primary
                    "is_board": self.is_board_member(cm.parent)
                })
            
            return chapters
            
        except Exception as e:
            frappe.log_error(f"Error getting current chapters: {str(e)}", "Member Chapter Query")
            return []


# Module-level functions for static calls
@frappe.whitelist()
def is_chapter_management_enabled():
    """Check if chapter management is enabled in settings"""
    from verenigingen.verenigingen.doctype.member.member_utils import is_chapter_management_enabled as check_enabled
    return check_enabled()

@frappe.whitelist()
def get_board_memberships(member_name):
    """Get board memberships for a member"""
    from verenigingen.verenigingen.doctype.member.member_utils import get_board_memberships
    return get_board_memberships(member_name)

@frappe.whitelist()
def get_active_sepa_mandate(member, iban=None):
    """Get active SEPA mandate for JavaScript calls"""
    member_doc = frappe.get_doc("Member", member)
    mandate = member_doc.get_default_sepa_mandate()
    return mandate.as_dict() if mandate else None

@frappe.whitelist()
def get_member_current_chapters(member_name):
    """Get current chapters for a member - safe for client calls"""
    if not member_name:
        return []
    
    try:
        # Check if user has permission to access this member
        member_doc = frappe.get_doc("Member", member_name)
        return member_doc.get_current_chapters()
        
    except frappe.PermissionError:
        # If no permission to member, return empty list
        return []
    except Exception as e:
        frappe.log_error(f"Error getting member chapters: {str(e)}", "Member Chapters API")
        return []

@frappe.whitelist()
def get_member_chapter_names(member_name):
    """Get simple list of chapter names for a member"""
    if not member_name:
        return []
    
    try:
        chapters = get_member_current_chapters(member_name)
        return [ch.get("chapter") for ch in chapters if ch.get("chapter")]
        
    except Exception as e:
        frappe.log_error(f"Error getting member chapter names: {str(e)}", "Member Chapters API")
        return []

@frappe.whitelist()
def get_member_chapter_display_html(member_name):
    """Get formatted HTML for member's chapter information"""
    if not member_name:
        return ""
    
    try:
        member_doc = frappe.get_doc("Member", member_name)
        chapters = member_doc.get_current_chapters()
        
        if not chapters:
            return '<p style="color: #888;"><em>No chapter assignment</em></p>'
        
        html_parts = []
        html_parts.append('<div class="member-chapters" style="margin: 10px 0;">')
        
        for chapter in chapters:
            chapter_info = frappe.get_value("Chapter", chapter['chapter'], ['region'], as_dict=True)
            chapter_display = chapter['chapter']
            if chapter_info and chapter_info.region:
                chapter_display += f" ({chapter_info.region})"
            
            status_badges = []
            # Removed the Primary badge as requested
            if chapter.get('is_board'):
                status_badges.append('<span class="badge badge-info" style="margin-right: 5px;">Board Member</span>')
            if chapter.get('chapter_join_date'):
                status_badges.append(f'<span class="badge badge-light" style="margin-right: 5px;">Joined: {chapter["chapter_join_date"]}</span>')
            
            badges_html = ''.join(status_badges)
            
            # Make chapter name clickable to open the chapter
            chapter_link = f'<a href="/app/chapter/{chapter["chapter"]}" target="_blank" style="color: #007bff; text-decoration: none; font-weight: bold;" onmouseover="this.style.textDecoration=\'underline\'" onmouseout="this.style.textDecoration=\'none\'">{chapter_display}</a>'
            
            html_parts.append(f'''
                <div class="chapter-item" style="margin-bottom: 8px; padding: 10px; border-left: 3px solid #007bff; background-color: #f8f9fa; border-radius: 4px;">
                    {chapter_link}
                    {f'<br><div style="margin-top: 5px;">{badges_html}</div>' if badges_html else ''}
                </div>
            ''')
        
        html_parts.append('</div>')
        return ''.join(html_parts)
        
    except Exception as e:
        frappe.log_error(f"Error getting member chapter display: {str(e)}", "Member Chapter Display API")
        return '<p style="color: #dc3545;">Error loading chapter information</p>'

def handle_fee_override_after_save(doc, method=None):
    """Hook function to handle fee override changes after save with improved atomicity"""
    frappe.logger().info(f"handle_fee_override_after_save called for member {doc.name}, method={method}")
    
    # Handle deferred fee changes
    if hasattr(doc, '_pending_fee_change'):
        try:
            frappe.logger().info(f"Processing pending fee change for member {doc.name}")
            
            # Use separate database transaction for fee change processing
            with frappe.db.transaction():
                # Create amendment request
                try:
                    from verenigingen.verenigingen.doctype.contribution_amendment_request.contribution_amendment_request import create_fee_change_amendment
                    
                    amendment = create_fee_change_amendment(
                        member_name=doc.name,
                        new_amount=doc._pending_fee_change["new_amount"],
                        reason=doc._pending_fee_change["reason"]
                    )
                    
                    subscription_action = f"Amendment request created: {amendment.name}"
                    
                except Exception as e:
                    frappe.logger().warning(f"Could not create amendment request: {str(e)}")
                    subscription_action = "Amendment creation failed, direct subscription update"
                
                # Record the change in history (using direct SQL to avoid recursion)
                history_entry = {
                    "change_date": doc._pending_fee_change["change_date"],
                    "old_amount": doc._pending_fee_change["old_amount"],
                    "new_amount": doc._pending_fee_change["new_amount"],
                    "reason": doc._pending_fee_change["reason"],
                    "changed_by": doc._pending_fee_change["changed_by"],
                    "subscription_action": subscription_action
                }
                
                # Get current fee change history
                current_history = frappe.db.get_value("Member", doc.name, "fee_change_history") or "[]"
                history_list = frappe.parse_json(current_history) if current_history != "[]" else []
                history_list.append(history_entry)
                
                # Update history directly in database
                frappe.db.sql("""
                    UPDATE `tabMember` 
                    SET fee_change_history = %s 
                    WHERE name = %s
                """, (frappe.as_json(history_list), doc.name))
                
                # Update subscriptions if needed
                try:
                    # Create a temporary member object to avoid modifying the original
                    temp_member = frappe.get_doc("Member", doc.name)
                    result = temp_member.update_active_subscriptions()
                    frappe.logger().info(f"Subscription update result: {result}")
                except Exception as e:
                    frappe.logger().error(f"Error updating subscriptions: {str(e)}")
                
                # Commit the transaction
                frappe.db.commit()
                
            delattr(doc, '_pending_fee_change')
            frappe.logger().info(f"Successfully processed fee override change for member {doc.name}")
            
        except Exception as e:
            frappe.logger().error(f"Error processing fee override for member {doc.name}: {str(e)}")
            # Clean up the pending change to avoid repeated processing
            if hasattr(doc, '_pending_fee_change'):
                delattr(doc, '_pending_fee_change')
    else:
        frappe.logger().debug(f"No pending fee change found for member {doc.name}")

@frappe.whitelist()
def get_current_subscription_details(member):
    """Get current active subscription details including billing interval for a member"""
    member_doc = frappe.get_doc("Member", member)
    
    if not member_doc.customer:
        return {"error": "No customer linked to this member"}
    
    try:
        # Get active subscriptions for this customer
        active_subscriptions = frappe.get_all(
            "Subscription",
            filters={
                "party": member_doc.customer,
                "party_type": "Customer",
                "status": "Active",
                "docstatus": 1
            },
            fields=["name", "start_date", "end_date", "status"]
        )
        
        if not active_subscriptions:
            return {
                "has_subscription": False,
                "message": "No active subscriptions found"
            }
        
        subscription_details = []
        for sub_data in active_subscriptions:
            try:
                subscription = frappe.get_doc("Subscription", sub_data.name)
                
                # Get subscription plan details
                plan_details = []
                total_amount = 0
                
                for plan in subscription.plans:
                    plan_doc = frappe.get_doc("Subscription Plan", plan.plan)
                    plan_details.append({
                        "plan_name": plan_doc.plan_name,
                        "price": plan_doc.cost,
                        "billing_interval": plan_doc.billing_interval,
                        "billing_interval_count": plan_doc.billing_interval_count,
                        "currency": plan_doc.currency
                    })
                    total_amount += plan_doc.cost
                
                subscription_details.append({
                    "name": subscription.name,
                    "status": subscription.status,
                    "start_date": subscription.start_date,
                    "end_date": subscription.end_date,
                    "current_invoice_start": subscription.current_invoice_start,
                    "current_invoice_end": subscription.current_invoice_end,
                    "total_amount": total_amount,
                    "plans": plan_details
                })
                
            except Exception as e:
                frappe.log_error(f"Error getting subscription details for {sub_data.name}: {str(e)}")
                continue
        
        return {
            "has_subscription": True,
            "subscriptions": subscription_details,
            "count": len(subscription_details)
        }
        
    except Exception as e:
        frappe.log_error(f"Error getting subscription details for member {member}: {str(e)}")
        return {"error": str(e)}

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
def assign_member_id(member_name):
    """
    Manually assign a member ID to a member who doesn't have one yet.
    This can be used for approved applications or existing members without IDs.
    """
    if not frappe.has_permission("Member", "write"):
        frappe.throw(_("Insufficient permissions to assign member ID"))
    
    # Only allow System Manager and Membership Manager roles to manually assign member IDs
    allowed_roles = ["System Manager", "Membership Manager"]
    user_roles = frappe.get_roles(frappe.session.user)
    if not any(role in user_roles for role in allowed_roles):
        frappe.throw(_("Only System Managers and Membership Managers can manually assign member IDs"))
    
    try:
        member = frappe.get_doc("Member", member_name)
        
        # Check if member already has an ID
        if member.member_id:
            return {
                "success": False,
                "message": _("Member already has ID: {0}").format(member.member_id)
            }
        
        # For application members, they should be approved first
        if member.is_application_member() and not member.should_have_member_id():
            return {
                "success": False,
                "message": _("Application member must be approved before assigning member ID. Current status: {0}").format(member.application_status)
            }
        
        # Generate and assign member ID
        from verenigingen.verenigingen.doctype.member.member_id_manager import MemberIDManager
        next_id = MemberIDManager.get_next_member_id()
        member.member_id = str(next_id)
        
        # Save the member
        member.save()
        
        frappe.msgprint(_("Member ID {0} assigned successfully to {1}").format(next_id, member.full_name))
        
        return {
            "success": True,
            "member_id": str(next_id),
            "message": _("Member ID {0} assigned successfully").format(next_id)
        }
        
    except Exception as e:
        frappe.log_error(f"Error assigning member ID to {member_name}: {str(e)}")
        return {
            "success": False,
            "message": _("Error assigning member ID: {0}").format(str(e))
        }

@frappe.whitelist()
def validate_mandate_creation(member, iban, mandate_id):
    """Validate mandate creation parameters and check for existing mandates"""
    try:
        # Check if member exists
        if not frappe.db.exists("Member", member):
            return {"error": _("Member does not exist")}
        
        # Check if mandate ID already exists
        existing_mandate = frappe.db.exists("SEPA Mandate", {"mandate_id": mandate_id})
        if existing_mandate:
            return {"error": _("Mandate ID {0} already exists").format(mandate_id)}
        
        # Check for existing active mandates for this member
        existing_mandates = frappe.get_all(
            "SEPA Mandate",
            filters={
                "member": member,
                "status": "Active",
                "is_active": 1
            },
            fields=["name", "mandate_id", "iban"]
        )
        
        # Check if there's an existing mandate for the same IBAN
        iban_mandate = None
        for mandate in existing_mandates:
            if mandate.iban == iban:
                iban_mandate = mandate.mandate_id
                break
        
        result = {"valid": True}
        
        if iban_mandate:
            result["existing_mandate"] = iban_mandate
            result["warning"] = _("An active mandate already exists for this IBAN: {0}").format(iban_mandate)
        
        return result
        
    except Exception as e:
        frappe.log_error(f"Error validating mandate creation: {str(e)}")
        return {"error": _("Error validating mandate: {0}").format(str(e))}

@frappe.whitelist()
def derive_bic_from_iban(iban):
    """Derive BIC code from IBAN"""
    try:
        from verenigingen.verenigingen.doctype.direct_debit_batch.direct_debit_batch import get_bic_from_iban
        bic = get_bic_from_iban(iban)
        return {"bic": bic} if bic else {"bic": None}
    except Exception as e:
        frappe.log_error(f"Error deriving BIC from IBAN {iban}: {str(e)}")
        return {"bic": None}

@frappe.whitelist()
def deactivate_old_sepa_mandates(member, new_iban):
    """Deactivate old SEPA mandates when IBAN changes"""
    try:
        # Get all active mandates for this member
        active_mandates = frappe.get_all(
            "SEPA Mandate",
            filters={
                "member": member,
                "status": "Active",
                "is_active": 1
            },
            fields=["name", "iban", "mandate_id", "status"]
        )
        
        deactivated_count = 0
        deactivated_mandates = []
        
        for mandate_data in active_mandates:
            # Only deactivate mandates with different IBAN
            if mandate_data.iban != new_iban:
                mandate = frappe.get_doc("SEPA Mandate", mandate_data.name)
                
                # Deactivate the mandate
                mandate.status = "Cancelled"
                mandate.is_active = 0
                mandate.cancellation_date = today()
                mandate.cancellation_reason = f"IBAN changed from {mandate.iban} to {new_iban}"
                
                mandate.save()
                
                deactivated_count += 1
                deactivated_mandates.append({
                    "mandate_id": mandate.mandate_id,
                    "old_iban": mandate.iban
                })
                
                frappe.logger().info(f"Deactivated SEPA mandate {mandate.mandate_id} for member {member} due to IBAN change")
        
        return {
            "success": True,
            "deactivated_count": deactivated_count,
            "deactivated_mandates": deactivated_mandates
        }
        
    except Exception as e:
        frappe.log_error(f"Error deactivating old SEPA mandates for member {member}: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def get_active_sepa_mandate(member, iban=None):
    """Get active SEPA mandate for a member"""
    try:
        filters = {
            "member": member,
            "status": "Active",
            "is_active": 1
        }
        
        if iban:
            filters["iban"] = iban
        
        mandates = frappe.get_all(
            "SEPA Mandate",
            filters=filters,
            fields=["name", "mandate_id", "status", "iban", "account_holder_name"],
            order_by="creation desc",
            limit=1
        )
        
        return mandates[0] if mandates else None
        
    except Exception as e:
        frappe.log_error(f"Error getting active SEPA mandate for member {member}: {str(e)}")
        return None

@frappe.whitelist()
def assign_missing_member_ids():
    """Assign member IDs to all members who should have them but don't"""
    members_without_ids = frappe.get_all(
        "Member",
        filters={
            "member_id": ["is", "not set"]
        },
        fields=["name", "application_status", "application_id", "full_name"]
    )
    
    assigned_count = 0
    for member_data in members_without_ids:
        try:
            member = frappe.get_doc("Member", member_data.name)
            if member.should_have_member_id():
                member.ensure_member_id()
                assigned_count += 1
                frappe.logger().info(f"Assigned member ID {member.member_id} to {member.full_name}")
        except Exception as e:
            frappe.logger().error(f"Failed to assign member ID to {member_data.name}: {str(e)}")
    
    return {
        "total_checked": len(members_without_ids),
        "assigned": assigned_count,
        "message": f"Assigned member IDs to {assigned_count} out of {len(members_without_ids)} members"
    }

@frappe.whitelist()
def create_and_link_mandate_enhanced(member, mandate_id, iban, bic="", account_holder_name="", 
                                   mandate_type="Recurring", sign_date=None, used_for_memberships=1, 
                                   used_for_donations=0, notes="", replace_existing=None):
    """Create a new SEPA mandate and link it to the member"""
    try:
        if not sign_date:
            sign_date = today()
        
        # Convert mandate type to internal format
        type_mapping = {
            "One-off": "OOFF",
            "Recurring": "RCUR"
        }
        internal_type = type_mapping.get(mandate_type, "RCUR")
        
        # Create mandate
        mandate = frappe.new_doc("SEPA Mandate")
        mandate.mandate_id = mandate_id
        mandate.member = member
        mandate.iban = iban
        mandate.bic = bic
        mandate.account_holder_name = account_holder_name
        mandate.mandate_type = internal_type
        mandate.sign_date = sign_date
        mandate.used_for_memberships = int(used_for_memberships)
        mandate.used_for_donations = int(used_for_donations)
        mandate.status = "Active"
        mandate.is_active = 1
        mandate.notes = notes
        
        mandate.insert()
        
        # Update member's SEPA mandates table
        member_doc = frappe.get_doc("Member", member)
        
        # Mark existing mandates as non-current if replacing
        if replace_existing:
            for link in member_doc.sepa_mandates:
                if link.mandate_reference == replace_existing:
                    link.is_current = 0
        
        # Add new mandate link
        member_doc.append("sepa_mandates", {
            "sepa_mandate": mandate.name,
            "mandate_reference": mandate_id,
            "is_current": 1,
            "status": "Active",
            "valid_from": sign_date
        })
        
        member_doc.save()
        
        return {
            "success": True,
            "mandate_name": mandate.name,
            "mandate_id": mandate_id
        }
        
    except Exception as e:
        frappe.log_error(f"Error creating SEPA mandate: {str(e)}")
        frappe.throw(_("Error creating SEPA mandate: {0}").format(str(e)))

@frappe.whitelist()
def debug_member_id_assignment(member_name):
    """Debug why member ID assignment is failing"""
    try:
        member = frappe.get_doc("Member", member_name)
        
        debug_info = {
            "member_name": member.name,
            "current_member_id": getattr(member, 'member_id', None),
            "has_member_id": bool(getattr(member, 'member_id', None)),
            "is_application_member": member.is_application_member(),
            "application_id": getattr(member, 'application_id', None),
            "application_status": getattr(member, 'application_status', None),
            "status": getattr(member, 'status', None),
            "should_have_member_id": member.should_have_member_id(),
            "can_assign_id": not member.member_id and member.should_have_member_id()
        }
        
        return debug_info
        
    except Exception as e:
        return {"error": str(e)}

@frappe.whitelist()
def create_member_user_account(member_name, send_welcome_email=True):
    """Create a user account for a member to access portal pages"""
    try:
        # Get the member document
        member = frappe.get_doc("Member", member_name)
        
        # Check if user already exists
        if member.user:
            return {
                "success": False,
                "message": _("User account already exists for this member"),
                "user": member.user
            }
        
        # Check if a user with this email already exists
        existing_user = frappe.db.get_value("User", {"email": member.email}, "name")
        if existing_user:
            # Link the existing user to the member
            member.user = existing_user
            member.save(ignore_permissions=True)
            
            # Add member roles to existing user
            add_member_roles_to_user(existing_user)
            
            return {
                "success": True,
                "message": _("Linked existing user account to member"),
                "user": existing_user,
                "action": "linked_existing"
            }
        
        # Create new user
        user = frappe.new_doc("User")
        user.email = member.email
        user.first_name = member.first_name or ""
        user.last_name = member.last_name or ""
        user.full_name = member.full_name
        user.send_welcome_email = int(send_welcome_email)
        user.user_type = "System User"
        user.enabled = 1
        
        # Insert the user
        user.insert(ignore_permissions=True)
        
        # Set allowed modules for member users
        set_member_user_modules(user.name)
        
        # Add member-specific roles
        add_member_roles_to_user(user.name)
        
        # Link user to member
        member.user = user.name
        member.save(ignore_permissions=True)
        
        frappe.logger().info(f"Created user account {user.name} for member {member.name}")
        
        return {
            "success": True,
            "message": _("User account created successfully"),
            "user": user.name,
            "action": "created_new"
        }
        
    except Exception as e:
        frappe.log_error(f"Error creating user account for member {member_name}: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def add_member_roles_to_user(user_name):
    """Add appropriate roles for a member user to access portal pages"""
    try:
        # Define the roles that members need for portal access
        member_roles = [
            "Verenigingen Member"  # Primary member role for all member access
        ]
        
        # Check if Verenigingen Member role exists, create if not
        if not frappe.db.exists("Role", "Verenigingen Member"):
            create_verenigingen_member_role()
        
        # Add roles to user
        user = frappe.get_doc("User", user_name)
        
        for role in member_roles:
            if not frappe.db.exists("Role", role):
                frappe.logger().warning(f"Role {role} does not exist, skipping")
                continue
            if not any(r.role == role for r in user.roles):
                user.append("roles", {"role": role})
        
        user.save(ignore_permissions=True)
        frappe.db.commit()  # Force immediate commit
        frappe.logger().info(f"Added member roles to user {user_name}")
        
        # Force reload to ensure consistency
        user.reload()
        return user.name
        
    except Exception as e:
        frappe.log_error(f"Error adding roles to user {user_name}: {str(e)}")
        return None

# Removed create_member_portal_role - consolidated into Verenigingen Member

def create_verenigingen_member_role():
    """Create the Verenigingen Member role for consolidated member access"""
    try:
        role = frappe.new_doc("Role")
        role.role_name = "Verenigingen Member"
        role.desk_access = 0  # Portal users don't need desk access
        role.is_custom = 1  # This is a custom role for the app
        role.insert(ignore_permissions=True)
        
        frappe.logger().info("Created Verenigingen Member role (consolidated from Member Portal User and Member)")
        return role.name
        
    except Exception as e:
        frappe.log_error(f"Error creating Verenigingen Member role: {str(e)}")
        return None

def set_member_user_modules(user_name):
    """Set allowed modules for member users - restrict to relevant modules only"""
    try:
        # Define modules that members should have access to
        allowed_modules = [
            "Verenigingen",  # Main app module
            "Core",  # Essential Frappe core functionality
            "Desk",  # Basic desk access
            "Home",  # Home page access
        ]
        
        user = frappe.get_doc("User", user_name)
        
        # Clear existing module access and set only allowed ones
        user.set("block_modules", [])
        
        # Get all available modules
        all_modules = frappe.get_all("Module Def", fields=["name"])
        
        # Block all modules except the allowed ones
        for module in all_modules:
            if module.name not in allowed_modules:
                user.append("block_modules", {"module": module.name})
        
        user.save(ignore_permissions=True)
        frappe.logger().info(f"Set module restrictions for user {user_name}")
        
    except Exception as e:
        frappe.log_error(f"Error setting module restrictions for user {user_name}: {str(e)}")

@frappe.whitelist()
def check_donor_exists(member_name):
    """Check if a donor record exists for this member"""
    try:
        member = frappe.get_doc("Member", member_name)
        
        # Check if donor record exists with matching email or member link
        existing_donor = frappe.db.get_value(
            "Donor", 
            {"donor_email": member.email}, 
            ["name", "donor_name"]
        )
        
        if existing_donor:
            return {
                "exists": True,
                "donor_name": existing_donor[0],
                "donor_display_name": existing_donor[1]
            }
        
        # Also check if member is linked to any donor record
        linked_donor = frappe.db.get_value("Donor", {"member": member_name}, "name")
        if linked_donor:
            return {
                "exists": True,
                "donor_name": linked_donor
            }
        
        return {
            "exists": False
        }
        
    except Exception as e:
        frappe.log_error(f"Error checking donor existence for member {member_name}: {str(e)}")
        return {
            "exists": False,
            "error": str(e)
        }

@frappe.whitelist()
def create_donor_from_member(member_name):
    """Create a donor record from member information"""
    try:
        member = frappe.get_doc("Member", member_name)
        
        # Check if donor already exists
        existing_check = check_donor_exists(member_name)
        if existing_check.get("exists"):
            return {
                "success": False,
                "message": _("Donor record already exists for this member"),
                "donor_name": existing_check.get("donor_name")
            }
        
        # Create donor record
        donor = frappe.new_doc("Donor")
        
        # Copy basic information from member
        donor.donor_name = member.full_name
        donor.donor_email = member.email
        donor.member = member_name  # Link back to member
        
        # Copy address information if available
        if member.primary_address:
            try:
                address_doc = frappe.get_doc("Address", member.primary_address)
                donor.address_line_1 = address_doc.address_line1
                donor.address_line_2 = address_doc.address_line2 or ""
                donor.city = address_doc.city
                donor.state = address_doc.state
                donor.pincode = address_doc.pincode
                donor.country = address_doc.country
            except Exception as addr_e:
                frappe.logger().warning(f"Could not copy address from member {member_name}: {str(addr_e)}")
        
        # Set other fields
        donor.donor_type = "Individual"
        donor.pan_number = ""  # Can be filled manually later
        
        # Copy phone numbers if available
        if hasattr(member, 'mobile_no') and member.mobile_no:
            donor.mobile_no = member.mobile_no
        if hasattr(member, 'phone') and member.phone:
            donor.phone = member.phone
        
        # Insert the donor record
        donor.insert(ignore_permissions=True)
        
        # Link the customer record if it exists
        if member.customer:
            try:
                # Update customer record to link to donor
                customer_doc = frappe.get_doc("Customer", member.customer)
                if hasattr(customer_doc, 'donor'):
                    customer_doc.donor = donor.name
                    customer_doc.save(ignore_permissions=True)
            except Exception as cust_e:
                frappe.logger().warning(f"Could not link customer to donor: {str(cust_e)}")
        
        frappe.logger().info(f"Created donor record {donor.name} for member {member.name}")
        
        return {
            "success": True,
            "message": _("Donor record created successfully. Member can now receive donation receipts."),
            "donor_name": donor.name
        }
        
    except Exception as e:
        frappe.log_error(f"Error creating donor from member {member_name}: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": _("Failed to create donor record: {0}").format(str(e))
        }