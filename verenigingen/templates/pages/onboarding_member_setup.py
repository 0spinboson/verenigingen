import frappe

def get_context(context):
    """Context for the member setup onboarding page"""
    if hasattr(context, '__setattr__'):
        context.no_cache = 1
    
    # Check if we have any existing members
    member_count = frappe.db.count("Member")
    
    # Check if test members exist
    test_members = frappe.get_all("Member",
        filters={"email": ["like", "%@email.nl"]},
        fields=["name", "full_name", "status"],
        limit=10
    )
    
    # Check if membership types exist
    membership_types = frappe.get_all("Membership Type", 
        fields=["name", "membership_type_name"],
        limit=5
    )
    
    context.member_count = member_count
    context.test_members = test_members
    context.has_test_data = len(test_members) > 0
    context.membership_types = membership_types
    context.has_membership_types = len(membership_types) > 0
    context.page_title = "Member Setup - Get Started"
    
    return context

@frappe.whitelist()
def generate_test_applications():
    """Generate test members including Noa"""
    try:
        # Check if members already exist
        existing_test_members = frappe.get_all("Member", 
            filters={"email": ["like", "%@email.nl"]},
            fields=["name", "full_name"]
        )
        
        if existing_test_members:
            return {
                "success": True,
                "message": f"✅ Test members already exist! Found {len(existing_test_members)} test members.",
                "summary": {"created": 0, "existing": len(existing_test_members)},
                "existing_members": [m.full_name for m in existing_test_members]
            }
        
        # Create test members directly
        test_members = [
            {
                "first_name": "Jan",
                "preposition": "van den",
                "last_name": "Berg",
                "email": "jan.vandenberg@email.nl",
                "mobile": "06-12345678",
                "postal_code": "1234 AB",
                "city": "Utrecht",
                "birth_date": "1985-05-01",
                "gender": "Male"
            },
            {
                "first_name": "Sophie",
                "last_name": "Jansen",
                "email": "sophie.jansen@email.nl",
                "mobile": "06-23456789",
                "postal_code": "2345 BC",
                "city": "Amsterdam",
                "birth_date": "1992-08-15",
                "gender": "Female"
            },
            {
                "first_name": "Eva",
                "last_name": "Mulder",
                "email": "eva.mulder@email.nl",
                "mobile": "06-89012345",
                "postal_code": "3012 CD",
                "city": "Rotterdam",
                "birth_date": "1999-06-18",
                "gender": "Female"
            },
            {
                "first_name": "Noa",
                "last_name": "Brouwer",
                "email": "noa.brouwer@email.nl",
                "mobile": "06-01234567",
                "postal_code": "1012 JK",
                "city": "Nijmegen",
                "birth_date": "2003-04-22",
                "gender": "Female"
            }
        ]
        
        created_members = []
        errors = []
        
        for member_data in test_members:
            try:
                # Create full name
                name_parts = [member_data["first_name"]]
                if member_data.get("preposition"):
                    name_parts.append(member_data["preposition"])
                name_parts.append(member_data["last_name"])
                full_name = " ".join(name_parts)
                
                # Create member with pending application status
                member = frappe.get_doc({
                    "doctype": "Member",
                    "first_name": member_data["first_name"],
                    "last_name": member_data["last_name"],
                    "full_name": full_name,
                    "email": member_data["email"],
                    "mobile": member_data["mobile"],
                    "postal_code": member_data["postal_code"],
                    "city": member_data["city"],
                    "birth_date": member_data["birth_date"],
                    "gender": member_data["gender"],
                    "status": "Pending",
                    "application_status": "Pending"
                })
                
                # Add preposition if exists
                if member_data.get("preposition"):
                    member.preposition = member_data["preposition"]
                
                member.insert(ignore_permissions=True)
                created_members.append({
                    "name": member.name,
                    "full_name": full_name,
                    "email": member.email
                })
                
            except Exception as e:
                errors.append({
                    "member": f"{member_data['first_name']} {member_data['last_name']}",
                    "error": str(e)
                })
        
        # Mark the onboarding step as complete if members were created
        if created_members:
            try:
                step = frappe.get_doc('Onboarding Step', 'Verenigingen-Create-Member')
                step.is_complete = 1
                step.save(ignore_permissions=True)
                frappe.db.commit()
            except:
                pass  # If step doesn't exist, ignore
        
        return {
            "success": True,
            "message": f"✅ Successfully created {len(created_members)} test members including Noa!",
            "summary": {
                "created": len(created_members),
                "errors": len(errors)
            },
            "created_members": created_members,
            "errors": errors
        }
        
    except Exception as e:
        frappe.log_error(f"Test member generation failed: {str(e)}")
        return {
            "success": False,
            "message": f"❌ Error generating test members: {str(e)}"
        }

@frappe.whitelist()
def get_test_status():
    """Get status of test members"""
    try:
        test_members = frappe.get_all("Member",
            filters={"email": ["like", "%@email.nl"]},
            fields=["name", "full_name", "email", "status", "creation"]
        )
        
        # Group by status
        status_summary = {}
        for member in test_members:
            status = member.status or "Unknown"
            if status not in status_summary:
                status_summary[status] = 0
            status_summary[status] += 1
        
        return {
            "total": len(test_members),
            "by_status": status_summary,
            "members": test_members
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }

@frappe.whitelist()
def update_test_members_to_pending():
    """Update existing test members to have pending application status"""
    try:
        test_members = frappe.get_all("Member",
            filters={"email": ["like", "%@email.nl"]},
            fields=["name"]
        )
        
        updated_count = 0
        for member in test_members:
            try:
                frappe.db.set_value("Member", member.name, "status", "Pending")
                frappe.db.set_value("Member", member.name, "application_status", "Pending")
                updated_count += 1
            except Exception as e:
                frappe.log_error(f"Failed to update test member {member.name}: {str(e)}")
        
        frappe.db.commit()
        
        return {
            "success": True,
            "updated": updated_count,
            "message": f"Updated {updated_count} test members to have pending application status"
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }

@frappe.whitelist()
def cleanup_test_data():
    """Clean up test members"""
    try:
        test_members = frappe.get_all("Member",
            filters={"email": ["like", "%@email.nl"]},
            fields=["name"]
        )
        
        deleted_count = 0
        for member in test_members:
            try:
                frappe.delete_doc("Member", member.name, ignore_permissions=True)
                deleted_count += 1
            except Exception as e:
                frappe.log_error(f"Failed to delete test member {member.name}: {str(e)}")
        
        return {
            "success": True,
            "deleted": deleted_count,
            "message": f"Deleted {deleted_count} test members"
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }