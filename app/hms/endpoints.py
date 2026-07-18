"""HMS Express route path constants (relative to tenant hms_base_url).

Aligned with srichakradiagnostics/hms-server routes.
"""

PATIENTS = "/patients"
PATIENT_BY_PHONE = "/patients/phone/{phone}"
# Path :id is UMRNo, not Mongo _id
PATIENT_BY_UMR = "/patients/{umr}"
PATIENT_INTERIM_BILL = "/patients/{umr}/interim-bill"

APPOINTMENTS = "/appointments"
APPOINTMENT_BY_ID = "/appointments/{appointment_id}"

DEPARTMENTS = "/departments"
STAFF_BY_TYPE = "/staff/type/{staff_type}"

DIAGNOSTICS_RECEIPTS = "/diagnostics-receipts"
DIAGNOSTICS_BY_PATIENT = "/diagnostics-receipts/patient/{umr}"
DIAGNOSTICS_BY_ACCOUNT_PHONE = "/diagnostics-receipts/account/{phone}"

# patientId path param is UMRNo
PRESCRIPTION_WHATSAPP = "/prescriptions/{umr}/{prescription_id}/send-whatsapp"
