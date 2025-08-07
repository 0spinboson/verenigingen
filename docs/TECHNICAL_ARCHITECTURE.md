# Technical Architecture Guide

## Overview

Verenigingen is a comprehensive association management system built on the Frappe Framework with advanced testing infrastructure, extensive integration capabilities, and modern development practices.

## System Architecture

### Core Framework
- **Frappe Framework v15+**: Modern Python-based web framework
- **ERPNext Integration**: Financial modules, customer management, and invoicing
- **MariaDB/MySQL**: Primary database with optimized queries and indexing
- **Redis**: Background job processing and caching
- **Python 3.10+**: Modern Python features and type hints

### Application Structure

```
verenigingen/
├── api/                          # RESTful API endpoints
├── patches.txt                   # Database migration scripts
├── public/                       # Static assets (CSS, JS, images)
├── templates/                    # Jinja2 templates and pages
├── tests/                        # Comprehensive test suite (186+ files)
├── utils/                        # Shared business logic utilities
└── verenigingen/                 # Core application modules
    ├── doctype/                  # Document type definitions
    ├── report/                   # Custom reports and analytics
    └── workspace/                # Frappe workspaces
```

## Enhanced Testing Framework

### VereningingenTestCase (New Standard)
All tests should inherit from `VereningingenTestCase` which provides:

```python
from verenigingen.tests.utils.base import VereningingenTestCase

class TestMyFeature(VereningingenTestCase):
    def setUp(self):
        super().setUp()
        # Automatic cleanup and factory methods available

    def test_something(self):
        # Use factory methods
        member = self.create_test_member(
            first_name="Test",
            last_name="User",
            email="test@example.com"
        )
        # Automatic cleanup handled by base class
```

#### Key Features:
- **Automatic Document Cleanup**: All created documents tracked and cleaned up automatically
- **Customer Cleanup**: Automatic customer record cleanup for member-related tests
- **Factory Methods**: Consistent test data generation with proper relationships
- **Permission Compliance**: No `ignore_permissions=True` violations
- **Performance Tracking**: Built-in query count and execution time monitoring
- **Enhanced Assertions**: Domain-specific assertions for common test patterns

#### Factory Methods Available:
```python
# Core entities
member = self.create_test_member(first_name="John", email="john@example.com")
volunteer = self.create_test_volunteer(member=member.name)
chapter = self.create_test_chapter(chapter_name="Test Chapter")
membership = self.create_test_membership(member=member.name)

# Banking and payments
mandate = self.create_sepa_mandate(member=member.name, bank_code="TEST")
iban = self.factory.generate_test_iban("TEST")  # Valid test IBAN with checksum
```

### Test Organization (2025 Reorganization)

#### Test Categories:
- **`backend/business_logic/`**: Core business logic and critical functionality
- **`backend/components/`**: Individual component and feature tests
- **`backend/integration/`**: Cross-system integration tests
- **`backend/workflows/`**: Complex multi-step process tests
- **`backend/validation/`**: Data validation and schema tests
- **`frontend/`**: JavaScript and UI component tests

#### Migration Status:
- ✅ **Phase 1 Complete**: Critical business logic tests migrated to VereningingenTestCase
- ✅ **Phase 2 Complete**: Core component tests migrated with factory methods
- ✅ **Phase 3 Complete**: Workflow and integration tests migrated
- 🚧 **Ongoing**: Permission violation cleanup across remaining test files

### Mock Bank Testing Support
Enhanced testing with realistic but clearly marked test data:

```python
# Generate valid test IBANs with proper MOD-97 checksums
test_iban = generate_test_iban("TEST")  # NL13TEST0123456789
mock_iban = generate_test_iban("MOCK")  # NL82MOCK0123456789
demo_iban = generate_test_iban("DEMO")  # NL93DEMO0123456789

# All pass full IBAN validation and work with SEPA mandate creation
```

## DocType Architecture

### Key Document Types

#### Member Management:
- **Member**: Core member records with mixin pattern for specialized functionality
- **Membership**: Lifecycle management with custom subscription overrides
- **Membership Application**: Review workflow with geographic assignment

