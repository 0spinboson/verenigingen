import frappe

@frappe.whitelist()
def test_mt940_availability():
    """Test if MT940 library is available"""
    try:
        import mt940
        version = getattr(mt940, '__version__', 'unknown')
        return {
            "success": True,
            "message": f"MT940 library available, version: {version}",
            "version": version,
            "has_parse": hasattr(mt940, 'parse')
        }
    except ImportError as e:
        return {
            "success": False,
            "message": f"MT940 library not available: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error testing MT940: {str(e)}"
        }

@frappe.whitelist()
def test_simple_mt940_parse():
    """Test basic MT940 parsing with minimal sample"""
    try:
        import mt940
        import tempfile
        import os
        
        # Simple MT940 sample for testing
        sample_mt940 = """:20:930831-001
:25:ABNANL2A
:28C:00001/001
:60F:C930831EUR000000001000,00
:61:9309010901DR1000,00NTRFNONREF
:86:TEST TRANSACTION
:62F:C930831EUR000000000000,00
-
"""
        
        # Write to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sta', delete=False) as temp_file:
            temp_file.write(sample_mt940)
            temp_file_path = temp_file.name
        
        try:
            # Parse the file
            transactions = mt940.parse(temp_file_path)
            transaction_list = list(transactions)
            
            # Count transactions
            total_transactions = 0
            for statement in transaction_list:
                if hasattr(statement, 'transactions'):
                    total_transactions += len(statement.transactions)
                elif hasattr(statement, '__iter__'):
                    total_transactions += len(list(statement))
                else:
                    total_transactions += 1
            
            return {
                "success": True,
                "message": f"Successfully parsed MT940 sample with {total_transactions} transactions",
                "transaction_count": total_transactions,
                "statements_count": len(transaction_list)
            }
            
        finally:
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                
    except ImportError:
        return {
            "success": False,
            "message": "MT940 library not available"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error parsing MT940: {str(e)}"
        }