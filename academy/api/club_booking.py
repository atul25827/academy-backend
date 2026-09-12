import frappe
from frappe import _
from frappe.utils import getdate, nowdate
import json
from typing import Any

def generate_club_booking_id():
	"""
	Generates a sequential booking ID based on the current Fiscal Year.
	Format: CB-FY{YY}-{00001} (e.g., CB-FY25-00001)
	"""
	today = getdate(nowdate())
	year = today.year
	month = today.month
	
	# Financial year typically starts in April
	fy_year = year if month >= 4 else year - 1
	yy = str(fy_year)[-2:]
	prefix = f"CB-FY{yy}-"
	
	# Query the latest sequential ID efficiently
	last_booking_id = frappe.db.sql("""
		SELECT club_booking_id FROM `tabClub Booking`
		WHERE club_booking_id LIKE %s
		ORDER BY club_booking_id DESC
		LIMIT 1
	""", (prefix + "%",))
	
	next_num = 1
	if last_booking_id and last_booking_id[0][0]:
		last_id_str = last_booking_id[0][0]
		parts = last_id_str.split("-")
		
		# Extract sequence ID from format 'CB-FY25-00001'
		if len(parts) > 2 and parts[-1].isdigit():
			next_num = int(parts[-1]) + 1
		elif len(parts) > 1 and parts[-1].isdigit():
			next_num = int(parts[-1]) + 1

	return f"{prefix}{next_num:05d}"



def _send_booking_email(to, subject, message, doc, recipient_name, redirect_path=""):
	"""
	Helper method to send an email notification.
	"""
	if not to:
		return

	frontend_url = frappe.utils.get_url()
	doc_link = f"{frontend_url}{redirect_path}"
	
	html_content = frappe.render_template("""
<div style="font-family: Arial, sans-serif; font-size: 14px; color: #333;">
    
    <p>Hello {{ recipient_name }},</p>

    <p>{{ message }}</p>

    <hr style="margin: 16px 0;" />

    <h4>Booking Details</h4>
    <table cellpadding="6" cellspacing="0" border="0">
        <tr><td><b>Booking ID:</b></td><td>{{ doc.club_booking_id }}</td></tr>
        <tr><td><b>Guest Region:</b></td><td>{{ doc.guest_region }}</td></tr>
        <tr><td><b>Event Name:</b></td><td>{{ doc.event_name }}</td></tr>
        <tr><td><b>From Date:</b></td><td>{{ doc.from_date }}</td></tr>
        <tr><td><b>To Date:</b></td><td>{{ doc.to_date }}</td></tr>
        {% if doc.get('cancel_comment') %}
        <tr><td><b>Cancel Comment:</b></td><td>{{ doc.cancel_comment }}</td></tr>
        {% endif %}
    </table>

    <br/>

    <p>
        <a href="{{ doc_link }}" 
           style="background:#4f46e5;color:#fff;padding:8px 12px;text-decoration:none;border-radius:6px;">
           View Booking
        </a>
    </p>

    <br/>
    <p>Thanks,<br/>Academy Team</p>

</div>
	""", {
		"recipient_name": recipient_name,
		"message": message,
		"doc": doc,
		"doc_link": doc_link
	})
	
	frappe.sendmail(
		recipients=to,
		subject=subject,
		message=html_content,
		now=True
	)

def log_booking_action(booking_id, action, comment=None, remark=None, status=None):
	"""
	Helper to create a Booking Log entry.
	"""
	try:
		user = frappe.session.user
		
		roles = frappe.get_roles(user)
		user_role = "User"
		if "System Manager" in roles or "Academy Admin" in roles:
			user_role = "Admin" 
		elif "Academy User" in roles:
			user_role = "Requestor"
		
		try:
			owner = frappe.db.get_value("Club Booking", booking_id, "owner")
			if owner == user:
				user_role = "Requestor"
			
			if action in ["Approved", "Rejected", "Cancellation Approved", "Cancellation Rejected"]:
				user_role = "Admin"
		except:
			pass

		log = frappe.get_doc({
			"doctype": "Booking Log",
			"booking": booking_id,
			"action": action,
			"action_by": user,
			"user_role": user_role,
			"comment": comment,
			"remark": remark,
			"status": status or frappe.db.get_value("Club Booking", booking_id, "booking_status")
		})
		log.insert(ignore_permissions=True)

	except Exception as e:
		frappe.log_error(title="Club Booking Log Error", message=str(e))

