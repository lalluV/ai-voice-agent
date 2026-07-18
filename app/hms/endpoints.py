"""HMS Express route path constants (relative to tenant hms_base_url)."""

PATIENTS = "/patients"
PATIENT_BY_PHONE = "/patients/phone/{phone}"
PATIENT_BY_ID = "/patients/{patient_id}"
PATIENT_INTERIM_BILL = "/patients/{patient_id}/interim-bill"

APPOINTMENTS = "/appointments"
APPOINTMENT_BY_ID = "/appointments/{appointment_id}"

DEPARTMENTS = "/departments"
STAFF_BY_TYPE = "/staff/type/{staff_type}"

DIAGNOSTICS_RECEIPTS = "/diagnostics-receipts"
PRESCRIPTION_WHATSAPP = "/prescriptions/{patient_id}/{prescription_id}/send-whatsapp"
