import frappe
import requests
import xml.etree.ElementTree as ET
import base64

@frappe.whitelist()
def test_soap_detailed():
    """Test E-Boekhouden SOAP API with better parsing"""
    
    settings = frappe.get_single("E-Boekhouden Settings")
    
    # SOAP endpoint
    soap_url = "https://soap.e-boekhouden.nl/soap.asmx"
    
    # Build SOAP request - using OpenSession first
    session_envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
               xmlns:xsd="http://www.w3.org/2001/XMLSchema" 
               xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <OpenSession xmlns="http://www.e-boekhouden.nl/soap">
      <Username>{settings.username if hasattr(settings, 'username') else ''}</Username>
      <SecurityCode1>{settings.security_code_1 if hasattr(settings, 'security_code_1') else ''}</SecurityCode1>
      <SecurityCode2>{settings.api_token}</SecurityCode2>
    </OpenSession>
  </soap:Body>
</soap:Envelope>"""
    
    headers = {
        'Content-Type': 'text/xml; charset=utf-8',
        'SOAPAction': '"http://www.e-boekhouden.nl/soap/OpenSession"'
    }
    
    try:
        # Try to open session
        session_response = requests.post(soap_url, data=session_envelope, headers=headers, timeout=30)
        
        session_id = None
        if session_response.status_code == 200:
            # Extract session ID
            root = ET.fromstring(session_response.text)
            for elem in root.iter():
                if 'OpenSessionResult' in elem.tag:
                    session_id = elem.text
                    break
        
        # Now try GetMutaties with session or without
        mutations_envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
               xmlns:xsd="http://www.w3.org/2001/XMLSchema" 
               xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetMutaties xmlns="http://www.e-boekhouden.nl/soap">
      <SecurityCode2>{settings.api_token}</SecurityCode2>
      <SessionID>{session_id or ''}</SessionID>
      <cFilter>
        <MutatieNr>0</MutatieNr>
        <MutatieNrVan>0</MutatieNrVan>
        <MutatieNrTot>10</MutatieNrTot>
        <DatumVan>2025-06-01</DatumVan>
        <DatumTot>2025-06-30</DatumTot>
      </cFilter>
    </GetMutaties>
  </soap:Body>
</soap:Envelope>"""
        
        headers['SOAPAction'] = '"http://www.e-boekhouden.nl/soap/GetMutaties"'
        
        response = requests.post(soap_url, data=mutations_envelope, headers=headers, timeout=30)
        
        if response.status_code == 200:
            # Better parsing - look for the actual result
            root = ET.fromstring(response.text)
            
            # The response might be base64 encoded or XML string
            result_text = None
            for elem in root.iter():
                if 'GetMutatiesResult' in elem.tag:
                    result_text = elem.text
                    break
            
            if result_text:
                # Try to decode if base64
                try:
                    decoded = base64.b64decode(result_text).decode('utf-8')
                    result_text = decoded
                except:
                    pass
                
                # Parse the result XML if it's XML
                try:
                    mutations_root = ET.fromstring(result_text)
                    mutations = []
                    
                    # Look for Mutatie elements
                    for mutatie in mutations_root.findall('.//Mutatie'):
                        mut_data = {}
                        for child in mutatie:
                            mut_data[child.tag] = child.text
                        mutations.append(mut_data)
                    
                    if mutations:
                        sample = mutations[0]
                        fields = list(sample.keys())
                    else:
                        sample = {}
                        fields = []
                        
                    return {
                        "success": True,
                        "session_id": session_id,
                        "mutations_found": len(mutations),
                        "available_fields": fields,
                        "sample_mutation": sample,
                        "has_omschrijving": 'Omschrijving' in fields,
                        "first_3_mutations": mutations[:3]
                    }
                except ET.ParseError:
                    return {
                        "success": False,
                        "session_id": session_id,
                        "result_text_preview": result_text[:500] if result_text else "No result text",
                        "note": "Result is not valid XML"
                    }
            else:
                return {
                    "success": False,
                    "error": "No GetMutatiesResult found",
                    "raw_response": response.text[:1000]
                }
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text[:500]
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }

if __name__ == "__main__":
    print(test_soap_detailed())