def _parse_child_tables(data):
	"""
	Helper Method: Parses JSON strings for child tables.
	Often needed when the REST API payload sends deep objects as stringified JSON.
	Modifies the provided dictionary in-place.
	"""
	child_tables = ["food_and_catering", "stay", "approver", "cancel_approver"]
	for field in child_tables:
		if field in data and isinstance(data[field], str):
			try:
				data[field] = json.loads(data[field])
			except json.JSONDecodeError as e:
				frappe.log_error(
					message=f"JSON Decode Error for field {field}:\n{str(e)}", 
					title="Club Booking Payload Parse Error"
				)
				# Skipping the field prevents a harsh crash, but logging assures visibility.
				pass


def _get_or_create_booking(data):
	"""
	Helper Method: Retrieves an existing Club Booking or initializes a new one.
	Updates the document fields safely with the provided data but DOES NOT save it.
	
	Returns:
		tuple: (doc (Document instance), is_new_doc (bool))
	"""
	name = data.get("name") or data.get("club_booking_id")
	is_new_doc = False

	# Filter out metadata and restricted fields that shouldn't be directly updated by frontend
	exclude_fields = ["name", "doctype", "club_booking_id", "cmd", "approver", "cancel_approver"]
	clean_data = {k: v for k, v in data.items() if k not in exclude_fields}

	if name and frappe.db.exists("Club Booking", name):
		doc = frappe.get_doc("Club Booking", name)
		
		child_tables = ["food_and_catering", "stay"]
		for ct in child_tables:
			if ct in clean_data:
				ct_data = clean_data.pop(ct)
				# 1. Update existing rows or append new rows
				for row in ct_data:
					row_name = row.get("name")
					if row_name:
						# Existing row: find it and update
						existing_row = next((r for r in doc.get(ct) if r.name == row_name), None)
						if existing_row:
							existing_row.update(row)
					else:
						# New row: append it
						doc.append(ct, row)

		# Update the rest of the parent fields
		doc.update(clean_data)
	else:
		is_new_doc = True
		doc = frappe.new_doc("Club Booking")
		doc.update(clean_data)
		
		# Auto-assign an ID if missing inside a new request
		if not doc.club_booking_id:
			doc.club_booking_id = generate_club_booking_id()

	# Auto-sync: If a food_and_catering row has is_stay=1, mirror it into the stay table
	_sync_stay_from_food(doc)

	return doc, is_new_doc


def _sync_stay_from_food(doc):
	"""
	Helper Method: Automatically copies entries from 'food_and_catering' into 'stay'
	if they have 'is_stay' set to true. Prevents duplicates by checking guest names.
	"""
	stay_list = doc.get("stay") or []
	
	for food_item in doc.get("food_and_catering") or []:
		# Check if this item is marked for stay
		if food_item.is_stay or food_item.both_stay_and_food:
			guest_name = food_item.distributor_or_guest_name
			
			# Ensure we have a guest name before matching to prevent blank duplicate rows
			if not guest_name:
				continue
				
			# Check if there's already a stay item for this guest and check_in
			exists = False
			for stay_item in stay_list:
				if stay_item.distributor_or_guest_name == guest_name and stay_item.check_in_date == food_item.check_in_date:
					exists = True
					# Auto-update the checkout date and remark if modified in food
					stay_item.check_out_date = food_item.check_out_date
					stay_item.remark = food_item.remark
					break
			
			if not exists:
				# Append a new mirrored row to stay
				doc.append("stay", {
					"distributor_or_guest_name": guest_name,
					"designation": food_item.designation,
					"firm_or_hospital_name": food_item.firm_or_hospital_name,
					"repeat_guest": food_item.repeat_guest,
					"state": food_item.state,
					"country": food_item.country,
					"check_in_date": food_item.check_in_date,
					"check_out_date": food_item.check_out_date,
					"remark": food_item.remark,
					"is_stay": 1
				})


