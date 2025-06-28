import frappe
from frappe import _
import requests
import xml.etree.ElementTree as ET

@frappe.whitelist()
def debug_soap_raw_response():
    """Debug raw SOAP response"""
    
    from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenSOAPAPI(settings)
    
    # Open session first
    session_result = api.open_session()
    if not session_result["success"]:
        return {"error": "Failed to open session"}
    
    # Build request for May 2025
    filter_xml = """
        <MutatieNr>0</MutatieNr>
        <MutatieNrVan>0</MutatieNrVan>
        <MutatieNrTot>0</MutatieNrTot>
        <Factuurnummer></Factuurnummer>
        <DatumVan>2025-05-01</DatumVan>
        <DatumTm>2025-05-31</DatumTm>"""
        
    envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
               xmlns:xsd="http://www.w3.org/2001/XMLSchema" 
               xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetMutaties xmlns="http://www.e-boekhouden.nl/soap">
      <SecurityCode2>{api.security_code_2}</SecurityCode2>
      <SessionID>{api.session_id}</SessionID>
      <cFilter>{filter_xml}
      </cFilter>
    </GetMutaties>
  </soap:Body>
</soap:Envelope>"""
    
    headers = {
        'Content-Type': 'text/xml; charset=utf-8',
        'SOAPAction': '"http://www.e-boekhouden.nl/soap/GetMutaties"'
    }
    
    try:
        response = requests.post(api.soap_url, data=envelope, headers=headers, timeout=60)
        
        # Save raw response
        with open("/tmp/soap_may_response.xml", "w") as f:
            f.write(response.text)
        
        # Parse to check error
        root = ET.fromstring(response.text)
        
        # Look for error message
        error_msg = None
        for elem in root.iter():
            if 'ErrorMsg' in elem.tag and elem.text:
                error_msg = elem.text
                break
        
        # Count mutations in response
        mutation_count = 0
        for elem in root.iter():
            if 'cMutatieList' in elem.tag:
                mutation_count += 1
        
        # Check if there's a GetMutatiesResult
        has_result = False
        for elem in root.iter():
            if 'GetMutatiesResult' in elem.tag:
                has_result = True
                break
        
        return {
            "status_code": response.status_code,
            "has_result": has_result,
            "error_msg": error_msg,
            "mutation_count": mutation_count,
            "saved_to": "/tmp/soap_may_response.xml",
            "request_envelope": envelope[:500] + "..."
        }
        
    except Exception as e:
        return {"error": str(e), "traceback": frappe.get_traceback()}