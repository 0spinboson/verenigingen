"""
Unit tests for SEPA Period-Based Duplicate Prevention
Tests preventing invoicing for the same period twice
"""

import frappe
import unittest
from unittest.mock import Mock, patch, MagicMock
from frappe.utils import getdate, add_months, get_first_day, get_last_day, add_days
from verenigingen.api.sepa_period_duplicate_prevention import (
    check_period_invoicing_duplicates,
    check_subscription_period_duplicates,
    prevent_sepa_batch_period_duplicates,
    generate_membership_billing_periods,
    validate_invoice_period_fields,
    generate_period_duplicate_report,
    _periods_overlap,
    _get_overlap_type,
    _is_membership_item
)

class TestSEPAPeriodDuplicatePrevention(unittest.TestCase):
    """Test period-based duplicate prevention for SEPA reconciliation"""
    
    def setUp(self):
        """Set up test data"""
        self.test_member_name = "Member-001"
        self.test_customer_name = "Customer-001"
        self.current_month_start = get_first_day(getdate())
        self.current_month_end = get_last_day(getdate())
        self.next_month_start = get_first_day(add_months(getdate(), 1))
        self.next_month_end = get_last_day(add_months(getdate(), 1))
        
    # =============================================================================
    # PERIOD OVERLAP TESTS
    # =============================================================================
    
    def test_periods_overlap_exact_match(self):
        """Test period overlap detection for exact matches"""
        start_date = "2025-01-01"
        end_date = "2025-01-31"
        
        # Exact same period should overlap
        self.assertTrue(_periods_overlap(start_date, end_date, start_date, end_date))
    
    def test_periods_overlap_partial(self):
        """Test period overlap detection for partial overlaps"""
        # Period 1: January 1-31
        # Period 2: January 15 - February 15
        period1_start, period1_end = "2025-01-01", "2025-01-31"
        period2_start, period2_end = "2025-01-15", "2025-02-15"
        
        self.assertTrue(_periods_overlap(period1_start, period1_end, period2_start, period2_end))
        self.assertTrue(_periods_overlap(period2_start, period2_end, period1_start, period1_end))
    
    def test_periods_no_overlap(self):
        """Test period overlap detection for non-overlapping periods"""
        # Period 1: January
        # Period 2: March
        period1_start, period1_end = "2025-01-01", "2025-01-31"
        period2_start, period2_end = "2025-03-01", "2025-03-31"
        
        self.assertFalse(_periods_overlap(period1_start, period1_end, period2_start, period2_end))
    
    def test_periods_adjacent_no_overlap(self):
        """Test that adjacent periods don't overlap"""
        # Period 1: January 1-31
        # Period 2: February 1-28
        period1_start, period1_end = "2025-01-01", "2025-01-31"
        period2_start, period2_end = "2025-02-01", "2025-02-28"
        
        self.assertFalse(_periods_overlap(period1_start, period1_end, period2_start, period2_end))
    
    def test_get_overlap_type_exact(self):
        """Test overlap type detection for exact matches"""
        start_date = "2025-01-01"
        end_date = "2025-01-31"
        
        overlap_type = _get_overlap_type(start_date, end_date, start_date, end_date)
        self.assertEqual(overlap_type, "exact")
    
    def test_get_overlap_type_contained(self):
        """Test overlap type detection for contained periods"""
        # Period 1: January 10-20 (contained)
        # Period 2: January 1-31 (container)
        period1_start, period1_end = "2025-01-10", "2025-01-20"
        period2_start, period2_end = "2025-01-01", "2025-01-31"
        
        overlap_type = _get_overlap_type(period1_start, period1_end, period2_start, period2_end)
        self.assertEqual(overlap_type, "contained")
    
    def test_get_overlap_type_partial(self):
        """Test overlap type detection for partial overlaps"""
        # Period 1: January 1-31
        # Period 2: January 15 - February 15
        period1_start, period1_end = "2025-01-01", "2025-01-31"
        period2_start, period2_end = "2025-01-15", "2025-02-15"
        
        overlap_type = _get_overlap_type(period1_start, period1_end, period2_start, period2_end)
        self.assertEqual(overlap_type, "partial_end")
    
    # =============================================================================
    # MEMBERSHIP ITEM DETECTION TESTS
    # =============================================================================
    
    def test_is_membership_item_positive_cases(self):
        """Test membership item detection for positive cases"""
        positive_cases = [
            {"item_code": "MEMBERSHIP-ANNUAL", "item_name": "Annual Membership", "description": ""},
            {"item_code": "LIDMAATSCHAP-2025", "item_name": "Lidmaatschap 2025", "description": ""},
            {"item_code": "CONTRIB-001", "item_name": "Monthly Contribution", "description": ""},
            {"item_code": "SUB-MONTHLY", "item_name": "Monthly Subscription", "description": ""},
            {"item_code": "MEMBER-FEE", "item_name": "Membership Fee", "description": "Annual dues"}
        ]
        
        for item in positive_cases:
            with self.subTest(item=item):
                self.assertTrue(_is_membership_item(item), f"Item should be detected as membership: {item}")
    
    def test_is_membership_item_negative_cases(self):
        """Test membership item detection for negative cases"""
        negative_cases = [
            {"item_code": "PRODUCT-001", "item_name": "Physical Product", "description": "Merchandise"},
            {"item_code": "DONATION-GIFT", "item_name": "Donation Gift", "description": "One-time donation"},
            {"item_code": "EVENT-TICKET", "item_name": "Event Ticket", "description": "Conference ticket"},
            {"item_code": "BOOK-VEGAN", "item_name": "Vegan Cookbook", "description": "Recipe book"}
        ]
        
        for item in negative_cases:
            with self.subTest(item=item):
                self.assertFalse(_is_membership_item(item), f"Item should NOT be detected as membership: {item}")
    
    # =============================================================================
    # PERIOD DUPLICATE DETECTION TESTS
    # =============================================================================
    
    def test_check_period_invoicing_duplicates_no_duplicates(self):
        """Test period duplicate checking when no duplicates exist"""
        with patch('frappe.get_doc') as mock_get_doc, \
             patch('frappe.get_all') as mock_get_all:
            
            # Mock member document
            mock_member = Mock()
            mock_member.customer = self.test_customer_name
            mock_member.full_name = "Test Member"
            mock_get_doc.return_value = mock_member
            
            # Mock no existing invoices
            mock_get_all.return_value = []
            
            result = check_period_invoicing_duplicates(
                self.test_member_name,
                self.current_month_start.strftime("%Y-%m-%d"),
                self.current_month_end.strftime("%Y-%m-%d")
            )
            
            self.assertFalse(result["has_duplicates"])
            self.assertEqual(result["existing_invoices"], 0)
            self.assertEqual(len(result["period_duplicates"]), 0)
    
    def test_check_period_invoicing_duplicates_with_duplicates(self):
        """Test period duplicate checking when duplicates exist"""
        with patch('frappe.get_doc') as mock_get_doc, \
             patch('frappe.get_all') as mock_get_all, \
             patch('verenigingen.api.sepa_period_duplicate_prevention._is_strict_mode_enabled') as mock_strict:
            
            # Mock member document
            mock_member = Mock()
            mock_member.customer = self.test_customer_name
            mock_member.full_name = "Test Member"
            mock_get_doc.return_value = mock_member
            
            # Mock existing invoice with overlapping period
            mock_get_all.side_effect = [
                # First call: get existing invoices
                [{
                    "name": "INV-001",
                    "posting_date": self.current_month_start,
                    "grand_total": 25.00,
                    "custom_period_start": self.current_month_start,
                    "custom_period_end": self.current_month_end
                }],
                # Second call: get invoice items
                [{
                    "item_code": "MEMBERSHIP-MONTHLY",
                    "item_name": "Monthly Membership",
                    "description": "Monthly membership fee",
                    "amount": 25.00
                }]
            ]
            
            # Disable strict mode for this test
            mock_strict.return_value = False
            
            result = check_period_invoicing_duplicates(
                self.test_member_name,
                self.current_month_start.strftime("%Y-%m-%d"),
                self.current_month_end.strftime("%Y-%m-%d")
            )
            
            self.assertTrue(result["has_duplicates"])
            self.assertEqual(len(result["period_duplicates"]), 1)
            self.assertEqual(result["period_duplicates"][0]["invoice"], "INV-001")
            self.assertEqual(result["period_duplicates"][0]["overlap_type"], "exact")
    
    def test_check_period_invoicing_duplicates_strict_mode(self):
        """Test period duplicate checking with strict mode enabled"""
        with patch('frappe.get_doc') as mock_get_doc, \
             patch('frappe.get_all') as mock_get_all, \
             patch('verenigingen.api.sepa_period_duplicate_prevention._is_strict_mode_enabled') as mock_strict:
            
            # Mock member document
            mock_member = Mock()
            mock_member.customer = self.test_customer_name
            mock_member.full_name = "Test Member"
            mock_get_doc.return_value = mock_member
            
            # Mock existing invoice
            mock_get_all.side_effect = [
                [{"name": "INV-001", "posting_date": self.current_month_start, "grand_total": 25.00,
                  "custom_period_start": self.current_month_start, "custom_period_end": self.current_month_end}],
                [{"item_code": "MEMBERSHIP-MONTHLY", "item_name": "Monthly Membership", 
                  "description": "", "amount": 25.00}]
            ]
            
            # Enable strict mode
            mock_strict.return_value = True
            
            with self.assertRaises(frappe.ValidationError) as context:
                check_period_invoicing_duplicates(
                    self.test_member_name,
                    self.current_month_start.strftime("%Y-%m-%d"),
                    self.current_month_end.strftime("%Y-%m-%d")
                )
            
            self.assertIn("already has invoices for period", str(context.exception))
    
    # =============================================================================
    # SUBSCRIPTION PERIOD DUPLICATE TESTS
    # =============================================================================
    
    def test_check_subscription_period_duplicates_no_overlap(self):
        """Test subscription period checking with no overlaps"""
        with patch('frappe.get_doc') as mock_get_doc, \
             patch('frappe.get_all') as mock_get_all:
            
            # Mock subscription document
            mock_subscription = Mock()
            mock_subscription.customer = self.test_customer_name
            mock_get_doc.return_value = mock_subscription
            
            # Mock existing invoices from different periods
            mock_get_all.return_value = [
                {
                    "name": "INV-001",
                    "posting_date": add_days(self.current_month_start, -60),  # 2 months ago
                    "from_date": add_days(self.current_month_start, -60),
                    "to_date": add_days(self.current_month_end, -60),
                    "grand_total": 25.00,
                    "status": "Paid"
                }
            ]
            
            result = check_subscription_period_duplicates(
                "SUB-001",
                self.current_month_start.strftime("%Y-%m-%d"),
                self.current_month_end.strftime("%Y-%m-%d")
            )
            
            self.assertFalse(result["has_duplicates"])
            self.assertEqual(len(result["overlapping_invoices"]), 0)
    
    def test_check_subscription_period_duplicates_with_overlap(self):
        """Test subscription period checking with overlapping invoices"""
        with patch('frappe.get_doc') as mock_get_doc, \
             patch('frappe.get_all') as mock_get_all:
            
            # Mock subscription document
            mock_subscription = Mock()
            mock_subscription.customer = self.test_customer_name
            mock_get_doc.return_value = mock_subscription
            
            # Mock overlapping invoice
            mock_get_all.return_value = [
                {
                    "name": "INV-001",
                    "posting_date": self.current_month_start,
                    "from_date": self.current_month_start,
                    "to_date": self.current_month_end,
                    "grand_total": 25.00,
                    "status": "Paid"
                }
            ]
            
            result = check_subscription_period_duplicates(
                "SUB-001",
                self.current_month_start.strftime("%Y-%m-%d"),
                self.current_month_end.strftime("%Y-%m-%d")
            )
            
            self.assertTrue(result["has_duplicates"])
            self.assertEqual(len(result["overlapping_invoices"]), 1)
            self.assertEqual(result["overlapping_invoices"][0]["invoice"], "INV-001")
    
    # =============================================================================
    # SEPA BATCH PERIOD VALIDATION TESTS
    # =============================================================================
    
    def test_prevent_sepa_batch_period_duplicates_no_conflicts(self):
        """Test SEPA batch period validation with no conflicts"""
        with patch('frappe.get_doc') as mock_get_doc, \
             patch('verenigingen.api.sepa_period_duplicate_prevention.check_period_invoicing_duplicates') as mock_check:
            
            # Mock SEPA batch
            mock_batch = Mock()
            mock_batch.invoices = [
                Mock(sales_invoice="INV-001"),
                Mock(sales_invoice="INV-002")
            ]
            
            # Mock invoices
            mock_invoice1 = Mock()
            mock_invoice1.customer = "Customer-001"
            mock_invoice1.posting_date = self.current_month_start
            mock_invoice1.get.return_value = self.current_month_start
            
            mock_invoice2 = Mock()
            mock_invoice2.customer = "Customer-002"
            mock_invoice2.posting_date = self.current_month_start
            mock_invoice2.get.return_value = self.current_month_start
            
            mock_get_doc.side_effect = [mock_batch, mock_invoice1, mock_invoice2]
            
            # Mock no duplicates found
            mock_check.return_value = {"has_duplicates": False}
            
            with patch('verenigingen.api.sepa_period_duplicate_prevention._get_member_from_customer') as mock_member:
                mock_member.return_value = "Member-001"
                
                result = prevent_sepa_batch_period_duplicates("BATCH-001")
                
                self.assertFalse(result["has_conflicts"])
                self.assertEqual(result["validated_items"], 2)
                self.assertEqual(result["conflict_items"], 0)
    
    def test_prevent_sepa_batch_period_duplicates_with_conflicts(self):
        """Test SEPA batch period validation with conflicts"""
        with patch('frappe.get_doc') as mock_get_doc, \
             patch('verenigingen.api.sepa_period_duplicate_prevention.check_period_invoicing_duplicates') as mock_check, \
             patch('verenigingen.api.sepa_period_duplicate_prevention._is_strict_mode_enabled') as mock_strict:
            
            # Mock SEPA batch with one invoice
            mock_batch = Mock()
            mock_batch.invoices = [Mock(sales_invoice="INV-001")]
            
            # Mock invoice
            mock_invoice = Mock()
            mock_invoice.customer = "Customer-001"
            mock_invoice.posting_date = self.current_month_start
            mock_invoice.get.return_value = self.current_month_start
            
            mock_get_doc.side_effect = [mock_batch, mock_invoice]
            
            # Mock duplicates found
            mock_check.return_value = {
                "has_duplicates": True,
                "period_duplicates": [{"invoice": "INV-EXISTING", "overlap_type": "exact"}]
            }
            
            # Disable strict mode for this test
            mock_strict.return_value = False
            
            with patch('verenigingen.api.sepa_period_duplicate_prevention._get_member_from_customer') as mock_member:
                mock_member.return_value = "Member-001"
                
                result = prevent_sepa_batch_period_duplicates("BATCH-001")
                
                self.assertTrue(result["has_conflicts"])
                self.assertEqual(result["conflict_items"], 1)
                self.assertEqual(len(result["conflicts"]), 1)
    
    # =============================================================================
    # BILLING PERIOD GENERATION TESTS
    # =============================================================================
    
    def test_generate_membership_billing_periods_monthly(self):
        """Test generation of monthly billing periods"""
        start_date = "2025-01-01"
        periods = generate_membership_billing_periods("Member-001", start_date, "Monthly")
        
        self.assertEqual(len(periods), 12)  # 12 monthly periods
        
        # Check first period
        self.assertEqual(periods[0]["period_start"], "2025-01-01")
        self.assertEqual(periods[0]["period_end"], "2025-01-31")
        self.assertEqual(periods[0]["billing_frequency"], "Monthly")
        
        # Check second period
        self.assertEqual(periods[1]["period_start"], "2025-02-01")
        self.assertEqual(periods[1]["period_end"], "2025-02-28")
    
    def test_generate_membership_billing_periods_quarterly(self):
        """Test generation of quarterly billing periods"""
        start_date = "2025-01-01"
        periods = generate_membership_billing_periods("Member-001", start_date, "Quarterly")
        
        self.assertEqual(len(periods), 4)  # 4 quarterly periods
        
        # Check first quarter
        self.assertEqual(periods[0]["period_start"], "2025-01-01")
        self.assertEqual(periods[0]["period_end"], "2025-03-31")
        
        # Check second quarter  
        self.assertEqual(periods[1]["period_start"], "2025-04-01")
        self.assertEqual(periods[1]["period_end"], "2025-06-30")
    
    def test_generate_membership_billing_periods_yearly(self):
        """Test generation of yearly billing periods"""
        start_date = "2025-01-01"
        periods = generate_membership_billing_periods("Member-001", start_date, "Yearly")
        
        self.assertEqual(len(periods), 1)  # 1 yearly period
        
        # Check yearly period
        self.assertEqual(periods[0]["period_start"], "2025-01-01")
        self.assertEqual(periods[0]["period_end"], "2025-12-31")
        self.assertEqual(periods[0]["billing_frequency"], "Yearly")
    
    def test_generate_membership_billing_periods_invalid_frequency(self):
        """Test handling of invalid billing frequency"""
        with self.assertRaises(frappe.ValidationError):
            generate_membership_billing_periods("Member-001", "2025-01-01", "Invalid")
    
    # =============================================================================
    # INVOICE VALIDATION TESTS
    # =============================================================================
    
    def test_validate_invoice_period_fields_non_membership(self):
        """Test invoice validation skips non-membership invoices"""
        mock_invoice = Mock()
        mock_invoice.customer = "Customer-001"
        mock_invoice.items = [
            Mock(item_code="PRODUCT-001", item_name="Physical Product", description="Merchandise")
        ]
        
        # Should not raise any errors or set period fields
        validate_invoice_period_fields(mock_invoice)
        
        # Period fields should not be set
        self.assertFalse(hasattr(mock_invoice, 'custom_period_start'))
    
    def test_validate_invoice_period_fields_membership_auto_populate(self):
        """Test automatic population of period fields for membership invoices"""
        with patch('verenigingen.api.sepa_period_duplicate_prevention.get_first_day') as mock_first_day, \
             patch('verenigingen.api.sepa_period_duplicate_prevention.get_last_day') as mock_last_day:
            
            mock_first_day.return_value = self.current_month_start
            mock_last_day.return_value = self.current_month_end
            
            mock_invoice = Mock()
            mock_invoice.customer = "Customer-001"
            mock_invoice.posting_date = self.current_month_start
            mock_invoice.items = [
                Mock(item_code="MEMBERSHIP-MONTHLY", item_name="Monthly Membership", description="")
            ]
            mock_invoice.get.return_value = None  # No existing period fields
            
            validate_invoice_period_fields(mock_invoice)
            
            # Period fields should be set
            self.assertEqual(mock_invoice.custom_period_start, self.current_month_start)
            self.assertEqual(mock_invoice.custom_period_end, self.current_month_end)
            self.assertEqual(mock_invoice.custom_membership_type, "Standard")
    
    # =============================================================================
    # PERIOD DUPLICATE REPORT TESTS
    # =============================================================================
    
    def test_generate_period_duplicate_report_no_duplicates(self):
        """Test period duplicate report generation with no duplicates"""
        with patch('frappe.get_all') as mock_get_all:
            # Mock no membership invoices
            mock_get_all.return_value = []
            
            result = generate_period_duplicate_report("Last Month")
            
            self.assertEqual(result["summary"]["total_membership_invoices"], 0)
            self.assertEqual(result["summary"]["customers_with_duplicates"], 0)
            self.assertEqual(result["summary"]["total_duplicate_pairs"], 0)
            self.assertEqual(len(result["top_duplicate_customers"]), 0)
    
    def test_generate_period_duplicate_report_with_duplicates(self):
        """Test period duplicate report generation with duplicates found"""
        with patch('frappe.get_all') as mock_get_all:
            # Mock membership invoices with overlapping periods
            mock_get_all.side_effect = [
                # First call: get invoices
                [
                    {
                        "name": "INV-001",
                        "customer": "Customer-001",
                        "posting_date": self.current_month_start,
                        "grand_total": 25.00,
                        "custom_period_start": self.current_month_start,
                        "custom_period_end": self.current_month_end
                    },
                    {
                        "name": "INV-002", 
                        "customer": "Customer-001",
                        "posting_date": self.current_month_start,
                        "grand_total": 25.00,
                        "custom_period_start": self.current_month_start,
                        "custom_period_end": self.current_month_end
                    }
                ],
                # Subsequent calls: get invoice items (membership items)
                [{"item_code": "MEMBERSHIP-001", "item_name": "Membership", "description": ""}],
                [{"item_code": "MEMBERSHIP-001", "item_name": "Membership", "description": ""}]
            ]
            
            result = generate_period_duplicate_report("Last Month")
            
            self.assertEqual(result["summary"]["total_membership_invoices"], 2)
            self.assertEqual(result["summary"]["customers_with_duplicates"], 1)
            self.assertTrue(result["summary"]["total_duplicate_pairs"] > 0)
            self.assertEqual(len(result["top_duplicate_customers"]), 1)
            self.assertEqual(result["top_duplicate_customers"][0][0], "Customer-001")

if __name__ == '__main__':
    unittest.main()