def _apply_approval_matrix(doc):
	"""
	Helper Method: Applies the "Academy Approval Matrix" rules to the Club Booking.
	Updates approvers list and statuses sequentially in-place.
	"""
	approval_matrix_name = frappe.db.get_value(
		"Club Approver Matrix",
		{"doctype_name": "Club Booking", "matrix_type": "Approve"},
		"name"
	)

	if not approval_matrix_name:
		frappe.throw(_("Approval matrix not found or set for 'Club Booking'."))

	approval_matrix = frappe.get_doc("Club Approver Matrix", approval_matrix_name)
	
	if not approval_matrix.approvers:
		frappe.throw(_("No approvers defined within the mapped Approval Matrix."))

	# Identify first approver for the status message
	first_approver = approval_matrix.approvers[0].approver_name
	first_approver_name = frappe.db.get_value("User", first_approver, "full_name") or first_approver
	
	doc.approval_status = f"Awaiting Approval from {first_approver_name}"
	doc.booking_status = "Submitted"
	doc.is_submitted = 1

	# Populate the 'approver' Child Table and initialize states
	doc.set("approver", [])
	
	for idx, approver in enumerate(approval_matrix.approvers):
		status = "Awaiting" if idx == 0 else "Pending"
		doc.append("approver", {
			"level": approver.level,
			"approver_name": approver.approver_name,
			"approver_status": status
		})


@frappe.whitelist()
def create_booking(**kwargs):
	"""
	[POST] Creates or updates a Club Booking, maintaining it in a 'Draft' state.
	"""
	try:
		data = frappe._dict(kwargs)
		_parse_child_tables(data)

		doc, is_new_doc = _get_or_create_booking(data)
		
		if is_new_doc:
			doc.booking_status = "Draft"
			doc.insert(ignore_permissions=True)
			action = "Created"
		else:
			doc.save(ignore_permissions=True)
			action = "Updated"
			
		return {
			"status": "success",
			"message": _("Booking {0} Successfully").format(action),
			"club_booking_id": doc.club_booking_id,
			"name": doc.name
		}

	except Exception as e:
		frappe.log_error(title="Club Booking Create API Error", message=frappe.get_traceback())
		frappe.local.response['http_status_code'] = 500
		return {
			"status": "error", 
			"message": _("Failed to save booking. Please contact administrator."), 
			"details": str(e)
		}

@frappe.whitelist()
def submit_booking(**kwargs):
	"""
	[POST] Creates or updates a Club Booking and immediately executes submission logic
	to generate the approval workflow cascade.
	"""
	try:
		data = frappe._dict(kwargs)
		_parse_child_tables(data)

		doc, is_new_doc = _get_or_create_booking(data)
		
		# Orchestrate the required approval workflows prior to saving
		_apply_approval_matrix(doc)

		# Commit final states to DB
		if is_new_doc:
			doc.insert(ignore_permissions=True)
		else:
			doc.save(ignore_permissions=True)
			
		log_booking_action(booking_id=doc.name, action="Submitted", status="Submitted")
		
		try:
			# To Requestor
			_send_booking_email(
				to=[doc.get("email") or doc.owner],
				subject="Booking Submitted",
				message="Your booking has been submitted successfully and is now awaiting approval.",
				doc=doc,
				recipient_name=doc.get("full_name") or frappe.utils.get_fullname(doc.owner),
				redirect_path="/club-booking-list"
			)
			# To First Approver
			if doc.get("approver") and len(doc.approver) > 0:
				first_approver_email = doc.approver[0].approver_name
				first_approver_fullname = frappe.db.get_value("User", first_approver_email, "full_name") or first_approver_email
				_send_booking_email(
					to=[first_approver_email],
					subject="Action Required: New Booking Approval",
					message="A new booking requires your approval. Please review the details below.",
					doc=doc,
					recipient_name=first_approver_fullname,
					redirect_path="/club-booking-list"
				)
		except Exception as e:
			frappe.log_error(title="Club Booking Submit Email Error", message=str(e))
        
		return {
			"status": "success",
			"message": _("Booking Submitted Successfully for Approval."),
			"club_booking_id": doc.club_booking_id,
			"name": doc.name
		}

	except frappe.ValidationError as ve:
		# Capture predictable validation issues (like missing approval matrix definitions)
		frappe.log_error(title="Club Booking Submit Validation Error", message=str(ve))
		frappe.local.response['http_status_code'] = 400
		return {
			"status": "error", 
			"message": str(ve.args[0] if ve.args else "")
		}

	except Exception as e:
		# Catch-all for unexpected crashes
		frappe.log_error(title="Club Booking Submit API Error", message=frappe.get_traceback())
		frappe.local.response['http_status_code'] = 500
		return {
			"status": "error", 
			"message": _("Failed to submit booking. Please contact administrator."), 
			"details": str(e)
		}

