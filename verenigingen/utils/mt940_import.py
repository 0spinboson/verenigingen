import frappe
from frappe import _
from frappe.utils import getdate, today
import traceback
import base64
import tempfile
import os


@frappe.whitelist()
def import_mt940_file(bank_account, file_content, company=None):
    """
    Import MT940 bank statement file without expensive fintech license.
    
    Args:
        bank_account: ERPNext Bank Account name
        file_content: Base64 encoded MT940 file content
        company: Company name (optional, will be fetched from bank account)
    
    Returns:
        dict: Import results with success/error information
    """
    try:
        # Validate inputs
        if not bank_account:
            return {"success": False, "message": "Bank Account is required"}
        
        if not file_content:
            return {"success": False, "message": "File content is required"}
        
        # Decode file content
        try:
            mt940_content = base64.b64decode(file_content).decode('utf-8')
        except Exception as e:
            return {"success": False, "message": f"Failed to decode file content: {str(e)}"}
        
        # Get company from bank account if not provided
        if not company:
            company = frappe.db.get_value("Bank Account", bank_account, "company")
            if not company:
                return {"success": False, "message": f"Could not determine company for bank account {bank_account}"}
        
        # Validate bank account exists
        if not frappe.db.exists("Bank Account", bank_account):
            return {"success": False, "message": f"Bank Account {bank_account} does not exist"}
        
        # Process the MT940 file
        result = process_mt940_document(mt940_content, bank_account, company)
        
        return result
        
    except Exception as e:
        frappe.logger().error(f"Error in MT940 import: {str(e)}")
        frappe.logger().error(traceback.format_exc())
        return {
            "success": False, 
            "message": f"Import failed with error: {str(e)}"
        }


def process_mt940_document(mt940_content, bank_account, company):
    """
    Process MT940 document content using the WoLpH/mt940 library.
    
    Uses the free mt940 library instead of expensive fintech license.
    """
    try:
        # Try to import the mt940 library
        try:
            import mt940
        except ImportError:
            return {
                "success": False,
                "message": "MT940 library not available. Please install with: pip install mt-940"
            }
        
        # Write content to temporary file (mt940 library expects file path)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sta', delete=False) as temp_file:
            temp_file.write(mt940_content)
            temp_file_path = temp_file.name
        
        try:
            # Parse the MT940 file
            transactions = mt940.parse(temp_file_path)
            
            # Convert to list to check if any transactions found
            transaction_list = list(transactions)
            
            if not transaction_list:
                return {
                    "success": False,
                    "message": "No transactions found in MT940 file"
                }
            
            # Get bank account IBAN for validation
            bank_account_iban = frappe.db.get_value("Bank Account", bank_account, "bank_account_no")
            
            # Process transactions
            transactions_created = 0
            transactions_skipped = 0
            errors = []
            statement_iban = None
            
            for statement in transaction_list:
                # Extract IBAN from statement
                if hasattr(statement, 'data') and 'account_identification' in statement.data:
                    statement_iban = statement.data['account_identification']
                
                # Validate IBAN matches (if available)
                if bank_account_iban and statement_iban and bank_account_iban != statement_iban:
                    return {
                        "success": False,
                        "message": f"IBAN mismatch: Bank Account IBAN {bank_account_iban} does not match MT940 IBAN {statement_iban}"
                    }
                
                # Process each transaction in the statement
                statement_transactions = []
                if hasattr(statement, 'transactions'):
                    statement_transactions = statement.transactions
                elif hasattr(statement, '__iter__'):
                    try:
                        statement_transactions = list(statement)
                    except:
                        statement_transactions = [statement]
                else:
                    statement_transactions = [statement]
                
                for transaction in statement_transactions:
                    try:
                        # Create bank transaction
                        if create_bank_transaction_from_mt940(transaction, bank_account, company):
                            transactions_created += 1
                        else:
                            transactions_skipped += 1
                            
                    except Exception as e:
                        errors.append(f"Transaction error: {str(e)}")
                        frappe.logger().error(f"Error processing MT940 transaction: {str(e)}")
            
            return {
                "success": True,
                "message": f"Import completed: {transactions_created} transactions created, {transactions_skipped} skipped",
                "transactions_created": transactions_created,
                "transactions_skipped": transactions_skipped,
                "errors": errors[:10],  # Limit errors shown
                "iban": statement_iban,
                "statement_date": str(getdate(today()))
            }
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to process MT940 document: {str(e)}"
        }


