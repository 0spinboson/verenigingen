import frappe

@frappe.whitelist()
def check_imported_invoices_for_file_references():
    """Check imported ERPNext Sales Invoices for file/document references from e-Boekhouden"""
    try:
        # Get Sales Invoices that might have been imported from e-Boekhouden
        # Look for invoices with custom fields or specific naming patterns
        
        results = {
            "imported_invoices": [],
            "file_references_found": [],
            "custom_fields_analysis": {},
            "attachment_analysis": {}
        }
        
        # Get recent invoices (assuming migration was recent)
        invoices = frappe.get_all("Sales Invoice", 
            fields=["name", "customer", "posting_date", "grand_total", "remarks"],
            limit=20,
            order_by="creation desc"
        )
        
        results["imported_invoices"] = f"Found {len(invoices)} recent invoices"
        
        if invoices:
            # Analyze first few invoices in detail
            for i, invoice in enumerate(invoices[:5]):
                invoice_details = frappe.get_doc("Sales Invoice", invoice.name)
                
                # Check all fields for file-related content
                file_related_fields = {}
                for field, value in invoice_details.as_dict().items():
                    if value and isinstance(value, str):
                        # Look for file extensions, URLs, or file paths
                        if any(ext in value.lower() for ext in ['.pdf', '.png', '.jpg', '.jpeg', '.doc', '.docx']):
                            file_related_fields[field] = value
                        # Look for URLs or file paths
                        elif any(keyword in value.lower() for keyword in ['http', 'file://', 'document', 'attachment']):
                            file_related_fields[field] = value
                        # Look for e-Boekhouden specific references
                        elif 'boekhouden' in value.lower() or 'eboekhouden' in value.lower():
                            file_related_fields[field] = value
                
                if file_related_fields:
                    results["file_references_found"].append({
                        "invoice": invoice.name,
                        "file_fields": file_related_fields
                    })
                
                # Check for attachments linked to this invoice
                attachments = frappe.get_all("File", 
                    filters={
                        "attached_to_doctype": "Sales Invoice",
                        "attached_to_name": invoice.name
                    },
                    fields=["name", "file_name", "file_url", "creation"]
                )
                
                if attachments:
                    results["attachment_analysis"][invoice.name] = attachments
        
        # Check for custom fields that might contain file references
        custom_fields = frappe.get_all("Custom Field",
            filters={"dt": "Sales Invoice"},
            fields=["fieldname", "label", "fieldtype", "options"]
        )
        
        for cf in custom_fields:
            if any(word in cf.fieldname.lower() for word in ['file', 'document', 'attachment', 'link', 'url']):
                results["custom_fields_analysis"][cf.fieldname] = {
                    "label": cf.label,
                    "fieldtype": cf.fieldtype,
                    "options": cf.options
                }
        
        # Also check for any e-Boekhouden specific fields or references
        meta = frappe.get_meta("Sales Invoice")
        all_invoice_fields = [df.fieldname for df in meta.get("fields")]
        eboekhouden_fields = [f for f in all_invoice_fields if 'boekhouden' in f.lower() or 'eboekhouden' in f.lower()]
        
        if eboekhouden_fields:
            results["eboekhouden_specific_fields"] = eboekhouden_fields
        
        # Also check Journal Entries since those were imported during migration
        journal_entries = frappe.get_all("Journal Entry", 
            fields=["name", "posting_date", "user_remark", "cheque_no", "cheque_date"],
            limit=10,
            order_by="creation desc"
        )
        
        results["journal_entries_count"] = len(journal_entries)
        
        if journal_entries:
            for je in journal_entries[:3]:
                je_doc = frappe.get_doc("Journal Entry", je.name)
                
                # Check all fields for file-related content
                file_related_fields = {}
                for field, value in je_doc.as_dict().items():
                    if value and isinstance(value, str):
                        # Look for file extensions, URLs, or file paths
                        if any(ext in value.lower() for ext in ['.pdf', '.png', '.jpg', '.jpeg', '.doc', '.docx']):
                            file_related_fields[field] = value
                        # Look for URLs or file paths
                        elif any(keyword in value.lower() for keyword in ['http', 'file://', 'document', 'attachment']):
                            file_related_fields[field] = value
                        # Look for e-Boekhouden specific references
                        elif 'boekhouden' in value.lower() or 'eboekhouden' in value.lower():
                            file_related_fields[field] = value
                
                if file_related_fields:
                    if "journal_entry_file_references" not in results:
                        results["journal_entry_file_references"] = []
                    results["journal_entry_file_references"].append({
                        "journal_entry": je.name,
                        "file_fields": file_related_fields
                    })
        
        # Check the original transaction data that was migrated
        # Look at the debug_transaction_data function results if available
        try:
            from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
            settings = frappe.get_single("E-Boekhouden Settings")
            api = EBoekhoudenAPI(settings)
            
            # Get some transaction data to see if it contains file references
            mutations_result = api.get_mutations({"limit": 5})
            if mutations_result["success"]:
                import json
                mutations_data = json.loads(mutations_result["data"])
                results["original_mutations_analysis"] = {
                    "success": True,
                    "items_count": len(mutations_data.get("items", [])),
                    "sample_data": mutations_data
                }
                
                # Check if any mutation contains file-related fields
                if mutations_data.get("items"):
                    for mutation in mutations_data["items"][:3]:
                        file_fields = {}
                        for key, value in mutation.items():
                            if isinstance(value, str) and any(keyword in key.lower() for keyword in ['file', 'document', 'attachment', 'link', 'url']):
                                file_fields[key] = value
                            elif isinstance(value, str) and any(ext in value.lower() for ext in ['.pdf', '.png', '.jpg', '.doc']):
                                file_fields[key] = value
                        
                        if file_fields:
                            if "original_file_references" not in results:
                                results["original_file_references"] = []
                            results["original_file_references"].append({
                                "mutation_id": mutation.get("id"),
                                "file_fields": file_fields
                            })
        except Exception as e:
            results["original_data_check_error"] = str(e)
        
        return {
            "success": True,
            "results": results
        }
        
    except Exception as e:
        frappe.log_error(f"Error checking imported invoices: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }