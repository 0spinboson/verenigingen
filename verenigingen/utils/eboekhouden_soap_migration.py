"""
E-Boekhouden SOAP-based migration
Uses the SOAP API to get complete mutation data including descriptions and transaction types
"""

import frappe
from frappe import _
from datetime import datetime
from collections import defaultdict
import json

def migrate_using_soap(migration_doc, settings, use_account_mappings=True):
    """
    Main migration function using SOAP API with mutation ID ranges
    
    Args:
        migration_doc: The migration document
        settings: E-Boekhouden settings
        use_account_mappings: Whether to use account mappings for document type determination
    """
    from .eboekhouden_soap_api import EBoekhoudenSOAPAPI
    
    try:
        api = EBoekhoudenSOAPAPI(settings)
        company = settings.default_company
        
        if not company:
            return {
                "success": False,
                "error": "No default company set"
            }
        
        # Get cost center - try multiple approaches
        cost_center = None
        
        # First try to get Main cost center (non-group)
        cost_center = frappe.db.get_value("Cost Center", {
            "company": company,
            "cost_center_name": "Main",
            "is_group": 0
        }, "name")
        
        # If still not found, try company abbreviation pattern
        if not cost_center:
            abbr = frappe.db.get_value("Company", company, "abbr")
            if abbr:
                cost_center = f"{company} - {abbr}"
                if not frappe.db.exists("Cost Center", cost_center):
                    cost_center = None
        
        # If still not found, try to get Main cost center
        if not cost_center:
            cost_center = frappe.db.get_value("Cost Center", {
                "company": company,
                "cost_center_name": "Main",
                "is_group": 0
            }, "name")
        
        # If still not found, get any non-group cost center
        if not cost_center:
            cost_center = frappe.db.get_value("Cost Center", {
                "company": company,
                "is_group": 0
            }, "name")
        
        if not cost_center:
            return {
                "success": False,
                "error": "No main cost center found"
            }
        
        # Pre-process: Fix account types before migration
        fix_account_types_for_migration(company)
        
        # First, get the highest mutation number to understand the range
        highest_result = api.get_highest_mutation_number()
        if not highest_result["success"]:
            return {
                "success": False,
                "error": f"Failed to determine mutation range: {highest_result.get('error')}"
            }
        
        highest_mutation_nr = highest_result["highest_mutation_number"]
        if highest_mutation_nr == 0:
            return {
                "success": False,
                "error": "No mutations found in E-Boekhouden"
            }
        
        # Process mutations in batches of 500
        batch_size = 500
        all_mutations = []
        
        # Check if we're resuming from a specific mutation number
        start_from = 1
        if hasattr(migration_doc, 'resume_from_mutation') and migration_doc.resume_from_mutation:
            start_from = migration_doc.resume_from_mutation
            frappe.publish_realtime(
                "migration_progress",
                {"message": f"Resuming from mutation number {start_from}..."},
                user=frappe.session.user
            )
        
        # Update migration doc with progress
        frappe.publish_realtime(
            "migration_progress",
            {"message": f"Found highest mutation number: {highest_mutation_nr}. Starting batch processing from #{start_from}..."},
            user=frappe.session.user
        )
        
        # Process from start_from to highest mutation number
        for start_nr in range(start_from, highest_mutation_nr + 1, batch_size):
            end_nr = min(start_nr + batch_size - 1, highest_mutation_nr)
            
            # Update progress
            frappe.publish_realtime(
                "migration_progress",
                {"message": f"Processing mutations {start_nr} to {end_nr}..."},
                user=frappe.session.user
            )
            
            result = api.get_mutations(mutation_nr_from=start_nr, mutation_nr_to=end_nr)
            
            if result["success"]:
                all_mutations.extend(result["mutations"])
            else:
                # Log error but continue with other batches
                frappe.log_error(
                    f"Failed to get mutations {start_nr}-{end_nr}: {result.get('error')}",
                    "E-Boekhouden Migration"
                )
        
        # Update progress
        frappe.publish_realtime(
            "migration_progress",
            {"message": f"Retrieved {len(all_mutations)} mutations. Processing..."},
            user=frappe.session.user
        )
        
        # Process mutations by type
        stats = {
            "total_mutations": len(all_mutations),
            "invoices_created": 0,
            "payments_processed": 0,
            "journal_entries_created": 0,
            "errors": [],
            "highest_mutation_number": highest_mutation_nr
        }
        
        # Group mutations by type for processing
        from .normalize_mutation_types import normalize_mutation_type
        mutations_by_type = defaultdict(list)
        for mut in all_mutations:
            soort = mut.get("Soort", "Unknown")
            # Normalize the mutation type to handle abbreviations
            normalized_soort = normalize_mutation_type(soort)
            mutations_by_type[normalized_soort].append(mut)
        
        # Process each type
        for soort, muts in mutations_by_type.items():
            if soort == "FactuurVerstuurd":
                # Sales invoices
                result = process_sales_invoices(muts, company, cost_center, migration_doc)
                stats["invoices_created"] += result.get("created", 0)
                stats["errors"].extend(result.get("errors", []))
                
            elif soort == "FactuurOntvangen":
                # Purchase invoices
                if use_account_mappings:
                    from .eboekhouden_mapping_migration import process_purchase_invoices_with_mapping
                    result = process_purchase_invoices_with_mapping(muts, company, cost_center, migration_doc)
                    stats["invoices_created"] += result.get("created_purchase_invoices", 0)
                    stats["journal_entries_created"] += result.get("created_journal_entries", 0)
                else:
                    result = process_purchase_invoices(muts, company, cost_center, migration_doc)
                    stats["invoices_created"] += result.get("created", 0)
                stats["errors"].extend(result.get("errors", []))
                
            elif soort == "FactuurbetalingOntvangen":
                # Customer payments
                result = process_customer_payments(muts, company, cost_center, migration_doc)
                stats["payments_processed"] += result.get("created", 0)
                stats["errors"].extend(result.get("errors", []))
                
            elif soort == "FactuurbetalingVerstuurd":
                # Supplier payments
                result = process_supplier_payments(muts, company, cost_center, migration_doc)
                stats["payments_processed"] += result.get("created", 0)
                stats["errors"].extend(result.get("errors", []))
                
            elif soort in ["GeldOntvangen", "GeldUitgegeven"]:
                # Direct bank transactions
                result = process_bank_transactions(muts, company, cost_center, migration_doc, soort)
                stats["journal_entries_created"] += result.get("created", 0)
                stats["errors"].extend(result.get("errors", []))
                
            elif soort == "Memoriaal":
                # Manual journal entries
                result = process_memorial_entries(muts, company, cost_center, migration_doc)
                stats["journal_entries_created"] += result.get("created", 0)
                stats["errors"].extend(result.get("errors", []))
        
        return {
            "success": True,
            "stats": stats,
            "message": f"Processed all {stats['total_mutations']} mutations (up to #{stats['highest_mutation_number']}): {stats['invoices_created']} invoices, {stats['payments_processed']} payments, {stats['journal_entries_created']} journal entries"
        }
        
    except Exception as e:
        frappe.log_error(f"SOAP migration error: {str(e)}", "E-Boekhouden Migration")
        return {
            "success": False,
            "error": str(e)
        }

