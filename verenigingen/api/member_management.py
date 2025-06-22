"""
Member management API endpoints
"""
import frappe
from frappe import _

@frappe.whitelist()
def assign_member_to_chapter(member_name, chapter_name):
    """Assign a member to a specific chapter using centralized manager"""
    try:
        # Validate inputs
        if not member_name or not chapter_name:
            return {
                "success": False,
                "error": "Member name and chapter name are required"
            }
        
        # Check permissions
        if not can_assign_member_to_chapter(member_name, chapter_name):
            return {
                "success": False,
                "error": "You don't have permission to assign members to this chapter"
            }
        
        # Use centralized chapter membership manager for proper history tracking
        from verenigingen.utils.chapter_membership_manager import ChapterMembershipManager
        
        result = ChapterMembershipManager.assign_member_to_chapter(
            member_id=member_name,
            chapter_name=chapter_name,
            reason="Assigned via admin interface",
            assigned_by=frappe.session.user
        )
        
        # Adapt result format for backward compatibility
        if result.get('success'):
            return {
                "success": True,
                "message": f"Member {member_name} has been assigned to {chapter_name}",
                "new_chapter": chapter_name
            }
        else:
            return result
        
    except Exception as e:
        frappe.log_error(f"Error assigning member to chapter: {str(e)}", "Member Assignment Error")
        return {
            "success": False,
            "error": f"Failed to assign member to chapter: {str(e)}"
        }

def can_assign_member_to_chapter(member_name, chapter_name):
    """Check if current user can assign a member to a specific chapter"""
    user = frappe.session.user
    
    # System managers and Association/Membership managers can assign anyone
    admin_roles = ["System Manager", "Verenigingen Administrator", "Membership Manager"]
    if any(role in frappe.get_roles(user) for role in admin_roles):
        return True
    
    # Get user's member record
    user_member = frappe.db.get_value("Member", {"user": user}, "name")
    if not user_member:
        return False
    
    # Check if user has admin/membership permissions in the target chapter
    try:
        volunteer_records = frappe.get_all("Volunteer", filters={"member": user_member}, fields=["name"])
        
        for volunteer_record in volunteer_records:
            board_positions = frappe.get_all(
                "Chapter Board Member",
                filters={
                    "parent": chapter_name,
                    "volunteer": volunteer_record.name,
                    "is_active": 1
                },
                fields=["chapter_role"]
            )
            
            for position in board_positions:
                try:
                    role_doc = frappe.get_doc("Chapter Role", position.chapter_role)
                    if role_doc.permissions_level in ["Admin", "Membership"]:
                        return True
                except Exception:
                    continue
        
        # Check if user has national board access
        try:
            settings = frappe.get_single("Verenigingen Settings")
            if hasattr(settings, 'national_board_chapter') and settings.national_board_chapter:
                national_board_positions = frappe.get_all(
                    "Chapter Board Member",
                    filters={
                        "parent": settings.national_board_chapter,
                        "volunteer": [v.name for v in volunteer_records],
                        "is_active": 1
                    },
                    fields=["chapter_role"]
                )
                
                for position in national_board_positions:
                    try:
                        role_doc = frappe.get_doc("Chapter Role", position.chapter_role)
                        if role_doc.permissions_level in ["Admin", "Membership"]:
                            return True
                    except Exception:
                        continue
        except Exception:
            pass
            
    except Exception:
        pass
    
    return False

