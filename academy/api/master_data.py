import frappe
from frappe import _


@frappe.whitelist(allow_guest=True)
def get_master_data():
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


# ---------------------------------------------------------------------------
# Distributor APIs
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=True)
def get_distributor_list(search=None, limit=10):
	"""Fetch distributor list with optional search on distributor_name."""
	if frappe.session.user == "Guest":
		frappe.throw(_("Please login to access this API"), frappe.PermissionError)

	limit = int(limit)
	filters = {"is_deleted": 0}
	if search:
		filters["distributor_name"] = ["like", f"%{search}%"]

	records = frappe.get_all(
		"Master Distributor",
		filters=filters,
		fields=["name", "distributor_name"],
		order_by="modified desc",
		page_length=limit,
	)

	return [{"value": r.name, "label": r.distributor_name} for r in records]


# ---------------------------------------------------------------------------
# Account APIs
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=True)
def get_account_list(search=None, limit=10):
	"""Fetch account list with optional search on account_name."""
	if frappe.session.user == "Guest":
		frappe.throw(_("Please login to access this API"), frappe.PermissionError)

	limit = int(limit)
	filters = {}
	if search:
		filters["account_name"] = ["like", f"%{search}%"]

	records = frappe.get_all(
		"Master Accounts",
		filters=filters,
		fields=["name", "account_name"],
		order_by="modified desc",
		page_length=limit,
	)

	return [{"value": r.name, "label": r.account_name} for r in records]


# ---------------------------------------------------------------------------
# Contact APIs
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=True)
def get_contact_list(search=None, limit=10):
	"""Fetch contact list with optional search on contact_name."""
	if frappe.session.user == "Guest":
		frappe.throw(_("Please login to access this API"), frappe.PermissionError)

	limit = int(limit)
	filters = {}
	if search:
		filters["contact_name"] = ["like", f"%{search}%"]

	records = frappe.get_all(
		"Master Contacts",
		filters=filters,
		fields=["name", "contact_name"],
		order_by="modified desc",
		page_length=limit,
	)

	return [{"value": r.name, "label": r.contact_name} for r in records]


# ---------------------------------------------------------------------------
# Accounts by Contact
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=True)
def get_accounts_by_contact(contact=None):
	"""Fetch accounts linked to a given contact."""
	if frappe.session.user == "Guest":
		frappe.throw(_("Please login to access this API"), frappe.PermissionError)

	if not contact:
		frappe.throw(_("Contact is required"), frappe.ValidationError)

	contact_doc = frappe.get_value(
		"Master Contacts", contact, ["account", "account_name"], as_dict=True
	)

	if not contact_doc or not contact_doc.account:
		return []

	account = frappe.get_value(
		"Master Accounts",
		contact_doc.account,
		["name", "account_name", "account_code", "address", "district", "city", "state", "customer_type"],
		as_dict=True,
	)

	if not account:
		return []

	return [{"value": account.name, "label": account.account_name}]


# ---------------------------------------------------------------------------
# Save / Add APIs
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=True)
def save_account(account_name, address, account_code=None, district=None,
				 customer_type=None, city=None, state=None, custom_name=None):
	"""Create a new Master Account."""
	if frappe.session.user == "Guest":
		frappe.throw(_("Please login to access this API"), frappe.PermissionError)

	if not account_name or not address:
		frappe.throw(_("Account Name and Address are required"), frappe.ValidationError)

	doc = frappe.get_doc({
		"doctype": "Master Accounts",
		"account_name": account_name,
		"address": address,
		"account_code": account_code,
		"district": district,
		"customer_type": customer_type,
		"city": city,
		"state": state,
		"custom_name": custom_name,
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()

	return {"value": doc.name, "label": doc.account_name}


@frappe.whitelist(allow_guest=True)
def save_contact(contact_name, account=None, contact_code=None, custom_name=None):
	"""Create a new Master Contact."""
	if frappe.session.user == "Guest":
		frappe.throw(_("Please login to access this API"), frappe.PermissionError)

	if not contact_name:
		frappe.throw(_("Contact Name is required"), frappe.ValidationError)

	doc = frappe.get_doc({
		"doctype": "Master Contacts",
		"contact_name": contact_name,
		"account": account,
		"contact_code": contact_code,
		"custom_name": custom_name,
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()

	return {"value": doc.name, "label": doc.contact_name}


@frappe.whitelist(allow_guest=True)
def save_distributor(distributor_name, distributor_code=None, email=None,
					 billing_address=None, city=None, country=None):
	"""Create a new Master Distributor."""
	if frappe.session.user == "Guest":
		frappe.throw(_("Please login to access this API"), frappe.PermissionError)

	if not distributor_name:
		frappe.throw(_("Distributor Name is required"), frappe.ValidationError)

	doc = frappe.get_doc({
		"doctype": "Master Distributor",
		"distributor_name": distributor_name,
		"distributor_code": distributor_code,
		"email": email,
		"billing_address": billing_address,
		"city": city,
		"country": country,
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()

	return {"value": doc.name, "label": doc.distributor_name}
