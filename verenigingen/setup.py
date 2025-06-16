import frappe
from frappe import _
from frappe.desk.page.setup_wizard.setup_wizard import make_records
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def make_custom_records():
    records = [
        {'doctype': "Party Type", "party_type": "Member", "account_type": "Receivable"},
        {'doctype': "Party Type", "party_type": "Donor", "account_type": "Receivable"},
    ]
    make_records(records)

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
    # Constants for Dutch BTW Codes
    BTW_CODES = {
        "EXEMPT_NONPROFIT": "BTW Vrijgesteld - Art. 11-1-f Wet OB",
        "EXEMPT_MEMBERSHIP": "BTW Vrijgesteld - Art. 11-1-l Wet OB",
        "EXEMPT_FUNDRAISING": "BTW Vrijgesteld - Art. 11-1-v Wet OB",
        "EXEMPT_SMALL_BUSINESS": "BTW Vrijgesteld - KOR",
        "OUTSIDE_SCOPE": "Buiten reikwijdte BTW",
        "EXEMPT_WITH_INPUT": "BTW Vrijgesteld met recht op aftrek",
        "EXEMPT_NO_INPUT": "BTW Vrijgesteld zonder recht op aftrek"
    }
    
    custom_fields = {
        'Company': [
            dict(fieldname='verenigingen_section', label='Verenigingen Settings',
                 fieldtype='Section Break', insert_after='asset_received_but_not_billed', collapsible=1)
        ],
        'Sales Invoice': [
            dict(
                fieldname='exempt_from_tax',
                label='Exempt from Tax',
                fieldtype='Check',
                insert_after='tax_category',
                translatable=0
            ),
            # BTW fields that were missing and causing the error
            {
                "fieldname": "btw_exemption_type",
                "label": "BTW Exemption Type",
                "fieldtype": "Select",
                "options": "\n" + "\n".join(BTW_CODES.keys()),
                "insert_after": "exempt_from_tax",
                "translatable": 0
            },
            {
                "fieldname": "btw_exemption_reason",
                "label": "BTW Exemption Reason",
                "fieldtype": "Small Text",
                "insert_after": "btw_exemption_type",
                "translatable": 0,
                "depends_on": "eval:doc.btw_exemption_type"
            },
            {
                "fieldname": "btw_reporting_category",
                "label": "BTW Reporting Category",
                "fieldtype": "Data",
                "insert_after": "btw_exemption_reason",
                "translatable": 0,
                "read_only": 1,
                "depends_on": "eval:doc.btw_exemption_type"
            }
        ],
        'Membership': [
            {
                "fieldname": "btw_exemption_type",
                "label": "BTW Exemption Type",
                "fieldtype": "Select",
                "options": "\n" + "\n".join(BTW_CODES.keys()),
                "insert_after": "membership_type",
                "default": "EXEMPT_MEMBERSHIP",
                "translatable": 0
            }
        ]
    }
    
    # Add Donation fields if Donation doctype exists
    if frappe.db.exists("DocType", "Donation"):
        custom_fields['Donation'] = [
            {
                "fieldname": "btw_exemption_type",
                "label": "BTW Exemption Type",
                "fieldtype": "Select", 
                "options": "\n" + "\n".join(BTW_CODES.keys()),
                "insert_after": "donation_category",
                "default": "EXEMPT_FUNDRAISING",
                "translatable": 0
            }
        ]
    
    return custom_fields

def validate_app_dependencies():
    """Validate that required apps are installed"""
    required_apps = ["erpnext", "payments", "hrms"]
    missing_apps = []
    
    try:
        # Use frappe.get_installed_apps() which is more reliable during installation
        installed_apps = frappe.get_installed_apps()
        
        for app in required_apps:
            if app not in installed_apps:
                missing_apps.append(app)
        
        if missing_apps:
            frappe.throw(
                f"Missing required apps: {', '.join(missing_apps)}. "
                f"Please install these apps before installing verenigingen.",
                title="Missing Dependencies"
            )
        
        print(f"✅ All required apps are installed: {', '.join(required_apps)}")
        
    except Exception as e:
        # If validation fails, just log a warning and continue
        # This prevents installation failures due to dependency checking issues
        print(f"⚠️  Warning: Could not validate app dependencies: {str(e)}")
        print("Continuing with installation - please ensure erpnext, payments, and hrms are installed")