@frappe.whitelist()
def get_club_booking_details(club_booking_id):
	"""
	[GET] Retrieves the full details of a Club Booking, including all child tables.
	"""
	try:
		# Check if the booking exists
		if not frappe.db.exists("Club Booking", club_booking_id):
			frappe.local.response['http_status_code'] = 404
			return {
				"status": "error",
				"message": _("Booking {0} not found").format(club_booking_id)
			}

		# Get the full document which automatically includes all child tables
		doc = frappe.get_doc("Club Booking", club_booking_id)
		doc_dict = doc.as_dict()
		
		# Filter out deleted rows from stay and food child tables
		if doc_dict.get("stay"):
			doc_dict["stay"] = [row for row in doc_dict["stay"] if not row.get("is_deleted")]
			
		if doc_dict.get("food_and_catering"):
			doc_dict["food_and_catering"] = [row for row in doc_dict["food_and_catering"] if not row.get("is_deleted")]

		user = frappe.session.user

		# Check Approval Permission (Regular Approval)
		can_approve = False
		if doc.get("approver"):
			for row in doc.get("approver"):
				if row.approver_name == user and row.approver_status == "Awaiting":
					# Only allow regular approval if status is not Cancel Request (booking_status in Club Booking)
					if doc.booking_status != "Cancel Request": 
						can_approve = True
					break
		
		doc_dict["can_approve"] = can_approve
		
		return {
			"status": "success",
			"data": doc_dict
		}

	except frappe.PermissionError:
		frappe.local.response['http_status_code'] = 403
		return {
			"status": "error",
			"message": _("Not permitted")
		}
	except Exception as e:
		frappe.log_error(title="Club Booking Get Details API Error", message=frappe.get_traceback())
		frappe.local.response['http_status_code'] = 500
		return {
			"status": "error",
			"message": _("Failed to fetch booking details. Please contact administrator."),
			"details": str(e)
		}

@frappe.whitelist()
def delete_club_booking_item(name):
	"""
	[POST] Soft deletes a Club Booking child item (food_and_catering or stay) by setting is_deleted = 1.
	Based on the row's name.
	"""
	try:
		# Both food_and_catering and stay use the "Food and Stay Child" doctype
		if not frappe.db.exists("Food and Stay Child", name):
			frappe.local.response['http_status_code'] = 404
			return {
				"status": "error",
				"message": _("Item {0} not found").format(name)
			}
			
		# Set is_deleted to 1
		frappe.db.set_value("Food and Stay Child", name, "is_deleted", 1)
		
		# Optionally, you could also update the modified timestamp of the parent here if needed.
		
		return {
			"status": "success",
			"message": _("Item deleted successfully")
		}

	except frappe.PermissionError:
		frappe.local.response['http_status_code'] = 403
		return {
			"status": "error",
			"message": _("Not permitted")
		}
	except Exception as e:
		frappe.log_error(title="Club Booking Delete Item Error", message=frappe.get_traceback())
		frappe.local.response['http_status_code'] = 500
		return {
			"status": "error",
			"message": _("Failed to delete item. Please contact administrator."),
			"details": str(e)
		}

