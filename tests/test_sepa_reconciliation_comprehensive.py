"""
Comprehensive unit tests for SEPA reconciliation system
Focuses on preventing double debiting and testing edge cases
"""

import frappe
import unittest
from unittest.mock import Mock, patch, MagicMock
from frappe.utils import getdate, add_days, now_datetime, flt
import json
import hashlib
from decimal import Decimal

class TestSEPAReconciliationComprehensive(unittest.TestCase):
    """Comprehensive tests for SEPA reconciliation with double debiting prevention"""
    
    def setUp(self):
        """Set up test data and environment"""
        self.test_bank_account = "Test Bank Account - SEPA"
        self.test_member_data = [
            {"name": "Member-001", "full_name": "John Doe", "iban": "NL02ABNA0123456789"},
            {"name": "Member-002", "full_name": "Jane Smith", "iban": "NL02ABNA0987654321"},
            {"name": "Member-003", "full_name": "Bob Johnson", "iban": "NL02ABNA0555666777"}
        ]
        
        # Create test batch data
        self.test_batch_data = {
            "name": "BATCH-2025-01-001",
            "batch_date": getdate(),
            "total_amount": 75.00,
            "entry_count": 3,
            "status": "Submitted"
        }
        
        # Create test bank transaction data
        self.test_transaction_data = {
            "name": "BT-2025-001",
            "date": getdate(),
            "description": "SEPA Collection BATCH-2025-01-001",
            "deposit": 75.00,
            "bank_account": self.test_bank_account
        }
    
    def tearDown(self):
        """Clean up test data"""
        # Clean up any test data created during tests
        pass
    
    # =============================================================================
    # DUPLICATE PREVENTION TESTS
    # =============================================================================
    
    def test_prevent_duplicate_payment_creation_exact_match(self):
        """Test preventing duplicate payments for same invoice with exact amount"""
        from verenigingen.api.sepa_reconciliation import create_payment_entry_with_duplicate_check
        
        invoice_name = "INV-001"
        amount = 25.00
        
        # Mock existing payment entry
        with patch('frappe.get_all') as mock_get_all:
            mock_get_all.return_value = [
                {"parent": "PE-001", "allocated_amount": 25.00}
            ]
            
            with self.assertRaises(frappe.ValidationError) as context:
                create_payment_entry_with_duplicate_check(invoice_name, amount, {})
            
            self.assertIn("already fully paid", str(context.exception))
    
    def test_prevent_duplicate_payment_creation_partial_existing(self):
        """Test preventing duplicate when partial payment exists"""
        from verenigingen.api.sepa_reconciliation import create_payment_entry_with_duplicate_check
        
        invoice_name = "INV-002"
        amount = 25.00
        
        # Mock partial existing payment
        with patch('frappe.get_all') as mock_get_all:
            mock_get_all.return_value = [
                {"parent": "PE-001", "allocated_amount": 15.00}
            ]
            
            # Should allow additional payment for remaining amount
            with patch('frappe.get_doc') as mock_get_doc, \
                 patch('frappe.db.commit') as mock_commit:
                
                mock_payment = Mock()
                mock_get_doc.return_value = mock_payment
                
                result = create_payment_entry_with_duplicate_check(invoice_name, 10.00, {})
                
                # Should succeed for remaining amount
                self.assertIsNotNone(result)
    
    def test_prevent_duplicate_payment_creation_overpayment(self):
        """Test preventing overpayment scenarios"""
        from verenigingen.api.sepa_reconciliation import create_payment_entry_with_duplicate_check
        
        invoice_name = "INV-003"
        
        # Mock existing full payment
        with patch('frappe.get_all') as mock_get_all:
            mock_get_all.return_value = [
                {"parent": "PE-001", "allocated_amount": 25.00}
            ]
            
            # Attempt to create additional payment
            with self.assertRaises(frappe.ValidationError) as context:
                create_payment_entry_with_duplicate_check(invoice_name, 5.00, {})
            
            self.assertIn("already fully paid", str(context.exception))
    
    def test_prevent_batch_reprocessing(self):
        """Test preventing reprocessing of already processed batches"""
        from verenigingen.api.sepa_reconciliation import check_batch_processing_status
        
        batch_name = "BATCH-2025-01-001"
        transaction_name = "BT-2025-001"
        
        # Mock already processed batch
        with patch('frappe.get_all') as mock_get_all:
            mock_get_all.return_value = [
                {"name": "PE-001", "custom_sepa_batch": batch_name}
            ]
            
            with self.assertRaises(frappe.ValidationError) as context:
                check_batch_processing_status(batch_name, transaction_name)
            
            self.assertIn("already been processed", str(context.exception))
    
    def test_prevent_return_file_reprocessing(self):
        """Test preventing duplicate processing of return files"""
        from verenigingen.api.sepa_reconciliation import check_return_file_processed
        
        return_file_hash = "abc123def456"
        
        # Mock already processed return file
        with patch('frappe.db.exists') as mock_exists:
            mock_exists.return_value = True
            
            with self.assertRaises(frappe.ValidationError) as context:
                check_return_file_processed(return_file_hash)
            
            self.assertIn("Return file already processed", str(context.exception))
    
    # =============================================================================
    # EDGE CASE TESTS - AMOUNT MATCHING
    # =============================================================================
    
    def test_multiple_batches_same_amount(self):
        """Test handling when multiple SEPA batches have the same amount"""
        from verenigingen.api.sepa_reconciliation import find_matching_sepa_batches
        
        transaction_amount = 50.00
        transaction_date = getdate()
        
        # Mock multiple batches with same amount
        with patch('frappe.get_all') as mock_get_all:
            mock_get_all.return_value = [
                {"name": "BATCH-001", "total_amount": 50.00, "batch_date": transaction_date},
                {"name": "BATCH-002", "total_amount": 50.00, "batch_date": transaction_date},
                {"name": "BATCH-003", "total_amount": 50.00, "batch_date": add_days(transaction_date, 1)}
            ]
            
            bank_transaction = Mock()
            bank_transaction.deposit = transaction_amount
            bank_transaction.date = transaction_date
            
            matches = find_matching_sepa_batches(bank_transaction)
            
            # Should return all matches with appropriate confidence levels
            self.assertEqual(len(matches), 3)
            
            # Same-day matches should have higher confidence
            same_day_matches = [m for m in matches if m["batch_date"] == transaction_date]
            self.assertEqual(len(same_day_matches), 2)
    
    def test_currency_rounding_edge_cases(self):
        """Test handling of currency rounding differences"""
        from verenigingen.api.sepa_reconciliation import amounts_match_with_tolerance
        
        # Test various rounding scenarios
        test_cases = [
            (25.00, 24.99, True),   # 1 cent difference - should match
            (25.00, 24.95, False),  # 5 cent difference - should not match
            (100.00, 99.98, True),  # 2 cent difference on larger amount
            (0.01, 0.00, False),    # Edge case with very small amounts
            (1000.00, 999.50, False)  # Large percentage difference
        ]
        
        for expected, actual, should_match in test_cases:
            with self.subTest(expected=expected, actual=actual):
                result = amounts_match_with_tolerance(expected, actual, tolerance=0.02)
                self.assertEqual(result, should_match,
                    f"Expected {expected} vs {actual} to {'match' if should_match else 'not match'}")
    
    def test_split_payment_scenarios(self):
        """Test when bank consolidates multiple batches into single transaction"""
        from verenigingen.api.sepa_reconciliation import identify_split_payment_scenario
        
        transaction_amount = 150.00
        
        # Mock multiple batches that sum to transaction amount
        with patch('frappe.get_all') as mock_get_all:
            mock_get_all.return_value = [
                {"name": "BATCH-001", "total_amount": 50.00, "batch_date": getdate()},
                {"name": "BATCH-002", "total_amount": 75.00, "batch_date": getdate()},
                {"name": "BATCH-003", "total_amount": 25.00, "batch_date": getdate()},
                {"name": "BATCH-004", "total_amount": 100.00, "batch_date": getdate()}  # This won't fit
            ]
            
            bank_transaction = Mock()
            bank_transaction.deposit = transaction_amount
            bank_transaction.date = getdate()
            
            split_scenarios = identify_split_payment_scenario(bank_transaction)
            
            # Should identify valid combinations that sum to transaction amount
            self.assertTrue(len(split_scenarios) > 0)
            
            # Verify each scenario sums correctly
            for scenario in split_scenarios:
                total = sum(batch["total_amount"] for batch in scenario["batches"])
                self.assertAlmostEqual(total, transaction_amount, places=2)
    
    def test_partial_success_amount_matching(self):
        """Test matching when received amount matches subset of batch items"""
        from verenigingen.api.sepa_reconciliation import identify_partial_success_items
        
        batch_items = [
            {"invoice": "INV-001", "amount": 25.00, "customer": "CUST-001"},
            {"invoice": "INV-002", "amount": 30.00, "customer": "CUST-002"},
            {"invoice": "INV-003", "amount": 20.00, "customer": "CUST-003"}
        ]
        received_amount = 45.00  # Should match first two items
        
        matched_items = identify_partial_success_items(batch_items, received_amount)
        
        # Should identify combinations that match received amount
        self.assertTrue(len(matched_items) > 0)
        
        for combination in matched_items:
            total = sum(item["amount"] for item in combination)
            self.assertAlmostEqual(total, received_amount, places=2)
    
    # =============================================================================
    # TIMING AND CONCURRENCY TESTS
    # =============================================================================
    
    def test_concurrent_processing_prevention(self):
        """Test preventing concurrent processing of same resource"""
        from verenigingen.api.sepa_reconciliation import acquire_processing_lock, release_processing_lock
        
        resource_id = "BATCH-2025-01-001"
        
        # First process acquires lock
        lock1 = acquire_processing_lock("sepa_batch", resource_id)
        self.assertTrue(lock1)
        
        # Second process should fail to acquire lock
        lock2 = acquire_processing_lock("sepa_batch", resource_id)
        self.assertFalse(lock2)
        
        # After releasing, should be able to acquire again
        release_processing_lock("sepa_batch", resource_id)
        lock3 = acquire_processing_lock("sepa_batch", resource_id)
        self.assertTrue(lock3)
        
        # Clean up
        release_processing_lock("sepa_batch", resource_id)
    
    def test_transaction_ordering_edge_cases(self):
        """Test handling when bank transactions arrive out of order"""
        from verenigingen.api.sepa_reconciliation import process_out_of_order_transactions
        
        # Create transactions with different dates but received out of order
        transactions = [
            {"name": "BT-003", "date": add_days(getdate(), 2), "amount": 25.00},
            {"name": "BT-001", "date": getdate(), "amount": 50.00},
            {"name": "BT-002", "date": add_days(getdate(), 1), "amount": 30.00}
        ]
        
        processed_order = process_out_of_order_transactions(transactions)
        
        # Should process in chronological order regardless of arrival order
        expected_order = ["BT-001", "BT-002", "BT-003"]
        actual_order = [t["name"] for t in processed_order]
        self.assertEqual(actual_order, expected_order)
    
    def test_delayed_return_processing(self):
        """Test processing return files days after initial reconciliation"""
        from verenigingen.api.sepa_reconciliation import process_delayed_return
        
        # Mock scenario where payments were created days ago
        with patch('frappe.get_all') as mock_get_all:
            mock_get_all.return_value = [
                {
                    "name": "PE-001",
                    "posting_date": add_days(getdate(), -5),
                    "custom_sepa_batch": "BATCH-001",
                    "reference_name": "INV-001"
                }
            ]
            
            return_data = {
                "Member_ID": "M001",
                "Invoice": "INV-001",
                "Amount": "25.00",
                "Return_Reason": "Insufficient funds"
            }
            
            with patch('frappe.get_doc') as mock_get_doc:
                mock_payment = Mock()
                mock_get_doc.return_value = mock_payment
                
                result = process_delayed_return(return_data)
                
                # Should successfully process even with time gap
                self.assertTrue(result["success"])
    
    # =============================================================================
    # DATA INTEGRITY TESTS
    # =============================================================================
    
    def test_orphaned_payment_entry_detection(self):
        """Test detection and handling of orphaned payment entries"""
        from verenigingen.api.sepa_reconciliation import detect_orphaned_payments
        
        with patch('frappe.get_all') as mock_get_all:
            # Mock payment entries without corresponding bank transactions
            mock_get_all.return_value = [
                {"name": "PE-001", "custom_bank_transaction": "BT-001"},
                {"name": "PE-002", "custom_bank_transaction": "BT-999"},  # Non-existent
                {"name": "PE-003", "custom_bank_transaction": None}  # Missing
            ]
            
            with patch('frappe.db.exists') as mock_exists:
                # Only BT-001 exists
                mock_exists.side_effect = lambda dt, name: name == "BT-001"
                
                orphaned = detect_orphaned_payments()
                
                # Should identify PE-002 and PE-003 as orphaned
                self.assertEqual(len(orphaned), 2)
                orphaned_names = [p["name"] for p in orphaned]
                self.assertIn("PE-002", orphaned_names)
                self.assertIn("PE-003", orphaned_names)
    
    def test_incomplete_reversal_detection(self):
        """Test detection of incomplete payment reversals"""
        from verenigingen.api.sepa_reconciliation import detect_incomplete_reversals
        
        with patch('frappe.get_all') as mock_get_all:
            # Mock scenario with failed reversal
            mock_get_all.return_value = [
                {
                    "name": "PE-001",
                    "payment_type": "Receive",
                    "custom_sepa_batch": "BATCH-001",
                    "reference_name": "INV-001",
                    "docstatus": 1  # Submitted
                }
            ]
            
            # Mock return record exists but no reversal payment
            with patch('frappe.db.exists') as mock_exists:
                mock_exists.side_effect = lambda dt, filters: dt == "SEPA Return Record"
                
                incomplete = detect_incomplete_reversals()
                
                # Should identify incomplete reversal
                self.assertTrue(len(incomplete) > 0)
                self.assertEqual(incomplete[0]["original_payment"], "PE-001")
    
    def test_missing_mandate_validation(self):
        """Test validation of SEPA mandates for batch items"""
        from verenigingen.api.sepa_reconciliation import validate_batch_mandates
        
        batch_data = {
            "name": "BATCH-001",
            "invoices": [
                {"customer": "CUST-001", "invoice": "INV-001"},
                {"customer": "CUST-002", "invoice": "INV-002"},
                {"customer": "CUST-003", "invoice": "INV-003"}
            ]
        }
        
        with patch('frappe.get_all') as mock_get_all:
            # Mock mandate check - only CUST-001 and CUST-002 have valid mandates
            mock_get_all.side_effect = [
                [{"name": "MANDATE-001"}],  # CUST-001 has mandate
                [{"name": "MANDATE-002"}],  # CUST-002 has mandate
                []  # CUST-003 has no mandate
            ]
            
            validation_result = validate_batch_mandates(batch_data)
            
            # Should identify missing mandate for CUST-003
            self.assertFalse(validation_result["valid"])
            self.assertEqual(len(validation_result["missing_mandates"]), 1)
            self.assertEqual(validation_result["missing_mandates"][0]["customer"], "CUST-003")
    
    def test_changed_bank_details_handling(self):
        """Test handling when IBAN changes between batch creation and processing"""
        from verenigingen.api.sepa_reconciliation import validate_bank_details_consistency
        
        batch_data = {
            "name": "BATCH-001",
            "creation_date": add_days(getdate(), -7),
            "invoices": [
                {"customer": "CUST-001", "mandate": "MANDATE-001"}
            ]
        }
        
        with patch('frappe.get_doc') as mock_get_doc:
            # Mock mandate with different IBAN than current member record
            mock_mandate = Mock()
            mock_mandate.iban = "NL02ABNA0123456789"
            
            mock_member = Mock()
            mock_member.iban = "NL02ABNA0987654321"  # Different IBAN
            
            mock_get_doc.side_effect = [mock_mandate, mock_member]
            
            validation_result = validate_bank_details_consistency(batch_data)
            
            # Should detect IBAN mismatch
            self.assertFalse(validation_result["valid"])
            self.assertTrue(len(validation_result["iban_mismatches"]) > 0)
    
    # =============================================================================
    # IDEMPOTENCY TESTS
    # =============================================================================
    
    def test_idempotency_key_generation(self):
        """Test generation of unique idempotency keys"""
        from verenigingen.api.sepa_reconciliation import generate_idempotency_key
        
        # Same inputs should generate same key
        key1 = generate_idempotency_key("BT-001", "BATCH-001", "reconcile")
        key2 = generate_idempotency_key("BT-001", "BATCH-001", "reconcile")
        self.assertEqual(key1, key2)
        
        # Different inputs should generate different keys
        key3 = generate_idempotency_key("BT-002", "BATCH-001", "reconcile")
        self.assertNotEqual(key1, key3)
        
        key4 = generate_idempotency_key("BT-001", "BATCH-002", "reconcile")
        self.assertNotEqual(key1, key4)
        
        key5 = generate_idempotency_key("BT-001", "BATCH-001", "reverse")
        self.assertNotEqual(key1, key5)
    
    def test_idempotent_operation_handling(self):
        """Test that operations with same idempotency key are handled correctly"""
        from verenigingen.api.sepa_reconciliation import execute_idempotent_operation
        
        operation_key = "test_operation_123"
        
        # First execution should succeed
        result1 = execute_idempotent_operation(operation_key, lambda: {"status": "success", "id": "PE-001"})
        self.assertEqual(result1["status"], "success")
        
        # Second execution with same key should return cached result
        result2 = execute_idempotent_operation(operation_key, lambda: {"status": "error", "id": "PE-002"})
        self.assertEqual(result2["status"], "success")  # Should return first result
        self.assertEqual(result2["id"], "PE-001")  # Should be same as first execution
    
    # =============================================================================
    # COMPREHENSIVE WORKFLOW TESTS
    # =============================================================================
    
    def test_complete_reconciliation_workflow_success(self):
        """Test complete successful reconciliation workflow"""
        from verenigingen.api.sepa_reconciliation import execute_complete_reconciliation
        
        workflow_data = {
            "bank_transaction": "BT-001",
            "sepa_batch": "BATCH-001",
            "processing_mode": "conservative"
        }
        
        with patch('verenigingen.api.sepa_reconciliation.check_batch_processing_status') as mock_check, \
             patch('verenigingen.api.sepa_reconciliation.acquire_processing_lock') as mock_lock, \
             patch('verenigingen.api.sepa_reconciliation.reconcile_full_sepa_batch') as mock_reconcile:
            
            mock_check.return_value = None  # No previous processing
            mock_lock.return_value = True   # Lock acquired
            mock_reconcile.return_value = {"success": True, "payments_created": 3}
            
            result = execute_complete_reconciliation(workflow_data)
            
            self.assertTrue(result["success"])
            self.assertEqual(result["payments_created"], 3)
    
    def test_complete_reconciliation_workflow_duplicate_prevention(self):
        """Test workflow properly prevents duplicate processing"""
        from verenigingen.api.sepa_reconciliation import execute_complete_reconciliation
        
        workflow_data = {
            "bank_transaction": "BT-001",
            "sepa_batch": "BATCH-001",
            "processing_mode": "conservative"
        }
        
        with patch('verenigingen.api.sepa_reconciliation.check_batch_processing_status') as mock_check:
            # Simulate batch already processed
            mock_check.side_effect = frappe.ValidationError("Batch already processed")
            
            with self.assertRaises(frappe.ValidationError):
                execute_complete_reconciliation(workflow_data)
    
    def test_return_file_processing_workflow(self):
        """Test complete return file processing workflow"""
        from verenigingen.api.sepa_reconciliation import process_complete_return_file
        
        return_file_content = """Member_ID,Amount,Return_Reason,Return_Code
M001,25.00,Insufficient funds,AM04
M002,30.00,Account closed,AC04"""
        
        with patch('verenigingen.api.sepa_reconciliation.check_return_file_processed') as mock_check, \
             patch('verenigingen.api.sepa_reconciliation.parse_sepa_return_csv') as mock_parse, \
             patch('verenigingen.api.sepa_reconciliation.process_individual_return') as mock_process:
            
            mock_check.return_value = None  # File not processed before
            mock_parse.return_value = [
                {"Member_ID": "M001", "Amount": "25.00", "Return_Reason": "Insufficient funds"},
                {"Member_ID": "M002", "Amount": "30.00", "Return_Reason": "Account closed"}
            ]
            mock_process.return_value = {"success": True}
            
            result = process_complete_return_file(return_file_content)
            
            self.assertTrue(result["success"])
            self.assertEqual(result["processed_count"], 2)
            self.assertEqual(mock_process.call_count, 2)

if __name__ == '__main__':
    unittest.main()