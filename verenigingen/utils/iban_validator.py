import re
import frappe
from frappe import _

# IBAN country specifications
IBAN_SPECS = {
    'AD': {'length': 24, 'bban_pattern': r'^\d{8}[A-Z0-9]{12}$'},
    'AT': {'length': 20, 'bban_pattern': r'^\d{16}$'},
    'BE': {'length': 16, 'bban_pattern': r'^\d{12}$'},
    'CH': {'length': 21, 'bban_pattern': r'^\d{5}[A-Z0-9]{12}$'},
    'CZ': {'length': 24, 'bban_pattern': r'^\d{20}$'},
    'DE': {'length': 22, 'bban_pattern': r'^\d{18}$'},
    'DK': {'length': 18, 'bban_pattern': r'^\d{14}$'},
    'ES': {'length': 24, 'bban_pattern': r'^\d{20}$'},
    'FI': {'length': 18, 'bban_pattern': r'^\d{14}$'},
    'FR': {'length': 27, 'bban_pattern': r'^\d{10}[A-Z0-9]{11}\d{2}$'},
    'GB': {'length': 22, 'bban_pattern': r'^[A-Z]{4}\d{14}$'},
    'IE': {'length': 22, 'bban_pattern': r'^[A-Z]{4}\d{14}$'},
    'IT': {'length': 27, 'bban_pattern': r'^[A-Z]\d{10}[A-Z0-9]{12}$'},
    'LU': {'length': 20, 'bban_pattern': r'^\d{3}[A-Z0-9]{13}$'},
    'NL': {'length': 18, 'bban_pattern': r'^[A-Z]{4}\d{10}$'},
    'NO': {'length': 15, 'bban_pattern': r'^\d{11}$'},
    'PL': {'length': 28, 'bban_pattern': r'^\d{24}$'},
    'PT': {'length': 25, 'bban_pattern': r'^\d{21}$'},
    'SE': {'length': 24, 'bban_pattern': r'^\d{20}$'},
}

@frappe.whitelist()
def validate_iban(iban):
    """
    Comprehensive IBAN validation with mod-97 checksum
    Returns: dict with 'valid' (bool) and 'message' (str)
    """
    if not iban:
        return {'valid': False, 'message': _('IBAN is required')}
    
    # Remove spaces and convert to uppercase
    iban_clean = iban.replace(' ', '').upper()
    
    # Basic format check
    if not re.match(r'^[A-Z]{2}\d{2}[A-Z0-9]+$', iban_clean):
        return {'valid': False, 'message': _('Invalid IBAN format')}
    
    # Extract country code
    country_code = iban_clean[:2]
    
    # Check if country is supported
    if country_code not in IBAN_SPECS:
        return {'valid': False, 'message': _('Country code {0} not supported').format(country_code)}
    
    # Check length
    expected_length = IBAN_SPECS[country_code]['length']
    if len(iban_clean) != expected_length:
        return {
            'valid': False, 
            'message': _('Invalid IBAN length for {0}. Expected {1} characters, got {2}').format(
                country_code, expected_length, len(iban_clean)
            )
        }
    
    # Validate BBAN pattern
    bban = iban_clean[4:]
    if not re.match(IBAN_SPECS[country_code]['bban_pattern'], bban):
        return {'valid': False, 'message': _('Invalid account number format for {0}').format(country_code)}
    
    # Perform mod-97 checksum validation
    if not validate_iban_checksum(iban_clean):
        return {'valid': False, 'message': _('Invalid IBAN checksum')}
    
    return {'valid': True, 'message': _('Valid IBAN')}

def validate_iban_checksum(iban):
    """
    Validate IBAN using mod-97 algorithm
    """
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

@frappe.whitelist()
def format_iban(iban):
    """
    Format IBAN with proper spacing (groups of 4)
    """
    if not iban:
        return ''
    
    # Clean IBAN
    iban_clean = iban.replace(' ', '').upper()
    
    # Format in groups of 4
    formatted = ' '.join([iban_clean[i:i+4] for i in range(0, len(iban_clean), 4)])
    return formatted