@frappe.whitelist()
def get_club_booking_list(page_number=1, page_length=10, status=None, search_name=None):
	"""
	[GET] Retrieves a paginated list of Club Bookings.
	Features flexible filtering and global search by 'club_booking_id' and 'event_name'.
	"""
	try:
		user = frappe.session.user
		
		# Validation
		page_number = int(page_number)
		page_length = int(page_length)
		start = (page_number - 1) * page_length

		# Base filters
		filters = [
			["Club Booking", "owner", "=", user]
		]

		if status and status != "all":
			filters.append(["Club Booking", "booking_status", "=", status])

		# Define the OR conditions for global search
		or_filters = []
		if search_name:
			# Search globally within club_booking_id OR event_name
			search_pattern = f"%{search_name}%"
			or_filters.append(["Club Booking", "club_booking_id", "like", search_pattern])
			or_filters.append(["Club Booking", "event_name", "like", search_pattern])

		# Fetch Data using ORM
		data = frappe.get_list(
			"Club Booking",
			filters=filters,
			or_filters=or_filters,
			fields=[
				"name", "club_booking_id", "event_name", "from_date", "to_date",
				"booking_status", "approval_status", "guest_region", "creation", "owner","is_submitted"
			],
			order_by="creation desc",
			start=start,
			page_length=page_length
		)

		# Function to get full name (optimization: all rows have same owner currently)
		user_full_name = frappe.utils.get_fullname(user)
		for row in data:
			row["full_name"] = user_full_name

		# Fetch Total Count using ORM (Wait: frappe.db.count natively supports filters but has limited support for complex or_filters directly.
		# A safer way to count when using complex filters is fetching the list length without pagination if count doesn't work out of the box, or using frappe.get_all with count parameter)
		# But frappe.db.count handles simple or_filters well in recent Frappe, let's use frappe.get_list with dict and pluck is safer.
		
		total_count_data = frappe.get_all(
			"Club Booking",
			filters=filters,
			or_filters=or_filters,
			pluck="name"
		)
		total_count = len(total_count_data)

		return {
			"data": data,
			"total_count": total_count,
			"page_length": page_length,
			"page_number": page_number,
			"total_pages": (total_count + page_length - 1) // page_length
		}

	except Exception as e:
		frappe.log_error(title="Club Booking List API Error", message=frappe.get_traceback())
		frappe.local.response['http_status_code'] = 500
		return {
			"error": "An error occurred while fetching the club booking list.",
			"details": str(e)
		}


@frappe.whitelist()
def get_user_club_booking_stats():
	"""
	Fetch club booking statistics for the current user.
	Uses checkbox fields: is_submitted, is_approved, is_rejected, is_cancelled.
	Returns:
		dict: {
			"total_bookings": int,
			"total_submitted": int,
			"total_approved": int,
			"total_pending": int,
			"total_rejected": int,
			"total_cancelled": int
		}
	"""
	try:
		user = frappe.session.user
		if user == "Guest":
			frappe.local.response['http_status_code'] = 401
			return {"message": "Unauthorized. Please login."}

		stats = frappe.db.sql("""
			SELECT
				COUNT(*) as total_bookings,
				SUM(CASE WHEN is_submitted = 1 THEN 1 ELSE 0 END) as total_submitted,
				SUM(CASE WHEN is_approved = 1 THEN 1 ELSE 0 END) as total_approved,
				SUM(CASE WHEN is_submitted = 1 AND is_approved = 0 AND is_rejected = 0 AND is_cancelled = 0 THEN 1 ELSE 0 END) as total_pending,
				SUM(CASE WHEN is_rejected = 1 THEN 1 ELSE 0 END) as total_rejected,
				SUM(CASE WHEN is_cancelled = 1 THEN 1 ELSE 0 END) as total_cancelled
			FROM `tabClub Booking`
			WHERE owner = %s
		""", (user,), as_dict=True)

		result = stats[0] if stats else {}

		return {
			"total_bookings": int(result.get("total_bookings") or 0),
			"total_submitted": int(result.get("total_submitted") or 0),
			"total_approved": int(result.get("total_approved") or 0),
			"total_pending": int(result.get("total_pending") or 0),
			"total_rejected": int(result.get("total_rejected") or 0),
			"total_cancelled": int(result.get("total_cancelled") or 0)
		}

	except Exception as e:
		frappe.log_error(title="Club Booking Stats Error", message=str(e))
		frappe.local.response['http_status_code'] = 500
		return {
			"error": "An error occurred while fetching club booking statistics.",
			"details": str(e)
		}

