"""
Create test data for SEPA reconciliation testing
"""

import frappe
from frappe import _
from frappe.utils import getdate, add_days, now_datetime, flt
import random

@frappe.whitelist()
def create_sepa_test_scenario():
    """Create a complete test scenario for SEPA reconciliation"""
    try:
        # Create test customers/members if they don't exist
        test_members = create_test_members()
        
        # Create test invoices
        test_invoices = create_test_invoices(test_members)
        
        # Create a SEPA batch
        sepa_batch = create_test_sepa_batch(test_invoices)
        
        # Create corresponding bank transactions (various scenarios)
        bank_transactions = create_test_bank_transactions(sepa_batch)
        
        return {
            "success": True,
            "test_data": {
                "members": [m["name"] for m in test_members],
                "invoices": [inv["name"] for inv in test_invoices],
                "sepa_batch": sepa_batch["name"],
                "bank_transactions": [txn["name"] for txn in bank_transactions]
            },
            "message": "Test scenario created successfully"
        }
        
    except Exception as e:
        frappe.log_error(f"Error creating SEPA test scenario: {str(e)}")
        return {"success": False, "error": str(e)}

def create_test_members():
    """Create test members for SEPA testing"""
    test_members = []
    
    member_data = [
        {"first_name": "John", "last_name": "Doe", "email": "john.doe@test.com", "member_id": "TEST001"},
        {"first_name": "Jane", "last_name": "Smith", "email": "jane.smith@test.com", "member_id": "TEST002"},
        {"first_name": "Bob", "last_name": "Johnson", "email": "bob.johnson@test.com", "member_id": "TEST003"},
        {"first_name": "Alice", "last_name": "Brown", "email": "alice.brown@test.com", "member_id": "TEST004"},
        {"first_name": "Charlie", "last_name": "Wilson", "email": "charlie.wilson@test.com", "member_id": "TEST005"}
    ]
    
    for data in member_data:
        # Check if member already exists
        existing = frappe.db.exists("Member", {"email": data["email"]})
        
        if not existing:
            # Create customer first
            customer = frappe.get_doc({
                "doctype": "Customer",
                "customer_name": f"{data['first_name']} {data['last_name']}",
                "customer_type": "Individual",
                "customer_group": "Individual"
            })
            customer.insert(ignore_permissions=True)
            
            # Create member
            member = frappe.get_doc({
                "doctype": "Member",
                "first_name": data["first_name"],
                "last_name": data["last_name"],
                "full_name": f"{data['first_name']} {data['last_name']}",
                "email": data["email"],
                "member_id": data["member_id"],
                "customer": customer.name,
                "membership_status": "Active"
            })
            member.insert(ignore_permissions=True)
            test_members.append({"name": member.name, "customer": customer.name})
        else:
            member = frappe.get_doc("Member", existing)
            test_members.append({"name": member.name, "customer": member.customer})
    
    return test_members

def create_test_invoices(test_members):
    """Create test invoices for the members"""
    test_invoices = []
    
    amounts = [15.00, 25.00, 30.00, 20.00, 35.00]  # Different membership amounts
    
    for i, member in enumerate(test_members):
        invoice = frappe.get_doc({
            "doctype": "Sales Invoice",
            "customer": member["customer"],
            "posting_date": getdate(),
            "due_date": add_days(getdate(), 14),
            "items": [{
                "item_code": "Membership Fee",  # Assuming this item exists
                "qty": 1,
                "rate": amounts[i],
                "amount": amounts[i]
            }]
        })
        
        # Set naming series if required
        if hasattr(invoice, 'naming_series'):
            invoice.naming_series = "ACC-SINV-.YYYY.-"
        
        invoice.insert(ignore_permissions=True)
        invoice.submit()
        
        test_invoices.append({
            "name": invoice.name,
            "customer": member["customer"],
            "amount": amounts[i]
        })
    
    return test_invoices