#### Financial Integration:
- **SEPA Mandate**: Direct debit authorization with enhanced validation
- **Direct Debit Batch**: SEPA file generation and processing
- **Payment Entry**: ERPNext integration for payment tracking

#### eBoekhouden Integration:
- **E-Boekhouden Settings**: Configuration management for API connections and mapping
- **EBoekhouden Cost Center Mapping**: Child table for intelligent cost center configuration
- **E-Boekhouden Account Mapping**: Chart of accounts synchronization and mapping

#### Organizational Structure:
- **Chapter**: Geographic organization with postal code validation
- **Team**: Project-based volunteer organization
- **Volunteer**: Assignment tracking and expense management

### Mixin Pattern Implementation
Key doctypes use specialized mixins for enhanced functionality:

```python
# Member uses multiple mixins for specialized operations
class Member:
    # PaymentMixin: SEPA mandate and payment processing
    # SEPAMandateMixin: Direct debit management
    # ChapterMixin: Geographic chapter assignment
    # TerminationMixin: Governance-compliant termination workflows
```

## Integration Architecture

### eBoekhouden Integration (Production Ready)
Comprehensive accounting system integration with REST API architecture:

#### REST API (Primary - Recommended):
- **Unlimited History**: Complete transaction and master data access
- **Enhanced Performance**: Modern JSON-based communication
- **Better Error Handling**: Detailed error responses and retry mechanisms
- **Future-Proof**: Actively maintained and enhanced

#### Features:
- **Complete Chart of Accounts**: Intelligent mapping with Dutch accounting standards
- **Opening Balance Import**: Comprehensive opening balance handling with validation
- **Multi-Account Support**: Receivable, Payable, Stock, and Cash accounts
- **Zero Amount Handling**: Imports ALL transactions including zero-amount invoices
- **Party Management**: Automatic customer/supplier creation with proper relationships
- **Smart Document Naming**: Meaningful names like `EBH-Payment-1234`, `EBH-Memoriaal-5678`

#### Enhanced Cost Center Integration (New):
**Intelligent Cost Center Creation from eBoekhouden Account Groups**

The system now provides intelligent cost center mapping that converts eBoekhouden rekeninggroepen (account groups) into ERPNext cost centers for advanced departmental and project tracking:

**Key Features:**
- **Backward Compatible**: Preserves existing text-based account group input workflow
- **Intelligent Analysis**: Dutch accounting logic automatically identifies suitable cost centers
- **Smart Suggestions**: Analyzes account codes and names using RGS (Reference Code System) patterns
- **User Control**: Toggle suggestions on/off with clear reasoning for each recommendation

**Business Logic:**
```python
# Expense groups (codes 5*, 6*) - Personnel costs, other expenses
if code.startswith(('5', '6')):
    if 'personeel' or 'salaris' or 'kosten' in name:
        → Suggest cost center (good for cost tracking)

# Revenue groups (codes 3*) - Departmental income analysis
if code.startswith('3'):
    if 'opbrengst' or 'omzet' or 'verkoop' in name:
        → Suggest cost center (departmental income tracking)

# Operational keywords
if 'afdeling' or 'team' or 'project' in name:
    → Suggest cost center (operational tracking)
```

**DocType Architecture:**
- **EBoekhouden Cost Center Mapping**: Child table with configurable mappings
- **Fields**: `group_code`, `group_name`, `create_cost_center`, `cost_center_name`, `is_group`, `suggestion_reason`
- **Workflow**: Parse → Analyze → Suggest → Configure → Create (Phase 2)

**User Experience:**
1. **Input**: Users continue pasting account groups exactly as before
2. **Parse**: Click "Parse Groups & Configure Cost Centers" button
3. **Review**: Intelligent suggestions with toggle controls and reasoning
4. **Customize**: Edit cost center names and hierarchies as needed
5. **Deploy**: Future enhancement will create actual ERPNext cost centers