@frappe.whitelist()
def get_approver_club_stats():
	"""
	Fetch stats for a user acting as an Approver or Owner using Frappe ORM.
	1. Total Bookings: User is Owner OR User is in Approver list.
	2. Pending: User is Approver AND status is 'Awaiting' (Waiting for THIS user).
	3. Approved: User is Approver AND status is 'Approved' (Approved BY this user) OR overall approved.
	4. Rejected: User is Approver AND status is 'Rejected' (Rejected BY this user) OR overall rejected.
	5. Cancelled: parent is_cancelled=1 in the user's allowed list.
	"""
	try:
		user = frappe.session.user

		# 1. Total Bookings (Owner OR Approver)
		owner_bookings = frappe.get_all("Club Booking", filters={"owner": user, "docstatus": ["<", 2]}, pluck="name")

		# Approver child records for this user to track personal status
		approver_records = frappe.get_all(
			"Club Approver List Child",
			filters={"approver_name": user, "parenttype": "Club Booking"},
			fields=["parent", "approver_status"]
		)

		approver_bookings = [r.parent for r in approver_records]

		# Union of both sets to get "his listing"
		allowed_ids = set(owner_bookings + approver_bookings)

		if not allowed_ids:
			return {
				"total_bookings": 0,
				"total_submitted": 0,
				"total_approved": 0,
				"total_rejected": 0,
				"total_pending": 0,
				"total_cancelled": 0
			}

		# Filter to ensure we don't count any deleted/orphaned records
		valid_parents = frappe.get_all(
			"Club Booking",
			filters={"name": ["in", list(allowed_ids)], "docstatus": ["<", 2]},
			fields=["name", "is_approved", "is_rejected", "is_cancelled", "is_submitted"]
		)

		total_bookings_count = len(valid_parents)
		
		# Map the parent record to the specific user's approver status
		approver_map = {}
		for r in approver_records:
			approver_map[r.parent] = r.approver_status

		total_submitted: int = 0
		total_pending: int = 0
		total_approved: int = 0
		total_rejected: int = 0
		total_cancelled: int = 0

		for p in valid_parents:
			if p.is_submitted:
				total_submitted += 1
			if p.is_cancelled:
				total_cancelled += 1
				
			my_status = approver_map.get(p.name)

			# Pending: User is Approver AND status is 'Awaiting'
			if my_status == "Awaiting" and not p.is_cancelled:
				total_pending += 1
				
			# Approved: Approved from his side OR overall approved by someone else
			if my_status == "Approved" or p.is_approved:
				total_approved += 1

			# Rejected: Rejected from his side OR overall rejected by someone else
			if my_status == "Rejected" or p.is_rejected:
				total_rejected += 1

		return {
			"total_bookings": total_bookings_count,
			"total_submitted": total_submitted,
			"total_approved": total_approved,
			"total_rejected": total_rejected,
			"total_pending": total_pending,
			"total_cancelled": total_cancelled
		}

	except Exception as e:
		frappe.log_error(title="Club Approver Stats Error", message=str(e))
		frappe.local.response['http_status_code'] = 500
		return {"error": str(e)}

