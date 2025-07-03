import frappe
from frappe import _
import xml.etree.ElementTree as ET

@frappe.whitelist()
def debug_soap_response():
    """Debug the SOAP response to understand structure"""
    
    from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    import requests
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenSOAPAPI(settings)
    
    # Open session first
    session_result = api.open_session()
    if not session_result["success"]:
        return {"error": "Failed to open session"}
    
    # Get mutations for just one day to see structure
    envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
               xmlns:xsd="http://www.w3.org/2001/XMLSchema" 
               xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetMutaties xmlns="http://www.e-boekhouden.nl/soap">
      <SecurityCode2>{api.security_code_2}</SecurityCode2>
      <SessionID>{api.session_id}</SessionID>
      <cFilter>
        <MutatieNr>0</MutatieNr>
        <MutatieNrVan>0</MutatieNrVan>
        <MutatieNrTm>0</MutatieNrTm>
        <Factuurnummer></Factuurnummer>
        <DatumVan>2025-05-01</DatumVan>
        <DatumTm>2025-05-01</DatumTm>
      </cFilter>
    </GetMutaties>
  </soap:Body>
</soap:Envelope>"""
    
    try:
        response = requests.post(
            api.soap_url,
            data=envelope,
            headers={
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': '"http://www.e-boekhouden.nl/soap/GetMutaties"'
            }
        )
        
        if response.status_code == 200:
            # Save raw XML for inspection
            with open("/tmp/soap_response.xml", "w") as f:
                f.write(response.text)
            
            # Parse and analyze structure
            root = ET.fromstring(response.text)
            
            # Find the namespace
            namespaces = {}
            for elem in root.iter():
                if elem.tag.startswith('{'):
                    ns = elem.tag.split('}')[0] + '}'
                    namespaces[ns] = True
            
            # Count different element types
            element_counts = {}
            for elem in root.iter():
                tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                if tag not in element_counts:
                    element_counts[tag] = 0
                element_counts[tag] += 1
            
            # Find first few mutations structure
            mutations_structure = []
            mutation_count = 0
            
            for elem in root.iter():
                if 'GetMutatiesResult' in elem.tag:
                    # This should contain the mutations
                    for child in elem:
                        child_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                        if child_tag == 'Mutaties' and mutation_count < 3:
                            # Get structure of a mutation
                            mutation_structure = {}
                            for mut_child in child:
                                mut_tag = mut_child.tag.split('}')[-1] if '}' in mut_child.tag else mut_child.tag
                                if mut_tag == 'cMutatieList':
                                    for field in mut_child:
                                        field_tag = field.tag.split('}')[-1] if '}' in field.tag else field.tag
                                        mutation_structure[field_tag] = field.text or "has_children"
                            
                            mutations_structure.append(mutation_structure)
                            mutation_count += 1
            
            return {
                "namespaces": list(namespaces.keys()),
                "element_counts": element_counts,
                "mutations_structure": mutations_structure,
                "saved_to": "/tmp/soap_response.xml"
            }
        else:
            return {"error": f"Failed: {response.status_code}"}
            
    except Exception as e:
        return {"error": str(e), "traceback": frappe.get_traceback()}