def process_sales_invoices(mutations, company, cost_center, migration_doc):
    """Process FactuurVerstuurd (sales invoices)"""
    created = 0
    errors = []
    
    for mut in mutations:
        try:
            # Skip if already imported
            invoice_no = mut.get("Factuurnummer")
            if not invoice_no:
                continue
                
            if frappe.db.exists("Sales Invoice", {"eboekhouden_invoice_number": invoice_no}):
                continue
            
            # Parse mutation data
            posting_date = parse_date(mut.get("Datum"))
            customer_code = mut.get("RelatieCode")
            description = mut.get("Omschrijving", "")
            
            # Get or create customer
            customer = get_or_create_customer(customer_code, description)
            
            # Create sales invoice
            si = frappe.new_doc("Sales Invoice")
            si.company = company
            si.customer = customer
            si.posting_date = posting_date
            si.eboekhouden_invoice_number = invoice_no
            si.remarks = description
            
            # Calculate and set due date
            try:
                payment_terms = int(mut.get("Betalingstermijn", 30))
            except (ValueError, TypeError):
                payment_terms = 30
            
            # Ensure payment terms is positive
            if payment_terms < 0:
                payment_terms = 0
            
            # Set due date - ensure it's not before posting date
            calculated_due_date = frappe.utils.add_days(posting_date, payment_terms)
            if frappe.utils.getdate(calculated_due_date) < frappe.utils.getdate(posting_date):
                si.due_date = posting_date
            else:
                si.due_date = calculated_due_date
            
            # Set the debit to account from E-Boekhouden mutation
            rekening_code = mut.get("Rekening")
            if rekening_code:
                # Get the account by code
                debit_account = get_account_by_code(rekening_code, company)
                if debit_account:
                    # Ensure it's marked as receivable
                    current_type = frappe.db.get_value("Account", debit_account, "account_type")
                    if current_type != "Receivable":
                        frappe.db.set_value("Account", debit_account, "account_type", "Receivable")
                        frappe.db.commit()
                    si.debit_to = debit_account
                else:
                    # Fallback to default
                    default_receivable = frappe.db.get_value("Company", company, "default_receivable_account")
                    if default_receivable:
                        si.debit_to = default_receivable
            else:
                # Use default if no Rekening specified
                default_receivable = frappe.db.get_value("Company", company, "default_receivable_account")
                if default_receivable:
                    si.debit_to = default_receivable
            
            # Set cost center
            si.cost_center = cost_center
            
            # Add line items from MutatieRegels
            for regel in mut.get("MutatieRegels", []):
                amount = float(regel.get("BedragExclBTW", 0))
                if amount > 0:
                    si.append("items", {
                        "item_code": get_or_create_item(regel.get("TegenrekeningCode")),
                        "qty": 1,
                        "rate": amount,
                        "income_account": get_account_by_code(regel.get("TegenrekeningCode"), company),
                        "cost_center": cost_center
                    })
            
            si.insert(ignore_permissions=True)
            si.submit()
            created += 1
            
        except Exception as e:
            errors.append(f"Invoice {mut.get('Factuurnummer')}: {str(e)}")
    
    return {"created": created, "errors": errors}

