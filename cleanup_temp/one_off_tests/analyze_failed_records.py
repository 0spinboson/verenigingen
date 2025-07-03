#!/usr/bin/env python3
import json
import os
from collections import Counter, defaultdict

# Path to log files
log_dir = "/home/frappe/frappe-bench/sites/dev.veganisme.net/private/files/eboekhouden_migration_logs"

# Analyze all failed record files
all_stats = []

for filename in sorted(os.listdir(log_dir)):
    if filename.startswith("failed_records_"):
        filepath = os.path.join(log_dir, filename)
        with open(filepath, 'r') as f:
            data = json.load(f)
            
        print(f"\n=== {filename} ===")
        print(f"Migration: {data['migration_name']} ({data['migration_id']})")
        print(f"Timestamp: {data['timestamp']}")
        print(f"Total Failed: {data['total_failed']}")
        
        # Analyze error patterns
        error_types = Counter()
        mutation_types = Counter()
        invoice_numbers = Counter()
        mutation_numbers = Counter()
        
        for record in data['failed_records']:
            error_types[record['error_message'][:100]] += 1
            record_data = record['record_data']
            mutation_types[record_data.get('Soort', 'Unknown')] += 1
            if record_data.get('Factuurnummer'):
                invoice_numbers[record_data['Factuurnummer']] += 1
            if record_data.get('MutatieNr'):
                mutation_numbers[record_data['MutatieNr']] += 1
        
        print("\nTop Error Messages:")
        for error, count in error_types.most_common(5):
            print(f"  {count:4d} - {error}")
            
        print("\nMutation Types:")
        for mut_type, count in mutation_types.most_common():
            print(f"  {count:4d} - {mut_type}")
            
        print("\nTop Repeated Invoices:")
        for invoice, count in invoice_numbers.most_common(5):
            if count > 1:
                print(f"  {count:4d} - Invoice {invoice}")
                
        print("\nTop Repeated Mutations:")
        for mutation, count in mutation_numbers.most_common(5):
            if count > 1:
                print(f"  {count:4d} - Mutation {mutation}")
        
        all_stats.append({
            'file': filename,
            'total_failed': data['total_failed'],
            'error_types': error_types,
            'mutation_types': mutation_types
        })

print("\n\n=== OVERALL SUMMARY ===")
total_failures = sum(s['total_failed'] for s in all_stats)
print(f"Total failures across all migrations: {total_failures}")

# Aggregate mutation types
all_mutation_types = Counter()
for s in all_stats:
    all_mutation_types.update(s['mutation_types'])

print("\nTotal failures by mutation type:")
for mut_type, count in all_mutation_types.most_common():
    print(f"  {count:4d} - {mut_type}")

# Check for unhandled mutation types
print("\n\nChecking for unhandled mutation types...")
handled_types = [
    'FactuurVerstuurd', 'FactuurOntvangen', 
    'FactuurbetalingOntvangen', 'FactuurbetalingVerstuurd',
    'GeldOntvangen', 'GeldUitgegeven', 'Memoriaal'
]

for mut_type in all_mutation_types:
    if mut_type not in handled_types:
        print(f"  UNHANDLED: {mut_type} ({all_mutation_types[mut_type]} failures)")