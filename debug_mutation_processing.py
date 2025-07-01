#!/usr/bin/env python3
"""Debug script to understand mutation processing"""

import json
import os
from collections import Counter

# Analyze the failed records to understand patterns
log_dir = "/home/frappe/frappe-bench/sites/dev.veganisme.net/private/files/eboekhouden_migration_logs"

# Get the most recent log file
files = [f for f in os.listdir(log_dir) if f.startswith("failed_records_")]
if not files:
    print("No failed record files found")
    exit()

latest_file = sorted(files)[-1]
filepath = os.path.join(log_dir, latest_file)

print(f"Analyzing: {latest_file}")

with open(filepath, 'r') as f:
    data = json.load(f)

print(f"\nMigration: {data['migration_name']}")
print(f"Total Failed: {data['total_failed']}")

# Extract unique mutation types from errors
mutation_types = set()
mutation_numbers = set()

for record in data['failed_records']:
    if 'record_data' in record:
        rd = record['record_data']
        if 'Soort' in rd:
            mutation_types.add(rd['Soort'])
        if 'MutatieNr' in rd:
            mutation_numbers.add(rd['MutatieNr'])

print(f"\nUnique mutation types in failures: {mutation_types}")
print(f"Unique mutation numbers that failed: {len(mutation_numbers)}")

# Check if these are the only types being processed
recognized_types = {
    'FactuurVerstuurd', 'FactuurOntvangen', 
    'FactuurbetalingOntvangen', 'FactuurbetalingVerstuurd',
    'GeldOntvangen', 'GeldUitgegeven', 'Memoriaal'
}

print(f"\nRecognized types in code: {recognized_types}")
print(f"Types in failures: {mutation_types}")
print(f"Missing from failures: {recognized_types - mutation_types}")

# Summary
print("\n=== ANALYSIS ===")
print("From the migration summary:")
print("- 9,018 total records")
print("- 7,383 mutations processed")
print("- 320 imported successfully") 
print("- 1,378 failed")
print(f"- {7383 - 320 - 1378} mutations unaccounted for!")

print("\nPossible reasons for missing mutations:")
print("1. Mutation types not in the recognized list are being silently skipped")
print("2. The 'already processed' check is filtering them out")
print("3. They're being normalized to 'Unknown' and not handled")
print("4. Date range filtering is excluding them")
print("5. Some mutations have no amount and are skipped")

# Check the normalized types
from verenigingen.utils.normalize_mutation_types import normalize_mutation_type

print("\n\nTesting normalization of common Dutch terms:")
test_types = [
    "Geld ontvangen", "GELD ONTVANGEN", "geld ontvangen",
    "Geld uitgegeven", "GELD UITGEGEVEN", 
    "Memoriaal", "MEMORIAAL", "memoriaal",
    "Kas", "KAS", "Bank", "BANK",
    "Contant", "CONTANT", "PIN", "iDEAL"
]

for t in test_types:
    normalized = normalize_mutation_type(t)
    if normalized != t:
        print(f"'{t}' -> '{normalized}'")