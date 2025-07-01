import frappe
import requests
import xml.etree.ElementTree as ET

@frappe.whitelist()
def test_soap_with_credentials():
    """Test E-Boekhouden SOAP API with provided credentials"""
    
    # Credentials provided by user
    username = "NVV_penningmeester"
    security_code_1 = "7e3169c820d849518853df7e30c4ba3f"
    security_code_2 = "BB51E315-A9B2-4D37-8E8E-96EF2E2554A7"
    
    soap_url = "https://soap.e-boekhouden.nl/soap.asmx"
    
    # First open a session
    session_envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
               xmlns:xsd="http://www.w3.org/2001/XMLSchema" 
               xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <OpenSession xmlns="http://www.e-boekhouden.nl/soap">
      <Username>{username}</Username>
      <SecurityCode1>{security_code_1}</SecurityCode1>
      <SecurityCode2>{security_code_2}</SecurityCode2>
    </OpenSession>
  </soap:Body>
</soap:Envelope>"""
    
    headers = {
        'Content-Type': 'text/xml; charset=utf-8',
        'SOAPAction': '"http://www.e-boekhouden.nl/soap/OpenSession"'
    }
    
    try:
        # Open session
        session_response = requests.post(soap_url, data=session_envelope, headers=headers, timeout=30)
        
        if session_response.status_code != 200:
            return {"error": f"Session failed: {session_response.status_code}", "response": session_response.text[:500]}
        
        # Extract session ID
        session_root = ET.fromstring(session_response.text)
        session_id = None
        
        # Look for SessionID element
        for elem in session_root.iter():
            if 'SessionID' in elem.tag and elem.text and elem.text.strip():
                session_id = elem.text.strip()
                break
        
        if not session_id:
            return {"error": "No session ID received", "response": session_response.text[:500]}
        
        # Now get mutations with the session
        mutations_envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
               xmlns:xsd="http://www.w3.org/2001/XMLSchema" 
               xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetMutaties xmlns="http://www.e-boekhouden.nl/soap">
      <SecurityCode2>{security_code_2}</SecurityCode2>
      <SessionID>{session_id}</SessionID>
      <cFilter>
        <DatumVan>2025-06-01</DatumVan>
        <DatumTot>2025-06-30</DatumTot>
      </cFilter>
    </GetMutaties>
  </soap:Body>
</soap:Envelope>"""
        
        headers['SOAPAction'] = '"http://www.e-boekhouden.nl/soap/GetMutaties"'
        
        mut_response = requests.post(soap_url, data=mutations_envelope, headers=headers, timeout=30)
        
        if mut_response.status_code == 200:
            # Parse response
            mut_root = ET.fromstring(mut_response.text)
            
            # Parse the SOAP response directly
            mutations = []
            
            # Find all cMutatieList elements
            for mutatie_elem in mut_root.iter():
                if 'cMutatieList' in mutatie_elem.tag:
                    mut_data = {}
                    # Get all child elements
                    for field in mutatie_elem:
                        field_name = field.tag.split('}')[-1] if '}' in field.tag else field.tag
                        if field.text:
                            mut_data[field_name] = field.text
                        # Handle nested MutatieRegels if present
                        if 'MutatieRegels' in field_name:
                            regels = []
                            for regel in field.iter():
                                if 'cMutatieListRegel' in regel.tag:
                                    regel_data = {}
                                    for regel_field in regel:
                                        regel_field_name = regel_field.tag.split('}')[-1] if '}' in regel_field.tag else regel_field.tag
                                        if regel_field.text:
                                            regel_data[regel_field_name] = regel_field.text
                                    if regel_data:
                                        regels.append(regel_data)
                            if regels:
                                mut_data['MutatieRegels'] = regels
                    
                    if mut_data:
                        mutations.append(mut_data)
            
            if mutations:
                fields = list(mutations[0].keys())
                
                # Extract descriptions and transaction types
                soorten = {}
                for m in mutations:
                    soort = m.get('Soort', 'Unknown')
                    soorten[soort] = soorten.get(soort, 0) + 1
                
                return {
                    "success": True,
                    "session_id": session_id,
                    "total_mutations": len(mutations),
                    "available_fields": sorted(fields),
                    "has_omschrijving": 'Omschrijving' in fields,
                    "transaction_types": soorten,
                    "sample_mutations": mutations[:3],
                    "omschrijving_samples": [m.get('Omschrijving', '') for m in mutations[:10] if m.get('Omschrijving')]
                }
            else:
                # Try to see what's in the response
                return {
                    "success": False,
                    "session_id": session_id,
                    "error": "Could not parse mutations",
                    "response_preview": mut_response.text[:2000]
                }
        else:
            return {
                "success": False,
                "session_id": session_id,
                "status_code": mut_response.status_code,
                "error": mut_response.text[:500]
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }

if __name__ == "__main__":
    print(test_soap_with_credentials())