**Technical Implementation:**
- **Parser**: Text-to-structured data with robust error handling
- **Analyzer**: Dutch accounting intelligence using keyword matching
- **UI Integration**: JavaScript handlers with real-time feedback
- **API Design**: RESTful endpoints with comprehensive validation


### ERPNext Integration
Deep integration with ERPNext modules:

#### Financial Modules:
- **Accounts**: Customer/supplier management and invoice processing
- **Payments**: Payment entry creation and bank reconciliation
- **Subscriptions**: Automated recurring billing with custom overrides

#### CRM Integration:
- **Customer Records**: Automatic creation from membership applications
- **Sales Invoices**: Membership fee and donation invoicing
- **Payment Tracking**: Complete payment history and reconciliation

### SEPA Direct Debit Processing
EU-compliant payment processing:

#### Features:
- **Mandate Management**: Electronic mandate creation and validation
- **Batch Processing**: Automated SEPA file generation
- **Bank Integration**: MT940 import and reconciliation
- **Error Handling**: Failed payment processing and retry mechanisms

## API Architecture

### RESTful APIs
Comprehensive API layer with `@frappe.whitelist()` decorators:

```python
@frappe.whitelist()
def get_member_details(member_id):
    """Get comprehensive member information"""
    # Proper permission checking
    # Structured response format
    # Error handling
```

#### API Categories:
- **Member Management**: CRUD operations and lifecycle management
- **Financial Operations**: Payment processing and invoice generation
- **Volunteer Coordination**: Assignment management and expense processing
- **Analytics**: Real-time KPI and reporting APIs

### JavaScript Integration
Modern JavaScript with ES6+ features:

#### Key Libraries:
- **IBAN Validation**: Client-side validation with MOD-97 checksum
- **SEPA Utilities**: Mandate creation and BIC derivation
- **Form Enhancements**: Dynamic field validation and UI improvements

#### Advanced Form Controllers:
**E-Boekhouden Settings Controller** (`e_boekhouden_settings.js`):
- **Real-time API Testing**: Connection validation with status feedback
- **Chart of Accounts Preview**: Live data preview with formatted display
- **Cost Center Parsing**: Intelligent account group analysis with UI integration
- **Dynamic Form Updates**: Child table population and section visibility control

```javascript
// Cost center parsing with UI feedback
parse_groups_button(frm) {
    frappe.call({
        method: 'parse_groups_and_suggest_cost_centers',
        args: {
            group_mappings_text: frm.doc.account_group_mappings,
            company: frm.doc.default_company
        },
        callback(r) {
            if (r.message.success) {
                // Populate child table with intelligent suggestions
                r.message.suggestions.forEach(function(suggestion) {
                    let row = frm.add_child('cost_center_mappings');
                    row.create_cost_center = suggestion.create_cost_center;
                    row.suggestion_reason = suggestion.reason;
                });
                frm.refresh_field('cost_center_mappings');
            }
        }
    });
}
```

## Development Best Practices

### Code Quality Standards

#### Frappe ORM Compliance:
```python
# ✅ Correct: Use Frappe ORM
doc = frappe.new_doc("DocType")
doc.field1 = "value"
doc.save()  # Let Frappe validate

# ❌ Never: Direct SQL manipulation
frappe.db.sql("INSERT INTO ...")  # Bypasses validation
```

#### Permission Compliance:
```python
# ✅ Correct: Use proper permissions
doc.insert()  # Respects role permissions

# ❌ Never: Bypass permissions in production code
doc.insert(ignore_permissions=True)  # Only for test setup
```

#### Field Reference Validation:
```python
# ✅ Always read DocType JSON first
# Check required fields: "reqd": 1
# Use exact field names from JSON
# Never guess field names
```

### Testing Requirements

#### Mandatory Test Patterns:
1. **Use VereningingenTestCase**: All new tests must inherit from enhanced base class
2. **Factory Methods**: Use provided factory methods for consistent test data
3. **Document Tracking**: Use `self.track_doc()` for automatic cleanup
4. **No Permission Bypassing**: Remove all `ignore_permissions=True` violations
5. **DocType Validation**: Read JSON files before writing tests that create documents

