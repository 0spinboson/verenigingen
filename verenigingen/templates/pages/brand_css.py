from verenigingen.verenigingen.doctype.brand_settings.brand_settings import generate_brand_css
import frappe

def get_context(context):
    """Generate CSS content for brand colors"""
    context.no_cache = 1
    frappe.response['content_type'] = 'text/css'
    frappe.response['body'] = generate_brand_css()
    return context