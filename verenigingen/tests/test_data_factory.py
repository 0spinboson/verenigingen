"""
Test Data Factory for Verenigingen
Creates consistent, reproducible test data for edge case testing and performance testing
"""

import frappe
import random
from datetime import datetime, timedelta
from frappe.utils import today, add_days, add_months, random_string


class TestDataFactory:
    """Factory for creating consistent test data"""
    
    def __init__(self, cleanup_on_exit=True):
        self.cleanup_on_exit = cleanup_on_exit
        self.created_records = []
        self.test_run_id = f"{random_string(8)}-{int(datetime.now().timestamp())}"
        
    def cleanup(self):
        """Clean up all created test data"""
        print(f"🧹 Cleaning up {len(self.created_records)} test records...")
        
        # Clean up in reverse order to respect dependencies
        for record in reversed(self.created_records):
            try:
                doc = frappe.get_doc(record['doctype'], record['name'])
                doc.delete(ignore_permissions=True, force=True)
            except Exception as e:
                print(f"⚠️  Failed to delete {record['doctype']} {record['name']}: {e}")
        
        self.created_records = []
    
    def _track_record(self, doctype, name):
        """Track a created record for cleanup"""
        self.created_records.append({'doctype': doctype, 'name': name})
    
    def create_test_chapters(self, count=5):
        """Create test chapters"""
        chapters = []
        countries = ["Netherlands", "Germany", "Belgium", "France", "Spain"]
        
        for i in range(count):
            chapter_name = f"Test Chapter {i+1} - {self.test_run_id}"
            chapter = frappe.get_doc({
                "doctype": "Chapter",
                "name": chapter_name,
                "region": f"Test Region {i+1}",
                "postal_codes": f"{1000 + i:04d}",
                "introduction": f"Automated test chapter {i+1} - {self.test_run_id}"
            })
            chapter.insert(ignore_permissions=True)
            self._track_record("Chapter", chapter.name)
            chapters.append(chapter)
            
        print(f"✅ Created {count} test chapters")
        return chapters
    
    def create_test_membership_types(self, count=3):
        """Create test membership types"""
        membership_types = []
        type_configs = [
            {"name": "Regular", "fee": 100.00, "description": "Regular membership"},
            {"name": "Student", "fee": 50.00, "description": "Student discount membership"},
            {"name": "Senior", "fee": 75.00, "description": "Senior citizen membership"},
            {"name": "Corporate", "fee": 500.00, "description": "Corporate membership"},
            {"name": "Honorary", "fee": 0.00, "description": "Honorary membership"},
        ]
        
        for i in range(min(count, len(type_configs))):
            config = type_configs[i]
            membership_type = frappe.get_doc({
                "doctype": "Membership Type",
                "membership_type": f"{config['name']} - {self.test_run_id}",
                "annual_fee": config['fee'],
                "currency": "EUR",
                "description": config['description']
            })
            membership_type.insert(ignore_permissions=True)
            self._track_record("Membership Type", membership_type.name)
            membership_types.append(membership_type)
            
        print(f"✅ Created {len(membership_types)} membership types")
        return membership_types
    
    def create_test_members(self, chapters, count=100, status_distribution=None):
        """Create test members distributed across chapters"""
        if status_distribution is None:
            status_distribution = {"Active": 0.8, "Suspended": 0.1, "Terminated": 0.1}
        
        members = []
        statuses = []
        
        # Build status list based on distribution
        for status, ratio in status_distribution.items():
            statuses.extend([status] * int(count * ratio))
        
        # Fill remaining slots with "Active"
        while len(statuses) < count:
            statuses.append("Active")
        
        random.shuffle(statuses)
        
        for i in range(count):
            chapter = random.choice(chapters)
            status = statuses[i]
            
            member = frappe.get_doc({
                "doctype": "Member",
                "first_name": f"TestMember{i+1:04d}",
                "last_name": f"Lastname{self.test_run_id}",
                "email": f"testmember{i+1:04d}.{self.test_run_id}@test.com",
                "status": status,
                "chapter": chapter.name,
                "join_date": add_days(today(), -random.randint(1, 365)),
                "phone": f"+31 6 {random.randint(10000000, 99999999)}",
                "birth_date": add_days(today(), -random.randint(6570, 25550))  # 18-70 years old
            })
            
            # Add status-specific fields
            if status == "Suspended":
                member.suspension_reason = random.choice([
                    "Payment overdue", "Behavior violation", "Administrative hold"
                ])
                member.suspension_date = add_days(today(), -random.randint(1, 30))
            elif status == "Terminated":
                member.termination_reason = random.choice([
                    "Voluntary resignation", "Non-payment", "Policy violation"
                ])
                member.termination_date = add_days(today(), -random.randint(1, 90))
            
            member.insert(ignore_permissions=True)
            self._track_record("Member", member.name)
            members.append(member)
        
        print(f"✅ Created {count} test members")
        return members
    
    def create_test_memberships(self, members, membership_types, coverage_ratio=0.9):
        """Create memberships for members"""
        memberships = []
        member_sample = random.sample(members, int(len(members) * coverage_ratio))
        
        status_options = ["Active", "Pending", "Overdue", "Cancelled"]
        
        for member in member_sample:
            membership_type = random.choice(membership_types)
            
            # Choose status based on member status
            if member.status == "Active":
                membership_status = random.choice(["Active", "Pending", "Overdue"])
            elif member.status == "Suspended":
                membership_status = random.choice(["Overdue", "Pending"])
            else:  # Terminated
                membership_status = "Cancelled"
            
            membership = frappe.get_doc({
                "doctype": "Membership",
                "member": member.name,
                "membership_type": membership_type.name,
                "status": membership_status,
                "annual_fee": membership_type.annual_fee,
                "start_date": member.join_date,
                "renewal_date": add_months(member.join_date, 12),
                "next_billing_date": add_months(today(), random.randint(1, 12))
            })
            membership.insert(ignore_permissions=True)
            self._track_record("Membership", membership.name)
            memberships.append(membership)
        
        print(f"✅ Created {len(memberships)} memberships")
        return memberships
    
    def create_test_volunteers(self, members, volunteer_ratio=0.3):
        """Create volunteer records for subset of members"""
        volunteers = []
        volunteer_members = random.sample(members, int(len(members) * volunteer_ratio))
        
        for member in volunteer_members:
            volunteer = frappe.get_doc({
                "doctype": "Volunteer",
                "volunteer_name": f"{member.first_name} {member.last_name}",
                "email": member.email,
                "member": member.name,
                "status": "Active" if member.status == "Active" else "Inactive",
                "start_date": add_days(member.join_date, random.randint(0, 180)),
                "skills": random.choice([
                    "Event organization", "Social media", "Fundraising", 
                    "Administration", "Photography", "Translation"
                ])
            })
            volunteer.insert(ignore_permissions=True)
            self._track_record("Volunteer", volunteer.name)
            volunteers.append(volunteer)
        
        print(f"✅ Created {len(volunteers)} volunteers")
        return volunteers
    
    def create_test_sepa_mandates(self, members, mandate_ratio=0.6):
        """Create SEPA mandates for subset of members"""
        mandates = []
        mandate_members = random.sample(
            [m for m in members if m.status == "Active"], 
            int(len([m for m in members if m.status == "Active"]) * mandate_ratio)
        )
        
        # Sample Dutch IBANs for testing
        sample_ibans = [
            "NL91ABNA0417164300", "NL63RABO0123456789", "NL20INGB0001234567",
            "NL85TRIO0123456789", "NL02BUNQ2025123456", "NL39KNAB0123456789"
        ]
        
        for member in mandate_members:
            iban = random.choice(sample_ibans)
            # Modify last digits to make unique
            iban = iban[:-4] + f"{random.randint(1000, 9999)}"
            
            mandate = frappe.get_doc({
                "doctype": "SEPA Mandate",
                "member": member.name,
                "iban": iban,
                "status": "Active",
                "mandate_date": add_days(member.join_date, random.randint(0, 30)),
                "mandate_reference": f"MANDT{random.randint(100000, 999999)}"
            })
            mandate.insert(ignore_permissions=True)
            self._track_record("SEPA Mandate", mandate.name)
            mandates.append(mandate)
        
        print(f"✅ Created {len(mandates)} SEPA mandates")
        return mandates
    
    def create_test_expenses(self, volunteers, expense_count_per_volunteer=5):
        """Create volunteer expenses"""
        expenses = []
        expense_categories = ["Travel", "Accommodation", "Materials", "Food", "Communication"]
        
        for volunteer in volunteers:
            num_expenses = random.randint(1, expense_count_per_volunteer)
            
            for i in range(num_expenses):
                expense = frappe.get_doc({
                    "doctype": "Volunteer Expense",
                    "volunteer": volunteer.name,
                    "description": f"Test expense {i+1} - {random.choice(expense_categories)}",
                    "amount": random.uniform(10.0, 500.0),
                    "currency": "EUR",
                    "expense_date": add_days(today(), -random.randint(1, 180)),
                    "status": random.choice(["Draft", "Submitted", "Approved", "Reimbursed"]),
                    "category": random.choice(expense_categories)
                })
                expense.insert(ignore_permissions=True)
                self._track_record("Volunteer Expense", expense.name)
                expenses.append(expense)
        
        print(f"✅ Created {len(expenses)} volunteer expenses")
        return expenses
    
    def create_stress_test_data(self, member_count=1000):
        """Create large dataset for stress testing"""
        print(f"🏗️  Creating stress test dataset with {member_count} members...")
        
        # Create supporting data
        chapters = self.create_test_chapters(count=10)
        membership_types = self.create_test_membership_types(count=5)
        
        # Create large member base
        members = self.create_test_members(chapters, count=member_count)
        
        # Create related data
        memberships = self.create_test_memberships(members, membership_types)
        volunteers = self.create_test_volunteers(members, volunteer_ratio=0.2)
        mandates = self.create_test_sepa_mandates(members, mandate_ratio=0.4)
        expenses = self.create_test_expenses(volunteers, expense_count_per_volunteer=3)
        
        dataset = {
            'chapters': chapters,
            'membership_types': membership_types,
            'members': members,
            'memberships': memberships,
            'volunteers': volunteers,
            'sepa_mandates': mandates,
            'expenses': expenses
        }
        
        print(f"✅ Stress test dataset complete:")
        for key, items in dataset.items():
            print(f"   - {len(items)} {key}")
        
        return dataset
    
    def create_edge_case_data(self):
        """Create specific edge case test data"""
        print("🔀 Creating edge case test data...")
        
        # Create base data
        chapters = self.create_test_chapters(count=3)
        membership_types = self.create_test_membership_types(count=3)
        
        # Create edge case members
        edge_case_members = []
        
        # Member with very long name
        long_name_member = frappe.get_doc({
            "doctype": "Member",
            "first_name": "VeryLongFirstNameThatTestsFieldLimits",
            "last_name": "VeryLongLastNameThatTestsFieldLimitsAndDatabaseConstraints",
            "email": f"longnametest.{self.test_run_id}@test.com",
            "status": "Active",
            "chapter": chapters[0].name
        })
        long_name_member.insert(ignore_permissions=True)
        self._track_record("Member", long_name_member.name)
        edge_case_members.append(long_name_member)
        
        # Member with special characters
        special_char_member = frappe.get_doc({
            "doctype": "Member",
            "first_name": "José María",
            "last_name": "González-Pérez",
            "email": f"specialchars.{self.test_run_id}@test.com",
            "status": "Active",
            "chapter": chapters[0].name
        })
        special_char_member.insert(ignore_permissions=True)
        self._track_record("Member", special_char_member.name)
        edge_case_members.append(special_char_member)
        
        # Member with minimum age
        young_member = frappe.get_doc({
            "doctype": "Member", 
            "first_name": "Young",
            "last_name": "Member",
            "email": f"youngmember.{self.test_run_id}@test.com",
            "status": "Active",
            "chapter": chapters[0].name,
            "birth_date": add_days(today(), -6570)  # Exactly 18 years old
        })
        young_member.insert(ignore_permissions=True)
        self._track_record("Member", young_member.name)
        edge_case_members.append(young_member)
        
        # Member with maximum age
        old_member = frappe.get_doc({
            "doctype": "Member",
            "first_name": "Senior", 
            "last_name": "Member",
            "email": f"seniormember.{self.test_run_id}@test.com",
            "status": "Active",
            "chapter": chapters[0].name,
            "birth_date": add_days(today(), -36500)  # 100 years old
        })
        old_member.insert(ignore_permissions=True)
        self._track_record("Member", old_member.name)
        edge_case_members.append(old_member)
        
        print(f"✅ Created {len(edge_case_members)} edge case members")
        
        return {
            'chapters': chapters,
            'membership_types': membership_types,
            'edge_case_members': edge_case_members
        }


