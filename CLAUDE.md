# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Verenigingen is a Frappe/ERPNext application for association management, specifically designed for non-profit organizations. It extends ERPNext's core functionality with features for membership management, volunteer coordination, chapter management, termination processes, and Dutch tax compliance.

## Common Development Commands

### Testing
```bash
# Run all tests
bench run-tests --app verenigingen

# Run specific test
bench run-tests --app verenigingen --module verenigingen.verenigingen.tests.test_termination_system

# Run unit tests for specific doctype
bench run-tests --app verenigingen --module verenigingen.verenigingen.doctype.member.test_member

# Run custom test runner (termination system)
bench execute verenigingen.test_runner.run_all_tests

# Run smoke tests
bench execute verenigingen.test_runner.run_quick_smoke_tests
```

### Development
```bash
# Build assets (CSS/JS)
bench build --app verenigingen

# Restart bench for code changes
bench restart

# Migrate database after schema changes
bench migrate

# Install/reinstall app
bench install-app verenigingen

# Set developer mode
bench set-config developer_mode 1
```

### Database and Setup
```bash
# Run app-specific setup
bench execute verenigingen.setup.execute_after_install

# Create/update custom fields
bench execute verenigingen.setup.make_custom_fields

# Setup termination system manually
bench execute verenigingen.setup.setup_termination_system_manual
```

## Architecture Overview

### Core Components

**Document Types (DocTypes):**
- **Member**: Core member records with auto-generated IDs, chapter assignments, payment tracking
- **Membership**: Time-bound membership records with renewal logic and subscription integration
- **Chapter**: Regional/local chapters with board management and volunteer coordination
- **Membership Termination Request**: Complex termination workflow with appeals process
- **Volunteer**: Volunteer management with activities, assignments, and skill tracking

**API Layer:**
- `verenigingen/api/` - REST API endpoints for web forms and external integrations
- `verenigingen/utils/` - Shared utilities organized by domain (applications, termination, etc.)

**Frontend:**
- `verenigingen/public/js/` - Custom JavaScript for form enhancements and dashboards
- `verenigingen/templates/` - Jinja2 templates for web pages and email

### Key Integrations

**ERPNext Integration:**
- Customer records auto-created for members
- Sales Invoice generation for membership fees
- Payment Entry tracking for financial records
- SEPA mandate management for direct debits

**Workflow System:**
- Complex approval workflows for termination requests
- Appeals process with timeline tracking
- Governance compliance reporting

**Dutch Tax Compliance:**
- BTW (VAT) exemption handling for non-profits
- Custom fields for tax reporting categories
- Automated tax template setup

### Event-Driven Architecture

The application uses Frappe's document event system extensively:

**Hooks Configuration** (`verenigingen/hooks.py`):
- Document lifecycle events (validate, before_save, on_submit, etc.)
- Scheduled tasks for automated processing
- Permission query filters for data access control

**Critical Event Handlers:**
- Membership subscription synchronization
- Member payment history updates  
- Termination status propagation
- Chapter access validation

### Data Flow Patterns

**Membership Application Process:**
1. Web form submission → API validation → Draft creation
2. Review process → Approval/rejection workflow
3. Payment processing → Invoice generation → Membership activation

**Termination Process:**
1. Request creation → Workflow routing → Approval chain
2. Appeals handling → Timeline tracking → Final execution
3. Cleanup: SEPA mandates, board positions, access rights

## Development Guidelines

### Testing Strategy
- Unit tests for each doctype in `doctype/*/test_*.py`
- Integration tests in `verenigingen/tests/`
- Custom test runner for complex systems (termination)
- Smoke tests for installation verification

### Code Organization
- **Utils modules**: Domain-specific shared functionality
- **Managers**: Complex business logic (in `chapter/managers/`)
- **Validators**: Input validation and business rules
- **API endpoints**: RESTful interfaces with proper error handling

### Database Patterns
- Auto-generated sequential IDs for members
- Audit trails for termination processes
- Subscription-membership synchronization
- Chapter-based data isolation

### Frontend Architecture
- Modular JavaScript components in `public/js/components/`
- Service layer for API communication
- Form validation and enhancement utilities
- Dashboard implementations for management views

## Reporting System

### Member Application Reports
- **Pending Membership Applications**: Role-based filtering for applications older than X days
- **Application review workflow**: Board member access controls by chapter assignment
- **URL parameter support**: `?preset=overdue` and `?preset=aging` for filtered views

### Financial Reports  
- **Overdue Member Payments**: Comprehensive overdue payment tracking with ERPNext integration
- **Payment reminder system**: Automated email reminders with customizable templates
- **Role-based chapter filtering**: Board members see only their chapter's payment issues
- **Bulk payment actions**: Suspend memberships, create payment plans, apply late fees
- **Export functionality**: CSV export for external collection agencies

## Key Configuration Files

- `hooks.py` - Frappe app configuration and event bindings
- `setup.py` - Installation and custom field setup
- `pyproject.toml` - Python package configuration
- `fixtures/` - Workflow and role definitions for deployment

## Important Notes

- This is a Frappe v15+ application requiring bench-based development
- All database changes must go through Frappe's migration system
- Custom fields are managed through setup.py, not manual creation
- Workflow changes require fixture updates for proper deployment
- Dutch tax compliance features require specific configuration