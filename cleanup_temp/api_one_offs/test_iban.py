import frappe
from frappe import _

@frappe.whitelist()
def test_iban_validation():
    """Test IBAN validation functionality"""
    from verenigingen.utils.iban_validator import validate_iban, format_iban, derive_bic_from_iban, get_bank_from_iban
    
    # Test cases
    test_results = []
    
    # Test valid Dutch IBAN
    result = validate_iban("NL91ABNA0417164300")
    test_results.append({
        "test": "Valid Dutch IBAN",
        "iban": "NL91ABNA0417164300",
        "valid": result['valid'],
        "message": result['message'],
        "bic": derive_bic_from_iban("NL91ABNA0417164300"),
        "bank": get_bank_from_iban("NL91ABNA0417164300")
    })
    
    # Test Dutch IBAN with spaces
    result = validate_iban("NL91 ABNA 0417 1643 00")
    test_results.append({
        "test": "Dutch IBAN with spaces",
        "iban": "NL91 ABNA 0417 1643 00",
        "valid": result['valid'],
        "formatted": format_iban("NL91 ABNA 0417 1643 00")
    })
    
    # Test invalid checksum
    result = validate_iban("NL91ABNA0417164301")
    test_results.append({
        "test": "Invalid checksum",
        "iban": "NL91ABNA0417164301",
        "valid": result['valid'],
        "message": result['message']
    })
    
    # Test different banks
    bank_tests = [
        ("NL86INGB0002445588", "ING Bank"),
        ("NL02RABO0104839460", "Rabobank"),
        ("NL81TRIO0212194988", "Triodos Bank"),
        ("BE68539007547034", "Belgian IBAN")
    ]
    
    for iban, bank_name in bank_tests:
        result = validate_iban(iban)
        test_results.append({
            "test": bank_name,
            "iban": iban,
            "valid": result['valid'],
            "bic": derive_bic_from_iban(iban) if result['valid'] else None,
            "bank": get_bank_from_iban(iban) if result['valid'] else None
        })
    
    return test_results