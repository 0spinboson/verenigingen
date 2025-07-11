# eBoekhouden API Integration Guide

Complete guide for integrating and using the eBoekhouden accounting API with the Verenigingen app.

## Quick Start

### API Endpoints Summary

The integration provides several key API endpoints for managing eBoekhouden data:

```python
# Core Migration Functions
@frappe.whitelist()
def start_full_rest_import(migration_name)
def test_opening_balance_import()
def fetch_and_cache_all_mutations(start_id=None, end_id=None, batch_size=100)

# Analysis and Monitoring
@frappe.whitelist()
def get_cache_statistics()
def analyze_missing_ledger_mappings()
def export_unprocessed_mutations(export_path="/tmp/unprocessed_mutations.json")

# Testing and Validation
@frappe.whitelist()
def test_rest_iterator()
def check_fiscal_years()
def estimate_mutation_range()
```

### Basic Usage Example

```python
# Start a complete REST API migration
bench --site your-site execute verenigingen.utils.eboekhouden_rest_full_migration.start_full_rest_import --args '{"migration_name": "My Migration"}'

# Test the opening balance import
bench --site your-site execute verenigingen.utils.eboekhouden_rest_full_migration.test_opening_balance_import

# Check API connectivity and data availability
bench --site your-site execute verenigingen.utils.eboekhouden_rest_iterator.test_rest_iterator
```

## Configuration Setup

### API Credentials

Configure eBoekhouden API access in the E-Boekhouden Settings doctype:

```python
# Required fields for API access
{
    "api_url": "https://secure.e-boekhouden.nl/bh/api.asp",  # SOAP API
    "rest_api_url": "https://api.e-boekhouden.nl",          # REST API
    "username": "your_username",
    "security_code1": "your_security_code_1",
    "security_code2": "your_security_code_2",
    "api_token": "your_rest_api_token",       # For REST API
    "default_company": "Your Company Name",
    "source_application": "Verenigingen ERPNext"
}
```

### Authentication Methods

#### REST API Authentication
```python
# Session-based authentication with token
session_data = {
    "accessToken": api_token,
    "source": source_application
}

# Token expires after 60 minutes
# System automatically handles token refresh
```

#### SOAP API Authentication
```python
# Direct credential authentication
soap_credentials = {
    "username": username,
    "securitycode1": security_code1,
    "securitycode2": security_code2
}
```

## Data Import Process

### Complete Migration Workflow

#### 1. Pre-Migration Setup
```python
# Validate system readiness
def pre_migration_validation():
    return {
        "api_connectivity": test_eboekhouden_api(),
        "account_mappings": validate_account_mappings(),
        "fiscal_years": check_fiscal_years(),
        "permissions": validate_user_permissions()
    }
```

#### 2. Account Import (Chart of Accounts)
```python
# Import complete chart of accounts
def import_chart_of_accounts():
    """
    Imports all accounts from eBoekhouden with:
    - Account hierarchy and grouping
    - Balance information
    - Account type classification
    - Mapping to ERPNext account structure
    """
    pass
```

#### 3. Master Data Import
```python
# Import customers and suppliers
def import_master_data():
    """
    Imports:
    - Customer records with contact information
    - Supplier records with payment terms
    - Item master data for products/services
    """
    pass
```

#### 4. Transaction Import
```python
# Import all transactions by type
transaction_types = {
    0: "Opening Balance",
    1: "Purchase Invoice",
    2: "Sales Invoice",
    3: "Customer Payment",
    4: "Supplier Payment",
    5: "Money Received",
    6: "Money Sent",
    7: "Memorial/Journal Entry"
}

# Process transactions in chronological order
for transaction_type, name in transaction_types.items():
    import_transactions_by_type(transaction_type)
```

### Smart Transaction Processing

#### Multi-Line Transaction Handling
```python
def process_complex_transaction(mutation):
    """
    Handles complex transactions including:
    - Multi-party payments
    - Split invoice payments
    - Memorial entries with multiple accounts
    - Automatic balancing entries
    """

    # Example: Multi-party payment processing
    if len(mutation.rows) > 1:
        # Analyze receivable/payable rows
        receivable_rows = [r for r in rows if is_receivable_account(r.ledgerId)]
        payable_rows = [r for r in rows if is_payable_account(r.ledgerId)]

        if len(receivable_rows) + len(payable_rows) > 1:
            # Create Journal Entry for complex payment
            create_journal_entry_for_multi_party_payment(mutation)
        else:
            # Create standard Payment Entry
            create_payment_entry(mutation)
```