def create_test_sepa_batch(test_invoices):
    """Create a SEPA batch with the test invoices"""
    
    batch = frappe.get_doc({
        "doctype": "Direct Debit Batch",
        "batch_date": getdate(),
        "batch_description": "Test SEPA Batch for Reconciliation",
        "batch_type": "CORE",
        "currency": "EUR"
    })
    
    total_amount = 0
    
    # Add invoices to batch
    for invoice in test_invoices:
        batch.append("invoices", {
            "sales_invoice": invoice["name"],
            "customer": invoice["customer"],
            "amount": invoice["amount"]
        })
        total_amount += invoice["amount"]
    
    batch.total_amount = total_amount
    batch.entry_count = len(test_invoices)
    batch.insert(ignore_permissions=True)
    batch.submit()
    
    return {"name": batch.name, "total_amount": total_amount}

def create_test_bank_transactions(sepa_batch):
    """Create test bank transactions for different scenarios"""
    bank_transactions = []
    
    # Get default bank account
    bank_account = frappe.db.get_value("Bank Account", {"is_default": 1})
    if not bank_account:
        # Create a test bank account
        bank_account = create_test_bank_account()
    
    # Scenario 1: Full success - exact amount received
    full_success_txn = frappe.get_doc({
        "doctype": "Bank Transaction",
        "date": add_days(getdate(), 1),
        "description": f"SEPA Collection {sepa_batch['name']} - Full Success",
        "bank_account": bank_account,
        "deposit": sepa_batch["total_amount"],
        "reference_number": f"SEPA-{sepa_batch['name']}-001"
    })
    full_success_txn.insert(ignore_permissions=True)
    bank_transactions.append({"name": full_success_txn.name, "type": "full_success"})
    
    # Scenario 2: Partial success - one payment failed
    partial_amount = sepa_batch["total_amount"] - 30.00  # Assume €30 failed
    partial_txn = frappe.get_doc({
        "doctype": "Bank Transaction",
        "date": add_days(getdate(), 2),
        "description": f"SEPA Collection {sepa_batch['name']} - Partial",
        "bank_account": bank_account,
        "deposit": partial_amount,
        "reference_number": f"SEPA-{sepa_batch['name']}-002"
    })
    partial_txn.insert(ignore_permissions=True)
    bank_transactions.append({"name": partial_txn.name, "type": "partial_success"})
    
    # Scenario 3: Return transaction - failed payment coming back
    return_txn = frappe.get_doc({
        "doctype": "Bank Transaction",
        "date": add_days(getdate(), 3),
        "description": f"SEPA Return {sepa_batch['name']} - Member TEST003",
        "bank_account": bank_account,
        "withdrawal": 30.00,  # Money going out = return
        "reference_number": f"RETURN-{sepa_batch['name']}-001"
    })
    return_txn.insert(ignore_permissions=True)
    bank_transactions.append({"name": return_txn.name, "type": "return"})
    
    # Scenario 4: Unrelated transaction (should not match)
    unrelated_txn = frappe.get_doc({
        "doctype": "Bank Transaction",
        "date": getdate(),
        "description": "Regular bank transfer from supplier",
        "bank_account": bank_account,
        "deposit": 500.00,
        "reference_number": "SUPP-TRANSFER-001"
    })
    unrelated_txn.insert(ignore_permissions=True)
    bank_transactions.append({"name": unrelated_txn.name, "type": "unrelated"})
    
    return bank_transactions

def create_test_bank_account():
    """Create a test bank account if none exists"""
    account = frappe.get_doc({
        "doctype": "Bank Account",
        "account_name": "Test Bank Account - SEPA",
        "bank": "Test Bank",
        "account_type": "Current",
        "currency": "EUR",
        "is_default": 1
    })
    account.insert(ignore_permissions=True)
    return account.name