#### Test Execution:
```bash
# Use Frappe test runner
bench --site dev.veganisme.net run-tests --app verenigingen --module test_module

# Never use direct Python execution (will fail with import errors)
python test_file.py  # ❌ Fails with "ModuleNotFoundError: No module named 'frappe'"
```

## Performance Optimizations

### Database Optimization:
- **Query Optimization**: Efficient database queries with proper indexing
- **Bulk Operations**: Batch processing for large data operations
- **Caching**: Redis-based caching for frequently accessed data

### API Performance:
- **Response Caching**: 1-hour CSS caching for brand management
- **Query Count Monitoring**: Built-in test framework monitoring
- **Background Jobs**: Async processing for heavy operations

## Security Features

### Access Control:
- **Role-Based Permissions**: Fine-grained access control
- **Document-Level Security**: Permission queries for data isolation
- **Field-Level Permissions**: Permlevel system for sensitive fields

### Data Protection:
- **GDPR Compliance**: Built-in privacy features
- **Audit Trails**: Complete change tracking
- **Secure Storage**: Encrypted sensitive data

## Deployment Architecture

### Requirements:
- **Python 3.10+**: Modern Python features
- **Frappe v15+**: Latest framework features
- **MariaDB/MySQL**: Optimized database configuration
- **Redis**: Background job processing
- **Required Apps**: ERPNext, Payments, HRMS, CRM

### Environment Configuration:
- **Development**: Full debug logging and test data
- **Production**: Optimized performance and monitoring
- **Cloud Deployment**: Scalable infrastructure support

## Monitoring and Maintenance

### Health Monitoring:
- **System Health Dashboard**: Real-time system status
- **Performance Metrics**: Query count and execution time tracking
- **Error Tracking**: Comprehensive error logging and alerting

### Maintenance Tasks:
- **Database Cleanup**: Automated cleanup of test and temporary data
- **Log Rotation**: Managed log file rotation and archival
- **Backup Management**: Automated backup and recovery procedures

## Future Enhancements

### Planned Features:
- **Enhanced Analytics**: Advanced business intelligence and predictive analytics
- **Mobile Apps**: Native mobile applications for members and volunteers
- **API Extensions**: Extended API capabilities for third-party integrations
- **Multi-Language Support**: Internationalization for non-Dutch organizations

### eBoekhouden Integration Roadmap:
**Phase 2: Cost Center Creation Engine** ✅ **COMPLETE**
- ✅ **Automatic Cost Center Creation**: Convert configured mappings into actual ERPNext cost centers
- ✅ **Hierarchical Structure**: Support parent-child cost center relationships
- ✅ **Validation Engine**: Prevent duplicate creation and naming conflicts
- ✅ **Migration Support**: Handle existing cost centers and merge intelligently
- ✅ **Preview Functionality**: Safe preview before actual creation
- ✅ **Batch Processing**: Efficient handling of multiple cost centers
- ✅ **Comprehensive Reporting**: Detailed success/skip/failure reporting with UI integration

**Phase 3: Advanced Cost Center Features** 🔄 **PLANNED**
- **Budget Integration**: Link cost centers to ERPNext budgeting system
- **Reporting Enhancement**: Cost center-based financial reports and dashboards
- **Multi-Company Support**: Cost center mapping across multiple ERPNext companies
- **API Extensions**: RESTful endpoints for cost center management and reporting
- **Advanced Analytics**: Cost center performance tracking and KPI dashboards
- **Automated Reconciliation**: Sync cost center usage with eBoekhouden transactions

### Technical Roadmap:
- **Microservices Architecture**: Gradual migration to microservices
- **Real-Time Features**: WebSocket integration for live updates
- **Advanced Security**: Enhanced security features and compliance tools
- **Performance Scaling**: Horizontal scaling capabilities

---

This technical architecture provides a solid foundation for developing, testing, and maintaining the Verenigingen application with modern best practices and comprehensive testing infrastructure.