#### Zero Amount Transaction Management
```python
def handle_zero_amount_transactions(mutation):
    """
    Intelligent handling of zero-amount transactions:
    - Skip Sales/Purchase Invoices with zero amounts
    - Skip Journal Entry rows with zero amounts
    - Log skipped transactions with explanations
    - Maintain transaction integrity
    """

    amount = frappe.utils.flt(mutation.get("amount", 0), 2)

    if amount == 0:
        if mutation.type in [1, 2]:  # Invoice types
            log_skipped_invoice(mutation, "Zero amount invoice")
            return "skip"
        elif mutation.type in [0, 5, 6, 7]:  # Journal types
            log_skipped_journal_row(mutation, "Zero amount journal row")
            return "skip_row"

    return "process"
```

## Document Creation Standards

### Intelligent Document Naming

The system creates meaningful document names for easy identification:

```python
# Journal Entry naming patterns
journal_naming_patterns = {
    "payment_with_invoice": "EBH-Payment-{invoice_number}",
    "payment_without_invoice": "EBH-Payment-{mutation_id}",
    "memorial_entry": "EBH-Memoriaal-{mutation_id}",
    "money_received": "EBH-Money-Received-{mutation_id}",
    "money_sent": "EBH-Money-Sent-{mutation_id}",
    "opening_balance": "EBH-Opening-Balance"
}

# Invoice naming patterns
invoice_naming_patterns = {
    "sales_invoice": "{customer_name} - {invoice_number}",
    "purchase_invoice": "{supplier_name} - {bill_number}"
}
```

### Document Field Mapping

#### Custom Fields for Traceability
```python
# eBoekhouden reference fields added to ERPNext documents
custom_fields = {
    "Journal Entry": [
        "eboekhouden_mutation_nr",      # Original mutation ID
        "eboekhouden_invoice_number",   # Invoice reference
        "eboekhouden_relation_code"     # Customer/supplier code
    ],
    "Sales Invoice": [
        "eboekhouden_mutation_nr",
        "eboekhouden_invoice_number",
        "eboekhouden_relation_code"
    ],
    "Purchase Invoice": [
        "eboekhouden_mutation_nr",
        "eboekhouden_invoice_number",
        "eboekhouden_relation_code"
    ],
    "Payment Entry": [
        "eboekhouden_mutation_nr",
        "eboekhouden_invoice_number"
    ]
}
```

### Party Management

#### Automatic Party Creation
```python
def create_or_update_party(relation_id, party_type, description):
    """
    Intelligent party management:
    - Create customers/suppliers automatically
    - Handle duplicate prevention
    - Manage name extraction from descriptions
    - Set up proper party-account relationships
    """

    if party_type == "Customer":
        return get_or_create_customer(relation_id, description)
    elif party_type == "Supplier":
        return get_or_create_supplier(relation_id, description)
    else:
        # Handle special cases like opening balances
        return create_generic_party(party_type, description)
```

## Advanced Features

### Account Type Intelligence

#### Smart Account Classification
```python
def classify_account_type(account_code, account_name, balance):
    """
    Automatic account type detection:
    - Receivable accounts: Customer-related accounts
    - Payable accounts: Supplier-related accounts
    - Stock accounts: Inventory management (special handling)
    - Bank accounts: Cash and bank balances
    - Income/Expense: P&L accounts
    """

    patterns = {
        "receivable": ["debiteuren", "te ontvangen", "customer"],
        "payable": ["crediteuren", "te betalen", "supplier"],
        "stock": ["voorraad", "stock", "inventory"],
        "bank": ["bank", "kas", "giro", "cash"],
        "income": ["omzet", "verkoop", "income", "revenue"],
        "expense": ["kosten", "uitgaven", "expense"]
    }

    return detect_account_type(account_name, patterns)
```

