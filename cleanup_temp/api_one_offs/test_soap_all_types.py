import frappe
import requests
import xml.etree.ElementTree as ET

@frappe.whitelist()
def test_all_transaction_types():
    """Get all transaction types from SOAP API"""
    
    # Credentials
    username = "NVV_penningmeester"
    security_code_1 = "7e3169c820d849518853df7e30c4ba3f"
    security_code_2 = "BB51E315-A9B2-4D37-8E8E-96EF2E2554A7"
    
    soap_url = "https://soap.e-boekhouden.nl/soap.asmx"
    
    # Open session
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
    
    session_response = requests.post(soap_url, data=session_envelope, headers=headers, timeout=30)
    session_root = ET.fromstring(session_response.text)
    session_id = None
    
    for elem in session_root.iter():
        if 'SessionID' in elem.tag and elem.text and elem.text.strip():
            session_id = elem.text.strip()
            break
    
    if not session_id:
        return {"error": "No session ID"}
    
    # Get mutations for wider date range to see all types
    mutations_envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
               xmlns:xsd="http://www.w3.org/2001/XMLSchema" 
               xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetMutaties xmlns="http://www.e-boekhouden.nl/soap">
      <SecurityCode2>{security_code_2}</SecurityCode2>
      <SessionID>{session_id}</SessionID>
      <cFilter>
        <DatumVan>2025-01-01</DatumVan>
        <DatumTot>2025-06-30</DatumTot>
      </cFilter>
    </GetMutaties>
  </soap:Body>
</soap:Envelope>"""
    
    headers['SOAPAction'] = '"http://www.e-boekhouden.nl/soap/GetMutaties"'
    mut_response = requests.post(soap_url, data=mutations_envelope, headers=headers, timeout=30)
    
    if mut_response.status_code != 200:
        return {"error": f"Failed: {mut_response.status_code}"}
    
    # Parse mutations
    mut_root = ET.fromstring(mut_response.text)
    mutations = []
    
    for mutatie_elem in mut_root.iter():
        if 'cMutatieList' in mutatie_elem.tag:
            mut_data = {}
            for field in mutatie_elem:
                field_name = field.tag.split('}')[-1] if '}' in field.tag else field.tag
                if field.text:
                    mut_data[field_name] = field.text
            if mut_data:
                mutations.append(mut_data)
    
    # Analyze transaction types
    type_analysis = {}
    payment_examples = []
    
    for m in mutations:
        soort = m.get('Soort', 'Unknown')
        
        if soort not in type_analysis:
            type_analysis[soort] = {
                "count": 0,
                "examples": []
            }
        
        type_analysis[soort]["count"] += 1
        
        # Keep examples of each type
        if len(type_analysis[soort]["examples"]) < 3:
            type_analysis[soort]["examples"].append({
                "date": m.get('Datum', '')[:10],
                "description": m.get('Omschrijving', '')[:100],
                "account": m.get('Rekening'),
                "invoice": m.get('Factuurnummer'),
                "relation": m.get('RelatieCode')
            })
        
        # Look for payment-related descriptions
        desc = (m.get('Omschrijving', '') or '').lower()
        if any(word in desc for word in ['betaling', 'ontvangen', 'verstuurd', 'geld']):
            if len(payment_examples) < 10:
                payment_examples.append({
                    "type": soort,
                    "description": m.get('Omschrijving', ''),
                    "date": m.get('Datum', '')[:10],
                    "invoice": m.get('Factuurnummer')
                })
    
    return {
        "total_mutations": len(mutations),
        "transaction_types": type_analysis,
        "payment_examples": payment_examples,
        "date_range": "2025-01-01 to 2025-06-30"
    }

if __name__ == "__main__":
    print(test_all_transaction_types())