import frappe
from frappe import _
from frappe.utils import today, cint, now
import random


@frappe.whitelist()
def is_chapter_management_enabled():
    """Check if chapter management is enabled in settings"""
    try:
        return frappe.db.get_single_value("Verenigingen Settings", "enable_chapter_management") == 1
    except:
        return True


@frappe.whitelist()
def get_board_memberships(member_name):
    """Get board memberships for a member with proper permission handling"""
    if not is_chapter_management_enabled():
        return []
        
    board_memberships = frappe.db.sql("""
        SELECT cbm.parent as chapter, cbm.chapter_role as role,
               cbm.from_date as start_date, cbm.to_date as end_date
        FROM `tabChapter Board Member` cbm
        JOIN `tabVolunteer` v ON cbm.volunteer = v.name
        WHERE v.member = %s AND cbm.is_active = 1
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
    
    for mandate in active_mandates:
        if mandate.expiry_date:
            days_to_expiry = frappe.utils.date_diff(mandate.expiry_date, today())
            if 0 < days_to_expiry <= 30:
                result["expiring_soon"] = True
                break
    
    return result


@frappe.whitelist()
def update_member_payment_history(doc, method=None):
    """Update payment history for member when a payment entry is modified"""
    if doc.party_type != "Customer":
        return
        
    members = frappe.get_all(
        "Member",
        filters={"customer": doc.party},
        fields=["name"]
    )
    
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
        
    members = frappe.get_all(
        "Member",
        filters={"customer": doc.customer},
        fields=["name"]
    )
    
    for member_doc in members:
        try:
            member = frappe.get_doc("Member", member_doc.name)
            member.load_payment_history()
            member.save(ignore_permissions=True)
        except Exception as e:
            frappe.log_error(f"Failed to update payment history for Member {member_doc.name}: {str(e)}")


@frappe.whitelist()
def add_manual_payment_record(member, amount, payment_date=None, payment_method=None, notes=None):
    """Manually add a payment record (e.g., for cash donations)"""
    if not member or not amount:
        frappe.throw(_("Member and amount are required"))
        
    member_doc = frappe.get_doc("Member", member)
    
    if not member_doc.customer:
        frappe.throw(_("Member must have a customer record"))
        
    payment = frappe.new_doc("Payment Entry")
    payment.payment_type = "Receive"
    payment.party_type = "Customer"
    payment.party = member_doc.customer
    payment.posting_date = payment_date or today()
    payment.paid_amount = float(amount)
    payment.received_amount = float(amount)
    payment.mode_of_payment = payment_method or "Cash"
    
    settings = frappe.get_single("Verenigingen Settings")
    payment.company = settings.company or frappe.defaults.get_global_default('company')
    
    payment.paid_from = frappe.get_value("Company", payment.company, "default_receivable_account")
    payment.paid_to = settings.donation_payment_account or frappe.get_value("Company", payment.company, "default_cash_account")
    
    payment.remarks = notes or "Manual donation entry"
    
    payment.insert(ignore_permissions=True)
    payment.submit()
    
    member_doc.load_payment_history()
    member_doc.save(ignore_permissions=True)
    
    return payment.name


@frappe.whitelist()
def get_linked_donations(member):
    """Find linked donor record for a member to view donations"""
    if not member:
        return {"success": False, "message": "No member specified"}
        
    member_doc = frappe.get_doc("Member", member)
    if member_doc.email:
        donors = frappe.get_all(
            "Donor",
            filters={"donor_email": member_doc.email},
            fields=["name"]
        )
        
        if donors:
            return {"success": True, "donor": donors[0].name}
            
    if member_doc.full_name:
        donors = frappe.get_all(
            "Donor",
            filters={"donor_name": ["like", f"%{member_doc.full_name}%"]},
            fields=["name"]
        )
        
        if donors:
            return {"success": True, "donor": donors[0].name}
    
    return {"success": False, "message": "No donor record found for this member"}


@frappe.whitelist()
def create_donor_from_member(member):
    """Create a donor record from a member for tracking donations"""
    if not member:
        frappe.throw(_("No member specified"))
        
    member_doc = frappe.get_doc("Member", member)
    
    if member_doc.email:
        existing_donor = frappe.db.exists("Donor", {"donor_email": member_doc.email})
        if existing_donor:
            return existing_donor
    
    donor = frappe.new_doc("Donor")
    donor.donor_name = member_doc.full_name or member_doc.name
    donor.donor_type = "Individual"
    donor.donor_email = member_doc.email
    donor.contact_person = member_doc.full_name or member_doc.name
    donor.phone = member_doc.contact_number or member_doc.phone
    
    donor.donor_category = "Regular Donor"
    
    if member_doc.email:
        donor.preferred_communication_method = "Email"
    elif member_doc.contact_number:
        donor.preferred_communication_method = "Phone"
    
    donor.insert(ignore_permissions=True)
    
    frappe.msgprint(_("Donor record {0} created from member").format(donor.name))
    return donor.name


@frappe.whitelist()
def create_sepa_mandate_from_bank_details(member, iban, bic=None, account_holder_name=None, mandate_type="RCUR", sign_date=None, used_for_memberships=1, used_for_donations=0):
    """Create a new SEPA mandate based on bank details already entered"""
    if not member or not iban:
        frappe.throw(_("Member and IBAN are required"))
    
    if not sign_date:
        sign_date = today()
    
    member_doc = frappe.get_doc("Member", member)
    if not account_holder_name:
        account_holder_name = member_doc.full_name
    
    timestamp = now().replace(' ', '').replace('-', '').replace(':', '')[:14]
    mandate_id = f"M-{member_doc.member_id}-{timestamp}"
    
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
    
    mandate.used_for_memberships = 1 if used_for_memberships else 0
    mandate.used_for_donations = 1 if used_for_donations else 0
    
    mandate.status = "Active"
    mandate.is_active = 1
    
    mandate.insert(ignore_permissions=True)
    
    member_doc.append("sepa_mandates", {
        "sepa_mandate": mandate.name,
        "is_current": 1
    })
    
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
    
    chapters = frappe.get_all(
        "Chapter",
        filters={"published": 1},
        fields=["name", "region", "postal_codes"]
    )
    
    matching_chapters = []
    
    for chapter in chapters:
        if not chapter.get("postal_codes"):
            continue
            
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
def check_mandate_iban_mismatch(member, current_iban):
    """Check if we should show SEPA mandate creation popup"""
    frappe.logger().debug(f"check_mandate_iban_mismatch called with member={member}, current_iban={current_iban}")
    
    if not member or not current_iban:
        return {"show_popup": False, "error": "Missing parameters"}
    
    current_iban_normalized = current_iban.replace(' ', '').upper()
    
    existing_mandates = frappe.get_all(
        "SEPA Mandate",
        filters={
            "member": member,
            "status": "Active",
            "is_active": 1
        },
        fields=["name", "mandate_id", "iban", "creation"],
        order_by="creation desc"
    )
    
    frappe.logger().debug(f"Found {len(existing_mandates)} active mandates")
    
    if not existing_mandates:
        frappe.logger().debug("No existing mandates found - showing first-time setup popup")
        return {
            "show_popup": True,
            "reason": "no_existing_mandates",
            "scenario": "first_time_setup",
            "message": "No SEPA mandate found. Create one for Direct Debit payments?"
        }
    
    for mandate in existing_mandates:
        mandate_iban_normalized = mandate.iban.replace(' ', '').upper() if mandate.iban else ''
        
        frappe.logger().debug(f"Comparing mandate IBAN '{mandate_iban_normalized}' with current '{current_iban_normalized}'")
        
        if mandate_iban_normalized and mandate_iban_normalized != current_iban_normalized:
            frappe.logger().debug(f"IBAN mismatch found in mandate {mandate.name}")
            return {
                "show_popup": True,
                "existing_mandate": mandate.name,
                "existing_iban": mandate.iban,
                "current_iban": current_iban,
                "reason": "iban_mismatch",
                "scenario": "bank_account_change",
                "message": f"Your IBAN differs from existing mandate. Create new mandate?"
            }
    
    frappe.logger().debug("All existing mandates have matching IBAN")
    return {
        "show_popup": False, 
        "reason": "iban_matches",
        "scenario": "no_change_needed"
    }


@frappe.whitelist()
def derive_bic_from_iban(iban):
    """Derive BIC/SWIFT code from IBAN for supported countries"""
    if not iban:
        return {"bic": None}
    
    iban = iban.replace(' ', '').upper()
    
    if len(iban) < 8:
        return {"bic": None}
    
    country_code = iban[:2]
    
    bank_code_map = {
        'NL': (4, 4),
        'DE': (4, 8),
        'BE': (4, 3),
        'FR': (4, 5),
        'IT': (5, 5),
        'ES': (4, 4),
        'GB': (4, 6),
    }
    
    if country_code not in bank_code_map:
        return {"bic": None}
    
    start_pos, length = bank_code_map[country_code]
    if len(iban) < start_pos + length:
        return {"bic": None}
    
    bank_code = iban[start_pos:start_pos+length]
    
    bank_to_bic = {
        # Netherlands
        'ABNA': 'ABNANL2A',
        'RABO': 'RABONL2U',
        'INGB': 'INGBNL2A',
        'SNSB': 'SNSBNL2A',
        'TRIO': 'TRIONL2U',
        'BUNQ': 'BUNQNL2A',
        'ASNB': 'ASNBNL21',
        
        # Germany
        '10010010': 'PBNKDEFF',
        '37040044': 'COBADEFF',
        '50010517': 'INGDDEFF',
        '70020270': 'HYVEDEMM',
        '10000000': 'MARKDEF1100',
    }
    
    bic = bank_to_bic.get(bank_code)
    
    if not bic and len(bank_code) >= 4:
        bic = bank_code[:4] + country_code + 'X'
    
    return {"bic": bic}


@frappe.whitelist()
def get_member_termination_status(member):
    """Get termination status for a member"""
    pending_requests = frappe.get_all(
        "Membership Termination Request",
        filters={
            "member": member,
            "status": ["in", ["Draft", "Pending Approval", "Approved"]]
        },
        fields=["name", "status", "termination_type", "request_date"]
    )
    
    executed_requests = frappe.get_all(
        "Membership Termination Request",
        filters={
            "member": member,
            "status": "Executed"
        },
        fields=["name", "termination_type", "execution_date"],
        limit=1,
        order_by="execution_date desc"
    )
    
    return {
        "pending_requests": pending_requests,
        "executed_requests": executed_requests,
        "is_terminated": len(executed_requests) > 0
    }


def update_termination_status_display(doc, method=None):
    """Update member fields to display current termination status"""
    member = doc
    
    executed_termination = frappe.get_all(
        "Membership Termination Request",
        filters={
            "member": member.name,
            "status": "Executed"
        },
        fields=["name", "termination_type", "execution_date", "termination_date"],
        order_by="execution_date desc",
        limit=1
    )
    
    pending_termination = frappe.get_all(
        "Membership Termination Request",
        filters={
            "member": member.name,
            "status": ["in", ["Draft", "Pending Approval", "Approved"]]
        },
        fields=["name", "status", "termination_type", "request_date"],
        order_by="request_date desc",
        limit=1
    )
    
    if executed_termination:
        term_data = executed_termination[0]
        
        if hasattr(member, 'termination_status'):
            member.termination_status = "Terminated"
        
        if hasattr(member, 'termination_date'):
            member.termination_date = term_data.execution_date or term_data.termination_date
        
        if hasattr(member, 'termination_type'):
            member.termination_type = term_data.termination_type
        
        if hasattr(member, 'termination_request'):
            member.termination_request = term_data.name
        
        if hasattr(member, 'status') and member.status != "Terminated":
            member.status = "Terminated"
        
        if hasattr(member, 'termination_notes'):
            member.termination_notes = f"Terminated on {term_data.execution_date} - Type: {term_data.termination_type}"
    
    elif pending_termination:
        pend_data = pending_termination[0]
        
        if hasattr(member, 'termination_status'):
            status_map = {
                "Draft": "Termination Draft",
                "Pending Approval": "Termination Pending Approval",
                "Approved": "Termination Approved"
            }
            member.termination_status = status_map.get(pend_data.status, "Termination Pending")
        
        if hasattr(member, 'pending_termination_type'):
            member.pending_termination_type = pend_data.termination_type
        
        if hasattr(member, 'pending_termination_request'):
            member.pending_termination_request = pend_data.name
    
    else:
        if hasattr(member, 'termination_status'):
            member.termination_status = "Active"
        
        if hasattr(member, 'termination_date'):
            member.termination_date = None
        
        if hasattr(member, 'termination_type'):
            member.termination_type = None
        
        if hasattr(member, 'termination_request'):
            member.termination_request = None
        
        if hasattr(member, 'pending_termination_type'):
            member.pending_termination_type = None
        
        if hasattr(member, 'pending_termination_request'):
            member.pending_termination_request = None


@frappe.whitelist()
def reset_member_id_counter(counter_value):
    """Reset the member ID counter (called from client-side)"""
    from verenigingen.verenigingen.doctype.member.member_id_manager import MemberIDManager
    
    if not frappe.has_permission("Member", "write"):
        frappe.throw(_("Insufficient permissions"))
    
    if not frappe.user.has_role("System Manager"):
        frappe.throw(_("Only System Managers can reset the member ID counter"))
    
    counter_value = cint(counter_value)
    if counter_value <= 0:
        frappe.throw(_("Counter value must be greater than 0"))
    
    MemberIDManager.reset_counter(counter_value)
    
    return {
        "success": True,
        "message": _("Member ID counter reset to {0}").format(counter_value)
    }


@frappe.whitelist()
def get_next_member_id_preview():
    """Get the next member ID that would be assigned"""
    from verenigingen.verenigingen.doctype.member.member_id_manager import MemberIDManager
    
    if not frappe.has_permission("Member", "read"):
        frappe.throw(_("Insufficient permissions"))
    
    counter_key = "member_id_counter"
    current_counter = frappe.cache().get(counter_key)
    
    if current_counter is None:
        current_counter = MemberIDManager._initialize_counter()
    
    return {
        "next_id": current_counter + 1,
        "current_counter": current_counter
    }


@frappe.whitelist()
def create_and_link_mandate_enhanced(member, mandate_id, iban, bic=None, account_holder_name=None, 
                                   mandate_type="RCUR", sign_date=None, 
                                   used_for_memberships=1, used_for_donations=0,
                                   notes=None, replace_mandate=None):
    """Enhanced version of create_and_link_mandate with better mandate management"""
    if not member or not iban or not mandate_id:
        frappe.throw(_("Member, IBAN, and Mandate ID are required"))
    
    if not sign_date:
        sign_date = today()
    
    member_doc = frappe.get_doc("Member", member)
    if not account_holder_name:
        account_holder_name = member_doc.full_name
    
    if frappe.db.exists("SEPA Mandate", {"mandate_id": mandate_id}):
        frappe.throw(_("Mandate ID {0} already exists. Please use a different reference.").format(mandate_id))
    
    if replace_mandate:
        try:
            old_mandate = frappe.get_doc("SEPA Mandate", replace_mandate)
            old_mandate.status = "Cancelled"
            old_mandate.is_active = 0
            old_mandate.cancelled_date = today()
            old_mandate.cancelled_reason = "Bank account change"
            if notes:
                old_mandate.notes = (old_mandate.notes or '') + f"\nReplaced on {today()}: {notes}"
            old_mandate.save(ignore_permissions=True)
            frappe.logger().debug(f"Marked mandate {replace_mandate} as replaced")
        except Exception as e:
            frappe.logger().error(f"Error replacing mandate {replace_mandate}: {str(e)}")
    
    existing_mandates = frappe.get_all(
        "SEPA Mandate",
        filters={
            "member": member,
            "status": "Active",
            "is_active": 1,
            "name": ["!=", replace_mandate] if replace_mandate else ["!=", ""]
        },
        fields=["name", "used_for_memberships", "used_for_donations"]
    )
    
    for mandate_data in existing_mandates:
        mandate = frappe.get_doc("SEPA Mandate", mandate_data.name)
        should_suspend = False
        
        if used_for_memberships and mandate.used_for_memberships:
            should_suspend = True
            
        if used_for_donations and mandate.used_for_donations:
            should_suspend = True
            
        if should_suspend:
            mandate.status = "Superseded"
            mandate.is_active = 0
            mandate.superseded_date = today()
            mandate.superseded_by = mandate_id
            mandate.save(ignore_permissions=True)
            frappe.logger().debug(f"Superseded mandate {mandate.name}")
    
    mandate = frappe.new_doc("SEPA Mandate")
    mandate.mandate_id = mandate_id
    mandate.member = member
    mandate.member_name = member_doc.full_name
    mandate.account_holder_name = account_holder_name
    mandate.iban = iban
    
    if not bic:
        bic_result = derive_bic_from_iban(iban)
        if bic_result and bic_result.get('bic'):
            bic = bic_result['bic']
    
    if bic:
        mandate.bic = bic
        
    mandate.sign_date = sign_date
    mandate.mandate_type = mandate_type
    
    mandate.used_for_memberships = 1 if used_for_memberships else 0
    mandate.used_for_donations = 1 if used_for_donations else 0
    
    mandate.status = "Active"
    mandate.is_active = 1
    
    if notes:
        mandate.notes = notes
        
    creation_notes = f"Created via member form on {today()}"
    if replace_mandate:
        creation_notes += f" (replacing {replace_mandate})"
    
    mandate.notes = (mandate.notes + "\n" + creation_notes) if mandate.notes else creation_notes
    
    mandate.insert(ignore_permissions=True)
    
    frappe.db.delete("Member SEPA Mandate Link", {
        "parent": member,
        "sepa_mandate": mandate.name
    })
    
    frappe.db.sql("""
        UPDATE `tabMember SEPA Mandate Link`
        SET is_current = 0
        WHERE parent = %s
    """, (member,))
    
    frappe.db.sql("""
        INSERT INTO `tabMember SEPA Mandate Link`
        (name, parent, parentfield, parenttype, sepa_mandate, is_current, mandate_reference, status, valid_from)
        VALUES (%s, %s, 'sepa_mandates', 'Member', %s, 1, %s, %s, %s)
    """, (
        frappe.generate_hash(), 
        member, 
        mandate.name, 
        mandate.mandate_id, 
        'Active', 
        mandate.sign_date
    ))
    
    frappe.db.commit()
    frappe.clear_document_cache("Member", member)
    
    frappe.logger().debug(f"Created and linked mandate {mandate.name} with ID {mandate_id}")
    
    return {
        "mandate_name": mandate.name,
        "mandate_id": mandate_id,
        "replaced_mandate": replace_mandate,
        "superseded_mandates": len([m for m in existing_mandates if used_for_memberships and m.used_for_memberships or used_for_donations and m.used_for_donations])
    }


@frappe.whitelist()
def generate_mandate_reference(member):
    """Generate a suggested mandate reference for a member"""
    member_doc = frappe.get_doc("Member", member)
    
    member_id = member_doc.member_id or member_doc.name.replace('Assoc-Member-', '').replace('-', '')
    
    from datetime import datetime
    now_dt = datetime.now()
    date_str = now_dt.strftime('%Y%m%d')
    
    existing_mandates_today = frappe.get_all(
        "SEPA Mandate",
        filters={
            "mandate_id": ["like", f"M-{member_id}-{date_str}-%"],
            "creation": [">=", now_dt.strftime('%Y-%m-%d 00:00:00')]
        },
        fields=["mandate_id"]
    )
    
    sequence = len(existing_mandates_today) + 1
    sequence_str = str(sequence).zfill(3)
    
    suggested_reference = f"M-{member_id}-{date_str}-{sequence_str}"
    
    return {"mandate_reference": suggested_reference}


@frappe.whitelist()
def validate_mandate_reference(mandate_id):
    """Validate if a mandate reference is available"""
    exists = frappe.db.exists("SEPA Mandate", {"mandate_id": mandate_id})
    
    return {
        "available": not bool(exists),
        "exists": bool(exists)
    }


@frappe.whitelist()
def check_and_handle_sepa_mandate(member, iban):
    """Check if a mandate exists for this IBAN and handle accordingly"""
    member_doc = frappe.get_doc("Member", member)
    
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
        mandate_doc = frappe.get_doc("SEPA Mandate", matching_mandates[0].name)
        
        is_current = False
        for mandate_link in member_doc.sepa_mandates:
            if mandate_link.sepa_mandate == mandate_doc.name and mandate_link.is_current:
                is_current = True
                break
        
        if not is_current:
            for mandate_link in member_doc.sepa_mandates:
                if mandate_link.sepa_mandate == mandate_doc.name:
                    mandate_link.is_current = 1
                else:
                    mandate_link.is_current = 0
            
            member_doc.save(ignore_permissions=True)
            return {"action": "use_existing", "mandate": mandate_doc.name}
        else:
            return {"action": "none_needed"}
    else:
        return {"action": "create_new"}


@frappe.whitelist()
def need_new_mandate(member, iban):
    """Check if we need to create a new mandate for this IBAN"""
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
    
    return {"need_new": not bool(matching_mandates)}


@frappe.whitelist()
def create_and_link_mandate(member, iban, bic=None, account_holder_name=None, 
                           mandate_type="RCUR", sign_date=None, 
                           used_for_memberships=1, used_for_donations=0):
    """Create a new mandate and link it to the member in one atomic operation"""
    if not member or not iban:
        frappe.throw(_("Member and IBAN are required"))
    
    if not sign_date:
        sign_date = today()
    
    member_doc = frappe.get_doc("Member", member)
    if not account_holder_name:
        account_holder_name = member_doc.full_name
    
    existing_mandates = frappe.get_all(
        "SEPA Mandate",
        filters={
            "member": member,
            "status": "Active",
            "is_active": 1
        },
        fields=["name"]
    )
    
    if used_for_memberships:
        for mandate_data in existing_mandates:
            mandate = frappe.get_doc("SEPA Mandate", mandate_data.name)
            if mandate.used_for_memberships:
                mandate.status = "Suspended"
                mandate.is_active = 0
                mandate.save(ignore_permissions=True)
    
    if used_for_donations:
        for mandate_data in existing_mandates:
            mandate = frappe.get_doc("SEPA Mandate", mandate_data.name)
            if mandate.used_for_donations and mandate.status == "Active":
                mandate.status = "Suspended"
                mandate.is_active = 0
                mandate.save(ignore_permissions=True)
    
    timestamp = now().replace(' ', '').replace('-', '').replace(':', '')[:14]
    mandate_id = f"M-{member_doc.member_id}-{timestamp}"
    
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
    
    mandate.used_for_memberships = 1 if used_for_memberships else 0
    mandate.used_for_donations = 1 if used_for_donations else 0
    
    mandate.status = "Active"
    mandate.is_active = 1
    
    mandate.insert(ignore_permissions=True)
    
    frappe.db.delete("Member SEPA Mandate Link", {
        "parent": member,
        "sepa_mandate": mandate.name
    })
    
    frappe.db.sql("""
        UPDATE `tabMember SEPA Mandate Link`
        SET is_current = 0
        WHERE parent = %s
    """, (member,))
    
    frappe.db.sql("""
        INSERT INTO `tabMember SEPA Mandate Link`
        (name, parent, parentfield, parenttype, sepa_mandate, is_current, mandate_reference, status, valid_from)
        VALUES (%s, %s, 'sepa_mandates', 'Member', %s, 1, %s, %s, %s)
    """, (frappe.generate_hash(), member, mandate.name, mandate.mandate_id, 'Active', mandate.sign_date))
    
    frappe.db.commit()
    frappe.clear_document_cache("Member", member)
    
    return mandate.name


@frappe.whitelist()
def debug_postal_code_matching(postal_code):
    """Debug function to test postal code matching"""
    if not postal_code:
        return {"error": "No postal code provided"}
    
    chapters = frappe.get_all(
        "Chapter",
        filters={"published": 1},
        fields=["name", "region", "postal_codes"]
    )
    
    results = {
        "postal_code": postal_code,
        "total_chapters": len(chapters),
        "matching_chapters": [],
        "non_matching_chapters": []
    }
    
    for chapter in chapters:
        if not chapter.get("postal_codes"):
            results["non_matching_chapters"].append({
                "name": chapter.name,
                "reason": "No postal codes defined"
            })
            continue
            
        try:
            chapter_doc = frappe.get_doc("Chapter", chapter.name)
            matches = chapter_doc.matches_postal_code(postal_code)
            
            if matches:
                results["matching_chapters"].append({
                    "name": chapter.name,
                    "region": chapter.region,
                    "postal_codes": chapter.postal_codes
                })
            else:
                results["non_matching_chapters"].append({
                    "name": chapter.name,
                    "postal_codes": chapter.postal_codes,
                    "reason": "No match"
                })
        except Exception as e:
            results["non_matching_chapters"].append({
                "name": chapter.name,
                "reason": f"Error: {str(e)}"
            })
    
    return results


def sync_member_counter_with_settings(doc, method=None):
    """Called when Verenigingen Settings is updated"""
    from verenigingen.verenigingen.doctype.member.member_id_manager import MemberIDManager
    
    if doc.doctype != "Verenigingen Settings":
        return
    
    if doc.has_value_changed("member_id_start"):
        old_start = doc.get_db_value("member_id_start") or 1000
        new_start = cint(doc.member_id_start) or 1000
        
        if new_start > old_start:
            MemberIDManager.sync_counter_with_settings()