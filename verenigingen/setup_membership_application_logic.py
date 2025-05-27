"""
Custom fields for Member doctype to integrate volunteer information
"""
import frappe

@frappe.whitelist()
def setup_member_application_system():
    """Main setup function for member application system"""
    try:
        # Setup custom fields
        setup_member_custom_fields()
        
        # Create email templates
        create_application_email_templates()
        
        # Create web pages
        create_application_web_pages()
        
        # Commit changes
        frappe.db.commit()
        
        return {"success": True, "message": "Member application system setup completed"}
    except Exception as e:
        frappe.log_error(f"Error setting up member application system: {str(e)}")
        return {"success": False, "message": str(e)}

def create_application_email_templates():
    """Create email templates for application workflow"""
    
    templates = [
        {
            "name": "membership_application_confirmation",
            "subject": "Membership Application Received - Payment Required",
            "response": """
                <h3>Thank you for your membership application!</h3>
                
                <p>Dear {{ member.first_name }},</p>
                
                <p>We have received your membership application for {{ membership_type }}.</p>
                
                <p><strong>Next Step: Complete Payment</strong></p>
                <p>To activate your membership, please complete the payment of {{ frappe.format_value(payment_amount, {"fieldtype": "Currency"}) }}.</p>
                
                <p><a href="{{ payment_url }}" class="btn btn-primary">Complete Payment</a></p>
                
                <p>Once your payment is processed, you will receive a welcome email with your member portal access details.</p>
                
                <p>If you have any questions, please don't hesitate to contact us.</p>
                
                <p>Best regards,<br>The Membership Team</p>
            """
        },
        {
            "name": "membership_welcome",
            "subject": "Welcome to {{ frappe.db.get_value('Company', company, 'company_name') }}!",
            "response": """
                <h2>Welcome to our Association, {{ member.first_name }}!</h2>
                
                <p>Your membership is now active and you have full access to all member benefits.</p>
                
                <h3>Your Membership Details:</h3>
                <table style="width: 100%; max-width: 500px;">
                    <tr>
                        <td><strong>Member ID:</strong></td>
                        <td>{{ member.name }}</td>
                    </tr>
                    <tr>
                        <td><strong>Membership Type:</strong></td>
                        <td>{{ membership_type.membership_type_name }}</td>
                    </tr>
                    <tr>
                        <td><strong>Valid From:</strong></td>
                        <td>{{ frappe.format_date(membership.start_date) }}</td>
                    </tr>
                    <tr>
                        <td><strong>Valid Until:</strong></td>
                        <td>{{ frappe.format_date(membership.renewal_date) }}</td>
                    </tr>
                    {% if member.primary_chapter %}
                    <tr>
                        <td><strong>Chapter:</strong></td>
                        <td>{{ member.primary_chapter }}</td>
                    </tr>
                    {% endif %}
                </table>
                
                {% if member.interested_in_volunteering %}
                <h3>Thank you for your interest in volunteering!</h3>
                <p>Our volunteer coordinator will be in touch with you soon to discuss opportunities that match your interests and availability.</p>
                {% endif %}
                
                <h3>Access Your Member Portal</h3>
                <p>You can access your member portal at: <a href="{{ member_portal_url }}">{{ member_portal_url }}</a></p>
                
                <p>If you haven't set up your password yet, please visit: <a href="{{ login_url }}">{{ login_url }}</a></p>
                
                <h3>Stay Connected</h3>
                <ul>
                    <li>Follow us on social media</li>
                    <li>Join our member forum</li>
                    <li>Attend our upcoming events</li>
                </ul>
                
                <p>We're excited to have you as part of our community!</p>
                
                <p>Best regards,<br>The {{ frappe.db.get_value('Company', company, 'company_name') }} Team</p>
            """
        },
        {
            "name": "volunteer_welcome",
            "subject": "Welcome to our Volunteer Team!",
            "response": """
                <h2>Welcome to our Volunteer Team, {{ volunteer.volunteer_name }}!</h2>
                
                <p>Thank you for your interest in volunteering with us. We're excited to have you join our team!</p>
                
                <h3>Your Volunteer Profile:</h3>
                <ul>
                    <li><strong>Availability:</strong> {{ volunteer.commitment_level }}</li>
                    <li><strong>Experience Level:</strong> {{ volunteer.experience_level }}</li>
                    {% if volunteer.interests %}
                    <li><strong>Areas of Interest:</strong>
                        <ul>
                        {% for interest in volunteer.interests %}
                            <li>{{ interest.interest_area }}</li>
                        {% endfor %}
                        </ul>
                    </li>
                    {% endif %}
                </ul>
                
                <h3>Next Steps:</h3>
                <ol>
                    <li>Complete your volunteer orientation (online)</li>
                    <li>Review our volunteer handbook</li>
                    <li>Sign up for your first volunteer opportunity</li>
                </ol>
                
                <p>Your volunteer coordinator will contact you within the next few days to discuss specific opportunities.</p>
                
                <p>In the meantime, you can access your volunteer portal using your organization email: <strong>{{ volunteer.email }}</strong></p>
                
                <p>Thank you for making a difference!</p>
                
                <p>Best regards,<br>The Volunteer Team</p>
            """
        },
        {
            "name": "membership_payment_failed",
            "subject": "Payment Failed - Membership Application",
            "response": """
                <p>Dear {{ member.first_name }},</p>
                
                <p>Unfortunately, your payment for the membership application could not be processed.</p>
                
                <p><strong>Don't worry - your application is still valid!</strong></p>
                
                <p>You can retry the payment at any time using this link:</p>
                <p><a href="{{ retry_url }}" class="btn btn-primary">Retry Payment</a></p>
                
                <p>If you continue to experience issues, please contact our support team at support@example.com</p>
                
                <p>Common reasons for payment failure:</p>
                <ul>
                    <li>Insufficient funds</li>
                    <li>Card declined by bank</li>
                    <li>Incorrect payment details</li>
                    <li>Technical issues</li>
                </ul>
                
                <p>Best regards,<br>The Membership Team</p>
            """
        }
    ]
    
    for template_data in templates:
        if not frappe.db.exists("Email Template", template_data["name"]):
            template = frappe.get_doc({
                "doctype": "Email Template",
                "name": template_data["name"],
                "subject": template_data["subject"],
                "use_html": 1,
                "response": template_data["response"]
            })
            template.insert(ignore_permissions=True)
            print(f"Created email template: {template_data['name']}")