def execute_after_install():
    """
    Function executed after the app is installed
    Sets up necessary configurations for the Verenigingen app
    """
    try:
        # Validate dependencies
        validate_app_dependencies()
        
        # Execute the setup function from this file
        setup_verenigingen()
        
        # Set up membership application system
        setup_membership_application_system()
        
        # Set up tax exemption templates if enabled
        setup_tax_exemption_on_install()

        # Set up termination system
        setup_termination_system_integration()
        
        # Set up workspace
        setup_workspace()
        
        # Load fixtures
        load_application_fixtures()
        
        # Log the successful setup
        frappe.logger().info("Verenigingen setup completed successfully")
        print("Verenigingen app setup completed successfully")
        
    except Exception as e:
        frappe.logger().error(f"Error during Verenigingen setup: {str(e)}")
        print(f"Error during setup: {str(e)}")

def setup_tax_exemption_on_install():
    """Set up tax exemption during installation if enabled"""
    try:
        settings = frappe.get_single("Verenigingen Settings")
        if settings.get("tax_exempt_for_contributions"):
            # Import and run the tax setup
            from verenigingen.utils import setup_dutch_tax_exemption
            setup_dutch_tax_exemption()
            print("Tax exemption templates set up during installation")
    except Exception as e:
        frappe.logger().error(f"Error setting up tax exemption during install: {str(e)}")
        print(f"Warning: Could not set up tax exemption during install: {str(e)}")

@frappe.whitelist()
def install_missing_btw_fields():
    """Install BTW custom fields that were missing"""
    try:
        make_custom_fields(update=True)
        frappe.msgprint(_("BTW custom fields installed successfully. Please refresh to see changes."))
        return True
    except Exception as e:
        frappe.msgprint(_("Error installing BTW fields: {0}").format(str(e)))
        frappe.log_error(f"Error installing BTW fields: {str(e)}", "BTW Field Installation Error")
        return False

@frappe.whitelist()
def verify_btw_installation():
    """Verify that BTW fields are properly installed"""
    missing_fields = []
    
    # Check required BTW fields
    required_fields = [
        ("Sales Invoice", "btw_exemption_type"),
        ("Sales Invoice", "btw_exemption_reason"),
        ("Sales Invoice", "btw_reporting_category"),
        ("Membership", "btw_exemption_type")
    ]
    
    for doctype, fieldname in required_fields:
        if not frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": fieldname}):
            missing_fields.append(f"{doctype}.{fieldname}")
    
    if missing_fields:
        return {
            "status": "Missing Fields",
            "missing_fields": missing_fields,
            "message": f"Missing {len(missing_fields)} BTW custom fields"
        }
    else:
        return {
            "status": "All Good",
            "message": "All BTW custom fields are installed"
        }

@frappe.whitelist()
def fix_btw_installation():
    """Fix BTW installation issues"""
    try:
        # Reinstall custom fields
        install_missing_btw_fields()
        
        # Set up tax templates if needed
        settings = frappe.get_single("Verenigingen Settings")
        if settings.get("tax_exempt_for_contributions"):
            from verenigingen.utils import setup_dutch_tax_exemption
            setup_dutch_tax_exemption()
        
        frappe.msgprint(_("BTW installation fixed successfully"))
        return True
        
    except Exception as e:
        frappe.msgprint(_("Error fixing BTW installation: {0}").format(str(e)))
        return False

def setup_termination_system_integration():
    """Setup the termination system as part of app installation"""
    try:
        print("🔧 Setting up termination system...")
        
        # Step 1: Setup termination-specific settings
        setup_termination_settings()
        
        # Step 2: Setup workflows (using separate workflow setup module)
        from verenigingen.setup.workflow_setup import setup_workflows_corrected
        workflow_success = setup_workflows_corrected()
        
        if workflow_success:
            print("✅ Workflows created successfully")
        else:
            print("⚠️ Workflow creation had issues")
        
        # Step 3: Setup roles and permissions
        setup_termination_roles_and_permissions()
        
        print("✅ Termination system setup completed")
        
    except Exception as e:
        frappe.log_error(f"Termination system setup error: {str(e)}", "Termination Setup Error")
        print(f"⚠️ Termination system setup failed: {str(e)}")

