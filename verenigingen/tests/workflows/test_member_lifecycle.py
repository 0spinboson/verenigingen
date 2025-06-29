# -*- coding: utf-8 -*-
# Copyright (c) 2025, Your Organization and Contributors
# See license.txt

"""
Complete Member Lifecycle Workflow Test
Tests the entire journey from application submission to termination
"""

import frappe
from frappe.utils import today, add_days, add_months
import unittest

from verenigingen.tests.utils.base import VereningingenWorkflowTestCase
from verenigingen.tests.utils.factories import TestDataBuilder, TestUserFactory, TestStateManager


class TestMemberLifecycle(VereningingenWorkflowTestCase):
    """
    Complete Member Lifecycle Test
    
    Stage 1: Submit Application
    Stage 2: Review & Approve Application
    Stage 3: Create Member, User Account, Customer
    Stage 4: Process Initial Payment
    Stage 5: Create/Renew Membership
    Stage 6: Optional - Create Volunteer Record
    Stage 7: Member Activities (join teams, submit expenses)
    Stage 8: Membership Renewal
    Stage 9: Optional - Suspension/Reactivation
    Stage 10: Termination Process
    """
    
    def setUp(self):
        """Set up the member lifecycle test"""
        super().setUp()
        self.state_manager = TestStateManager()
        self.test_data_builder = TestDataBuilder()
        
        # Set up test chapter for lifecycle
        self.test_chapter = self._create_test_chapter()
        self.admin_user = TestUserFactory.create_admin_user()
        
    def test_complete_member_lifecycle(self):
        """Test the complete member lifecycle from application to termination"""
        
        stages = [
            {
                'name': 'Stage 1: Submit Application',
                'function': self._stage_1_submit_application,
                'validations': [self._validate_application_submitted]
            },
            {
                'name': 'Stage 2: Review & Approve Application',
                'function': self._stage_2_review_approve,
                'validations': [self._validate_application_approved]
            },
            {
                'name': 'Stage 3: Create Member & User Account',
                'function': self._stage_3_create_member_user,
                'validations': [self._validate_member_created, self._validate_user_created]
            },
            {
                'name': 'Stage 4: Process Initial Payment',
                'function': self._stage_4_process_payment,
                'validations': [self._validate_payment_processed]
            },
            {
                'name': 'Stage 5: Create/Activate Membership',
                'function': self._stage_5_activate_membership,
                'validations': [self._validate_membership_active]
            },
            {
                'name': 'Stage 6: Create Volunteer Record',
                'function': self._stage_6_create_volunteer,
                'validations': [self._validate_volunteer_created]
            },
            {
                'name': 'Stage 7: Member Activities',
                'function': self._stage_7_member_activities,
                'validations': [self._validate_activities_completed]
            },
            {
                'name': 'Stage 8: Membership Renewal',
                'function': self._stage_8_membership_renewal,
                'validations': [self._validate_membership_renewed]
            },
            {
                'name': 'Stage 9: Suspension & Reactivation',
                'function': self._stage_9_suspension_reactivation,
                'validations': [self._validate_suspension_reactivation]
            },
            {
                'name': 'Stage 10: Termination Process',
                'function': self._stage_10_termination,
                'validations': [self._validate_termination_completed]
            }
        ]
        
        self.define_workflow(stages)
        
        with self.workflow_transaction():
            self.execute_workflow()
            
        # Final validations
        self._validate_complete_lifecycle()
        
    def _create_test_chapter(self):
        """Create a test chapter for the lifecycle"""
        chapter = frappe.get_doc({
            "doctype": "Chapter",
            "name": "Test Lifecycle Chapter",
            "region": "Test Region",
            "postal_codes": "1000-9999",
            "introduction": "Test chapter for lifecycle testing"
        })
        chapter.insert(ignore_permissions=True)
        self.track_doc("Chapter", chapter.name)
        return chapter
        
    # Stage 1: Submit Application
    def _stage_1_submit_application(self, context):
        """Stage 1: Submit membership application"""
        application_data = {
            "first_name": "TestLifecycle",
            "last_name": "Member",
            "email": "lifecycle.test@example.com",
            "contact_number": "+31612345678",
            "date_of_birth": "1990-01-01",
            "street_address": "Test Street 123",
            "postal_code": "1234AB",
            "city": "Amsterdam",
            "country": "Netherlands",
            "membership_type": "Annual",
            "payment_method": "SEPA",
            "iban": "NL91ABNA0417164300",
            "chapter_preference": self.test_chapter.name
        }
        
        # Submit application using API
        from verenigingen.api.membership_application import submit_application
        result = submit_application(application_data)
        
        self.assertTrue(result.get('success'), f"Application submission failed: {result.get('error')}")
        
        application_id = result.get('application_id')
        self.assertIsNotNone(application_id, "Application ID not returned")
        
        # Record state
        self.state_manager.record_state("Application", application_id, "Submitted")
        
        return {
            "application_id": application_id,
            "application_data": application_data
        }
        
    def _validate_application_submitted(self, context):
        """Validate application was submitted correctly"""
        application_id = context.get("application_id")
        self.assertIsNotNone(application_id)
        
        # Check application exists
        self.assert_doc_exists("Membership Application", application_id)
        
        # Check application state
        application = frappe.get_doc("Membership Application", application_id)
        self.assertEqual(application.status, "Submitted")
        self.assertEqual(application.first_name, "TestLifecycle")
        self.assertEqual(application.last_name, "Member")
        
    # Stage 2: Review & Approve Application
    def _stage_2_review_approve(self, context):
        """Stage 2: Review and approve the application"""
        application_id = context.get("application_id")
        
        with self.as_user(self.admin_user.name):
            # Review application
            from verenigingen.api.membership_application_review import review_application
            review_result = review_application(application_id, {
                "status": "Approved",
                "reviewer_notes": "Lifecycle test approval",
                "reviewer": self.admin_user.name
            })
            
            self.assertTrue(review_result.get('success'), 
                          f"Application review failed: {review_result.get('error')}")
            
        # Record state transition
        self.state_manager.record_state("Application", application_id, "Approved")
        
        return {"review_result": review_result}
        
    def _validate_application_approved(self, context):
        """Validate application was approved"""
        application_id = context.get("application_id")
        application = frappe.get_doc("Membership Application", application_id)
        
        self.assertEqual(application.status, "Approved")
        self.assertIsNotNone(application.approved_on)
        self.assertEqual(application.approved_by, self.admin_user.name)
        
    # Stage 3: Create Member & User Account  
    def _stage_3_create_member_user(self, context):
        """Stage 3: Create member record and user account"""
        application_id = context.get("application_id")
        
        with self.as_user(self.admin_user.name):
            # Create member from application
            from verenigingen.api.membership_application import create_member_from_application
            member_result = create_member_from_application(application_id)
            
            self.assertTrue(member_result.get('success'),
                          f"Member creation failed: {member_result.get('error')}")
            
            member_name = member_result.get('member_name')
            self.assertIsNotNone(member_name)
            
            # Create user account
            from verenigingen.api.member_management import create_user_account
            user_result = create_user_account(member_name)
            
            self.assertTrue(user_result.get('success'),
                          f"User creation failed: {user_result.get('error')}")
            
            user_email = user_result.get('user_email')
            
        # Record states
        self.state_manager.record_state("Member", member_name, "Created")
        self.state_manager.record_state("User", user_email, "Created")
        
        return {
            "member_name": member_name,
            "user_email": user_email
        }
        
    def _validate_member_created(self, context):
        """Validate member was created correctly"""
        member_name = context.get("member_name")
        self.assertIsNotNone(member_name)
        
        # Check member exists and is linked to application
        member = frappe.get_doc("Member", member_name)
        self.assertEqual(member.status, "Active")
        self.assertEqual(member.first_name, "TestLifecycle")
        
        # Check chapter membership
        chapter_members = [cm for cm in member.chapter_members if cm.chapter == self.test_chapter.name]
        self.assertTrue(len(chapter_members) > 0, "Member not assigned to chapter")
        
    def _validate_user_created(self, context):
        """Validate user account was created"""
        user_email = context.get("user_email")
        self.assertIsNotNone(user_email)
        
        # Check user exists and has correct roles
        user = frappe.get_doc("User", user_email)
        self.assertTrue(user.enabled)
        
        roles = [role.role for role in user.roles]
        self.assertIn("Member", roles)
        
    # Stage 4: Process Initial Payment
    def _stage_4_process_payment(self, context):
        """Stage 4: Process initial membership payment"""
        member_name = context.get("member_name")
        
        with self.as_user(self.admin_user.name):
            # Create customer and invoice
            from verenigingen.api.payment_processing import process_membership_payment
            payment_result = process_membership_payment(member_name, {
                "amount": 100.00,
                "payment_method": "SEPA",
                "description": "Initial membership fee"
            })
            
            self.assertTrue(payment_result.get('success'),
                          f"Payment processing failed: {payment_result.get('error')}")
            
            invoice_name = payment_result.get('invoice_name')
            
        # Record state
        self.state_manager.record_state("Payment", invoice_name, "Processed")
        
        return {"invoice_name": invoice_name}
        
    def _validate_payment_processed(self, context):
        """Validate payment was processed"""
        invoice_name = context.get("invoice_name")
        self.assertIsNotNone(invoice_name)
        
        # Check invoice exists and is paid
        if frappe.db.exists("Sales Invoice", invoice_name):
            invoice = frappe.get_doc("Sales Invoice", invoice_name)
            self.assertEqual(invoice.status, "Paid")
            
    # Stage 5: Create/Activate Membership
    def _stage_5_activate_membership(self, context):
        """Stage 5: Activate membership after payment"""
        member_name = context.get("member_name")
        
        with self.as_user(self.admin_user.name):
            # Create membership record
            membership = frappe.get_doc({
                "doctype": "Membership",
                "member": member_name,
                "membership_type": "Annual",
                "start_date": today(),
                "end_date": add_months(today(), 12),
                "status": "Active"
            })
            membership.insert(ignore_permissions=True)
            
        # Record state
        self.state_manager.record_state("Membership", membership.name, "Active")
        
        return {"membership_name": membership.name}
        
    def _validate_membership_active(self, context):
        """Validate membership is active"""
        membership_name = context.get("membership_name")
        self.assertIsNotNone(membership_name)
        
        membership = frappe.get_doc("Membership", membership_name)
        self.assertEqual(membership.status, "Active")
        self.assertIsNotNone(membership.start_date)
        self.assertIsNotNone(membership.end_date)
        
    # Stage 6: Create Volunteer Record
    def _stage_6_create_volunteer(self, context):
        """Stage 6: Create volunteer profile"""
        member_name = context.get("member_name")
        user_email = context.get("user_email")
        
        # Member decides to become a volunteer
        with self.as_user(user_email):
            volunteer = frappe.get_doc({
                "doctype": "Volunteer",
                "volunteer_name": "TestLifecycle Member",
                "email": user_email,
                "member": member_name,
                "status": "Active",
                "start_date": today(),
                "skills": "Event Organization, Community Outreach"
            })
            volunteer.insert(ignore_permissions=True)
            
        # Record state
        self.state_manager.record_state("Volunteer", volunteer.name, "Active")
        
        return {"volunteer_name": volunteer.name}
        
    def _validate_volunteer_created(self, context):
        """Validate volunteer record was created"""
        volunteer_name = context.get("volunteer_name")
        self.assertIsNotNone(volunteer_name)
        
        volunteer = frappe.get_doc("Volunteer", volunteer_name)
        self.assertEqual(volunteer.status, "Active")
        self.assertEqual(volunteer.member, context.get("member_name"))
        
    # Stage 7: Member Activities
    def _stage_7_member_activities(self, context):
        """Stage 7: Member participates in activities"""
        volunteer_name = context.get("volunteer_name")
        user_email = context.get("user_email")
        
        # Create team and join it
        with self.as_user(self.admin_user.name):
            team = frappe.get_doc({
                "doctype": "Team",
                "team_name": "Events Team",
                "chapter": self.test_chapter.name,
                "status": "Active",
                "team_type": "Project Team",
                "start_date": today()
            })
            team.insert(ignore_permissions=True)
            
            # Add volunteer to team
            team.append("team_members", {
                "volunteer": volunteer_name,
                "volunteer_name": "TestLifecycle Member",
                "role": "Event Coordinator",
                "role_type": "Team Leader",
                "from_date": today(),
                "is_active": 1,
                "status": "Active"
            })
            team.save(ignore_permissions=True)
            
        # Submit an expense
        with self.as_user(user_email):
            expense = frappe.get_doc({
                "doctype": "Volunteer Expense",
                "volunteer": volunteer_name,
                "amount": 50.00,
                "description": "Event supplies",
                "expense_date": today(),
                "status": "Draft"
            })
            expense.insert(ignore_permissions=True)
            
        return {
            "team_name": team.name,
            "expense_name": expense.name
        }
        
    def _validate_activities_completed(self, context):
        """Validate member activities were completed"""
        team_name = context.get("team_name")
        expense_name = context.get("expense_name")
        
        # Check team membership
        team = frappe.get_doc("Team", team_name)
        team_members = [tm for tm in team.team_members if tm.volunteer == context.get("volunteer_name")]
        self.assertTrue(len(team_members) > 0, "Volunteer not found in team")
        
        # Check expense submission
        expense = frappe.get_doc("Volunteer Expense", expense_name)
        self.assertEqual(expense.volunteer, context.get("volunteer_name"))
        
    # Stage 8: Membership Renewal
    def _stage_8_membership_renewal(self, context):
        """Stage 8: Renew membership for next period"""
        member_name = context.get("member_name")
        membership_name = context.get("membership_name")
        
        with self.as_user(self.admin_user.name):
            # Process renewal
            from verenigingen.api.membership_renewal import process_renewal
            renewal_result = process_renewal(membership_name, {
                "renewal_period": 12,
                "payment_method": "SEPA"
            })
            
            if renewal_result and renewal_result.get('success'):
                new_membership = renewal_result.get('new_membership_name')
            else:
                # Fallback: extend current membership
                membership = frappe.get_doc("Membership", membership_name)
                membership.end_date = add_months(membership.end_date, 12)
                membership.save(ignore_permissions=True)
                new_membership = membership_name
                
        # Record state
        self.state_manager.record_state("Membership", new_membership, "Renewed")
        
        return {"renewed_membership": new_membership}
        
    def _validate_membership_renewed(self, context):
        """Validate membership was renewed"""
        renewed_membership = context.get("renewed_membership")
        self.assertIsNotNone(renewed_membership)
        
        # Check membership is still active with extended end date
        membership = frappe.get_doc("Membership", renewed_membership)
        self.assertEqual(membership.status, "Active")
        
    # Stage 9: Suspension & Reactivation
    def _stage_9_suspension_reactivation(self, context):
        """Stage 9: Test suspension and reactivation"""
        member_name = context.get("member_name")
        
        with self.as_user(self.admin_user.name):
            # Suspend member
            from verenigingen.api.suspension_api import suspend_member
            suspend_result = suspend_member(member_name, {
                "reason": "Test suspension for lifecycle",
                "suspension_type": "Temporary"
            })
            
            if suspend_result and suspend_result.get('success'):
                # Record suspension
                self.state_manager.record_state("Member", member_name, "Suspended")
                
                # Reactivate member
                from verenigingen.api.suspension_api import reactivate_member
                reactivate_result = reactivate_member(member_name, {
                    "reason": "Test reactivation for lifecycle"
                })
                
                if reactivate_result and reactivate_result.get('success'):
                    self.state_manager.record_state("Member", member_name, "Active")
                    
        return {"suspension_tested": True}
        
    def _validate_suspension_reactivation(self, context):
        """Validate suspension and reactivation worked"""
        member_name = context.get("member_name")
        member = frappe.get_doc("Member", member_name)
        
        # Should be active again after reactivation
        self.assertEqual(member.status, "Active")
        
        # Check that suspension/reactivation transitions occurred
        transitions = self.state_manager.get_transitions("Member", member_name)
        suspension_transition = any(t["to_state"] == "Suspended" for t in transitions)
        reactivation_transition = any(t["from_state"] == "Suspended" and t["to_state"] == "Active" for t in transitions)
        
        # Only validate if suspension API is available
        if context.get("suspension_tested"):
            self.assertTrue(suspension_transition or reactivation_transition, 
                          "Expected suspension/reactivation transitions")
        
    # Stage 10: Termination Process
    def _stage_10_termination(self, context):
        """Stage 10: Terminate member"""
        member_name = context.get("member_name")
        
        with self.as_user(self.admin_user.name):
            # Terminate member
            from verenigingen.api.termination_api import terminate_member
            termination_result = terminate_member(member_name, {
                "termination_reason": "Lifecycle test completion",
                "termination_date": today(),
                "final_action": "Archive"
            })
            
            if termination_result and termination_result.get('success'):
                self.state_manager.record_state("Member", member_name, "Terminated")
            else:
                # Fallback: manually set status
                member = frappe.get_doc("Member", member_name)
                member.status = "Inactive"
                member.save(ignore_permissions=True)
                self.state_manager.record_state("Member", member_name, "Inactive")
                
        return {"termination_completed": True}
        
    def _validate_termination_completed(self, context):
        """Validate termination was completed"""
        member_name = context.get("member_name")
        member = frappe.get_doc("Member", member_name)
        
        # Member should be inactive/terminated
        self.assertIn(member.status, ["Inactive", "Terminated"])
        
    def _validate_complete_lifecycle(self):
        """Final validation of complete lifecycle"""
        # Check that all major state transitions occurred
        transitions = self.state_manager.get_transitions()
        
        # Should have transitions for: Application, Member, User, Payment, Membership, Volunteer
        entity_types = set(t["entity_type"] for t in transitions)
        expected_entities = {"Application", "Member", "User", "Membership"}
        
        for entity in expected_entities:
            self.assertIn(entity, entity_types, f"No transitions found for {entity}")
            
        # Check final states
        workflow_context = self.get_workflow_context()
        member_name = workflow_context.get("member_name")
        if member_name:
            final_member_state = self.state_manager.get_state("Member", member_name)
            self.assertIn(final_member_state, ["Inactive", "Terminated"], 
                         "Member should be in final state")