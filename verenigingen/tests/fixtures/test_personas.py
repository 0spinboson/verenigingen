# -*- coding: utf-8 -*-
# Copyright (c) 2025, Your Organization and Contributors
# See license.txt

"""
Standard Test Personas for Verenigingen
Provides pre-configured test personas for various testing scenarios
"""


import frappe
from frappe.utils import add_days, today

from verenigingen.tests.utils.factories import TestDataBuilder


class TestPersonas:
    """Factory for creating standard test personas"""

    @staticmethod
    def create_happy_path_hannah():
        """Create 'Happy Path Hannah' - Everything works perfectly"""
        builder = TestDataBuilder()

        # Perfect member with all details correct
        test_data = (
            builder.with_chapter("Amsterdam Test Chapter", postal_codes="1000-1099")
            .with_member(
                first_name="Hannah",
                last_name="Happy",
                email="hannah.happy@test.com",
                contact_number="+31612345678",
                birth_date=add_days(today(), -365 * 25),  # 25 years old
                street_name="Hoofdstraat",
                house_number="123",
                postal_code="1012",
                city="Amsterdam",
                country="Netherlands",
                payment_method="SEPA Direct Debit",
                iban="NL91ABNA0417164300",
                bank_account_name="Hannah Happy",
                newsletter_opt_in=1,
                status="Active",
            )
            .with_membership(membership_type="Annual Membership", payment_method="SEPA Direct Debit")
            .with_volunteer_profile(
                interests=["Event Planning", "Communications"],
                availability="Weekends",
                skills="Event organization, Social media",
            )
            .with_team_assignment(team_name="Events Team", role="Event Coordinator")
            .build()
        )

        return test_data

    @staticmethod
    def create_payment_problem_peter():
        """Create 'Payment Problem Peter' - Various payment issues"""
        builder = TestDataBuilder()

        # Member with payment failures
        test_data = (
            builder.with_chapter("Rotterdam Test Chapter", postal_codes="3000-3099")
            .with_member(
                first_name="Peter",
                last_name="Payment",
                email="peter.payment@test.com",
                contact_number="+31687654321",
                birth_date=add_days(today(), -365 * 35),  # 35 years old
                street_name="Betalingstraat",
                house_number="456",
                postal_code="3012",
                city="Rotterdam",
                country="Netherlands",
                payment_method="SEPA Direct Debit",
                iban="NL18RABO0123456789",
                bank_account_name="Peter Payment",
                status="Active",
            )
            .with_membership(membership_type="Monthly Membership", payment_method="SEPA Direct Debit")
            .build()
        )

        # Simulate payment failures
        member = test_data["member"]
        member.payment_failure_count = 2
        member.last_payment_failure_date = today()
        member.save(ignore_permissions=True)

        return test_data

    @staticmethod
    def create_volunteer_victor():
        """Create 'Volunteer Victor' - Active volunteer with expenses"""
        builder = TestDataBuilder()

        # Active volunteer with multiple assignments
        test_data = (
            builder.with_chapter("Amsterdam Test Chapter", postal_codes="1000-1099")
            .with_member(
                first_name="Victor",
                last_name="Volunteer",
                email="victor.volunteer@test.com",
                contact_number="+31698765432",
                birth_date=add_days(today(), -365 * 30),  # 30 years old
                street_name="Vrijwilligerslaan",
                house_number="789",
                postal_code="1015",
                city="Amsterdam",
                country="Netherlands",
                payment_method="Bank Transfer",
                status="Active",
            )
            .with_membership(membership_type="Annual Membership", payment_method="Bank Transfer")
            .with_volunteer_profile(
                interests=["Technical Support", "Event Planning", "Fundraising"],
                availability="Flexible",
                skills="IT support, Project management, Fundraising",
                emergency_contact_name="Emma Volunteer",
                emergency_contact_phone="+31612121212",
            )
            .with_team_assignment("Technical Team", role="Technical Lead")
            .with_team_assignment("Events Team", role="Member")
            .with_team_assignment("Fundraising Team", role="Coordinator")
            .with_expense(50.00, "Travel expenses for event setup")
            .with_expense(25.00, "Materials for fundraising campaign")
            .with_expense(100.00, "Conference registration")
            .build()
        )

        # Mark some expenses as approved
        if "expenses" in test_data:
            test_data["expenses"][0].status = "Approved"
            test_data["expenses"][0].save(ignore_permissions=True)

        return test_data

    @staticmethod
    def create_terminated_tom():
        """Create 'Terminated Tom' - Goes through termination"""
        builder = TestDataBuilder()

        # Member who will be terminated
        test_data = (
            builder.with_chapter("Rotterdam Test Chapter", postal_codes="3000-3099")
            .with_member(
                first_name="Tom",
                last_name="Terminated",
                email="tom.terminated@test.com",
                contact_number="+31676543210",
                birth_date=add_days(today(), -365 * 45),  # 45 years old
                street_name="Eindstraat",
                house_number="999",
                postal_code="3015",
                city="Rotterdam",
                country="Netherlands",
                payment_method="Bank Transfer",
                status="Active",
                member_since_date=add_days(today(), -365 * 5),  # 5 year member
            )
            .with_membership(
                membership_type="Annual Membership",
                payment_method="Bank Transfer",
                start_date=add_days(today(), -365),
                end_date=add_days(today(), -30),  # Expired
            )
            .build()
        )

        # Set termination fields
        member = test_data["member"]
        member.termination_reason = "Non-payment"
        member.termination_date = today()
        member.status = "Pending Termination"
        member.save(ignore_permissions=True)

        return test_data

    @staticmethod
    def create_suspended_susan():
        """Create 'Suspended Susan' - Suspension and reactivation"""
        builder = TestDataBuilder()

        # Member who will be suspended
        test_data = (
            builder.with_chapter("Amsterdam Test Chapter", postal_codes="1000-1099")
            .with_member(
                first_name="Susan",
                last_name="Suspended",
                email="susan.suspended@test.com",
                contact_number="+31665432109",
                birth_date=add_days(today(), -365 * 28),  # 28 years old
                street_name="Schorsingsweg",
                house_number="111",
                postal_code="1018",
                city="Amsterdam",
                country="Netherlands",
                payment_method="SEPA Direct Debit",
                iban="NL02ABNA0123456789",
                bank_account_name="Susan Suspended",
                status="Suspended",
            )
            .with_membership(membership_type="Monthly Membership", payment_method="SEPA Direct Debit")
            .build()
        )

        # Set suspension details
        member = test_data["member"]
        member.suspension_date = add_days(today(), -30)
        member.suspension_reason = "Payment failure"
        member.suspension_lifted_date = None
        member.save(ignore_permissions=True)

        return test_data

    @staticmethod
    def create_new_member_nancy():
        """Create 'New Member Nancy' - Just joined"""
        builder = TestDataBuilder()

        # Brand new member
        test_data = (
            builder.with_chapter("Amsterdam Test Chapter", postal_codes="1000-1099")
            .with_member(
                first_name="Nancy",
                last_name="New",
                email="nancy.new@test.com",
                contact_number="+31654321098",
                birth_date=add_days(today(), -365 * 22),  # 22 years old
                street_name="Nieuweweg",
                house_number="1",
                postal_code="1011",
                city="Amsterdam",
                country="Netherlands",
                payment_method="iDEAL",
                status="Active",
                member_since_date=today(),
            )
            .with_membership(membership_type="Student Membership", payment_method="iDEAL", start_date=today())
            .build()
        )

        return test_data

    @staticmethod
    def create_board_member_bob():
        """Create 'Board Member Bob' - Has board positions"""
        builder = TestDataBuilder()

        # Board member with special permissions
        test_data = (
            builder.with_chapter("Rotterdam Test Chapter", postal_codes="3000-3099")
            .with_member(
                first_name="Bob",
                last_name="Board",
                email="bob.board@test.com",
                contact_number="+31643210987",
                birth_date=add_days(today(), -365 * 50),  # 50 years old
                street_name="Bestuursplein",
                house_number="100",
                postal_code="3020",
                city="Rotterdam",
                country="Netherlands",
                payment_method="Bank Transfer",
                status="Active",
                member_since_date=add_days(today(), -365 * 10),  # 10 year member
            )
            .with_membership(membership_type="Annual Membership", payment_method="Bank Transfer")
            .with_volunteer_profile()
            .with_team_assignment("Board", role="Treasurer", role_type="Board Member")
            .build()
        )

        return test_data

    @staticmethod
    def create_multi_chapter_mary():
        """Create 'Multi-Chapter Mary' - Member of multiple chapters"""
        builder = TestDataBuilder()

        # Member in multiple chapters
        test_data = (
            builder.with_chapter("Amsterdam Test Chapter", postal_codes="1000-1099")
            .with_member(
                first_name="Mary",
                last_name="Multi",
                email="mary.multi@test.com",
                contact_number="+31632109876",
                birth_date=add_days(today(), -365 * 40),  # 40 years old
                street_name="Veelzijdige",
                house_number="250",
                postal_code="1016",
                city="Amsterdam",
                country="Netherlands",
                payment_method="Bank Transfer",
                status="Active",
            )
            .with_membership(membership_type="Annual Membership", payment_method="Bank Transfer")
            .build()
        )

        # Add to second chapter
        rotterdam_chapter = frappe.get_doc("Chapter", "Rotterdam Test Chapter")
        if rotterdam_chapter:
            rotterdam_chapter.append(
                "chapter_members",
                {
                    "member": test_data["member"].name,
                    "chapter_join_date": add_days(today(), -180),
                    "enabled": 1,
                    "status": "Active",
                },
            )
            rotterdam_chapter.save(ignore_permissions=True)

        return test_data

    @staticmethod
    def create_all_personas():
        """Create all test personas and return them in a dict"""
        personas = {
            "happy_hannah": TestPersonas.create_happy_path_hannah(),
            "payment_peter": TestPersonas.create_payment_problem_peter(),
            "volunteer_victor": TestPersonas.create_volunteer_victor(),
            "terminated_tom": TestPersonas.create_terminated_tom(),
            "suspended_susan": TestPersonas.create_suspended_susan(),
            "new_nancy": TestPersonas.create_new_member_nancy(),
            "board_bob": TestPersonas.create_board_member_bob(),
            "multi_mary": TestPersonas.create_multi_chapter_mary(),
        }

        return personas

    @staticmethod
    def cleanup_all_personas():
        """Clean up all test persona data"""
        # Clean up in reverse dependency order
        persona_emails = [
            "hannah.happy@test.com",
            "peter.payment@test.com",
            "victor.volunteer@test.com",
            "tom.terminated@test.com",
            "susan.suspended@test.com",
            "nancy.new@test.com",
            "bob.board@test.com",
            "mary.multi@test.com",
        ]

        for email in persona_emails:
            # Find and delete associated records
            members = frappe.get_all("Member", filters={"email": email})
            for member in members:
                # Delete in dependency order
                for doctype in ["Volunteer_Expense", "Volunteer", "Membership", "Member"]:
                    related = frappe.get_all(doctype, filters={"member": member.name})
                    for record in related:
                        frappe.delete_doc(doctype, record.name, force=True)