#### Special Account Handling
```python
def handle_special_accounts(account_type, transaction_data):
    """
    Special processing for different account types:

    - Stock Accounts: Skip in Journal Entries (require Stock Transactions)
    - Receivable Accounts: Require Customer party assignment
    - Payable Accounts: Require Supplier party assignment
    - Bank Accounts: Integration with bank reconciliation
    """

    if account_type == "Stock":
        return handle_stock_account_transaction(transaction_data)
    elif account_type in ["Receivable", "Payable"]:
        return handle_party_account_transaction(transaction_data)
    else:
        return handle_standard_account_transaction(transaction_data)
```

### Error Handling and Recovery

#### Comprehensive Error Management
```python
def error_handling_framework():
    """
    Multi-level error handling:

    1. Connection Errors: API timeout, authentication failures
    2. Data Errors: Missing mappings, invalid amounts
    3. Validation Errors: ERPNext document validation failures
    4. System Errors: Database constraints, memory issues
    """

    error_categories = {
        "connection": {
            "retry": True,
            "max_retries": 3,
            "backoff": "exponential"
        },
        "validation": {
            "retry": False,
            "skip": True,
            "log_detail": True
        },
        "mapping": {
            "retry": False,
            "create_fallback": True,
            "notify_admin": True
        }
    }

    return error_categories
```

#### Automatic Recovery Mechanisms
```python
def automatic_recovery_system():
    """
    Built-in recovery mechanisms:

    - Failed transactions are logged and can be retried
    - Missing account mappings trigger fallback creation
    - Validation errors are categorized and handled appropriately
    - Progress is saved incrementally to allow resumption
    """

    recovery_strategies = {
        "missing_mapping": create_fallback_account_mapping,
        "party_validation": create_generic_party,
        "balance_mismatch": add_balancing_entry,
        "duplicate_entry": skip_with_reference_logging
    }

    return recovery_strategies
```

## Monitoring and Maintenance

### Real-Time Progress Monitoring

#### Migration Progress Tracking
```python
def monitor_migration_progress():
    """
    Real-time migration monitoring provides:

    - Transaction processing counters
    - Success/failure statistics
    - Error categorization and reporting
    - Performance metrics (transactions/minute)
    - Estimated completion time
    """

    progress_data = {
        "total_mutations": 7163,
        "processed": 1250,
        "successful": 1200,
        "failed": 50,
        "percentage_complete": 17.4,
        "current_processing": "ID=4549, Type=2 (Sales Invoice)",
        "errors_by_type": {
            "validation": 30,
            "mapping": 15,
            "connection": 5
        }
    }

    return progress_data
```

#### Health Check System
```python
@frappe.whitelist()
def system_health_check():
    """
    Comprehensive system health verification:

    - API connectivity and authentication
    - Database integrity and performance
    - Account mapping completeness
    - Balance accuracy verification
    - Transaction completeness check
    """

    health_report = {
        "api_status": check_api_connectivity(),
        "database_health": verify_database_integrity(),
        "mapping_coverage": calculate_mapping_coverage(),
        "balance_accuracy": verify_balance_reconciliation(),
        "data_completeness": check_transaction_completeness()
    }

    return health_report
```

### Maintenance Operations

#### Regular Maintenance Tasks
```python
def maintenance_scheduler():
    """
    Automated maintenance tasks:

    - Incremental imports of new transactions
    - Balance reconciliation verification
    - Error log cleanup and analysis
    - Performance optimization
    - Cache management
    """

    maintenance_tasks = {
        "daily": [
            "incremental_import",
            "balance_verification",
            "error_log_review"
        ],
        "weekly": [
            "full_reconciliation",
            "performance_analysis",
            "mapping_optimization"
        ],
        "monthly": [
            "comprehensive_audit",
            "data_cleanup",
            "documentation_update"
        ]
    }

    return maintenance_tasks
```

## Performance Optimization

### Batch Processing Strategies

#### Efficient Data Processing
```python
def optimized_batch_processing():
    """
    Performance optimization techniques:

    - Batch size optimization based on transaction complexity
    - Memory management for large datasets
    - Database query optimization
    - Cache utilization for frequently accessed data
    - Parallel processing where applicable
    """

    optimization_settings = {
        "batch_size": 500,              # Transactions per batch
        "memory_limit": "512MB",        # Memory usage limit
        "cache_timeout": 3600,          # Cache expiry (1 hour)
        "parallel_workers": 4,          # Background job workers
        "query_optimization": True      # Enable query caching
    }

    return optimization_settings
```