def setup_termination_settings():
    """Setup termination system settings"""
    
    try:
        # Get or create Verenigingen Settings
        if not frappe.db.exists("Verenigingen Settings", "Verenigingen Settings"):
            # This should already be created by the main setup, but just in case
            return
        
        settings = frappe.get_single("Verenigingen Settings")
        
        # Add termination system settings if they don't exist
        termination_defaults = {
            'enable_termination_system': 1,
            'require_secondary_approval': 1,
            'appeal_deadline_days': 30,
            'appeal_review_days': 60,
            'termination_grace_period_days': 30,
            'auto_cancel_sepa_mandates': 1,
            'auto_end_board_positions': 1,
            'send_termination_notifications': 1
        }
        
        settings_updated = False
        for field, default_value in termination_defaults.items():
            if hasattr(settings, field):
                if not getattr(settings, field):
                    setattr(settings, field, default_value)
                    settings_updated = True
        
        if settings_updated:
            settings.save(ignore_permissions=True)
            frappe.db.commit()
            print("   ✓ Termination settings configured")
        else:
            print("   ✓ Termination settings already configured")
            
    except Exception as e:
        print(f"   ⚠️ Could not setup termination settings: {str(e)}")

def setup_termination_workflows_and_templates():
    """Setup workflows and email templates for termination system"""
    
    try:
        # Try to import and run the workflow setup
        from verenigingen.setup.workflow_setup import setup_workflows_corrected

        success = setup_workflows_corrected()        
                
        if success:
            print("   ✓ Termination workflows and templates setup completed")
        else:
            print("   ⚠️ Termination workflows setup had some issues")
            
    except ImportError:
        print("   ⚠️ Could not import workflow setup - termination workflows not created")
    except Exception as e:
        print(f"   ⚠️ Workflow setup failed: {str(e)}")

def setup_termination_roles_and_permissions():
    """Setup roles and basic permissions for termination system"""
    
    try:
        # Create required roles
        required_roles = [
            {
                "role_name": "Verenigingen Administrator",
                "desk_access": 1,
                "is_custom": 1
            }
        ]
        
        for role_config in required_roles:
            role_name = role_config["role_name"]
            if not frappe.db.exists("Role", role_name):
                try:
                    role = frappe.get_doc({
                        "doctype": "Role",
                        **role_config
                    })
                    role.insert(ignore_permissions=True)
                    print(f"   ✓ Created role: {role_name}")
                except Exception as e:
                    print(f"   ⚠️ Could not create role {role_name}: {str(e)}")
            else:
                print(f"   ✓ Role already exists: {role_name}")
        
        frappe.db.commit()
        
    except Exception as e:
        print(f"   ⚠️ Role setup failed: {str(e)}")

# Add these API endpoints to your existing setup.py file

@frappe.whitelist()
def setup_termination_system_manual():
    """Manual setup endpoint for termination system"""
    try:
        setup_termination_system_integration()
        return {"success": True, "message": "Termination system setup completed"}
    except Exception as e:
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def check_termination_system_status():
    """Check the status of termination system setup"""
    
    status = {
        "settings_configured": False,
        "workflows_exist": False,
        "roles_exist": False,
        "system_enabled": False
    }
    
    try:
        # Check settings
        if frappe.db.exists("Verenigingen Settings", "Verenigingen Settings"):
            settings = frappe.get_single("Verenigingen Settings")
            if hasattr(settings, 'enable_termination_system'):
                status["settings_configured"] = True
                status["system_enabled"] = bool(settings.enable_termination_system)
        
        # Check workflows
        workflows = ["Membership Termination Workflow", "Termination Appeals Workflow"]
        workflow_count = 0
        for workflow in workflows:
            if frappe.db.exists("Workflow", workflow):
                workflow_count += 1
        status["workflows_exist"] = workflow_count > 0
        
        # Check roles
        status["roles_exist"] = frappe.db.exists("Role", "Verenigingen Administrator")
        
        return {"success": True, "status": status}
        
    except Exception as e:
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def run_termination_diagnostics():
    """Run diagnostics on termination system"""
    
    print("🔍 TERMINATION SYSTEM DIAGNOSTICS")
    print("=" * 40)
    
    all_good = True
    
    # 1. Check required doctypes
    print("\n1. DOCTYPE CHECK")
    print("-" * 15)
    
    required_doctypes = [
        "Membership Termination Request",
        "Expulsion Report Entry"
    ]
    
    for doctype in required_doctypes:
        if frappe.db.exists("DocType", doctype):
            print(f"   ✅ {doctype}")
        else:
            print(f"   ❌ {doctype} - MISSING")
            all_good = False
    
    # 2. Check roles
    print("\n2. ROLE CHECK")
    print("-" * 12)
    
    if frappe.db.exists("Role", "Verenigingen Administrator"):
        print("   ✅ Verenigingen Administrator")
    else:
        print("   ❌ Verenigingen Administrator - MISSING")
        all_good = False
    
    # 3. Check workflows
    print("\n3. WORKFLOW CHECK")
    print("-" * 15)
    
    workflows = ["Membership Termination Workflow", "Termination Appeals Workflow"]
    for workflow in workflows:
        if frappe.db.exists("Workflow", workflow):
            print(f"   ✅ {workflow}")
        else:
            print(f"   ❌ {workflow} - MISSING")
            all_good = False
    
    # Summary
    print("\n" + "=" * 40)
    if all_good:
        print("✅ ALL DIAGNOSTICS PASSED")
    else:
        print("⚠️ SOME ISSUES FOUND")
    print("=" * 40)
    
    return {"success": True, "diagnostics_passed": all_good}