@frappe.whitelist()
def run_sepa_test_workflow():
    """Run through the complete SEPA reconciliation workflow with test data"""
    try:
        # Step 1: Create test scenario
        test_result = create_sepa_test_scenario()
        if not test_result["success"]:
            return test_result
        
        # Step 2: Identify SEPA transactions
        from verenigingen.api.sepa_reconciliation import identify_sepa_transactions
        identify_result = identify_sepa_transactions()
        
        # Step 3: Process the matches
        workflow_results = []
        
        if identify_result["success"] and identify_result["potential_matches"]:
            for match in identify_result["potential_matches"][:2]:  # Process first 2 matches
                for batch_match in match["matching_batches"]:
                    if batch_match["confidence"] == "high":
                        from verenigingen.api.sepa_reconciliation import process_sepa_transaction_conservative
                        process_result = process_sepa_transaction_conservative(
                            match["bank_transaction"],
                            batch_match["batch_name"]
                        )
                        workflow_results.append({
                            "transaction": match["bank_transaction"],
                            "batch": batch_match["batch_name"],
                            "result": process_result
                        })
        
        # Step 4: Test return correlation
        from verenigingen.api.sepa_reconciliation import correlate_return_transactions
        correlation_result = correlate_return_transactions()
        
        return {
            "success": True,
            "test_creation": test_result,
            "identification": identify_result,
            "processing": workflow_results,
            "correlation": correlation_result,
            "message": "Complete SEPA test workflow executed successfully"
        }
        
    except Exception as e:
        frappe.log_error(f"Error running SEPA test workflow: {str(e)}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def cleanup_sepa_test_data():
    """Clean up test data created for SEPA testing"""
    try:
        cleanup_results = []
        
        # Delete test bank transactions
        test_transactions = frappe.get_all("Bank Transaction",
            filters={"description": ["like", "%Test%"]},
            fields=["name"]
        )
        for txn in test_transactions:
            frappe.delete_doc("Bank Transaction", txn.name, ignore_permissions=True)
        cleanup_results.append(f"Deleted {len(test_transactions)} test bank transactions")
        
        # Delete test SEPA batches
        test_batches = frappe.get_all("Direct Debit Batch",
            filters={"batch_description": ["like", "%Test%"]},
            fields=["name"]
        )
        for batch in test_batches:
            frappe.delete_doc("Direct Debit Batch", batch.name, ignore_permissions=True)
        cleanup_results.append(f"Deleted {len(test_batches)} test SEPA batches")
        
        # Delete test invoices
        test_invoices = frappe.get_all("Sales Invoice",
            filters={"customer": ["like", "%Test%"]},
            fields=["name"]
        )
        for invoice in test_invoices:
            frappe.delete_doc("Sales Invoice", invoice.name, ignore_permissions=True)
        cleanup_results.append(f"Deleted {len(test_invoices)} test invoices")
        
        # Delete test customers
        test_customers = frappe.get_all("Customer",
            filters={"customer_name": ["like", "%Test%"]},
            fields=["name"]
        )
        for customer in test_customers:
            frappe.delete_doc("Customer", customer.name, ignore_permissions=True)
        cleanup_results.append(f"Deleted {len(test_customers)} test customers")
        
        # Delete test members
        test_members = frappe.get_all("Member",
            filters={"email": ["like", "%test.com"]},
            fields=["name"]
        )
        for member in test_members:
            frappe.delete_doc("Member", member.name, ignore_permissions=True)
        cleanup_results.append(f"Deleted {len(test_members)} test members")
        
        frappe.db.commit()
        
        return {
            "success": True,
            "cleanup_results": cleanup_results,
            "message": "Test data cleanup completed"
        }
        
    except Exception as e:
        frappe.log_error(f"Error cleaning up SEPA test data: {str(e)}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def create_sample_return_file():
    """Create a sample SEPA return file for testing"""
    return_data = [
        {"Member_ID": "TEST003", "Amount": "30.00", "Return_Reason": "Insufficient funds", "Return_Code": "AM04"},
        {"Member_ID": "TEST005", "Amount": "35.00", "Return_Reason": "Account closed", "Return_Code": "AC04"}
    ]
    
    csv_content = "Member_ID,Amount,Return_Reason,Return_Code\n"
    for item in return_data:
        csv_content += f"{item['Member_ID']},{item['Amount']},{item['Return_Reason']},{item['Return_Code']}\n"
    
    return {
        "success": True,
        "csv_content": csv_content,
        "filename": "sepa_returns_sample.csv"
    }