### Database Optimization

#### Index Management
```python
def database_optimization():
    """
    Database performance enhancements:

    - Custom indexes on eBoekhouden reference fields
    - Query optimization for large datasets
    - Transaction log management
    - Backup and recovery optimization
    """

    db_indexes = [
        "idx_eboekhouden_mutation_nr",
        "idx_eboekhouden_invoice_number",
        "idx_eboekhouden_relation_code",
        "idx_posting_date_company"
    ]

    return db_indexes
```

## Best Practices

### Implementation Guidelines

#### Pre-Implementation Checklist
```python
pre_implementation_checklist = [
    "✓ ERPNext system properly configured",
    "✓ Chart of accounts structure planned",
    "✓ eBoekhouden API credentials obtained",
    "✓ Test environment available",
    "✓ Backup procedures established",
    "✓ User training plan prepared",
    "✓ Go-live timeline defined"
]
```

#### Security Best Practices
```python
security_guidelines = {
    "credential_management": [
        "Use encrypted password fields",
        "Rotate API credentials regularly",
        "Limit access to integration settings",
        "Monitor API usage and access logs"
    ],
    "data_protection": [
        "Ensure GDPR compliance for imported data",
        "Implement proper access controls",
        "Maintain audit trails",
        "Regular security assessments"
    ]
}
```

#### Operational Guidelines
```python
operational_best_practices = {
    "migration_strategy": [
        "Start with small date ranges",
        "Use validation mode first",
        "Monitor progress actively",
        "Document custom configurations"
    ],
    "maintenance": [
        "Schedule regular incremental imports",
        "Perform balance reconciliation",
        "Review error logs regularly",
        "Keep documentation updated"
    ]
}
```

## Troubleshooting Guide

### Common Issues and Solutions

#### API Connection Issues
```python
def troubleshoot_api_connection():
    """
    Common API connection problems:

    1. Invalid credentials -> Verify username/password/tokens
    2. Network connectivity -> Check firewall and proxy settings
    3. API rate limiting -> Implement proper retry mechanisms
    4. Session expiry -> Automatic token refresh handling
    """

    troubleshooting_steps = {
        "test_credentials": test_api_authentication,
        "check_network": verify_network_connectivity,
        "validate_endpoints": test_api_endpoints,
        "check_permissions": verify_api_permissions
    }

    return troubleshooting_steps
```

#### Data Import Issues
```python
def troubleshoot_data_import():
    """
    Common data import problems:

    1. Missing account mappings -> Create or update mappings
    2. Validation errors -> Check ERPNext document requirements
    3. Balance discrepancies -> Investigate source data
    4. Performance issues -> Optimize batch sizes and queries
    """

    diagnostic_tools = {
        "mapping_analysis": analyze_missing_mappings,
        "validation_checker": validate_document_requirements,
        "balance_reconciliation": compare_system_balances,
        "performance_profiler": analyze_import_performance
    }

    return diagnostic_tools
```

## Migration Examples

### Complete Migration Example
```python
# Example: Complete eBoekhouden migration
def complete_migration_example():
    """
    Step-by-step migration example with error handling
    """

    try:
        # 1. Pre-migration validation
        validation_result = pre_migration_validation()
        if not validation_result["success"]:
            return handle_validation_errors(validation_result)

        # 2. Start migration with monitoring
        migration_name = f"eBoekhouden Migration {frappe.utils.today()}"
        result = start_full_rest_import(migration_name)

        # 3. Monitor progress
        while migration_in_progress():
            progress = get_migration_progress()
            print(f"Progress: {progress['percentage']}% - {progress['current_operation']}")
            time.sleep(30)  # Check every 30 seconds

        # 4. Post-migration validation
        final_result = post_migration_validation()

        return {
            "success": True,
            "migration_name": migration_name,
            "imported_transactions": result["imported"],
            "errors": result["errors"],
            "validation": final_result
        }

    except Exception as e:
        return handle_migration_error(e)
```

This comprehensive API guide provides everything needed to successfully implement and maintain the eBoekhouden integration with the Verenigingen app.