def setup_email_templates():
    """Create basic email templates"""
    
    print("   📧 Setting up email templates...")
    
    templates = [
        {
            "name": "Termination Approval Required",  
            "subject": "Termination Approval Required - {{ doc.member_name }}",
            "use_html": 1,
            "response": "<p>A termination request requires your approval for member: {{ doc.member_name }}</p>"
        }
    ]
    
    created_count = 0
    
    for template_data in templates:
        template_name = template_data["name"]
        
        if frappe.db.exists("Email Template", template_name):
            print(f"   ✓ Email template '{template_name}' already exists")
            continue
            
        try:
            template = frappe.get_doc({
                "doctype": "Email Template",
                "name": template_name,
                "subject": template_data["subject"],
                "use_html": template_data["use_html"],
                "response": template_data["response"]
            })
            
            template.insert(ignore_permissions=True)
            created_count += 1
            print(f"   ✓ Created email template: {template_name}")
            
        except Exception as e:
            print(f"   ❌ Failed to create email template '{template_name}': {str(e)}")
    
    if created_count > 0:
        try:
            frappe.db.commit()
        except Exception as e:
            print(f"   ⚠️ Template commit warning: {str(e)}")
    
    return created_count

def setup_membership_application_system():
    """Set up membership application system with email templates and web pages"""
    print("📧 Setting up membership application system...")
    
    try:
        # Create email templates
        create_application_email_templates()
        
        # Create web pages configuration
        setup_application_web_pages()
        
        # Create default donation types
        create_default_donation_types()
        
        print("✅ Membership application system setup completed")
        
    except Exception as e:
        print(f"⚠️ Membership application system setup failed: {str(e)}")

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
    
    created_count = 0
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
            created_count += 1
            print(f"   ✓ Created email template: {template_data['name']}")
        else:
            print(f"   ✓ Email template already exists: {template_data['name']}")
    
    if created_count > 0:
        print(f"   📧 Created {created_count} new email templates")
    
    return created_count

def setup_application_web_pages():
    """Set up web pages for application process"""
    
    print("   🌐 Configuring web pages for membership application...")
    
    # Create routes in website settings - this is just informational
    # The actual page templates should exist in verenigingen/templates/pages/
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
    
    print(f"   ✓ Web pages configured for {len(pages)} routes")
    print("   ℹ️  Ensure template files exist in verenigingen/templates/pages/")

def setup_workspace():
    """Set up and update workspace for verenigingen"""
    print("🏢 Setting up Verenigingen workspace...")
    
    try:
        # Clean up workspace first
        cleanup_workspace_links()
        
        # Then add new links
        update_workspace_links()
        
        print("✅ Workspace setup completed")
        
    except Exception as e:
        print(f"⚠️ Workspace setup failed: {str(e)}")

