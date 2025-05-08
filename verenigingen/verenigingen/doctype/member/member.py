import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today, add_days, date_diff

class Member(Document):
    def before_save(self):
        if not self.member_id:
            self.member_id = self.generate_member_id()

    def generate_membership_id(self):
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
        self.update_address_display()

    def after_insert(self):
        """Create linked entities after member is created"""
        # Create customer if not already linked
        if not self.customer and self.email:
            self.create_customer()
    def on_load(self):
        """Load payment history when the document is loaded"""
        if self.customer:
            self.load_payment_history()

    def load_payment_history(self):
        """Load payment history for this member"""
        if not self.customer:
            return
        
        # Clear existing payment history
        self.payment_history = []
    
        # Get payment entries for this customer
        payment_entries = frappe.get_all(
            "Payment Entry",
            filters={
                "party_type": "Customer",
                "party": self.customer
            },
            fields=["name", "posting_date", "payment_type", "paid_amount", 
                "mode_of_payment", "status", "reference_no", "reference_date"],
            order_by="posting_date desc"
        )
    
        # Add payment entries to child table
        for entry in payment_entries:
            # Get reference documents
            references = frappe.get_all(
                "Payment Entry Reference",
                filters={"parent": entry.name},
                fields=["reference_doctype", "reference_name"]
            )
        
            ref_doctype = references[0].reference_doctype if references else None
            ref_name = references[0].reference_name if references else None
        
            self.append("payment_history", {
                "payment_entry": entry.name,
                "posting_date": entry.posting_date,
                "amount": entry.paid_amount,
                "payment_type": entry.payment_type,
                "mode_of_payment": entry.mode_of_payment,
                "status": entry.status,
                "reference_doctype": ref_doctype,
                "reference_name": ref_name
            })
    
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
            
    def update_address_display(self):
        # Format and set the address display
        address_parts = []
        if self.address_line1:
            address_parts.append(self.address_line1)
        if self.address_line2:
            address_parts.append(self.address_line2)
            
        city_state = []
        if self.city:
            city_state.append(self.city)
        if self.state:
            city_state.append(self.state)
        if city_state:
            address_parts.append(", ".join(city_state))
            
        if self.postal_code:
            address_parts.append(self.postal_code)
        if self.country:
            # Get country name if country code is provided
            if frappe.db.exists("Country", self.country):
                country_name = frappe.db.get_value("Country", self.country, "country_name")
                address_parts.append(country_name)
            else:
                address_parts.append(self.country)
                
        self.address_display = "\n".join(address_parts)
            
    def update_membership_status(self):
        # Update the membership status section
        active_membership = self.get_active_membership()
        
        if active_membership:
            self.current_membership_details = active_membership.name
            
            if active_membership.end_date:
                # Calculate time remaining until end date
                days_left = date_diff(active_membership.end_date, getdate(today()))
                if days_left < 0:
                    self.time_remaining = _("Expired")
                elif days_left == 0:
                    self.time_remaining = _("Expires today")
                else:
                    # Format as days/months/years depending on length
                    if days_left < 30:
                        self.time_remaining = _("{0} days").format(days_left)
                    elif days_left < 365:
                        months = int(days_left / 30)
                        self.time_remaining = _("{0} months").format(months)
                    else:
                        years = round(days_left / 365, 1)
                        self.time_remaining = _("{0} years").format(years)
            else:
                # Lifetime membership
                self.time_remaining = _("Lifetime")
        else:
            self.current_membership_details = None
            self.current_membership_type = None
            self.current_membership_start = None
            self.current_membership_end = None
            self.membership_status = None
            self.time_remaining = None
            
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
        
        # Check if customer with same email already exists
        if self.email:
            existing_customer = frappe.db.get_value("Customer", {"email_id": self.email})
            if existing_customer:
                self.customer = existing_customer
                self.save(ignore_permissions=True)
                frappe.msgprint(_("Linked to existing customer {0}").format(existing_customer))
                return existing_customer
    
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
                self.customer = exact_name_match.name
                self.save(ignore_permissions=True)
                frappe.msgprint(_("Linked to existing customer {0} with exact name match").format(exact_name_match.name))
                return exact_name_match.name
        
            # If no exact match but we have similar names, prompt the user
            if similar_name_customers:
                # Log similar customers for review
                customer_list = "\n".join([f"- {c.customer_name} ({c.name})" for c in similar_name_customers[:5]])
                frappe.msgprint(
                    _("Found similar customer names. Please review and link manually if appropriate:") + 
                    f"\n{customer_list}" +
                    (_("\n(Showing first 5 of {0} matches)").format(len(similar_name_customers)) if len(similar_name_customers) > 5 else "")
                )
            
        # Create new customer if no match found
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
        filters = {"member": self.name, "is_active": 1}
        
        if chapter:
            filters["parent"] = chapter
        
        return frappe.db.exists("Chapter Board Member", filters)
    
    def get_board_roles(self):
        """Get all board roles for this member"""
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

@frappe.whitelist()
def get_board_memberships(member_name):
    """Get board memberships for a member with proper permission handling"""
    # Query directly using SQL to bypass permission checks
    board_memberships = frappe.db.sql("""
        SELECT cbm.parent, cbm.chapter_role 
        FROM `tabChapter Board Member` cbm
        WHERE cbm.member = %s AND cbm.is_active = 1
    """, (member_name,), as_dict=True)
    
    return board_memberships
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
