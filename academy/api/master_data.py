import frappe
from frappe import _

@frappe.whitelist(allow_guest=True)
def get_master_data():
	"""
	Fetch Master Company, Department Master, Booking Type, and IT Requirements.
	Access is restricted to logged-in users.
	"""
	if frappe.session.user == "Guest":
		frappe.throw(_("Please login to access this API"), frappe.PermissionError)

	data = {
		"master_company": [],
		"department_master": [],
		"booking_type": [],
		"it_requirements": []
	}

	try:
		# Master Company
		# Fields: company_code, name (company_name), description (company_description)
		data["master_company"] = frappe.get_all(
			"Master Company",
			fields=["company_code", "company_name as name", "company_description as description"]
		)
	except Exception as e:
		frappe.log_error(message=str(e), title="Master Data API - Master Company Error")

	try:
		# Department Master
		# Fields: name (department_name), description
		data["department_master"] = frappe.get_all(
			"Department Master",
			fields=["department_name as name", "description"]
		)
	except Exception as e:
		frappe.log_error(message=str(e), title="Master Data API - Department Master Error")

	try:
		# Booking Type
		# Fields: name (booking_type), description
		# Note: Assuming DocType is "Booking Type" and field is "booking_type" per user request
		data["booking_type"] = frappe.get_all(
			"Booking Type",
			fields=["booking_type as name", "description"]
		)
	except Exception as e:
		frappe.log_error(message=str(e), title="Master Data API - Booking Type Error")

	try:
		# IT Requirements
		# Fields: name (requirement), description
		data["it_requirements"] = frappe.get_all(
			"IT Requirement",
			fields=["requirement as name", "description"]
		)
	except Exception as e:
		frappe.log_error(message=str(e), title="Master Data API - IT Requirements Error")

	return data