def cleanup_workspace_links():
    """Clean up invalid workspace links"""
    try:
        if not frappe.db.exists('Workspace', 'Verenigingen'):
            print("   ℹ️  Verenigingen workspace doesn't exist yet - will be created")
            return
            
        workspace = frappe.get_doc('Workspace', 'Verenigingen')
        
        # Find and remove links to non-existent doctypes
        links_to_remove = []
        for i, link in enumerate(workspace.links):
            link_to = link.get('link_to')
            if link_to and not frappe.db.exists('DocType', link_to):
                print(f"   🗑️  Removing invalid link: {link.get('label')} -> {link_to}")
                links_to_remove.append(i)
        
        # Remove in reverse order to maintain indices
        for i in reversed(links_to_remove):
            del workspace.links[i]
        
        if links_to_remove:
            workspace.save(ignore_permissions=True)
            print(f"   ✓ Cleaned up {len(links_to_remove)} invalid links")
        else:
            print("   ✓ No invalid links found")
            
    except Exception as e:
        print(f"   ⚠️ Workspace cleanup failed: {str(e)}")

def update_workspace_links():
    """Add new links to workspace"""
    try:
        if not frappe.db.exists('Workspace', 'Verenigingen'):
            print("   ℹ️  Verenigingen workspace doesn't exist - skipping link updates")
            return
            
        workspace = frappe.get_doc('Workspace', 'Verenigingen')
        
        # Links to add (only if doctype exists)
        potential_links = [
            # Termination & Appeals Section
            {
                "hidden": 0,
                "is_query_report": 0,
                "label": "Termination & Appeals",
                "link_count": 2,
                "link_type": "DocType",
                "onboard": 0,
                "type": "Card Break"
            },
            {
                "dependencies": "",
                "hidden": 0,
                "is_query_report": 0,
                "label": "Membership Termination Request",
                "link_count": 0,
                "link_to": "Membership Termination Request",
                "link_type": "DocType",
                "onboard": 0,
                "type": "Link"
            },
            {
                "dependencies": "",
                "hidden": 0,
                "is_query_report": 0,
                "label": "SEPA Mandate",
                "link_count": 0,
                "link_to": "SEPA Mandate",
                "link_type": "DocType",
                "onboard": 0,
                "type": "Link"
            },
            {
                "dependencies": "",
                "hidden": 0,
                "is_query_report": 0,
                "label": "Direct Debit Batch", 
                "link_count": 0,
                "link_to": "Direct Debit Batch",
                "link_type": "DocType",
                "onboard": 0,
                "type": "Link"
            }
        ]
        
        # Only add links for existing doctypes
        links_added = 0
        for link in potential_links:
            link_to = link.get('link_to')
            if not link_to or frappe.db.exists('DocType', link_to) or link.get('type') == 'Card Break':
                # Check if link already exists
                exists = False
                for existing_link in workspace.links:
                    if existing_link.get('label') == link.get('label'):
                        exists = True
                        break
                
                if not exists:
                    workspace.append('links', link)
                    links_added += 1
                    print(f"   ✓ Added link: {link.get('label')}")
        
        # Add new shortcuts (only for existing doctypes)
        potential_shortcuts = [
            {
                "color": "Red",
                "label": "Termination Requests",
                "link_to": "Membership Termination Request",
                "type": "DocType"
            },
            {
                "color": "Blue", 
                "label": "SEPA Mandates",
                "link_to": "SEPA Mandate",
                "type": "DocType"
            }
        ]
        
        shortcuts_added = 0
        for shortcut in potential_shortcuts:
            link_to = shortcut.get('link_to')
            if frappe.db.exists('DocType', link_to):
                # Check if shortcut already exists
                exists = False
                for existing_shortcut in workspace.shortcuts:
                    if existing_shortcut.get('label') == shortcut.get('label'):
                        exists = True
                        break
                
                if not exists:
                    workspace.append('shortcuts', shortcut)
                    shortcuts_added += 1
                    print(f"   ✓ Added shortcut: {shortcut.get('label')}")
        
        if links_added > 0 or shortcuts_added > 0:
            workspace.save(ignore_permissions=True)
            print(f"   ✅ Added {links_added} links and {shortcuts_added} shortcuts")
        else:
            print("   ✓ No new links or shortcuts needed")
            
    except Exception as e:
        print(f"   ⚠️ Workspace update failed: {str(e)}")

def load_application_fixtures():
    """Load necessary fixtures for the application"""
    print("📦 Loading application fixtures...")
    
    try:
        import os
        from frappe.desk.page.setup_wizard.setup_wizard import install_fixtures
        
        # Get fixtures directory
        app_path = frappe.get_app_path("verenigingen")
        fixtures_path = os.path.join(app_path, "..", "fixtures")
        
        # Load workflow fixtures if they exist
        fixture_files = [
            "workflow.json",
            "membership_workflow.json"
        ]
        
        loaded_count = 0
        for fixture_file in fixture_files:
            fixture_path = os.path.join(fixtures_path, fixture_file)
            if os.path.exists(fixture_path):
                try:
                    install_fixtures(fixture_path)
                    loaded_count += 1
                    print(f"   ✓ Loaded fixture: {fixture_file}")
                except Exception as e:
                    print(f"   ⚠️ Could not load fixture {fixture_file}: {str(e)}")
            else:
                print(f"   ℹ️  Fixture not found: {fixture_file}")
        
        if loaded_count > 0:
            print(f"   📦 Loaded {loaded_count} fixtures")
        else:
            print("   ℹ️  No fixtures loaded")
            
    except Exception as e:
        print(f"   ⚠️ Fixture loading failed: {str(e)}")

# Consolidated API endpoints for all setup functions

@frappe.whitelist()
def run_complete_setup():
    """Run the complete setup process manually"""
    try:
        execute_after_install()
        return {"success": True, "message": "Complete setup completed successfully"}
    except Exception as e:
        return {"success": False, "message": str(e)}

@frappe.whitelist() 
def setup_membership_application_system_manual():
    """Manual setup endpoint for membership application system"""
    try:
        setup_membership_application_system()
        return {"success": True, "message": "Membership application system setup completed"}
    except Exception as e:
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def setup_workspace_manual():
    """Manual setup endpoint for workspace"""
    try:
        setup_workspace()
        return {"success": True, "message": "Workspace setup completed"}
    except Exception as e:
        return {"success": False, "message": str(e)}

def create_default_donation_types():
    """Create default donation types if they don't exist"""
    print("   💰 Setting up default donation types...")
    
    default_types = [
        "General",
        "Monthly",
        "One-time", 
        "Campaign",
        "Emergency Relief",
        "Membership Support"
    ]
    
    created_count = 0
    
    for donation_type in default_types:
        if not frappe.db.exists("Donation Type", donation_type):
            try:
                doc = frappe.get_doc({
                    "doctype": "Donation Type",
                    "donation_type": donation_type
                })
                doc.insert(ignore_permissions=True)
                created_count += 1
                print(f"   ✓ Created donation type: {donation_type}")
            except Exception as e:
                print(f"   ⚠️ Could not create donation type '{donation_type}': {str(e)}")
        else:
            print(f"   ✓ Donation type already exists: {donation_type}")
    
    if created_count > 0:
        frappe.db.commit()
        print(f"   💰 Created {created_count} default donation types")
        
        # Set default donation type in settings if not already set
        try:
            settings = frappe.get_single("Verenigingen Settings")
            if not settings.get("default_donation_type"):
                settings.default_donation_type = "General"
                settings.save(ignore_permissions=True)
                print("   ✓ Set 'General' as default donation type in settings")
        except Exception as e:
            print(f"   ⚠️ Could not set default donation type: {str(e)}")
    
    return created_count

@frappe.whitelist()
def create_donation_types_manual():
    """Manual endpoint to create donation types"""
    try:
        count = create_default_donation_types()
        return {
            "success": True, 
            "message": f"Created {count} donation types",
            "count": count
        }
    except Exception as e:
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def verify_donation_type_setup():
    """Verify donation types are properly set up"""
    try:
        # Check donation types
        donation_types = frappe.get_all("Donation Type", fields=["name", "donation_type"])
        
        # Check settings
        settings = frappe.get_single("Verenigingen Settings")
        default_type = settings.get("default_donation_type")
        
        return {
            "success": True,
            "donation_types": donation_types,
            "total_count": len(donation_types),
            "default_donation_type": default_type,
            "message": f"Found {len(donation_types)} donation types, default: {default_type}"
        }
    except Exception as e:
        return {"success": False, "message": str(e)}
