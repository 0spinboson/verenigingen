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
	
	def get_color_brightness(self, hex_color):
		"""Calculate brightness of a hex color (0-255 scale)"""
		if not hex_color or not hex_color.startswith('#'):
			return 128  # Default medium brightness
		
		hex_part = hex_color[1:]
		
		# Convert 3-digit hex to 6-digit
		if len(hex_part) == 3:
			hex_part = ''.join([c*2 for c in hex_part])
		
		try:
			r = int(hex_part[0:2], 16)
			g = int(hex_part[2:4], 16) 
			b = int(hex_part[4:6], 16)
			
			# Calculate perceived brightness using standard formula
			brightness = (r * 299 + g * 587 + b * 114) / 1000
			return brightness
		except (ValueError, IndexError):
			return 128  # Default medium brightness
	
	def get_contrasting_text_color(self, background_color):
		"""Get white or black text color based on background brightness"""
		brightness = self.get_color_brightness(background_color)
		return "#ffffff" if brightness < 128 else "#000000"
	
	def on_update(self):
		"""Clear cache when settings are updated"""
		frappe.cache().delete_key("active_brand_settings")
		frappe.cache().delete_key("brand_settings_css")
		frappe.cache().delete_key("organization_logo")
		
		# Trigger CSS rebuild for brand changes
		if self.is_active:
			frappe.publish_realtime("brand_settings_updated", {
				"message": "Brand settings updated",
				"settings_name": self.settings_name
			})

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
		"logo": None,
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
	
	# Create a temporary BrandSettings instance to access color calculation methods
	brand_instance = BrandSettings()
	
	# Calculate contrasting text colors for smart styling
	primary_text = brand_instance.get_contrasting_text_color(settings['primary_color'])
	secondary_text = brand_instance.get_contrasting_text_color(settings['secondary_color'])
	accent_text = brand_instance.get_contrasting_text_color(settings['accent_color'])
	
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
	--brand-primary-text: {primary_text};
	--brand-secondary-text: {secondary_text};
	--brand-accent-text: {accent_text};
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

/* Compact section styling for better space utilization */
.page-header {{
	padding: 1.25rem 1.5rem !important;
	margin-bottom: 1.5rem !important;
}}

.page-header h1 {{
	margin: 0 0 0.25rem 0 !important;
	font-size: 2rem !important;
	color: var(--brand-primary-text) !important;
}}

.page-header p {{
	margin: 0 !important;
	font-size: 1rem !important;
	opacity: 0.85 !important;
}}

/* Compact info boxes */
.bg-teal-50, .bg-blue-50, .bg-yellow-50, .bg-green-50, .bg-red-50 {{
	padding: 0.875rem 1rem !important;
	margin-bottom: 1rem !important;
}}

/* Brand-colored headers with smart text colors */
.bg-red-600, .bg-teal-600, .bg-purple-600 {{
	color: var(--brand-primary-text) !important;
}}

.bg-red-600 h1, .bg-red-600 h2, .bg-red-600 h3, .bg-red-600 h4 {{
	color: var(--brand-primary-text) !important;
}}

.bg-teal-600 h1, .bg-teal-600 h2, .bg-teal-600 h3, .bg-teal-600 h4 {{
	color: var(--brand-secondary-text) !important;
}}

.bg-purple-600 h1, .bg-purple-600 h2, .bg-purple-600 h3, .bg-purple-600 h4 {{
	color: var(--brand-accent-text) !important;
}}

/* Compact button styling */
.btn-primary, .btn-brand-primary {{
	color: var(--brand-primary-text) !important;
}}

.btn-secondary, .btn-brand-secondary {{
	color: var(--brand-secondary-text) !important;
}}

/* More compact card spacing */
.rounded-xl {{
	padding: 1.25rem !important;
}}

.rounded-xl h3, .rounded-xl h4 {{
	margin-bottom: 0.75rem !important;
}}

/* Expense form button override */
.bg-green-600, .bg-green-500 {{
	background-color: var(--brand-primary) !important;
	color: var(--brand-primary-text) !important;
}}

.bg-green-600:hover, .bg-green-500:hover {{
	background-color: var(--brand-primary-hover) !important;
}}

/* Logo integration styles */
.organization-logo {{
	max-height: 60px;
	max-width: 200px;
	object-fit: contain;
	margin-bottom: 1rem;
}}

.header-with-logo {{
	display: flex;
	align-items: center;
	gap: 1rem;
	margin-bottom: 2rem;
}}

.header-with-logo .organization-logo {{
	margin-bottom: 0;
}}

/* Responsive logo adjustments */
@media (max-width: 768px) {{
	.header-with-logo {{
		flex-direction: column;
		text-align: center;
		gap: 0.5rem;
	}}
	
	.organization-logo {{
		max-height: 40px;
		margin-bottom: 0.5rem;
	}}
}}
"""
	
	# Cache for 1 hour
	frappe.cache().set_value("brand_settings_css", css, expires_in_sec=3600)
	
	return css

@frappe.whitelist()
def get_organization_logo():
	"""Get the currently active organization logo"""
	# Try to get from cache first
	cached_logo = frappe.cache().get_value("organization_logo")
	if cached_logo:
		return cached_logo
	
	settings = get_active_brand_settings()
	logo_url = settings.get('logo')
	
	# Cache for 1 hour
	if logo_url:
		frappe.cache().set_value("organization_logo", logo_url, expires_in_sec=3600)
	
	return logo_url

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