def process_customer_payments(mutations, company, cost_center, migration_doc):
    """Process FactuurbetalingOntvangen (customer payments)"""
    created = 0
    errors = []
    
    for mut in mutations:
        try:
            invoice_no = mut.get("Factuurnummer")
            if not invoice_no:
                continue
            
            # Find the related sales invoice
            si_name = frappe.db.get_value("Sales Invoice", 
                {"eboekhouden_invoice_number": invoice_no}, "name")
            
            if not si_name:
                # Invoice not found, create unreconciled payment entry
                from .create_unreconciled_payment import create_unreconciled_payment_entry
                result = create_unreconciled_payment_entry(mut, company, cost_center, "Customer")
                if result["success"]:
                    created += 1
                else:
                    errors.append(f"Unreconciled payment {mut.get('MutatieNr')}: {result['error']}")
                continue
            
            # Create payment entry
            pe = frappe.new_doc("Payment Entry")
            pe.payment_type = "Receive"
            pe.company = company
            pe.posting_date = parse_date(mut.get("Datum"))
            pe.party_type = "Customer"
            pe.party = frappe.db.get_value("Sales Invoice", si_name, "customer")
            
            # Set descriptive title
            from .eboekhouden_payment_naming import get_payment_entry_title, enhance_payment_entry_fields
            pe.title = get_payment_entry_title(mut, pe.party, "Receive")
            pe = enhance_payment_entry_fields(pe, mut)
            
            # Get amount from mutation lines
            total_amount = 0
            for regel in mut.get("MutatieRegels", []):
                total_amount += float(regel.get("BedragInclBTW", 0))
            
            pe.paid_amount = total_amount
            pe.received_amount = total_amount
            
            # Link to invoice
            pe.append("references", {
                "reference_doctype": "Sales Invoice",
                "reference_name": si_name,
                "allocated_amount": total_amount
            })
            
            # Set accounts
            bank_account = get_bank_account(mut.get("Rekening"), company)
            pe.paid_to = bank_account
            
            pe.insert(ignore_permissions=True)
            pe.submit()
            created += 1
            
        except Exception as e:
            errors.append(f"Payment {mut.get('MutatieNr')}: {str(e)}")
    
    return {"created": created, "errors": errors}

def process_bank_transactions(mutations, company, cost_center, migration_doc, transaction_type):
    """Process GeldOntvangen and GeldUitgegeven (direct bank transactions)"""
    created = 0
    errors = []
    
    # Get already processed mutations
    processed = get_processed_mutation_numbers(company)
    
    for mut in mutations:
        try:
            # Skip if already processed
            mutation_nr = mut.get("MutatieNr")
            if mutation_nr and is_mutation_processed(mutation_nr, processed):
                continue
            
            # Create journal entry
            je = frappe.new_doc("Journal Entry")
            je.company = company
            je.posting_date = parse_date(mut.get("Datum"))
            je.eboekhouden_mutation_nr = mutation_nr
            
            # Set descriptive title and enhanced remarks
            from .eboekhouden_payment_naming import get_journal_entry_title, enhance_journal_entry_fields
            je.title = get_journal_entry_title(mut, transaction_type)
            je = enhance_journal_entry_fields(je, mut, "Bank Transaction")
            
            # Get amount
            total_amount = 0
            for regel in mut.get("MutatieRegels", []):
                total_amount += float(regel.get("BedragInclBTW", 0))
            
            if total_amount == 0:
                continue
            
            # Bank account
            bank_account = get_bank_account(mut.get("Rekening"), company)
            
            if transaction_type == "GeldOntvangen":
                # Money received - debit bank, credit income
                je.append("accounts", {
                    "account": bank_account,
                    "debit_in_account_currency": total_amount,
                    "cost_center": cost_center
                })
                
                # Try to determine income account from description
                income_account = determine_income_account(mut.get("Omschrijving", ""), company)
                je.append("accounts", {
                    "account": income_account,
                    "credit_in_account_currency": total_amount,
                    "cost_center": cost_center
                })
            else:
                # Money spent - credit bank, debit expense
                je.append("accounts", {
                    "account": bank_account,
                    "credit_in_account_currency": total_amount,
                    "cost_center": cost_center
                })
                
                # Try to determine expense account from description
                expense_account = determine_expense_account(mut.get("Omschrijving", ""), company)
                je.append("accounts", {
                    "account": expense_account,
                    "debit_in_account_currency": total_amount,
                    "cost_center": cost_center
                })
            
            je.insert(ignore_permissions=True)
            je.submit()
            created += 1
            
        except Exception as e:
            errors.append(f"Bank transaction {mut.get('MutatieNr')}: {str(e)}")
    
    return {"created": created, "errors": errors}

