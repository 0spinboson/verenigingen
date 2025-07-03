"""
Diagnose account creation issues
"""

import frappe

@frappe.whitelist()
def diagnose_account_creation_issue():
    """
    Diagnose why account creation is failing
    """
    try:
        company = "Ned Ver Vegan"
        
        # Check if company exists and is valid
        company_doc = frappe.get_doc("Company", company)
        company_abbr = company_doc.abbr
        
        # Try to create a very simple test account with minimal fields
        test_account = frappe.new_doc("Account")
        test_account.account_name = "Test Account"
        test_account.company = company
        test_account.root_type = "Asset"
        test_account.is_group = 1
        
        # Try to validate first (this will show us what's missing)
        validation_errors = []
        try:
            test_account.run_method("validate")
        except Exception as e:
            validation_errors.append(str(e))
        
        # Check the Account DocType structure
        account_meta = frappe.get_meta("Account")
        mandatory_fields = []
        for field in account_meta.fields:
            if field.reqd:
                mandatory_fields.append({
                    "fieldname": field.fieldname,
                    "label": field.label,
                    "fieldtype": field.fieldtype
                })
        
        # Check if parent_account is mandatory
        parent_account_field = None
        for field in account_meta.fields:
            if field.fieldname == "parent_account":
                parent_account_field = {
                    "fieldname": field.fieldname,
                    "label": field.label,
                    "reqd": field.reqd,
                    "fieldtype": field.fieldtype
                }
                break
        
        return {
            "success": True,
            "company_info": {
                "name": company,
                "abbr": company_abbr,
                "exists": True
            },
            "validation_errors": validation_errors,
            "mandatory_fields": mandatory_fields,
            "parent_account_field": parent_account_field,
            "account_meta_info": {
                "total_fields": len(account_meta.fields),
                "mandatory_count": len(mandatory_fields)
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def try_create_account_with_all_fields():
    """
    Try to create an account with all possible fields populated
    """
    try:
        company = "Ned Ver Vegan"
        company_abbr = frappe.db.get_value("Company", company, "abbr")
        
        # Try with all standard fields
        account = frappe.new_doc("Account")
        account.account_name = "Test Root Account"
        account.account_number = "TEST001"
        account.company = company
        account.root_type = "Asset"
        account.account_type = ""  # Empty for root accounts
        account.is_group = 1
        account.disabled = 0
        
        # Check if we need to set parent_account to None explicitly
        account.parent_account = None
        
        # Try to save
        try:
            account.insert(ignore_permissions=True)
            frappe.db.commit()
            
            return {
                "success": True,
                "account_created": account.name,
                "message": "Successfully created test account"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Account creation failed: {str(e)}",
                "account_data": account.as_dict()
            }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }