#!/usr/bin/env python3
"""Check BUNQ IBAN checksum"""

def validate_iban_checksum(iban):
    """Validate IBAN using mod-97 algorithm"""
    # Move first 4 characters to end
    rearranged = iban[4:] + iban[:4]
    
    # Convert letters to numbers (A=10, B=11, ..., Z=35)
    numeric_iban = ''
    for char in rearranged:
        if char.isdigit():
            numeric_iban += char
        else:
            numeric_iban += str(ord(char) - ord('A') + 10)
    
    # Calculate mod 97
    return int(numeric_iban) % 97 == 1

# Test the BUNQ IBAN
test_iban = 'NL77BUNQ1234567890'
print(f"Testing IBAN: {test_iban}")
print(f"Checksum valid: {validate_iban_checksum(test_iban)}")

# Calculate correct checksum
base_iban = 'NL00BUNQ1234567890'
rearranged = base_iban[4:] + base_iban[:2] + '00'
numeric_iban = ''
for char in rearranged:
    if char.isdigit():
        numeric_iban += char
    else:
        numeric_iban += str(ord(char) - ord('A') + 10)

check_digits = 98 - (int(numeric_iban) % 97)
correct_iban = f'NL{check_digits:02d}BUNQ1234567890'
print(f"Correct IBAN should be: {correct_iban}")
print(f"Checksum valid: {validate_iban_checksum(correct_iban)}")