def create_bank_transaction_from_mt940(mt940_transaction, bank_account, company):
    """
    Create ERPNext Bank Transaction from MT940 transaction.
    Adapted from banking app's _create_bank_transaction function.
    """
    try:
        import hashlib
        import contextlib
        
        # Extract transaction data from MT940 transaction
        transaction_data = mt940_transaction.data
        
        # Generate transaction ID
        transaction_id = (
            transaction_data.get('transaction_reference', '') or
            transaction_data.get('bank_reference', '') or
            generate_mt940_transaction_hash(mt940_transaction)
        )
        
        # Check if transaction already exists
        if transaction_id and frappe.db.exists(
            "Bank Transaction",
            {"transaction_id": transaction_id, "bank_account": bank_account}
        ):
            return False  # Already exists
        
        # Create new Bank Transaction
        bt = frappe.new_doc("Bank Transaction")
        bt.date = mt940_transaction.date
        bt.bank_account = bank_account
        bt.company = company
        
        # Handle amount and direction
        amount = float(mt940_transaction.amount.amount)
        bt.deposit = max(amount, 0)
        bt.withdrawal = abs(min(amount, 0))
        bt.currency = getattr(mt940_transaction.amount, 'currency', 'EUR')
        
        # Set description from available fields
        description_parts = []
        if hasattr(mt940_transaction, 'purpose_code') and mt940_transaction.purpose_code:
            description_parts.append(mt940_transaction.purpose_code)
        if transaction_data.get('purpose'):
            description_parts.append(transaction_data['purpose'])
        if transaction_data.get('extra_details'):
            description_parts.append(transaction_data['extra_details'])
        
        bt.description = "\n".join(filter(None, description_parts)) or "MT940 Transaction"
        
        # Set reference and party information
        bt.reference_number = transaction_data.get('transaction_reference', '')
        bt.transaction_id = transaction_id
        
        # Extract counterparty information
        if transaction_data.get('counterparty_name'):
            bt.bank_party_name = transaction_data['counterparty_name']
        if transaction_data.get('counterparty_account'):
            bt.bank_party_iban = transaction_data['counterparty_account']
        
        # Insert and submit
        with contextlib.suppress(frappe.exceptions.UniqueValidationError):
            bt.insert()
            bt.submit()
            return True
            
    except Exception as e:
        frappe.logger().error(f"Error creating bank transaction from MT940: {str(e)}")
        raise
    
    return False


def generate_mt940_transaction_hash(transaction):
    """Generate a hash for MT940 transaction identification"""
    import hashlib
    
    sha = hashlib.sha256()
    hash_components = [
        str(transaction.date),
        str(transaction.amount.amount),
        str(getattr(transaction.amount, 'currency', 'EUR')),
        str(transaction.data.get('transaction_reference', '')),
        str(transaction.data.get('bank_reference', '')),
        str(transaction.data.get('purpose', '')),
        str(transaction.data.get('counterparty_name', '')),
        str(transaction.data.get('counterparty_account', '')),
    ]
    
    sha.update("".join(hash_components).encode())
    return sha.hexdigest()[:16]  # Use first 16 characters