@frappe.whitelist()
def get_bank_from_iban(iban):
    """
    Extract bank information from IBAN
    Returns: dict with bank_code and bank_name
    """
    if not iban:
        return None
    
    iban_clean = iban.replace(' ', '').upper()
    
    if len(iban_clean) < 8:
        return None
    
    country_code = iban_clean[:2]
    
    if country_code == 'NL':
        # Dutch IBAN: NLkk BBBB CCCC CCCC CC
        bank_code = iban_clean[4:8]
        bank_names = {
            'INGB': 'ING Bank',
            'ABNA': 'ABN AMRO',
            'RABO': 'Rabobank',
            'TRIO': 'Triodos Bank',
            'SNSB': 'SNS Bank',
            'ASNB': 'ASN Bank',
            'KNAB': 'Knab',
            'BUNQ': 'bunq Bank',
            'REVO': 'Revolut',
            'BITV': 'Bitonic',
            'FVLB': 'Van Lanschot Kempen',
            'HAND': 'Svenska Handelsbanken',
            'DHBN': 'Demir-Halk Bank Nederland',
            'NWAB': 'Nederlandse Waterschapsbank',
            'COBA': 'Commerzbank',
            'DEUT': 'Deutsche Bank',
            'FBHL': 'Credit Europe Bank',
            'NNBA': 'Nationale-Nederlanden Bank',
        }
        return {
            'bank_code': bank_code,
            'bank_name': bank_names.get(bank_code, 'Unknown Bank'),
            'country': 'Netherlands'
        }
    
    elif country_code == 'BE':
        # Belgian IBAN: BEkk BBBC CCCC CCCC
        bank_code = iban_clean[4:7]
        bank_names = {
            '001': 'bpost bank',
            '068': 'Crelan',
            '096': 'Belfius',
            '363': 'KBC',
            '734': 'BNP Paribas Fortis',
            '050': 'Argenta',
            '285': 'ING Belgium',
        }
        return {
            'bank_code': bank_code,
            'bank_name': bank_names.get(bank_code, 'Unknown Bank'),
            'country': 'Belgium'
        }
    
    elif country_code == 'DE':
        # German IBAN: DEkk BBBB BBBB CCCC CCCC CC
        bank_code = iban_clean[4:12]
        # Limited set of German banks
        return {
            'bank_code': bank_code,
            'bank_name': 'German Bank',
            'country': 'Germany'
        }
    
    return None

@frappe.whitelist()
def derive_bic_from_iban(iban):
    """
    Enhanced BIC derivation from IBAN with extended bank database
    """
    if not iban:
        return None
    
    iban_clean = iban.replace(' ', '').upper()
    
    # Validate IBAN first
    validation = validate_iban(iban)
    if not validation['valid']:
        return None
    
    country_code = iban_clean[:2]
    
    # Enhanced Dutch BIC database
    if country_code == 'NL':
        bank_code = iban_clean[4:8]
        nl_bic_codes = {
            'INGB': 'INGBNL2A',
            'ABNA': 'ABNANL2A',
            'RABO': 'RABONL2U',
            'TRIO': 'TRIONL2U',
            'SNSB': 'SNSBNL2A',
            'ASNB': 'ASNBNL21',
            'KNAB': 'KNABNL2H',
            'BUNQ': 'BUNQNL2A',
            'REVO': 'REVOLT21',
            'BITV': 'BITVNL21',
            'FVLB': 'FVLBNL22',
            'HAND': 'HANDNL2A',
            'DHBN': 'DHBNNL2R',
            'NWAB': 'NWABNL2G',
            'COBA': 'COBANL2X',
            'DEUT': 'DEUTNL2A',
            'FBHL': 'FBHLNL2A',
            'NNBA': 'NNBANL2G',
            'AEGN': 'AEGNNL2A',
            'ZWLB': 'ZWLBNL21',
            'VOPA': 'VOPANL22',
        }
        return nl_bic_codes.get(bank_code)
    
    # Belgian BIC database
    elif country_code == 'BE':
        bank_code = iban_clean[4:7]
        be_bic_codes = {
            '001': 'BPOTBEB1',
            '068': 'JVBABE22',
            '096': 'GKCCBEBB',
            '363': 'BBRUBEBB',
            '734': 'GEBABEBB',
            '050': 'ARSPBE22',
            '285': 'BBRUBEBB',
            '733': 'ABNABE22',
            '103': 'NICABEBB',
            '539': 'HBKABE22',
        }
        return be_bic_codes.get(bank_code)
    
    # German BIC database (extended)
    elif country_code == 'DE':
        bank_code = iban_clean[4:12]
        de_bic_codes = {
            '10070000': 'DEUTDEFF',
            '20070000': 'DEUTDEDBHAM',
            '50070010': 'DEUTDEFF500',
            '12030000': 'BYLADEM1001',
            '43060967': 'GENODEM1GLS',
            '50010517': 'INGDDEFF',
            '76026000': 'HYVEDEMM473',
            '20041133': 'COBADEFFXXX',
            '10010010': 'PBNKDEFFXXX',
            '50010060': 'PBNKDEFF',
            '30010700': 'BOTKDEDXXXX',
            '37040044': 'COBADEFFXXX',
            '70120400': 'DABBDEMMXXX',
        }
        return de_bic_codes.get(bank_code)
    
    # French BIC database (basic)
    elif country_code == 'FR':
        bank_code = iban_clean[4:9]
        fr_bic_codes = {
            '10011': 'PSSTFRPPPAR',
            '10041': 'BDFEFRPPCEE',
            '10051': 'CEPAFRPP',
            '10057': 'SOCGFRPP',
            '11006': 'AGRIFRPP',
            '12006': 'BMCEFRPP',
            '13606': 'CCFRFRPP',
            '14406': 'CMCIFRPP',
            '30001': 'BDFEFRPPCCT',
            '30002': 'CRLYFRPP',
            '30003': 'SOGEFRPP',
            '30004': 'BNPAFRPP',
        }
        return fr_bic_codes.get(bank_code)
    
    return None