# Helper functions

def parse_date(date_str):
    """Parse date from E-Boekhouden format"""
    if not date_str:
        return frappe.utils.today()
    
    if 'T' in date_str:
        return date_str.split('T')[0]  # Return string format YYYY-MM-DD
    else:
        return date_str  # Already in correct format

def get_or_create_customer(code, description=""):
    """Get or create customer based on code and description"""
    if not code:
        # Try to extract from description
        if description:
            # Look for patterns in description
            return "E-Boekhouden Import Customer"
        return "E-Boekhouden Import Customer"
    
    # Check if customer exists with this code
    customer = frappe.db.get_value("Customer", {"eboekhouden_relation_code": code}, "name")
    if customer:
        return customer
    
    # Create new customer
    customer = frappe.new_doc("Customer")
    customer.customer_name = f"Customer {code}"
    customer.eboekhouden_relation_code = code
    customer.customer_group = frappe.db.get_value("Customer Group", {"is_group": 0}, "name") or "All Customer Groups"
    customer.territory = frappe.db.get_value("Territory", {"is_group": 0}, "name") or "All Territories"
    customer.insert(ignore_permissions=True)
    
    return customer.name

def get_or_create_supplier(code, description=""):
    """Get or create supplier based on code and description"""
    if not code:
        # Try to extract from description
        if description:
            # Look for patterns in description
            return "E-Boekhouden Import Supplier"
        return "E-Boekhouden Import Supplier"
    
    # Check if supplier exists with this code
    supplier = frappe.db.get_value("Supplier", {"eboekhouden_relation_code": code}, "name")
    if supplier:
        return supplier
    
    # Create new supplier
    supplier = frappe.new_doc("Supplier")
    supplier.supplier_name = f"Supplier {code}"
    supplier.eboekhouden_relation_code = code
    supplier.supplier_group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name") or "All Supplier Groups"
    supplier.insert(ignore_permissions=True)
    
    return supplier.name

def get_or_create_item(code):
    """Get or create item for invoice line"""
    if not code:
        code = "MISC"
    
    item_name = f"Service {code}"
    if not frappe.db.exists("Item", item_name):
        try:
            item = frappe.new_doc("Item")
            item.item_code = item_name
            item.item_name = item_name
            item.item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "Services"
            item.stock_uom = "Nos"
            item.is_stock_item = 0
            item.insert(ignore_permissions=True)
        except Exception as e:
            frappe.log_error(f"Failed to create item {item_name}: {str(e)}")
            # Return a default item
            default_item = frappe.db.get_value("Item", {"is_stock_item": 0}, "name")
            if default_item:
                return default_item
            # As last resort, create a generic item
            try:
                generic = frappe.new_doc("Item")
                generic.item_code = "Generic Service"
                generic.item_name = "Generic Service"
                generic.item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
                generic.stock_uom = "Nos"
                generic.is_stock_item = 0
                generic.insert(ignore_permissions=True)
                return generic.name
            except:
                raise Exception("Cannot create items for invoices")
    
    return item_name

def get_account_by_code(code, company):
    """Get account by E-Boekhouden code"""
    if not code:
        # Return default income account
        return frappe.db.get_value("Account", {
            "company": company,
            "account_type": "Income Account",
            "is_group": 0
        }, "name")
    
    account = frappe.db.get_value("Account", {
        "company": company,
        "account_number": code
    }, "name")
    
    if account:
        return account
    
    # Return default
    return frappe.db.get_value("Account", {
        "company": company,
        "account_type": "Income Account",
        "is_group": 0
    }, "name")

