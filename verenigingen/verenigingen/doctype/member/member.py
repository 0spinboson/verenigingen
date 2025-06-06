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

# Run one-time migration on module load
def run_backend_member_migration():
    """One-time migration to fix backend members showing as Pending"""
    try:
        # Check if migration has already been run
        if frappe.db.exists("Singles", {"doctype": "System Settings", "field": "backend_member_migration_done"}):
            return
        
        # Get members with Pending application_status but no application_id
        members = frappe.db.sql("""
            SELECT name, full_name 
            FROM `tabMember` 
            WHERE application_status = 'Pending' 
            AND (application_id IS NULL OR application_id = '')
            LIMIT 100
        """, as_dict=True)
        
        if members:
            frappe.logger().info(f"Fixing {len(members)} backend-created members")
            
            for member_data in members:
                try:
                    frappe.db.sql("""
                        UPDATE `tabMember` 
                        SET application_status = 'Active', status = 'Active'
                        WHERE name = %s
                    """, member_data.name)
                except Exception as e:
                    frappe.logger().error(f"Error fixing member {member_data.name}: {str(e)}")
            
            frappe.db.commit()
            frappe.logger().info(f"Fixed {len(members)} backend-created members")
        
        # Mark migration as done
        frappe.db.set_value("System Settings", "System Settings", "backend_member_migration_done", 1)
        frappe.db.commit()
        
    except Exception as e:
        frappe.logger().error(f"Backend member migration error: {str(e)}")

# Run migration when module is imported
if frappe.db:
    try:
        run_backend_member_migration()
    except:
        pass  # Ignore errors during import


class Member(Document, PaymentMixin, SEPAMandateMixin, ChapterMixin, TerminationMixin):
    """
    Member doctype with refactored structure using mixins for better organization
    """
    
    def before_save(self):
        """Execute before saving the document"""
        if not self.member_id:
            self.member_id = self.generate_member_id()
        self.handle_chapter_assignment()
        if hasattr(self, 'reset_counter_to') and self.reset_counter_to:
            self.reset_counter_to = None
        
        # Set appropriate defaults for application_status
        self.set_application_status_defaults()

    def before_insert(self):
        """Execute before inserting new document"""
        self.generate_member_id()

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
    
    def validate(self):
        """Validate document data"""
        self.validate_name()
        self.update_full_name()
        self.update_membership_status()
        self.calculate_age()
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
                # Backend-created members are Active by default
                self.application_status = "Active"
    
    def sync_status_fields(self):
        """Ensure status and application_status fields are synchronized"""
        # Check if this member was created through application process
        is_application_member = bool(getattr(self, 'application_id', None))
        
        if is_application_member:
            # Handle application-created members
            if hasattr(self, 'application_status') and self.application_status:
                if self.application_status == "Active" and self.status != "Active":
                    self.status = "Active"
                elif self.application_status == "Rejected" and self.status != "Rejected":
                    self.status = "Rejected"
                elif self.application_status == "Pending" and self.status not in ["Pending", "Active"]:
                    # For pending applications, default to Pending unless already Active
                    if self.status != "Active":
                        self.status = "Pending"
        else:
            # Handle backend-created members (no application process)
            if not hasattr(self, 'application_status') or not self.application_status:
                # Set application_status to Active for backend-created members
                self.application_status = "Active"
            
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
        """Update the full name based on first, middle and last name"""
        full_name = " ".join(filter(None, [self.first_name, self.middle_name, self.last_name]))
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
        if self.mobile_no:
            customer.mobile_no = self.mobile_no
        if self.phone:
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
        user.user_type = "Website User"
        
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
        """Handle changes to membership fee override"""
        if not self.has_value_changed("membership_fee_override"):
            return
            
        old_amount = self.get_db_value("membership_fee_override")
        new_amount = self.membership_fee_override
        
        # Set audit fields
        if new_amount and not old_amount:
            self.fee_override_date = today()
            self.fee_override_by = frappe.session.user
            
        # Validate fee override
        if new_amount:
            if new_amount <= 0:
                frappe.throw(_("Membership fee override must be greater than 0"))
            if not self.fee_override_reason:
                frappe.throw(_("Please provide a reason for the fee override"))
        
        # Record the change in history (will be added in after_save)
        self._pending_fee_change = {
            "old_amount": old_amount,
            "new_amount": new_amount,
            "reason": self.fee_override_reason,
            "change_date": now(),
            "changed_by": frappe.session.user
        }
    
    
    def record_fee_change(self, change_data):
        """Record fee change in history"""
        self.append("fee_change_history", {
            "change_date": change_data["change_date"],
            "old_amount": change_data["old_amount"],
            "new_amount": change_data["new_amount"],
            "reason": change_data["reason"],
            "changed_by": change_data["changed_by"],
            "subscription_action": "Pending subscription update"
        })
        self.save(ignore_permissions=True)
    
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
        """Update existing subscription plans based on current fee override"""
        if not self.customer:
            return {"message": "No customer linked to member"}
        
        try:
            current_fee = self.get_current_membership_fee()
            
            if current_fee["amount"] <= 0:
                return {"message": "No fee amount set, skipping subscription update"}
            
            # Find existing active subscriptions
            active_subscriptions = frappe.get_all(
                "Subscription",
                filters={
                    "party": self.customer,
                    "party_type": "Customer", 
                    "status": "Active",
                    "docstatus": 1
                }
            )
            
            updated_subscriptions = []
            
            # Instead of modifying submitted subscriptions, cancel them and create new ones
            for sub_data in active_subscriptions:
                try:
                    subscription = frappe.get_doc("Subscription", sub_data.name)
                    
                    # Cancel the existing subscription
                    subscription.cancel()
                    print(f"Cancelled subscription {subscription.name}")
                    
                    # Create a new subscription with the updated fee
                    active_membership = self.get_active_membership()
                    if active_membership:
                        new_subscription = self.get_or_create_subscription_for_membership(
                            active_membership, current_fee["amount"]
                        )
                        if new_subscription:
                            updated_subscriptions.append(new_subscription.name)
                            print(f"Created new subscription {new_subscription.name} with fee {current_fee['amount']}")
                            
                            # Update subscription history
                            self.update_subscription_history_entry(new_subscription.name, "created")
                    
                except Exception as e:
                    print(f"Error replacing subscription {sub_data.name}: {str(e)}")
                    # If cancellation fails due to membership link, just create a new one
                    try:
                        active_membership = self.get_active_membership()
                        if active_membership:
                            new_subscription = self.get_or_create_subscription_for_membership(
                                active_membership, current_fee["amount"]
                            )
                            if new_subscription:
                                updated_subscriptions.append(new_subscription.name)
                                print(f"Created additional subscription {new_subscription.name} with fee {current_fee['amount']}")
                                self.update_subscription_history_entry(new_subscription.name, "created")
                    except Exception as e2:
                        print(f"Error creating new subscription: {str(e2)}")
            
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
            
            return {
                "message": f"Updated {len(updated_subscriptions)} subscription(s)",
                "updated_subscriptions": updated_subscriptions
            }
                
        except Exception as e:
            print(f"Error in update_active_subscriptions for member {self.name}: {str(e)}")
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

def handle_fee_override_after_save(doc, method=None):
    """Hook function to handle fee override changes after save"""
    if hasattr(doc, '_pending_fee_change'):
        doc.record_fee_change(doc._pending_fee_change)
        doc.update_active_subscriptions()
        delattr(doc, '_pending_fee_change')