@frappe.whitelist()
def get_approver_club_booking_list(page_number=1, page_length=10, status=None, search_name=None):
	"""
	Fetch list of Club Bookings where current user is Owner OR Approver.
	Supported Filters: Status (via checkboxes), Search (club_booking_id / event_name).
	Status values: 'Approved', 'Rejected', 'Pending', 'Cancelled', 'Awaiting', 'Draft', 'all'.
	"""
	try:
		user = frappe.session.user
		page_number = int(page_number)
		page_length = int(page_length)
		start = (page_number - 1) * page_length

		# 1. Base Scope: Owner OR Approver
		owner_bookings = frappe.get_all("Club Booking", filters={"owner": user}, pluck="name")
		approver_bookings = frappe.get_all(
			"Club Approver List Child",
			filters={"approver_name": user, "parenttype": "Club Booking"},
			pluck="parent"
		)

		# Set of Club Booking Names visible to this user
		allowed_ids = set(owner_bookings + approver_bookings)

		if not allowed_ids:
			return {
				"data": [],
				"total_count": 0,
				"page_length": page_length,
				"page_number": page_number,
				"total_pages": 0
			}

		filters: list[Any] = []

		# 2. Status Filter (using checkbox fields)
		if status and status != "all":
			if status == "Approved":
				filters.append(["Club Booking", "is_approved", "=", 1])
			elif status == "Rejected":
				filters.append(["Club Booking", "is_rejected", "=", 1])
			elif status == "Cancelled":
				filters.append(["Club Booking", "is_cancelled", "=", 1])
			elif status == "Pending":
				# Submitted but not yet approved, rejected, or cancelled
				filters.append(["Club Booking", "is_submitted", "=", 1])
				filters.append(["Club Booking", "is_approved", "=", 0])
				filters.append(["Club Booking", "is_rejected", "=", 0])
				filters.append(["Club Booking", "is_cancelled", "=", 0])
			elif status == "Awaiting":
				# Special case: Filter bookings where THIS user has 'Awaiting' status
				awaiting_bookings = frappe.get_all(
					"Club Approver List Child",
					filters={
						"approver_name": user,
						"approver_status": "Awaiting",
						"parenttype": "Club Booking"
					},
					pluck="parent"
				)

				if not awaiting_bookings:
					return {
						"data": [], "total_count": 0, "page_length": page_length,
						"page_number": page_number, "total_pages": 0
					}
				filters.append(["Club Booking", "name", "in", awaiting_bookings])
			elif status == "Draft":
				filters.append(["Club Booking", "booking_status", "=", "Draft"])

		# 3. Search Filter
		or_filters = []
		if search_name:
			search_pattern = f"%{search_name}%"
			or_filters.append(["Club Booking", "club_booking_id", "like", search_pattern])
			or_filters.append(["Club Booking", "event_name", "like", search_pattern])

		# Apply the final list of allowed booking IDs
		filters.append(["Club Booking", "name", "in", list(allowed_ids)])

		# Fetch Data
		data = frappe.get_list(
			"Club Booking",
			filters=filters,
			or_filters=or_filters if or_filters else None,
			fields=[
				"name", "club_booking_id", "event_name", "from_date", "to_date",
				"booking_status", "approval_status", "guest_region",
				"is_submitted", "is_approved", "is_rejected", "is_cancelled",
				"creation", "owner"
			],
			order_by="creation desc",
			start=start,
			page_length=page_length
		)

		# Enrich Owner Name
		for row in data:
			row["full_name"] = frappe.utils.get_fullname(row["owner"])

		# Total Count
		total_count_data = frappe.get_all(
			"Club Booking",
			filters=filters,
			or_filters=or_filters if or_filters else None,
			pluck="name"
		)
		total_count = len(total_count_data)

		return {
			"data": data,
			"total_count": total_count,
			"page_length": page_length,
			"page_number": page_number,
			"total_pages": (total_count + page_length - 1) // page_length
		}

	except Exception as e:
		frappe.log_error(title="Club Approver Booking List Error", message=frappe.get_traceback())
		frappe.local.response['http_status_code'] = 500
		return {"error": str(e)}