@frappe.whitelist()
def get_mt940_import_status():
    """Get status of recent MT940 imports"""
    try:
        # Get recent bank transactions that might have been imported
        recent_transactions = frappe.get_all(
            "Bank Transaction",
            filters={"modified": [">=", frappe.utils.add_days(today(), -7)]},
            fields=["name", "date", "bank_account", "deposit", "withdrawal", "description"],
            order_by="modified desc",
            limit=20
        )
        
        return {
            "success": True,
            "recent_transactions": recent_transactions,
            "total_recent": len(recent_transactions)
        }
        
    except Exception as e:
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def validate_mt940_file(file_content):
    """Validate an MT940 file without importing it"""
    try:
        # Decode file content
        mt940_content = base64.b64decode(file_content).decode('utf-8')
        
        # Try to import mt940 library
        try:
            import mt940
        except ImportError:
            return {
                "success": False,
                "message": "MT940 library not available. Please install with: pip install mt-940"
            }
        
        # Write to temporary file and parse
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sta', delete=False) as temp_file:
            temp_file.write(mt940_content)
            temp_file_path = temp_file.name
        
        try:
            # Parse document
            transactions = mt940.parse(temp_file_path)
            transaction_list = list(transactions)
            
            # Count total transactions
            total_transactions = 0
            statement_iban = None
            
            for statement in transaction_list:
                if hasattr(statement, 'data') and 'account_identification' in statement.data:
                    statement_iban = statement.data['account_identification']
                
                # Count transactions in statement
                if hasattr(statement, 'transactions'):
                    total_transactions += len(statement.transactions)
                elif hasattr(statement, '__iter__'):
                    try:
                        total_transactions += len(list(statement))
                    except:
                        total_transactions += 1
                else:
                    total_transactions += 1
            
            return {
                "success": True,
                "message": f"Valid MT940 file with {total_transactions} transactions",
                "transaction_count": total_transactions,
                "iban": statement_iban or 'Unknown',
                "file_size": len(mt940_content),
                "statements_count": len(transaction_list)
            }
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
        
    except Exception as e:
        return {
            "success": False,
            "message": f"Invalid MT940 file: {str(e)}"
        }


@frappe.whitelist()
def convert_mt940_to_csv(file_content, bank_account):
    """
    Convert MT940 file to CSV format that ERPNext can import.
    
    This provides an alternative approach using ERPNext's existing
    Bank Statement Import functionality.
    """
    try:
        # Decode and validate MT940 content
        mt940_content = base64.b64decode(file_content).decode('utf-8')
        
        # Import mt940 library
        try:
            import mt940
        except ImportError:
            return {
                "success": False,
                "message": "MT940 library not available. Please install with: pip install mt-940"
            }
        
        # Parse MT940 file
        import csv
        import io
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sta', delete=False) as temp_file:
            temp_file.write(mt940_content)
            temp_file_path = temp_file.name
        
        try:
            transactions = mt940.parse(temp_file_path)
            
            # Create CSV output
            output = io.StringIO()
            csv_writer = csv.writer(output)
            
            # Write header row matching ERPNext Bank Transaction fields
            csv_writer.writerow([
                'Date', 'Description', 'Reference Number', 'Deposit', 'Withdrawal',
                'Bank Account', 'Bank Party Name', 'Bank Party IBAN'
            ])
            
            # Write transaction rows
            for statement in transactions:
                statement_transactions = []
                if hasattr(statement, 'transactions'):
                    statement_transactions = statement.transactions
                elif hasattr(statement, '__iter__'):
                    try:
                        statement_transactions = list(statement)
                    except:
                        statement_transactions = [statement]
                else:
                    statement_transactions = [statement]
                
                for transaction in statement_transactions:
                    transaction_data = transaction.data
                    amount = float(transaction.amount.amount)
                    
                    csv_writer.writerow([
                        transaction.date.strftime('%Y-%m-%d'),
                        transaction_data.get('purpose', 'MT940 Transaction'),
                        transaction_data.get('transaction_reference', ''),
                        max(amount, 0),  # Deposit (positive amounts)
                        abs(min(amount, 0)),  # Withdrawal (negative amounts as positive)
                        bank_account,
                        transaction_data.get('counterparty_name', ''),
                        transaction_data.get('counterparty_account', '')
                    ])
            
            csv_content = output.getvalue()
            output.close()
            
            # Encode as base64 for download
            csv_base64 = base64.b64encode(csv_content.encode()).decode()
            
            return {
                "success": True,
                "message": "MT940 file converted to CSV successfully",
                "csv_content": csv_base64,
                "filename": f"mt940_import_{today()}.csv"
            }
            
        finally:
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to convert MT940 to CSV: {str(e)}"
        }