@frappe.whitelist()
def get_members_without_chapter():
    """Get list of members without chapter assignment"""
    try:
        # Check permissions
        if not can_view_members_without_chapter():
            return {
                "success": False,
                "error": "You don't have permission to view this data"
            }
        
        # Get members who are not in any Chapter Member records
        members_with_chapters = frappe.get_all(
            "Chapter Member",
            filters={"enabled": 1},
            fields=["member"],
            distinct=True
        )
        
        excluded_members = [m.member for m in members_with_chapters]
        
        # Get members without chapter
        member_filters = {}
        if excluded_members:
            member_filters["name"] = ["not in", excluded_members]
            
        members = frappe.get_all(
            "Member",
            filters=member_filters,
            fields=[
                "name", "full_name", "email", "status", "creation"
            ],
            order_by="creation desc"
        )
        
        return {
            "success": True,
            "members": members,
            "count": len(members)
        }
        
    except Exception as e:
        frappe.log_error(f"Error getting members without chapter: {str(e)}", "Members Without Chapter Error")
        return {
            "success": False,
            "error": f"Failed to get members: {str(e)}"
        }

def can_view_members_without_chapter():
    """Check if current user can view members without chapter"""
    user = frappe.session.user
    
    # System managers and Association/Membership managers can view
    admin_roles = ["System Manager", "Verenigingen Administrator", "Membership Manager"]
    if any(role in frappe.get_roles(user) for role in admin_roles):
        return True
    
    # Chapter board members with admin/membership permissions can view
    user_member = frappe.db.get_value("Member", {"user": user}, "name")
    if not user_member:
        return False
    
    try:
        volunteer_records = frappe.get_all("Volunteer", filters={"member": user_member}, fields=["name"])
        
        for volunteer_record in volunteer_records:
            board_positions = frappe.get_all(
                "Chapter Board Member",
                filters={
                    "volunteer": volunteer_record.name,
                    "is_active": 1
                },
                fields=["chapter_role"]
            )
            
            for position in board_positions:
                try:
                    role_doc = frappe.get_doc("Chapter Role", position.chapter_role)
                    if role_doc.permissions_level in ["Admin", "Membership"]:
                        return True
                except Exception:
                    continue
    except Exception:
        pass
    
    return False

@frappe.whitelist()
def bulk_assign_members_to_chapters(assignments):
    """Bulk assign multiple members to chapters
    
    Args:
        assignments: List of dicts with member_name and chapter_name
    """
    try:
        if not assignments:
            return {
                "success": False,
                "error": "No assignments provided"
            }
        
        results = []
        success_count = 0
        error_count = 0
        
        for assignment in assignments:
            member_name = assignment.get("member_name")
            chapter_name = assignment.get("chapter_name")
            
            result = assign_member_to_chapter(member_name, chapter_name)
            results.append({
                "member_name": member_name,
                "chapter_name": chapter_name,
                "result": result
            })
            
            if result.get("success"):
                success_count += 1
            else:
                error_count += 1
        
        return {
            "success": True,
            "message": f"Processed {len(assignments)} assignments: {success_count} successful, {error_count} failed",
            "results": results,
            "success_count": success_count,
            "error_count": error_count
        }
        
    except Exception as e:
        frappe.log_error(f"Error in bulk assignment: {str(e)}", "Bulk Assignment Error")
        return {
            "success": False,
            "error": f"Failed to process bulk assignments: {str(e)}"
        }

def add_member_to_chapter_roster(member_name, new_chapter):
    """Add member to chapter's member roster using centralized manager"""
    try:
        if new_chapter:
            # Use centralized chapter membership manager for proper history tracking
            from verenigingen.utils.chapter_membership_manager import ChapterMembershipManager
            
            result = ChapterMembershipManager.assign_member_to_chapter(
                member_id=member_name,
                chapter_name=new_chapter,
                reason="Administrative assignment",
                assigned_by=frappe.session.user
            )
            
            if not result.get('success'):
                frappe.log_error(f"Failed to add member {member_name} to chapter {new_chapter}: {result.get('error')}", "Chapter Roster Update Error")
        
    except Exception as e:
        frappe.log_error(f"Error updating chapter roster: {str(e)}", "Chapter Roster Update Error")