@frappe.whitelist()
def update_club_booking_status(club_booking_id, action, remark=None):
	"""
	[POST] Approve or Reject a Club Booking.
	Args:
		club_booking_id (str): Name/ID of the Club Booking.
		action (str): 'Approve' or 'Reject'.
		remark (str, optional): Comments from the approver.
	"""
	try:
		user = frappe.session.user
		if user == "Guest":
			frappe.local.response['http_status_code'] = 401
			return {"status": "error", "message": _("Unauthorized. Please login.")}

		if not frappe.db.exists("Club Booking", club_booking_id):
			frappe.local.response['http_status_code'] = 404
			return {"status": "error", "message": _("Booking {0} not found").format(club_booking_id)}

		doc = frappe.get_doc("Club Booking", club_booking_id)

		# Validation: Only allow updates if the booking is submitted and not already finalized
		if not doc.is_submitted:
			return {"status": "error", "message": _("Booking is not yet submitted for approval.")}
		
		if doc.is_approved or doc.is_rejected or doc.is_cancelled:
			return {"status": "error", "message": _("This booking has already been finalized (Approved/Rejected/Cancelled).")}

		child_table = doc.get("approver")
		if not child_table:
			return {"status": "error", "message": _("No approvers found.")}

		found_approver = False
		current_index = -1

		# --- Find the current user in the correct child table ---
		for idx, row in enumerate(child_table):
			if row.approver_name == user and row.approver_status == 'Awaiting':
				found_approver = True
				current_index = idx
				
				# Update status & remark
				if action == "Approve":
					row.approver_status = "Approved"
				elif action == "Reject":
					row.approver_status = "Rejected"
				else:
					return {"status": "error", "message": "Invalid Action. Use 'Approve' or 'Reject'."}
				
				row.remark = remark
				row.action_date = frappe.utils.now()
				
				# Force saving child row directly to database to avoid caching/tracking issues
				frappe.db.set_value(row.doctype, row.name, {
					"approver_status": row.approver_status,
					"remark": remark,
					"action_date": row.action_date
				})
				break
		
		if not found_approver:
			frappe.local.response['http_status_code'] = 403
			return {"status": "error", "message": _("You are not authorized to approve/reject this request at this stage.")}

		current_approver_name = frappe.utils.get_fullname(user)

		# --- Handle Cascade Logic ---
		if action == "Approve":
			# check if there is a next approver in this specific table
			if current_index + 1 < len(child_table):
				# Next approver exists
				next_approver_row = child_table[current_index + 1]
				next_approver_row.approver_status = "Awaiting"
				
				# Force saving to db
				frappe.db.set_value(next_approver_row.doctype, next_approver_row.name, "approver_status", "Awaiting")
				
				next_name = frappe.utils.get_fullname(next_approver_row.approver_name)
				doc.approval_status = f"Awaiting Approval from {next_name}"
				
				try:
					_send_booking_email(
						to=[user],
						subject="Booking Approved",
						message="You have approved this booking. It has been forwarded to the next approver.",
						doc=doc,
						recipient_name=current_approver_name,
						redirect_path="/club-booking-list"
					)
					_send_booking_email(
						to=[next_approver_row.approver_name],
						subject="Action Required: Booking Approval",
						message="A booking requires your approval. Please review the details below.",
						doc=doc,
						recipient_name=next_name,
						redirect_path="/club-booking-list"
					)
				except Exception as e:
					frappe.log_error(title="Intermediate Approval Email Error", message=str(e))
					
			else:
				# --- Last approver approved ---
				doc.booking_status = "Approved"
				doc.is_approved = 1
				doc.approval_status = f"Approved By {current_approver_name}"
				
				try:
					_send_booking_email(
						to=[doc.get("email") or doc.owner],
						subject="Booking Approved Fully",
						message="Your booking has been fully approved.",
						doc=doc,
						recipient_name=doc.get("full_name") or frappe.utils.get_fullname(doc.owner),
						redirect_path="/club-booking-list"
					)
				except Exception as e:
					frappe.log_error(title="Final Approval Email Error", message=str(e))

		elif action == "Reject":
			# Booking Request Rejected
			doc.is_rejected = 1
			doc.booking_status = "Rejected"
			doc.approval_status = f"Rejected By {current_approver_name}"
			
			try:
				_send_booking_email(
					to=[doc.get("email") or doc.owner],
					subject="Booking Rejected",
					message=f"Your booking has been rejected by {current_approver_name}.",
					doc=doc,
					recipient_name=doc.get("full_name") or frappe.utils.get_fullname(doc.owner),
					redirect_path="/club-booking-list"
				)
			except Exception as e:
				frappe.log_error(title="Rejection Email Error", message=str(e))

		# Save the document with the updated statuses
		doc.save(ignore_permissions=True)
		frappe.db.commit()
		
		# Log action
		log_booking_action(booking_id=doc.name, action="Approved" if action == "Approve" else "Rejected", remark=remark, status=doc.booking_status)
		
		return {
			"status": "success",
			"message": _("Booking {0} successfully").format(action),
			"booking_status": doc.booking_status,
			"approval_status": doc.approval_status
		}

	except Exception as e:
		frappe.log_error(title="Update Club Booking Status Error", message=frappe.get_traceback())
		frappe.local.response['http_status_code'] = 500
		return {
			"status": "error", 
			"message": _("Failed to update booking status."), 
			"details": str(e)
		}
