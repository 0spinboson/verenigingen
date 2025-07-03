"""
Fix chapter visibility in portal
"""

import frappe
from frappe import _

@frappe.whitelist()
def check_and_fix_chapter_visibility():
    """Check and optionally fix chapter visibility issues"""
    
    # Check all chapters and their published status
    chapters = frappe.db.sql("""
        SELECT 
            c.name,
            c.published,
            c.status,
            COUNT(cm.name) as member_count
        FROM `tabChapter` c
        LEFT JOIN `tabChapter Member` cm ON cm.parent = c.name AND cm.enabled = 1
        GROUP BY c.name
    """, as_dict=True)
    
    unpublished_active = []
    inactive_chapters = []
    
    for chapter in chapters:
        if chapter.status == 'Active' and not chapter.published:
            unpublished_active.append(chapter)
        elif chapter.status != 'Active':
            inactive_chapters.append(chapter)
    
    return {
        "total_chapters": len(chapters),
        "unpublished_active_chapters": unpublished_active,
        "inactive_chapters": inactive_chapters,
        "recommendations": get_recommendations(unpublished_active, inactive_chapters)
    }

def get_recommendations(unpublished_active, inactive_chapters):
    """Get recommendations for fixing visibility"""
    recommendations = []
    
    if unpublished_active:
        recommendations.append({
            "issue": f"{len(unpublished_active)} active chapters are not published",
            "fix": "Run fix_unpublished_chapters() to publish all active chapters",
            "chapters": [c.name for c in unpublished_active]
        })
    
    if inactive_chapters:
        recommendations.append({
            "issue": f"{len(inactive_chapters)} chapters have inactive status",
            "fix": "Review and update chapter status to 'Active' if needed",
            "chapters": [c.name for c in inactive_chapters]
        })
    
    if not unpublished_active and not inactive_chapters:
        recommendations.append({
            "issue": "No visibility issues found",
            "fix": "All active chapters are properly published"
        })
    
    return recommendations

@frappe.whitelist()
def fix_unpublished_chapters():
    """Publish all active chapters that are not published"""
    
    if frappe.session.user == "Guest":
        return {"error": "Please login first"}
    
    # Check if user has permission
    if "System Manager" not in frappe.get_roles():
        return {"error": "You need System Manager role to perform this action"}
    
    # Get unpublished active chapters
    unpublished = frappe.db.sql("""
        SELECT name
        FROM `tabChapter`
        WHERE status = 'Active' AND (published = 0 OR published IS NULL)
    """, as_dict=True)
    
    fixed_chapters = []
    errors = []
    
    for chapter in unpublished:
        try:
            frappe.db.set_value("Chapter", chapter.name, "published", 1)
            fixed_chapters.append(chapter.name)
        except Exception as e:
            errors.append({"chapter": chapter.name, "error": str(e)})
    
    frappe.db.commit()
    
    return {
        "fixed_count": len(fixed_chapters),
        "fixed_chapters": fixed_chapters,
        "errors": errors,
        "message": f"Published {len(fixed_chapters)} chapters"
    }

@frappe.whitelist()
def ensure_chapter_fields():
    """Ensure all chapters have required fields for display"""
    
    # Check if chapters have the display fields we need
    sample_chapter = frappe.db.sql("""
        SELECT *
        FROM `tabChapter`
        LIMIT 1
    """, as_dict=True)
    
    if not sample_chapter:
        return {"error": "No chapters found in system"}
    
    # Get column names
    columns = list(sample_chapter[0].keys())
    
    # Check for expected display fields
    expected_fields = ['chapter_name', 'city', 'province', 'description', 'status', 
                      'meeting_location', 'meeting_schedule', 'contact_email']
    
    missing_fields = [f for f in expected_fields if f not in columns]
    
    # Get field info from DocType
    doctype_fields = frappe.db.sql("""
        SELECT fieldname, label, fieldtype
        FROM `tabDocField`
        WHERE parent = 'Chapter'
        AND fieldname IN ('introduction', 'address', 'region')
    """, as_dict=True)
    
    return {
        "existing_columns": columns,
        "missing_display_fields": missing_fields,
        "doctype_fields": doctype_fields,
        "sample_chapter": sample_chapter[0],
        "recommendation": get_field_recommendations(missing_fields, doctype_fields)
    }

def get_field_recommendations(missing_fields, doctype_fields):
    """Get recommendations for field setup"""
    
    if not missing_fields:
        return "All expected display fields are present"
    
    # Map existing fields to display fields
    field_mapping = {
        'name': 'chapter_name',  # Use name as chapter_name
        'introduction': 'description',  # Use introduction as description
        'address': 'meeting_location'  # Use address as meeting location
    }
    
    recommendations = []
    for missing in missing_fields:
        if missing in field_mapping.values():
            source = [k for k, v in field_mapping.items() if v == missing][0]
            recommendations.append(f"Use '{source}' field for '{missing}'")
        else:
            recommendations.append(f"Add custom field '{missing}' to Chapter doctype")
    
    return recommendations