@frappe.whitelist()
def debug_address_members(member_id):
    """Debug method to test address members functionality"""
    try:
        member = frappe.get_doc("Member", member_id)
        
        result = {
            "member_id": member.name,
            "member_name": f"{member.first_name} {member.last_name}",
            "primary_address": member.primary_address,
            "address_members_html": None,
            "address_members_html_length": 0,
            "other_members_count": 0,
            "other_members_list": [],
            "current_field_value": member.get("other_members_at_address")
        }
        
        # Test the HTML generation
        html_result = member.get_address_members_html()
        result["address_members_html"] = html_result
        result["address_members_html_length"] = len(html_result) if html_result else 0
        
        # Test the underlying method
        other_members = member.get_other_members_at_address()
        result["other_members_count"] = len(other_members) if other_members else 0
        result["other_members_list"] = other_members if other_members else []
        
        return result
        
    except Exception as e:
        return {
            "error": str(e),
            "traceback": frappe.get_traceback()
        }

@frappe.whitelist()
def manually_populate_address_members(member_id):
    """Manually populate the address members field to test UI"""
    try:
        member = frappe.get_doc("Member", member_id)
        
        # Generate the HTML content
        html_content = member.get_address_members_html()
        
        # Set the field value directly
        member.other_members_at_address = html_content
        member.save(ignore_permissions=True)
        
        return {
            "success": True,
            "message": f"Field populated for {member_id}",
            "html_length": len(html_content) if html_content else 0,
            "field_value": member.other_members_at_address
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "traceback": frappe.get_traceback()
        }

@frappe.whitelist()
def clear_address_members_field(member_id):
    """Clear the address members field to test automatic population"""
    try:
        member = frappe.get_doc("Member", member_id)
        member.other_members_at_address = None
        member.save(ignore_permissions=True)
        
        return {
            "success": True,
            "message": f"Field cleared for {member_id}"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def test_simple_field_population(member_id):
    """Test setting a simple value to verify field visibility"""
    try:
        member = frappe.get_doc("Member", member_id)
        
        # Set a simple test value
        test_html = '<div style="background: red; color: white; padding: 10px;">TEST: This field is working! If you can see this, the field is visible.</div>'
        member.other_members_at_address = test_html
        member.save(ignore_permissions=True)
        
        return {
            "success": True,
            "message": f"Test content set for {member_id}",
            "test_html": test_html
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def get_address_members_html_api(member_id):
    """Dedicated API method to get address members HTML - completely separate from document methods"""
    try:
        member = frappe.get_doc("Member", member_id)
        
        if not member.primary_address:
            return {
                "success": True,
                "html": '<div class="text-muted"><i class="fa fa-home"></i> No address selected</div>'
            }
            
        # Get the address document
        try:
            address_doc = frappe.get_doc("Address", member.primary_address)
        except Exception:
            return {
                "success": True,
                "html": '<div class="text-muted"><i class="fa fa-exclamation-triangle"></i> Address not found</div>'
            }
        
        # Find other members at the same physical address
        if not address_doc.address_line1 or not address_doc.city:
            return {
                "success": True,
                "html": '<div class="text-muted"><i class="fa fa-info-circle"></i> Incomplete address information</div>'
            }
        
        # Normalize the address components for matching
        normalized_address_line = address_doc.address_line1.lower().strip()
        normalized_city = address_doc.city.lower().strip()
        
        # Find all addresses with matching physical location (optimized query)
        matching_addresses = frappe.get_all("Address", 
            fields=["name", "address_line1", "city"],
            filters={
                "address_line1": address_doc.address_line1,  # Exact match instead of LIKE
                "city": address_doc.city
            }
        )
        
        same_location_addresses = []
        for addr in matching_addresses:
            if addr.address_line1 and addr.city:
                addr_line_normalized = addr.address_line1.lower().strip()
                addr_city_normalized = addr.city.lower().strip()
                
                # Match if address line AND city are the same (case-insensitive)
                if (addr_line_normalized == normalized_address_line and 
                    addr_city_normalized == normalized_city):
                    same_location_addresses.append(addr.name)
        
        if not same_location_addresses:
            return {
                "success": True,
                "html": '<div class="text-muted"><i class="fa fa-info-circle"></i> No other members found at this address</div>'
            }
        
        # Find members using any of the matching addresses, excluding current member
        other_members = frappe.get_all(
            "Member",
            filters={
                "primary_address": ["in", same_location_addresses],
                "name": ["!=", member.name],
                "status": ["in", ["Active", "Pending", "Suspended"]]
            },
            fields=["name", "full_name", "email", "status", "member_since", "birth_date"]
        )
        
        if not other_members:
            return {
                "success": True,
                "html": '<div class="text-muted"><i class="fa fa-info-circle"></i> No other members found at this address</div>'
            }
        
        # Generate HTML
        html_content = f'<div class="address-members-display"><h6>Other Members at This Address ({len(other_members)} found):</h6>'
        
        for other in other_members:
            # Guess relationship
            relationship = guess_relationship_simple(member, other)
            
            # Get age group
            age_group = get_age_group_simple(other.get("birth_date"))
            
            # Get status color
            status_color = get_status_color_simple(other.get("status", "Unknown"))
            
            html_content += f'''
            <div class="member-card" style="border: 1px solid #ddd; padding: 8px; margin: 4px 0; border-radius: 4px; background: #f8f9fa;">
                <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <div style="flex-grow: 1;">
                        <strong>{other.get("full_name", "Unknown")}</strong> 
                        <span class="text-muted">({other.get("name", "Unknown ID")})</span>
                        <br><small class="text-muted">
                            <i class="fa fa-users"></i> {relationship} | 
                            <i class="fa fa-birthday-cake"></i> {age_group} | 
                            <i class="fa fa-circle text-{status_color}"></i> {other.get("status", "Unknown")}
                        </small>
                        <br><small class="text-muted">
                            <i class="fa fa-envelope"></i> {other.get("email", "Unknown")}
                        </small>
                    </div>
                    <div style="margin-left: 12px;">
                        <button type="button" class="btn btn-xs btn-default view-member-btn" 
                                data-member="{other.get("name", "")}" 
                                style="font-size: 11px; padding: 4px 8px;">
                            <i class="fa fa-external-link" style="margin-right: 4px;"></i>View
                        </button>
                    </div>
                </div>
            </div>
            '''
        html_content += '</div>'
        
        return {
            "success": True,
            "html": html_content
        }
        
    except Exception as e:
        frappe.log_error(f"Error in get_address_members_html_api for {member_id}: {str(e)}")
        return {
            "success": False,
            "html": f'<div class="text-danger"><i class="fa fa-exclamation-triangle"></i> Error loading member information: {str(e)}</div>'
        }

def guess_relationship_simple(member1, member2_data):
    """Simple relationship guessing"""
    # Extract last names
    member1_last = member1.last_name.lower() if member1.last_name else ""
    member2_name = member2_data.get("full_name", "")
    member2_last = member2_name.split()[-1].lower() if member2_name else ""
    
    # Same last name suggests family
    if member1_last and member2_last and member1_last == member2_last:
        return "Family Member"
    else:
        return "Household Member"

def get_age_group_simple(birth_date):
    """Simple age group calculation"""
    if not birth_date:
        return "Unknown"
    
    try:
        from frappe.utils import date_diff, today
        age = date_diff(today(), birth_date) / 365.25
        
        if age < 18:
            return "Minor"
        elif age < 30:
            return "Young Adult"
        elif age < 50:
            return "Adult"
        elif age < 65:
            return "Middle-aged"
        else:
            return "Senior"
    except:
        return "Unknown"

def get_status_color_simple(status):
    """Simple status color mapping"""
    status_colors = {
        "Active": "success",
        "Pending": "warning", 
        "Suspended": "danger",
        "Terminated": "secondary"
    }
    return status_colors.get(status, "secondary")