def get_bank_account(code, company):
    """Get bank account by code"""
    if code:
        account = frappe.db.get_value("Account", {
            "company": company,
            "account_number": code
        }, "name")
        if account:
            return account
    
    # Return default bank account
    return frappe.db.get_value("Account", {
        "company": company,
        "account_type": "Bank",
        "is_group": 0
    }, "name")

def determine_income_account(description, company):
    """Try to determine income account from description"""
    desc_lower = description.lower()
    
    # Check for donation keywords
    if any(word in desc_lower for word in ["donatie", "gift", "donation"]):
        return frappe.db.get_value("Account", {
            "company": company,
            "account_name": ["like", "%Donation%"],
            "is_group": 0
        }, "name") or get_default_income_account(company)
    
    return get_default_income_account(company)

def determine_expense_account(description, company):
    """Try to determine expense account from description"""
    desc_lower = description.lower()
    
    # Check for specific expense types
    if any(word in desc_lower for word in ["bank", "kosten", "fee"]):
        return frappe.db.get_value("Account", {
            "company": company,
            "account_name": ["like", "%Bank Charges%"],
            "is_group": 0
        }, "name") or get_default_expense_account(company)
    
    return get_default_expense_account(company)

def get_expense_account_by_code(code, company):
    """Get expense account by code"""
    if not code:
        # Return default expense account
        return get_default_expense_account(company)
    
    account = frappe.db.get_value("Account", {
        "company": company,
        "account_number": code
    }, "name")
    
    if account:
        return account
    
    # Return default expense account
    return get_default_expense_account(company)

def get_default_income_account(company):
    """Get default income account"""
    return frappe.db.get_value("Account", {
        "company": company,
        "account_type": "Income Account",
        "is_group": 0
    }, "name")

def get_default_expense_account(company):
    """Get default expense account"""
    return frappe.db.get_value("Account", {
        "company": company,
        "account_type": "Expense Account",
        "is_group": 0
    }, "name")

def create_payment_journal_entry(mut, company, cost_center, party_type):
    """Create journal entry for payment when invoice is not found"""
    try:
        je = frappe.new_doc("Journal Entry")
        je.company = company
        je.posting_date = parse_date(mut.get("Datum"))
        je.eboekhouden_mutation_nr = mut.get("MutatieNr")
        je.eboekhouden_invoice_number = mut.get("Factuurnummer")
        
        # Set descriptive title and enhanced remarks
        from .eboekhouden_payment_naming import get_journal_entry_title, enhance_journal_entry_fields
        mutation_type = mut.get("Soort", "Payment")
        je.title = get_journal_entry_title(mut, mutation_type)
        je = enhance_journal_entry_fields(je, mut, f"{party_type} Payment - Invoice Not Found")
        
        # Get amount
        total_amount = 0
        for regel in mut.get("MutatieRegels", []):
            total_amount += float(regel.get("BedragInclBTW", 0) or regel.get("BedragInvoer", 0))
        
        if total_amount == 0:
            return {"success": False, "error": "No amount found"}
        
        # Get bank account
        bank_account = get_bank_account(mut.get("Rekening"), company)
        
        # Get default receivable/payable account
        if party_type == "Customer":
            party_account = frappe.db.get_value("Company", company, "default_receivable_account")
            # Money received
            je.append("accounts", {
                "account": bank_account,
                "debit_in_account_currency": abs(total_amount),
                "cost_center": cost_center
            })
            je.append("accounts", {
                "account": party_account,
                "credit_in_account_currency": abs(total_amount),
                "cost_center": cost_center,
                "party_type": party_type,
                "party": get_or_create_customer(mut.get("RelatieCode"), mut.get("Omschrijving", ""))
            })
        else:
            party_account = frappe.db.get_value("Company", company, "default_payable_account")
            # Money paid
            je.append("accounts", {
                "account": party_account,
                "debit_in_account_currency": abs(total_amount),
                "cost_center": cost_center,
                "party_type": party_type,
                "party": get_or_create_supplier(mut.get("RelatieCode"), mut.get("Omschrijving", ""))
            })
            je.append("accounts", {
                "account": bank_account,
                "credit_in_account_currency": abs(total_amount),
                "cost_center": cost_center
            })
        
        je.insert(ignore_permissions=True)
        je.submit()
        
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

