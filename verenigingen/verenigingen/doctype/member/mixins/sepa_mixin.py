import frappe
from frappe import _
from frappe.utils import today, now


class SEPAMandateMixin:
    """Mixin for SEPA mandate-related functionality"""
    
    def get_active_sepa_mandates(self):
        """Get all active SEPA mandates for this member"""
        return frappe.get_all(
            "SEPA Mandate",
            filters={
                "member": self.name,
                "status": "Active",
                "is_active": 1
            },
            fields=["name", "mandate_id", "status", "expiry_date", "used_for_memberships", "used_for_donations"]
        )
    
    def get_default_sepa_mandate(self):
        """Get the default SEPA mandate for this member"""
        for link in self.sepa_mandates:
            if link.is_current and link.sepa_mandate:
                try:
                    mandate = frappe.get_doc("SEPA Mandate", link.sepa_mandate)
                    if mandate.status == "Active" and mandate.is_active:
                        return mandate
                except frappe.DoesNotExistError:
                    continue
        
        active_mandates = self.get_active_sepa_mandates()
        if active_mandates:
            for link in self.sepa_mandates:
                if link.sepa_mandate == active_mandates[0].name:
                    link.is_current = 1
                    break
            
            return frappe.get_doc("SEPA Mandate", active_mandates[0].name)
        
        return None
    
    def has_active_sepa_mandate(self, purpose="memberships"):
        """Check if member has an active SEPA mandate for a specific purpose"""
        filters = {
            "member": self.name,
            "status": "Active",
            "is_active": 1
        }
        
        if purpose == "memberships":
            filters["used_for_memberships"] = 1
        elif purpose == "donations":
            filters["used_for_donations"] = 1
        
        return frappe.db.exists("SEPA Mandate", filters)
    
    @frappe.whitelist()
    def create_sepa_mandate(self):
        """Create a new SEPA mandate for this member with enhanced prefilling"""
        mandate_ref_result = self._generate_mandate_reference()
        suggested_reference = mandate_ref_result.get("mandate_reference", f"M-{self.member_id}-{today().replace('-', '')}")
        
        mandate = frappe.new_doc("SEPA Mandate")
        mandate.member = self.name
        mandate.member_name = self.full_name
        mandate.mandate_id = suggested_reference
        mandate.account_holder_name = self.bank_account_name or self.full_name
        mandate.sign_date = today()
        
        if hasattr(self, 'iban') and self.iban:
            mandate.iban = self.iban
        if hasattr(self, 'bic') and self.bic:
            mandate.bic = self.bic
        
        mandate.used_for_memberships = 1
        mandate.used_for_donations = 0
        mandate.mandate_type = "RCUR"
        
        mandate.notes = f"Created from Member {self.name} on {today()}"
        
        mandate.insert()
        
        self.append("sepa_mandates", {
            "sepa_mandate": mandate.name,
            "mandate_reference": mandate.mandate_id,
            "is_current": 0,
            "status": "Draft",
            "valid_from": mandate.sign_date
        })
        
        self.save()
        
        return mandate.name
    
    def _generate_mandate_reference(self):
        """Generate a suggested mandate reference for a member"""
        member_id = self.member_id or self.name.replace('Assoc-Member-', '').replace('-', '')
        
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