import frappe
import requests
import xml.etree.ElementTree as ET

@frappe.whitelist()
def test_soap_api():
    """Test E-Boekhouden SOAP API to see if it provides more mutation details"""
    
    settings = frappe.get_single("E-Boekhouden Settings")
    
    # SOAP endpoint from the PDF
    soap_url = "https://soap.e-boekhouden.nl/soap.asmx"
    
    # First, let's get the WSDL to see available methods
    try:
        wsdl_response = requests.get(f"{soap_url}?wsdl", timeout=10)
        if wsdl_response.status_code == 200:
            wsdl_info = "WSDL retrieved successfully"
            # Parse to find GetMutaties method
            root = ET.fromstring(wsdl_response.text)
            # Look for operation names
            operations = []
            for elem in root.iter():
                if 'operation' in elem.tag and elem.get('name'):
                    operations.append(elem.get('name'))
        else:
            wsdl_info = f"WSDL request failed: {wsdl_response.status_code}"
            operations = []
    except Exception as e:
        wsdl_info = f"WSDL error: {str(e)}"
        operations = []
    
    # Build a SOAP request for GetMutaties
    soap_envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
               xmlns:xsd="http://www.w3.org/2001/XMLSchema" 
               xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetMutaties xmlns="http://www.e-boekhouden.nl/soap">
      <SecurityCode2>{settings.api_token}</SecurityCode2>
      <SessionID></SessionID>
      <MutatieFilter>
        <DatumVan>2025-06-01</DatumVan>
        <DatumTot>2025-06-30</DatumTot>
      </MutatieFilter>
    </GetMutaties>
  </soap:Body>
</soap:Envelope>"""
    
    # Try to call GetMutaties
    headers = {
        'Content-Type': 'text/xml; charset=utf-8',
        'SOAPAction': '"http://www.e-boekhouden.nl/soap/GetMutaties"'
    }
    
    try:
        response = requests.post(soap_url, data=soap_envelope, headers=headers, timeout=30)
        
        if response.status_code == 200:
            # Parse response
            response_root = ET.fromstring(response.text)
            
            # Find mutation data
            mutations = []
            for elem in response_root.iter():
                if 'Mutatie' in elem.tag and 'Envelope' not in elem.tag:
                    mutation_data = {}
                    for child in elem:
                        tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                        mutation_data[tag_name] = child.text
                    if mutation_data:
                        mutations.append(mutation_data)
            
            # Get first mutation as sample
            sample_mutation = mutations[0] if mutations else {}
            available_fields = list(sample_mutation.keys()) if sample_mutation else []
            
            result = {
                "soap_status": "Success",
                "mutations_found": len(mutations),
                "available_fields": available_fields,
                "sample_mutation": sample_mutation,
                "has_description": 'Omschrijving' in available_fields or 'omschrijving' in available_fields
            }
        else:
            result = {
                "soap_status": f"Failed: {response.status_code}",
                "response_text": response.text[:500]
            }
            
    except Exception as e:
        result = {
            "soap_status": f"Error: {str(e)}",
            "error_type": type(e).__name__
        }
    
    return {
        "wsdl_info": wsdl_info,
        "operations_found": operations[:10] if operations else [],
        "soap_test": result,
        "recommendation": "Check if SOAP API provides the missing description fields"
    }

if __name__ == "__main__":
    print(test_soap_api())