# Add custom fields for tracking
@frappe.whitelist()
def add_eboekhouden_custom_fields():
    """Add custom fields for E-Boekhouden tracking"""
    
    # Sales Invoice
    if not frappe.db.has_column("Sales Invoice", "eboekhouden_invoice_number"):
        frappe.get_doc({
            "doctype": "Custom Field",
            "dt": "Sales Invoice",
            "fieldname": "eboekhouden_invoice_number",
            "fieldtype": "Data",
            "label": "E-Boekhouden Invoice Number",
            "unique": 1,
            "no_copy": 1
        }).insert(ignore_permissions=True)
    
    # Customer
    if not frappe.db.has_column("Customer", "eboekhouden_relation_code"):
        frappe.get_doc({
            "doctype": "Custom Field",
            "dt": "Customer",
            "fieldname": "eboekhouden_relation_code",
            "fieldtype": "Data",
            "label": "E-Boekhouden Relation Code",
            "unique": 1
        }).insert(ignore_permissions=True)
    
    # Journal Entry
    if not frappe.db.has_column("Journal Entry", "eboekhouden_mutation_nr"):
        frappe.get_doc({
            "doctype": "Custom Field",
            "dt": "Journal Entry",
            "fieldname": "eboekhouden_mutation_nr",
            "fieldtype": "Data",
            "label": "E-Boekhouden Mutation Nr",
            "unique": 1,
            "no_copy": 1
        }).insert(ignore_permissions=True)
    
    return {"success": True, "message": "Custom fields added"}

def fix_account_types_for_migration(company):
    """Fix account types based on actual usage in E-Boekhouden data"""
    
    # Instead of relying on account numbers, analyze actual usage from mutations
    # This is more reliable as it reflects how accounts are actually used
    
    # Get a sample of recent mutations to understand account usage
    from .eboekhouden_soap_api import EBoekhoudenSOAPAPI
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenSOAPAPI(settings)
    
    # Get last 3 months of data to understand account usage
    date_to = frappe.utils.today()
    date_from = frappe.utils.add_months(date_to, -3)
    
    result = api.get_mutations(date_from=date_from, date_to=date_to)
    
    if result["success"]:
        receivable_accounts = set()
        payable_accounts = set()
        
        for mut in result["mutations"]:
            mutation_type = mut.get("Soort")
            
            # Collect receivable accounts from sales invoices
            if mutation_type == "FactuurVerstuurd":
                account_code = mut.get("Rekening")
                if account_code:
                    receivable_accounts.add(account_code)
                    
            # Collect payable accounts from purchase invoices
            elif mutation_type == "FactuurOntvangen":
                account_code = mut.get("Rekening")
                if account_code:
                    payable_accounts.add(account_code)
        
        # Now fix the account types based on actual usage
        for account_code in receivable_accounts:
            fix_account_type(account_code, company, "Receivable")
            
        for account_code in payable_accounts:
            fix_account_type(account_code, company, "Payable")
    
    # Also check account names for common patterns (language-agnostic approach)
    common_receivable_keywords = [
        "debtor", "debiteur", "receivable", "te ontvangen", "vordering", 
        "customer", "klant", "afnemer"
    ]
    
    common_payable_keywords = [
        "creditor", "crediteur", "payable", "te betalen", "schuld",
        "supplier", "leverancier", "vendor"
    ]
    
    tax_keywords = [
        "btw", "vat", "tax", "belasting", "omzetbelasting"
    ]
    
    # Check all accounts by name
    accounts = frappe.db.get_all("Account", {
        "company": company,
        "is_group": 0
    }, ["name", "account_name", "account_type"])
    
    for account in accounts:
        account_name_lower = account.account_name.lower()
        
        # Skip if it's a tax account
        if any(keyword in account_name_lower for keyword in tax_keywords):
            if account.account_type != "Tax":
                frappe.db.set_value("Account", account.name, "account_type", "Tax")
            continue
            
        # Check for receivable patterns
        if any(keyword in account_name_lower for keyword in common_receivable_keywords):
            if account.account_type not in ["Receivable", "Bank", "Cash"]:
                frappe.db.set_value("Account", account.name, "account_type", "Receivable")
                
        # Check for payable patterns
        elif any(keyword in account_name_lower for keyword in common_payable_keywords):
            if account.account_type != "Payable":
                frappe.db.set_value("Account", account.name, "account_type", "Payable")
    
    frappe.db.commit()

def fix_account_type(account_code, company, target_type):
    """Fix a specific account to have the target account type"""
    # Try to find account by number
    account = frappe.db.get_value("Account", {
        "account_number": account_code,
        "company": company
    }, ["name", "account_type"], as_dict=True)
    
    if not account:
        # Try by name pattern
        account = frappe.db.get_value("Account", {
            "name": ["like", f"{account_code}%"],
            "company": company
        }, ["name", "account_type"], as_dict=True)
    
    if account and account.account_type != target_type:
        frappe.db.set_value("Account", account.name, "account_type", target_type)