# Convenience functions for quick test data creation
def create_minimal_test_data():
    """Create minimal test data for quick tests"""
    factory = TestDataFactory()
    
    chapters = factory.create_test_chapters(count=2)
    membership_types = factory.create_test_membership_types(count=2)
    members = factory.create_test_members(chapters, count=10)
    
    return {
        'factory': factory,
        'chapters': chapters,
        'membership_types': membership_types,
        'members': members
    }

def create_performance_test_data(member_count=1000):
    """Create performance test data"""
    factory = TestDataFactory()
    return factory.create_stress_test_data(member_count)

def create_edge_case_test_data():
    """Create edge case test data"""
    factory = TestDataFactory()
    return factory.create_edge_case_data()


# Context manager for automatic cleanup
class TestDataContext:
    """Context manager for automatic test data cleanup"""
    
    def __init__(self, data_type="minimal", **kwargs):
        self.data_type = data_type
        self.kwargs = kwargs
        self.factory = None
        self.data = None
    
    def __enter__(self):
        self.factory = TestDataFactory()
        
        if self.data_type == "minimal":
            self.data = create_minimal_test_data()
        elif self.data_type == "performance":
            member_count = self.kwargs.get('member_count', 1000)
            self.data = self.factory.create_stress_test_data(member_count)
        elif self.data_type == "edge_case":
            self.data = self.factory.create_edge_case_data()
        
        return self.data
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.factory:
            self.factory.cleanup()


# Usage examples
if __name__ == "__main__":
    # Example 1: Create minimal test data
    with TestDataContext("minimal") as data:
        print(f"Created {len(data['members'])} test members")
        # Run your tests here
    
    # Example 2: Create performance test data
    with TestDataContext("performance", member_count=500) as data:
        print(f"Created {len(data['members'])} members for performance testing")
        # Run performance tests here
    
    # Example 3: Create edge case data
    with TestDataContext("edge_case") as data:
        print(f"Created {len(data['edge_case_members'])} edge case members")
        # Run edge case tests here