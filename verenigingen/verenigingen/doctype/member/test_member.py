import frappe
import unittest
import random
import string
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today, getdate
from verenigingen.verenigingen.doctype.member.member import Member

class TestMember(FrappeTestCase):
    def setUp(self):
        # Generate a unique identifier using only alphanumeric characters
        self.unique_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        
        # Create test member data with unique name
        self.member_data = {
            "first_name": f"Test{self.unique_id}",
            "last_name": "Member",
            "email": f"testmember{self.unique_id}@example.com",
            "mobile_no": "+31612345678",
            "payment_method": "Bank Transfer",
            "status": "Active",
            "member_since": today()
        }
        
        # Delete existing test members
        self.cleanup_test_data()
    
    def tearDown(self):
        # Clean up test data
        self.cleanup_test_data()
    
    def cleanup_test_data(self):
        # Clear any members with our test email pattern
        for m in frappe.get_all("Member", filters={"email": ["like", "testmember%@example.com"]}):
            try:
                frappe.delete_doc("Member", m.name, force=True)
            except Exception as e:
                # Ignore errors during cleanup
                print(f"Error cleaning up member {m.name}: {str(e)}")
            
        # Clean up any test customers
        for c in frappe.get_all("Customer", filters={"email_id": ["like", "testmember%@example.com"]}):
            try:
                frappe.delete_doc("Customer", c.name, force=True)
            except Exception as e:
                # Ignore errors during cleanup
                print(f"Error cleaning up customer {c.name}: {str(e)}")
            
        # Clean up any test users
        for u in frappe.get_all("User", filters={"email": ["like", "testmember%@example.com"]}):
            try:
                frappe.delete_doc("User", u.name, force=True)
            except Exception as e:
                # Ignore errors during cleanup
                print(f"Error cleaning up user {u.name}: {str(e)}")
    
    def test_create_member(self):
        """Test creating a new member"""
        member = frappe.new_doc("Member")
        member.update(self.member_data)
        member.insert()
        
        self.assertEqual(member.full_name, f"Test{self.unique_id} Member")
        self.assertEqual(member.email, f"testmember{self.unique_id}@example.com")
        self.assertTrue(member.name.startswith("Assoc-Member-"))
        
        # Test member_id generation
        self.assertTrue(member.member_id, "Member ID should be generated")
    
    def test_update_full_name(self):
        """Test that full_name is updated when component names change"""
        # Create unique member data for this test
        unique_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        member_data = {
            "first_name": f"Test{unique_id}",
            "last_name": "Member",
            "email": f"testmember{unique_id}@example.com",
            "mobile_no": "+31612345678",
            "payment_method": "Bank Transfer"
        }
        
        member = frappe.new_doc("Member")
        member.update(member_data)
        member.insert()
        
        # Initial full name
        self.assertEqual(member.full_name, f"Test{unique_id} Member")
        
        # Update name components
        member.middle_name = "Middle"
        member.update_full_name()
        
        # Verify full name is updated
        self.assertEqual(member.full_name, f"Test{unique_id} Middle Member")
    
    def test_validate_name(self):
        """Test validation for name fields"""
        # Create unique member data for this test
        unique_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        member_data = {
            "first_name": f"Test{unique_id}@", # Invalid character
            "last_name": "Member",
            "email": f"testmember{unique_id}@example.com",
            "mobile_no": "+31612345678",
            "payment_method": "Bank Transfer"
        }
        
        member = frappe.new_doc("Member")
        member.update(member_data)
        
        # Should raise an error
        with self.assertRaises(frappe.exceptions.ValidationError):
            member.insert()
    
    def test_validate_bank_details(self):
        """Test bank details validation for direct debit payment method"""
        # Create unique member data for this test
        unique_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        member_data = {
            "first_name": f"Test{unique_id}",
            "last_name": "Member",
            "email": f"testmember{unique_id}@example.com",
            "mobile_no": "+31612345678",
            "payment_method": "Direct Debit",
            "iban": "NL02ABNA0123456789",
            "bank_account_name": f"Test{unique_id} Member"
        }
        
        member = frappe.new_doc("Member")
        member.update(member_data)
        member.insert()
        
        # Verify IBAN is formatted correctly
        self.assertEqual(member.iban, "NL02 ABNA 0123 4567 89")
    
    def test_create_customer(self):
        """Test customer creation from member"""
        # Create unique member data for this test
        unique_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        member_data = {
            "first_name": f"Test{unique_id}",
            "last_name": "Member",
            "email": f"testmember{unique_id}@example.com",
            "mobile_no": "+31612345678",
            "payment_method": "Bank Transfer"
        }
        
        member = frappe.new_doc("Member")
        member.update(member_data)
        member.insert()
        
        # Check if customer is already created or not
        initial_customer = member.customer
        
        # If customer is already created during insertion, we'll verify it
        # If not, we'll create it manually
        if initial_customer:
            # Customer already exists, verify details
            customer = frappe.get_doc("Customer", initial_customer)
            self.assertEqual(customer.customer_name, member.full_name)
            self.assertEqual(customer.email_id, member.email)
            
            # Try calling create_customer again - should return existing customer
            customer_name = member.create_customer()
            self.assertEqual(customer_name, initial_customer)
        else:
            # No customer yet - create one
            self.assertFalse(member.customer)
            
            # Create customer
            customer_name = member.create_customer()
            
            # Reload member
            member.reload()
            
            # Verify customer is linked
            self.assertTrue(member.customer)
            self.assertEqual(member.customer, customer_name)
            
            # Verify customer details
            customer = frappe.get_doc("Customer", customer_name)
            self.assertEqual(customer.customer_name, member.full_name)
            self.assertEqual(customer.email_id, member.email)
            self.assertEqual(customer.mobile_no, member.mobile_no)
    
    def test_create_user(self):
        """Test user creation from member"""
        # This test may need to be skipped or modified based on permissions
        # Creating users often requires system manager privileges
        try:
            # Create unique member data for this test
            unique_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
            member_data = {
                "first_name": f"Test{unique_id}",
                "last_name": "Member",
                "email": f"testmember{unique_id}@example.com",
                "mobile_no": "+31612345678",
                "payment_method": "Bank Transfer"
            }
            
            member = frappe.new_doc("Member")
            member.update(member_data)
            member.insert()
            
            # Initially no user
            self.assertFalse(member.user)
            
            # Create user
            user_name = member.create_user()
            
            # Reload member
            member.reload()
            
            # Verify user is linked
            self.assertTrue(member.user)
            self.assertEqual(member.user, user_name)
            
            # Verify user details
            user = frappe.get_doc("User", user_name)
            self.assertEqual(user.email, member.email)
            self.assertEqual(user.first_name, member.first_name)
            self.assertEqual(user.last_name, member.last_name)
        except frappe.PermissionError:
            # If permission error, skip this test
            self.skipTest("Skipping test_create_user due to permission constraints")
    
    def test_payment_history(self):
        """Test payment history loading"""
        # Create unique member data for this test
        unique_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        member_data = {
            "first_name": f"Test{unique_id}",
            "last_name": "Member",
            "email": f"testmember{unique_id}@example.com",
            "mobile_no": "+31612345678",
            "payment_method": "Bank Transfer"
        }
        
        member = frappe.new_doc("Member")
        member.update(member_data)
        member.insert()
        
        # Create customer if not already created
        if not member.customer:
            member.create_customer()
            member.reload()
        
        # Verify the method exists
        self.assertTrue(hasattr(member, 'load_payment_history'))
        self.assertTrue(callable(getattr(member, 'load_payment_history')))
        
        # Try to load payment history (should not error even if empty)
        try:
            result = member.load_payment_history()
            self.assertTrue(result)
        except Exception as e:
            self.fail(f"load_payment_history raised {type(e).__name__} unexpectedly!")
    
    def test_calculate_age(self):
        """Test age calculation from birth date"""
        # Create unique member data for this test
        unique_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        member_data = {
            "first_name": f"Test{unique_id}",
            "last_name": "Member",
            "email": f"testmember{unique_id}@example.com",
            "mobile_no": "+31612345678",
            "payment_method": "Bank Transfer",
            "birth_date": add_days(today(), -365 * 30) # 30 years ago
        }
        
        member = frappe.new_doc("Member")
        member.update(member_data)
        member.insert()
        
        # Age should be 30 (or 29 if today is before birthday this year)
        self.assertTrue(member.age in [29, 30])
    
    def test_validate_iban_format(self):
        """Test IBAN validation and formatting"""
        member = frappe.new_doc("Member")
        
        # Test various IBAN formats
        test_cases = [
            ("NL02ABNA0123456789", "NL02 ABNA 0123 4567 89"),  # Dutch IBAN
            ("DE89370400440532013000", "DE89 3704 0044 0532 0130 00"),  # German IBAN
            ("GB29NWBK60161331926819", "GB29 NWBK 6016 1331 9268 19"),  # UK IBAN
        ]
        
        for input_iban, expected_output in test_cases:
            formatted_iban = member.validate_iban_format(input_iban)
            self.assertEqual(formatted_iban, expected_output)
        
        # Test invalid IBAN (too short)
        with self.assertRaises(frappe.exceptions.ValidationError):
            member.validate_iban_format("NL02ABNA")

    def test_chapter_matching(self):
        """Test chapter assignment and matching based on address"""
        # Create a test chapter with postal code patterns
        if frappe.db.exists("Chapter", "Test Chapter"):
            chapter = frappe.get_doc("Chapter", "Test Chapter")
        else:
            chapter = frappe.new_doc("Chapter")
            chapter.name = "Test Chapter"
            chapter.region = "Test Region"
            chapter.introduction = "Test Chapter for Chapter Matching"
            chapter.postal_codes = "1000-1099, 2500, 3*"
            chapter.published = 1
            chapter.insert(ignore_permissions=True)
                
        # Create an address in the chapter's region
        address = frappe.new_doc("Address")
        address.address_title = f"Test Address for {self.member_data['email']}"
        address.address_type = "Personal"
        address.address_line1 = "Test Street 123"
        address.city = "Test City"
        address.state = "Test Region"
        address.country = "Netherlands"
        address.pincode = "1050"  # Within the chapter's range
        address.insert(ignore_permissions=True)
            
        # Create a test member
        member = frappe.new_doc("Member")
        member.update(self.member_data)
        member.primary_address = address.name
        member.insert()
            
        # Test postal code matching
        self.assertTrue(chapter.matches_postal_code("1050"))
        self.assertTrue(chapter.matches_postal_code("2500"))
        self.assertTrue(chapter.matches_postal_code("3123"))
        self.assertFalse(chapter.matches_postal_code("4000"))
            
        # Test chapter suggestion
        result = frappe.call("verenigingen.verenigingen.doctype.chapter.chapter.suggest_chapter_for_member",
                            member_name=member.name,
                            postal_code=address.pincode,
                            state=address.state,
                            city=address.city)
        
        # Check if chapter management is disabled
        if result.get("disabled"):
            self.skipTest("Chapter management is disabled in the system")
        else:
            # Should find our test chapter
            self.assertTrue(result)
            self.assertTrue(result.get("matches_by_postal") or result.get("matches_by_region"))
                        
        # Clean up - Fix: First unlink the address from the member, then delete
        try:
            # First update the member to remove the address link
            member.primary_address = None
            member.save()
            
            # Now delete the member and address
            frappe.delete_doc("Member", member.name)
            
            # Try to delete the address, but use force if needed
            try:
                frappe.delete_doc("Address", address.name)
            except frappe.LinkExistsError:
                # If it still can't be deleted, use force_delete=True
                frappe.delete_doc("Address", address.name, force=True)
        except Exception as e:
            print(f"Cleanup error (can be ignored): {str(e)}")

    def test_new_member_skips_membership_status_update(self):
            """Test that new members don't trigger membership status updates"""
            # Create unique member data for this test
            unique_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
            member_data = {
                "first_name": f"Test{unique_id}",
                "last_name": "Member",
                "email": f"testmember{unique_id}@example.com",
                "mobile_no": "+31612345678",
                "payment_method": "Bank Transfer"
            }
            
            member = frappe.new_doc("Member")
            member.update(member_data)
            
            # Mock the update_membership_status method to track if it's called
            original_method = member.update_membership_status
            call_count = [0]  # Use list to allow modification in nested function
            
            def mock_update_membership_status():
                call_count[0] += 1
                return original_method()
            
            member.update_membership_status = mock_update_membership_status
            
            # Insert the new member - this should NOT call update_membership_status
            member.insert()
            
            # Verify that update_membership_status was NOT called for new member
            self.assertEqual(call_count[0], 0, "update_membership_status should not be called for new members")
            
            # Verify the member was created successfully
            self.assertTrue(member.name)
            self.assertEqual(member.full_name, f"Test{unique_id} Member")
    
    def test_existing_member_calls_membership_status_update(self):
        """Test that existing members DO trigger membership status updates on save"""
        # Create unique member data for this test
        unique_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        member_data = {
            "first_name": f"Test{unique_id}",
            "last_name": "Member",
            "email": f"testmember{unique_id}@example.com",
            "mobile_no": "+31612345678",
            "payment_method": "Bank Transfer"
        }
        
        # First create and save the member
        member = frappe.new_doc("Member")
        member.update(member_data)
        member.insert()
        
        # Now test updating an existing member
        member.reload()  # Ensure it's not considered "new"
        
        # Mock the update_membership_status method to track if it's called
        original_method = member.update_membership_status
        call_count = [0]  # Use list to allow modification in nested function
        
        def mock_update_membership_status():
            call_count[0] += 1
            # Don't call original method to avoid the database error for this test
            pass
        
        member.update_membership_status = mock_update_membership_status
        
        # Update something and save - this SHOULD call update_membership_status
        member.mobile_no = "+31687654321"
        member.save()
        
        # Verify that update_membership_status WAS called for existing member
        self.assertEqual(call_count[0], 1, "update_membership_status should be called for existing members")

    def test_member_creation_no_database_error(self):
        """Test that creating a new member doesn't cause database errors"""
        # This is a regression test for the original issue
        unique_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        member_data = {
            "first_name": f"Test{unique_id}",
            "last_name": "Member",
            "email": f"testmember{unique_id}@example.com",
            "mobile_no": "+31612345678",
            "payment_method": "Bank Transfer"
        }
        
        # This should not raise any database errors
        member = frappe.new_doc("Member")
        member.update(member_data)
        
        try:
            member.insert()
            # If we get here, the fix worked
            self.assertTrue(member.name)
            self.assertEqual(member.status, "Active")  # Default status
        except Exception as e:
            self.fail(f"Member creation failed with error: {str(e)}")

    def test_membership_status_fields_empty_for_new_member(self):
        """Test that membership status fields are empty for new members"""
        unique_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        member_data = {
            "first_name": f"Test{unique_id}",
            "last_name": "Member",
            "email": f"testmember{unique_id}@example.com",
            "mobile_no": "+31612345678",
            "payment_method": "Bank Transfer"
        }
        
        member = frappe.new_doc("Member")
        member.update(member_data)
        member.insert()
        
        # These fields should be empty for new members
        self.assertFalse(member.current_membership_details)
        self.assertFalse(member.current_membership_type)
        self.assertFalse(member.current_membership_start)
        self.assertFalse(member.current_membership_end)
        self.assertFalse(member.membership_status)