def process_purchase_invoices(mutations, company, cost_center, migration_doc):
    """Process FactuurOntvangen (purchase invoices)"""
    created = 0
    errors = []
    
    for mut in mutations:
        try:
            # Skip if already imported
            invoice_no = mut.get("Factuurnummer")
            if not invoice_no:
                continue
                
            if frappe.db.exists("Purchase Invoice", {"eboekhouden_invoice_number": invoice_no}):
                continue
            
            # Parse mutation data
            posting_date = parse_date(mut.get("Datum"))
            supplier_code = mut.get("RelatieCode")
            description = mut.get("Omschrijving", "")
            
            # Get or create supplier
            supplier = get_or_create_supplier(supplier_code, description)
            
            # Create purchase invoice
            pi = frappe.new_doc("Purchase Invoice")
            pi.company = company
            pi.supplier = supplier
            pi.posting_date = posting_date
            pi.bill_date = posting_date  # Set bill_date same as posting_date
            pi.eboekhouden_invoice_number = invoice_no
            pi.remarks = description
            
            # Calculate and set due date
            try:
                payment_terms = int(mut.get("Betalingstermijn", 30))
            except (ValueError, TypeError):
                payment_terms = 30
            
            # Ensure payment terms is positive
            if payment_terms < 0:
                payment_terms = 0
            
            # Set due date - ensure it's not before posting date
            calculated_due_date = frappe.utils.add_days(posting_date, payment_terms)
            
            if frappe.utils.getdate(calculated_due_date) < frappe.utils.getdate(posting_date):
                pi.due_date = posting_date
            else:
                pi.due_date = calculated_due_date
            
            # Set the credit to account from E-Boekhouden mutation
            rekening_code = mut.get("Rekening")
            if rekening_code:
                # Get the account by code
                credit_account = get_account_by_code(rekening_code, company)
                if credit_account:
                    # Ensure it's marked as payable
                    current_type = frappe.db.get_value("Account", credit_account, "account_type")
                    if current_type != "Payable":
                        frappe.db.set_value("Account", credit_account, "account_type", "Payable")
                        frappe.db.commit()
                    pi.credit_to = credit_account
                else:
                    # Fallback to default
                    default_payable = frappe.db.get_value("Company", company, "default_payable_account")
                    if default_payable:
                        pi.credit_to = default_payable
            else:
                # Use default if no Rekening specified
                default_payable = frappe.db.get_value("Company", company, "default_payable_account")
                if default_payable:
                    pi.credit_to = default_payable
            
            # Set cost center
            pi.cost_center = cost_center
            
            # Add line items from MutatieRegels
            for regel in mut.get("MutatieRegels", []):
                amount = float(regel.get("BedragExclBTW", 0))
                if amount > 0:
                    pi.append("items", {
                        "item_code": get_or_create_item(regel.get("TegenrekeningCode")),
                        "qty": 1,
                        "rate": amount,
                        "expense_account": get_expense_account_by_code(regel.get("TegenrekeningCode"), company),
                        "cost_center": cost_center
                    })
            
            pi.insert(ignore_permissions=True)
            pi.submit()
            created += 1
            
        except Exception as e:
            errors.append(f"Purchase Invoice {mut.get('Factuurnummer')}: {str(e)}")
            migration_doc.log_error(f"Failed to create purchase invoice {invoice_no}: {str(e)}", "purchase_invoice", mut)
    
    return {"created": created, "errors": errors}

def process_supplier_payments(mutations, company, cost_center, migration_doc):
    """Process FactuurbetalingVerstuurd (supplier payments)"""
    created = 0
    errors = []
    
    for mut in mutations:
        try:
            invoice_no = mut.get("Factuurnummer")
            if not invoice_no:
                continue
            
            # Find the related purchase invoice
            pi_name = frappe.db.get_value("Purchase Invoice", 
                {"eboekhouden_invoice_number": invoice_no}, "name")
            
            if not pi_name:
                # Invoice not found, create unreconciled payment entry
                from .create_unreconciled_payment import create_unreconciled_payment_entry
                result = create_unreconciled_payment_entry(mut, company, cost_center, "Supplier")
                if result["success"]:
                    created += 1
                else:
                    errors.append(f"Unreconciled payment {mut.get('MutatieNr')}: {result['error']}")
                continue
            
            # Check if payment already exists for this mutation
            mutation_nr = mut.get("MutatieNr")
            existing_payment = frappe.db.exists("Payment Entry", {
                "reference_no": mutation_nr,
                "docstatus": ["!=", 2]  # Not cancelled
            })
            
            if existing_payment:
                # Payment already exists for this mutation, skip
                continue
            
            # Get the purchase invoice
            pi = frappe.get_doc("Purchase Invoice", pi_name)
            
            # Check if already paid
            if pi.outstanding_amount <= 0:
                continue
            
            # Create payment entry
            pe = frappe.new_doc("Payment Entry")
            pe.payment_type = "Pay"
            pe.company = company
            pe.posting_date = parse_date(mut.get("Datum"))
            pe.party_type = "Supplier"
            pe.party = pi.supplier
            
            # Set descriptive title
            from .eboekhouden_payment_naming import get_payment_entry_title, enhance_payment_entry_fields
            pe.title = get_payment_entry_title(mut, pe.party, "Pay")
            pe = enhance_payment_entry_fields(pe, mut)
            
            # Get amount from MutatieRegels
            amount = 0
            for regel in mut.get("MutatieRegels", []):
                amount += float(regel.get("BedragInvoer", 0))
            
            if amount <= 0:
                # Skip if no amount
                continue
                
            pe.paid_amount = amount
            pe.received_amount = pe.paid_amount
            pe.reference_no = mut.get("MutatieNr")
            pe.reference_date = pe.posting_date
            
            # Set bank account
            bank_code = mut.get("Rekening")
            if bank_code:
                bank_account = get_bank_account(bank_code, company)
                pe.paid_from = bank_account
            else:
                # Get default bank account
                default_bank = frappe.db.get_value("Account", {
                    "company": company,
                    "account_type": "Bank",
                    "is_group": 0
                }, "name")
                pe.paid_from = default_bank
            
            # Set payable account from invoice
            pe.paid_to = pi.credit_to
            
            # Add reference to the invoice
            pe.append("references", {
                "reference_doctype": "Purchase Invoice",
                "reference_name": pi_name,
                "allocated_amount": pe.paid_amount
            })
            
            pe.insert(ignore_permissions=True)
            pe.submit()
            created += 1
            
        except Exception as e:
            errors.append(f"Payment for Invoice {mut.get('Factuurnummer')}: {str(e)}")
            migration_doc.log_error(f"Failed to create supplier payment for invoice {invoice_no}: {str(e)}", "supplier_payment", mut)
    
    return {"created": created, "errors": errors}

def process_memorial_entries(mutations, company, cost_center, migration_doc):
    """Process Memoriaal entries - placeholder"""
    # Create journal entries for manual bookings
    return {"created": 0, "errors": []}

def get_processed_mutation_numbers(company):
    """Get list of already processed mutation numbers to avoid duplicates"""
    processed = set()
    
    # Check journal entries
    je_mutations = frappe.db.sql("""
        SELECT DISTINCT eboekhouden_mutation_nr 
        FROM `tabJournal Entry` 
        WHERE company = %s 
        AND eboekhouden_mutation_nr IS NOT NULL 
        AND eboekhouden_mutation_nr != ''
    """, company, as_dict=True)
    
    for je in je_mutations:
        processed.add(je.eboekhouden_mutation_nr)
    
    # We can add checks for other doctypes if they store mutation numbers
    
    return processed

def is_mutation_processed(mutation_nr, processed_set):
    """Check if a mutation has already been processed"""
    return str(mutation_nr) in processed_set

def get_last_processed_mutation_number(company):
    """Get the highest mutation number that has been processed"""
    last_processed = 0
    
    # Check journal entries
    last_je = frappe.db.sql("""
        SELECT MAX(CAST(eboekhouden_mutation_nr AS UNSIGNED)) as last_nr
        FROM `tabJournal Entry` 
        WHERE company = %s 
        AND eboekhouden_mutation_nr IS NOT NULL 
        AND eboekhouden_mutation_nr != ''
        AND eboekhouden_mutation_nr REGEXP '^[0-9]+$'
    """, company, as_dict=True)
    
    if last_je and last_je[0].get('last_nr'):
        last_processed = max(last_processed, int(last_je[0]['last_nr']))
    
    return last_processed

@frappe.whitelist()
def resume_migration(migration_doc_name=None):
    """Resume migration from where it left off"""
    if migration_doc_name:
        migration_doc = frappe.get_doc("E-Boekhouden Migration", migration_doc_name)
    else:
        # Get the latest migration doc
        migration_doc = frappe.get_last_doc("E-Boekhouden Migration")
    
    settings = frappe.get_single("E-Boekhouden Settings")
    company = settings.default_company
    
    if not company:
        return {
            "success": False,
            "error": "No default company set"
        }
    
    # Get the last processed mutation number
    last_processed = get_last_processed_mutation_number(company)
    
    if last_processed > 0:
        frappe.msgprint(f"Resuming migration from mutation number {last_processed + 1}")
        # Update the migration logic to start from last_processed + 1
        migration_doc.resume_from_mutation = last_processed + 1
    
    # Run the migration
    return migrate_using_soap(migration_doc, settings)