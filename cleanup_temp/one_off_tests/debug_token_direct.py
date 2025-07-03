import frappe
from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI

@frappe.whitelist()
def test_token_issue():
    """Test token issue with detailed logging"""
    try:
        # Test the settings
        settings = frappe.get_single("E-Boekhouden Settings")
        
        result = {
            "api_url": settings.api_url,
            "source": settings.source_application,
        }
        
        # Test token retrieval
        token = settings.get_password('api_token')
        result["token_available"] = bool(token)
        result["token_length"] = len(token) if token else 0
        
        # Test API class initialization
        api = EBoekhoudenAPI(settings)
        result["api_initialized"] = True
        
        # Test session token
        session_token = api.get_session_token()
        result["session_token_obtained"] = bool(session_token)
        
        if session_token:
            result["session_token_length"] = len(session_token)
            
            # Test a simple API call
            api_result = api.make_request("v1/ledger", "GET", {"limit": 1})
            result["test_api_call_success"] = api_result['success']
            if not api_result['success']:
                result["api_error"] = api_result['error']
        else:
            result["session_token_error"] = "Failed to get session token"
            
        return {"success": True, "result": result}
        
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }