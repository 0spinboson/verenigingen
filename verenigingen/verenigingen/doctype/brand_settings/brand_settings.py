# Copyright (c) 2025, Verenigingen and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _

class BrandSettings(Document):
	def validate(self):
		"""Validate brand settings"""
		self.validate_colors()
		self.validate_active_settings()
	
	def validate_colors(self):
		"""Validate that all colors are valid hex colors"""
		color_fields = [
			'primary_color', 'primary_hover_color',
			'secondary_color', 'secondary_hover_color', 
			'accent_color', 'accent_hover_color',
			'success_color', 'warning_color', 'error_color', 'info_color',
			'text_primary_color', 'text_secondary_color',
			'background_primary_color', 'background_secondary_color'
		]
		
		for field in color_fields:
			color = self.get(field)
			if color and not self.is_valid_hex_color(color):
				frappe.throw(_("Invalid color format for {0}. Please use hex format like #ff0000").format(
					self.meta.get_field(field).label
				))
	
	def validate_active_settings(self):
		"""Ensure only one settings can be active at a time"""
		if self.is_active:
			# Deactivate all other settings
			existing_active = frappe.get_all("Brand Settings", 
				filters={"is_active": 1, "name": ["!=", self.name]}, 
				fields=["name"])
			
			for setting in existing_active:
				frappe.db.set_value("Brand Settings", setting.name, "is_active", 0)
				frappe.msgprint(_("Deactivated {0} as only one Brand Settings can be active").format(setting.name))
	
	def is_valid_hex_color(self, color):
		"""Check if color is a valid hex color"""
		if not color or not color.startswith('#'):
			return False
		
		# Remove # and check if remaining characters are valid hex
		hex_part = color[1:]
		if len(hex_part) not in [3, 6]:
			return False
		
		try:
			int(hex_part, 16)
			return True
		except ValueError:
			return False
	
	def on_update(self):
		"""Clear cache when settings are updated"""
		frappe.cache().delete_key("active_brand_settings")
		frappe.cache().delete_key("brand_settings_css")

@frappe.whitelist()
def get_active_brand_settings():
	"""Get the currently active brand settings"""
	# Try to get from cache first
	cached_settings = frappe.cache().get_value("active_brand_settings")
	if cached_settings:
		return cached_settings
	
	# Get from database
	active_settings = frappe.get_all("Brand Settings", 
		filters={"is_active": 1}, 
		fields=["*"],
		limit=1)
	
	if active_settings:
		settings = active_settings[0]
		# Cache for 1 hour
		frappe.cache().set_value("active_brand_settings", settings, expires_in_sec=3600)
		return settings
	
	# Return default settings if none found
	default_settings = {
		"primary_color": "#cf3131",
		"primary_hover_color": "#b82828", 
		"secondary_color": "#01796f",
		"secondary_hover_color": "#015a52",
		"accent_color": "#663399",
		"accent_hover_color": "#4d2673",
		"success_color": "#28a745",
		"warning_color": "#ffc107",
		"error_color": "#dc3545", 
		"info_color": "#17a2b8",
		"text_primary_color": "#333333",
		"text_secondary_color": "#666666",
		"background_primary_color": "#ffffff",
		"background_secondary_color": "#f8f9fa"
	}
	
	return default_settings

@frappe.whitelist()
def generate_brand_css():
	"""Generate CSS with brand colors"""
	# Try to get from cache first
	cached_css = frappe.cache().get_value("brand_settings_css")
	if cached_css:
		return cached_css
	
	settings = get_active_brand_settings()
	
	css = f"""
/* Brand Settings CSS - Auto-generated */
:root {{
	--brand-primary: {settings['primary_color']};
	--brand-primary-hover: {settings['primary_hover_color']};
	--brand-secondary: {settings['secondary_color']};
	--brand-secondary-hover: {settings['secondary_hover_color']};
	--brand-accent: {settings['accent_color']};
	--brand-accent-hover: {settings['accent_hover_color']};
	--brand-success: {settings['success_color']};
	--brand-warning: {settings['warning_color']};
	--brand-error: {settings['error_color']};
	--brand-info: {settings['info_color']};
	--brand-text-primary: {settings['text_primary_color']};
	--brand-text-secondary: {settings['text_secondary_color']};
	--brand-bg-primary: {settings['background_primary_color']};
	--brand-bg-secondary: {settings['background_secondary_color']};
}}

/* Override Tailwind classes with brand colors */
.bg-red-600 {{ background-color: var(--brand-primary) !important; }}
.bg-red-700 {{ background-color: var(--brand-primary-hover) !important; }}
.hover\\:bg-red-700:hover {{ background-color: var(--brand-primary-hover) !important; }}

.bg-teal-600 {{ background-color: var(--brand-secondary) !important; }}
.bg-teal-700 {{ background-color: var(--brand-secondary-hover) !important; }}
.hover\\:bg-teal-700:hover {{ background-color: var(--brand-secondary-hover) !important; }}

.bg-purple-600 {{ background-color: var(--brand-accent) !important; }}
.bg-purple-700 {{ background-color: var(--brand-accent-hover) !important; }}
.hover\\:bg-purple-700:hover {{ background-color: var(--brand-accent-hover) !important; }}

.text-red-600 {{ color: var(--brand-primary) !important; }}
.text-teal-600 {{ color: var(--brand-secondary) !important; }}
.text-purple-600 {{ color: var(--brand-accent) !important; }}

.border-red-500 {{ border-color: var(--brand-primary) !important; }}
.border-teal-500 {{ border-color: var(--brand-secondary) !important; }}
.border-purple-500 {{ border-color: var(--brand-accent) !important; }}

.focus\\:ring-red-500:focus {{ --tw-ring-color: var(--brand-primary) !important; }}
.focus\\:border-red-500:focus {{ border-color: var(--brand-primary) !important; }}

/* Gradient overrides */
.from-purple-600 {{ --tw-gradient-from: var(--brand-accent) !important; }}
.from-purple-700 {{ --tw-gradient-from: var(--brand-accent-hover) !important; }}
.to-red-600 {{ --tw-gradient-to: var(--brand-primary) !important; }}
.to-purple-800 {{ --tw-gradient-to: var(--brand-accent-hover) !important; }}

/* Custom brand utility classes */
.btn-brand-primary {{
	background-color: var(--brand-primary);
	color: white;
	border-color: var(--brand-primary);
}}

.btn-brand-primary:hover {{
	background-color: var(--brand-primary-hover);
	border-color: var(--brand-primary-hover);
}}

.btn-brand-secondary {{
	background-color: var(--brand-secondary);
	color: white;
	border-color: var(--brand-secondary);
}}

.btn-brand-secondary:hover {{
	background-color: var(--brand-secondary-hover);
	border-color: var(--brand-secondary-hover);
}}

.text-brand-primary {{ color: var(--brand-primary); }}
.text-brand-secondary {{ color: var(--brand-secondary); }}
.text-brand-accent {{ color: var(--brand-accent); }}

.bg-brand-primary {{ background-color: var(--brand-primary); }}
.bg-brand-secondary {{ background-color: var(--brand-secondary); }}
.bg-brand-accent {{ background-color: var(--brand-accent); }}

.border-brand-primary {{ border-color: var(--brand-primary); }}
.border-brand-secondary {{ border-color: var(--brand-secondary); }}
.border-brand-accent {{ border-color: var(--brand-accent); }}

/* Existing CSS overrides for custom pages */
.btn-primary {{
	background-color: var(--brand-primary) !important;
	border-color: var(--brand-primary) !important;
}}

.btn-primary:hover {{
	background-color: var(--brand-primary-hover) !important;
	border-color: var(--brand-primary-hover) !important;
}}

/* Text primary overrides for existing pages */
.text-primary {{
	color: var(--brand-primary) !important;
}}

/* Form focus states */
.form-control:focus {{
	border-color: var(--brand-primary) !important;
	box-shadow: 0 0 0 2px rgba(207, 49, 49, 0.25) !important;
}}
"""
	
	# Cache for 1 hour
	frappe.cache().set_value("brand_settings_css", css, expires_in_sec=3600)
	
	return css

@frappe.whitelist()
def create_default_brand_settings():
	"""Create default brand settings if none exist"""
	existing = frappe.get_all("Brand Settings", limit=1)
	if existing:
		return False
	
	default_settings = frappe.get_doc({
		"doctype": "Brand Settings",
		"settings_name": "Default Brand Settings",
		"description": "Default brand colors for the organization",
		"is_active": 1,
		"primary_color": "#cf3131",
		"primary_hover_color": "#b82828",
		"secondary_color": "#01796f", 
		"secondary_hover_color": "#015a52",
		"accent_color": "#663399",
		"accent_hover_color": "#4d2673",
		"success_color": "#28a745",
		"warning_color": "#ffc107",
		"error_color": "#dc3545",
		"info_color": "#17a2b8",
		"text_primary_color": "#333333",
		"text_secondary_color": "#666666",
		"background_primary_color": "#ffffff",
		"background_secondary_color": "#f8f9fa"
	})
	
	default_settings.insert(ignore_permissions=True)
	return True