def create_application_web_pages():
    """Create web pages for application process"""
    
    # Create routes in website settings
    pages = [
        {
            "route": "apply-for-membership",
            "title": "Apply for Membership",
            "published": 1
        },
        {
            "route": "payment/complete",
            "title": "Complete Payment",
            "published": 1
        },
        {
            "route": "payment/success",
            "title": "Payment Successful",
            "published": 1
        },
        {
            "route": "payment/failed",
            "title": "Payment Failed",
            "published": 1
        }
    ]
    
    # Note: Actual page templates should be created in the templates folder
    print("Web pages configured. Please ensure template files exist in verenigingen/templates/pages/")

if __name__ == "__main__":
    setup_member_application_system(),
            {
                "fieldname": "payment_date",
                "fieldtype": "Datetime",
                "label": "Payment Date",
                "insert_after": "application_date",
                "read_only": 1
            },
            {
                "fieldname": "payment_amount",
                "fieldtype": "Currency",
                "label": "Payment Amount",
                "insert_after": "payment_date",
                "read_only": 1
            },
            {
                "fieldname": "column_break_app1",
                "fieldtype": "Column Break",
                "insert_after": "payment_amount"
            },
            {
                "fieldname": "reviewed_by",
                "fieldtype": "Link",
                "label": "Reviewed By",
                "options": "User",
                "insert_after": "column_break_app1",
                "read_only": 1
            },
            {
                "fieldname": "review_date",
                "fieldtype": "Datetime",
                "label": "Review Date",
                "insert_after": "reviewed_by",
                "read_only": 1
            },
            {
                "fieldname": "review_notes",
                "fieldtype": "Small Text",
                "label": "Review Notes",
                "insert_after": "review_date"
            },
            
            # Chapter Selection
            {
                "fieldname": "chapter_selection_section",
                "fieldtype": "Section Break",
                "label": "Chapter Information",
                "insert_after": "review_notes",
                "collapsible": 1
            },
            {
                "fieldname": "selected_chapter",
                "fieldtype": "Link",
                "label": "Selected Chapter",
                "options": "Chapter",
                "description": "Chapter selected by applicant during application",
                "insert_after": "chapter_selection_section"
            },
            {
                "fieldname": "suggested_chapter",
                "fieldtype": "Link",
                "label": "Suggested Chapter",
                "options": "Chapter",
                "description": "Auto-suggested based on postal code",
                "insert_after": "selected_chapter",
                "read_only": 1
            },
            {
                "fieldname": "column_break_ch1",
                "fieldtype": "Column Break",
                "insert_after": "suggested_chapter"
            },
            {
                "fieldname": "selected_membership_type",
                "fieldtype": "Link",
                "label": "Selected Membership Type",
                "options": "Membership Type",
                "insert_after": "column_break_ch1"
            },
            
            # Volunteer Interest Section - Using existing child tables
            {
                "fieldname": "volunteer_section",
                "fieldtype": "Section Break",
                "label": "Volunteer Information",
                "insert_after": "selected_membership_type",
                "collapsible": 1
            },
            {
                "fieldname": "interested_in_volunteering",
                "fieldtype": "Check",
                "label": "Interested in Volunteering",
                "insert_after": "volunteer_section"
            },
            {
                "fieldname": "volunteer_availability",
                "fieldtype": "Select",
                "label": "Volunteer Availability",
                "options": "\nOccasional\nMonthly\nWeekly\nProject-based",
                "depends_on": "eval:doc.interested_in_volunteering",
                "insert_after": "interested_in_volunteering"
            },
            {
                "fieldname": "volunteer_experience_level",
                "fieldtype": "Select",
                "label": "Experience Level",
                "options": "\nBeginner\nIntermediate\nExperienced\nExpert",
                "depends_on": "eval:doc.interested_in_volunteering",
                "insert_after": "volunteer_availability"
            },
            {
                "fieldname": "column_break_vol1",
                "fieldtype": "Column Break",
                "insert_after": "volunteer_experience_level"
            },
            {
                "fieldname": "volunteer_interests",
                "fieldtype": "Table",
                "label": "Areas of Interest",
                "options": "Member Volunteer Interest",
                "depends_on": "eval:doc.interested_in_volunteering",
                "insert_after": "column_break_vol1"
            },
            {
                "fieldname": "volunteer_skills",
                "fieldtype": "Table",
                "label": "Skills and Qualifications",
                "options": "Member Volunteer Skill",
                "depends_on": "eval:doc.interested_in_volunteering",
                "insert_after": "volunteer_interests"
            },
            
            # Communication Preferences
            {
                "fieldname": "communication_preferences_section",
                "fieldtype": "Section Break",
                "label": "Communication Preferences",
                "insert_after": "volunteer_skills",
                "collapsible": 1
            },
            {
                "fieldname": "accepts_mandatory_communications",
                "fieldtype": "Check",
                "label": "Accepts Mandatory Communications",
                "default": 1,
                "read_only": 1,
                "description": "Required for membership (AGM invites, official notices)",
                "insert_after": "communication_preferences_section"
            },
            {
                "fieldname": "newsletter_opt_in",
                "fieldtype": "Check",
                "label": "Newsletter Subscription",
                "default": 1,
                "description": "Optional newsletters, updates, events",
                "insert_after": "accepts_mandatory_communications"
            },
            {
                "fieldname": "column_break_comm1",
                "fieldtype": "Column Break",
                "insert_after": "newsletter_opt_in"
            },
            {
                "fieldname": "application_source",
                "fieldtype": "Select",
                "label": "Application Source",
                "options": "\nWebsite\nSocial Media\nFriend/Family\nEvent\nOther",
                "insert_after": "column_break_comm1"
            },
            {
                "fieldname": "application_source_details",
                "fieldtype": "Data",
                "label": "Source Details",
                "depends_on": "eval:doc.application_source=='Other'",
                "insert_after": "application_source"
            },
            
            # Payment tracking
            {
                "fieldname": "application_payment_section",
                "fieldtype": "Section Break",
                "label": "Payment Information",
                "insert_after": "application_source_details",
                "depends_on": "eval:doc.application_status!='Pending'",
                "collapsible": 1
            },
            {
                "fieldname": "application_invoice",
                "fieldtype": "Link",
                "label": "Application Invoice",
                "options": "Sales Invoice",
                "insert_after": "application_payment_section",
                "read_only": 1
            },
            {
                "fieldname": "application_payment",
                "fieldtype": "Link",
                "label": "Payment Entry",
                "options": "Payment Entry",
                "insert_after": "application_invoice",
                "read_only": 1
            },
            {
                "fieldname": "column_break_pay1",
                "fieldtype": "Column Break",
                "insert_after": "application_payment"
            },
            {
                "fieldname": "refund_status",
                "fieldtype": "Select",
                "label": "Refund Status",
                "options": "\nPending\nProcessed\nN/A",
                "insert_after": "column_break_pay1",
                "depends_on": "eval:doc.application_status=='Rejected' && doc.application_payment"
            },
            {
                "fieldname": "refund_reference",
                "fieldtype": "Data",
                "label": "Refund Reference",
                "insert_after": "refund_status",
                "depends_on": "eval:doc.refund_status=='Processed'",
                "read_only": 1
            }
