# E-Boekhouden SOAP API Credentials

## Where Credentials Are Stored

The SOAP API credentials for E-Boekhouden are now stored in the **E-Boekhouden Settings** doctype with the following fields:

1. **SOAP Username** (`soap_username`) - Stored as plain text
2. **Security Code 1** (`soap_security_code1`) - Stored as encrypted password
3. **Security Code 2 (GUID)** (`soap_security_code2`) - Stored as encrypted password
4. **Administration GUID** (`soap_guid`) - Optional, stored as plain text

## Accessing Credentials in the UI

1. Go to the ERPNext desk
2. Search for "E-Boekhouden Settings" or navigate to:
   - Verenigingen → Settings → E-Boekhouden Settings
3. Scroll down to the "SOAP API Credentials" section
4. Enter or update the credentials as needed

## Accessing Credentials in Code

```python
# Get settings
settings = frappe.get_single("E-Boekhouden Settings")

# Access username (plain text)
username = settings.soap_username

# Access passwords (encrypted)
security_code1 = settings.get_password('soap_security_code1')
security_code2 = settings.get_password('soap_security_code2')

# Access optional GUID
admin_guid = settings.soap_guid
```

## Testing Connection

1. In E-Boekhouden Settings, click the **"Test SOAP Connection"** button
2. This will verify that the credentials are valid and can connect to the SOAP API

## Migration from Hardcoded Values

The existing hardcoded credentials have been automatically migrated to the database:
- Username: `NVV_penningmeester`
- Security codes are stored encrypted

## Security Notes

- Password fields (`soap_security_code1` and `soap_security_code2`) are encrypted in the database
- Only users with System Manager or Verenigingen Administrator roles can access these settings
- The SOAP API client will fall back to hardcoded values if database credentials are not set (for backward compatibility)

## API Usage

The SOAP API client automatically uses these credentials:

```python
from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI

# Initialize without settings - will auto-load from database
api = EBoekhoudenSOAPAPI()

# Or pass specific settings
settings = frappe.get_single("E-Boekhouden Settings")
api = EBoekhoudenSOAPAPI(settings)
```