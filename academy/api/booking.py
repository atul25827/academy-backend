import frappe
from frappe import _
from frappe.utils import getdate, nowdate
import random

@frappe.whitelist()
def create_booking(**kwargs):
	"""
	Create a new Booking.
	Generates a custom booking_id (FY{YY}-{Sequential 5 digits}).
	Accepts parameters matching the Booking DocType fields.
	"""
	try:
		# 1. Generate Custom Booking ID
		booking_id = generate_booking_id()

		# 2. Prepare Data
		# We use the kwargs passsed to the function.
		# Expected keys: academy, department, event_title, etc.
		
		data = kwargs.copy()
		data['doctype'] = 'Booking'
		data['booking_id'] = booking_id
		
		# Set Defaults
		data['is_submitted'] = 1
		data['event_status'] = 'Pending'
		
		# Ensure new fields are included if passed (explicitly listing valid fields is safer but kwargs.copy covers it)
		# Fields: merilian_code, full_name, email, contact_number, mats_request_number, mats_event
		
		# 3. Approver Logic
		academy = data.get('academy')
		if not academy:
			frappe.throw(_("Academy is required to fetch Approval Matrix"))

		# Fetch Approval Matrix
		# User specified field is now 'doctype_name' instead of 'link_foqr'
		# However, the field in DB is still 'link_foqr' according to JSON. 'doctype_name' is just the label.
		approval_matrix_name = frappe.db.get_value(
			"Academy Approval Matrix",
			{"academy": academy, "link_doc": "Booking"}, 
			"name"
		)

		if not approval_matrix_name:
			frappe.local.response['http_status_code'] = 404
			return {
				"message": _("Approval Matrix not found for Academy: {0}").format(academy)
			}

		approval_matrix = frappe.get_doc("Academy Approval Matrix", approval_matrix_name)
		
		if not approval_matrix.approvers:
			frappe.local.response['http_status_code'] = 404
			return {
				"message": _("No approvers defined in the Approval Matrix")
			}

		# Set Overall Status
		first_approver = approval_matrix.approvers[0].approver_name
		# Fetch the full name of the approver for the status message if needed, or just use the ID if that's what 'approver_name' stores (Likely User ID)
		first_approver_name = frappe.db.get_value("User", first_approver, "full_name") or first_approver
		data['overall_status'] = f"Awaiting Approval from {first_approver_name}"

		# Populate Approver Child Table
		# We need to construct the list of dicts for the child table
		approvers_list = []
		for idx, approver in enumerate(approval_matrix.approvers):
			status = "Awaiting" if idx == 0 else "Pending"
			approvers_list.append({
				"level": approver.level,
				"approver_name": approver.approver_name,
				"approver_status": status
			})
		
		data['approver'] = approvers_list

		# Handle child tables if they are passed as JSON strings (common in some API calls)
		# but if passed as list/dict from frappe.call/json, it works directly.
		# Ideally the client sends proper JSON.

		# 4. Create Document
		doc = frappe.get_doc(data)
		doc.insert(ignore_permissions=True) # or False depending on need. Using True for now to strict API control.

		return {
			"message": "Booking Created Successfully",
			"name": doc.name,
			"booking_id": doc.booking_id
		}

	except Exception as e:
		frappe.log_error(title="Create Booking Error", message=str(e))
		frappe.local.response['http_status_code'] = 500
		return {
			"error": str(e)
		}

def generate_booking_id():
	"""
	Generates a sequential booking ID based on the current Fiscal Year.
	Format: FY{YY}-{00001} (e.g., FY25-00001)
	"""
	today = getdate(nowdate())
	year = today.year
	month = today.month
	
	# Determine Fiscal Year (April to March)
	if month >= 4:
		fy_year = year
	else:
		fy_year = year - 1
		
	yy = str(fy_year)[-2:] # Last 2 digits
	prefix = f"FY{yy}-"
	
	# Find the last booking ID with this prefix
	# We query the DB for the max booking_id that matches the pattern 'FY{YY}-%'
	last_booking_id = frappe.db.sql("""
		SELECT booking_id FROM `tabBooking`
		WHERE booking_id LIKE %s
		ORDER BY booking_id DESC
		LIMIT 1
	""", (prefix + "%",))
	
	if last_booking_id and last_booking_id[0][0]:
		# Extract the number part
		last_id_str = last_booking_id[0][0]
		# Assuming format FYXX-XXXXX, split by '-' and take the last part
		parts = last_id_str.split("-")
		if len(parts) > 1 and parts[-1].isdigit():
			last_num = int(parts[-1])
			next_num = last_num + 1
		else:
			# Fallback if format is weird
			next_num = 1
	else:
		next_num = 1
		
	# Format with zero padding to 5 digits
	booking_id = f"{prefix}{next_num:05d}"
	
	return booking_id

@frappe.whitelist()
def get_user_booking_stats():
	"""
	Fetch booking statistics for the current user.
	Returns:
		dict: {
			"total_bookings": int,
			"total_approved": int,
			"total_pending": int,
			"total_rejected": int
		}
	"""
	try:
		user = frappe.session.user
		if user == "Guest":
			frappe.local.response['http_status_code'] = 401
			return {"message": "Unauthorized. Please login."}

		# count bookings based on status for the logged-in user
		stats = frappe.db.sql("""
			SELECT
				COUNT(*) as total_bookings,
				SUM(CASE WHEN is_approved = 1 OR event_status = 'Approved' THEN 1 ELSE 0 END) as total_approved,
				SUM(CASE WHEN event_status = 'Pending' THEN 1 ELSE 0 END) as total_pending,
				SUM(CASE WHEN event_status = 'Rejected' THEN 1 ELSE 0 END) as total_rejected
			FROM `tabBooking`
			WHERE owner = %s
		""", (user,), as_dict=True)

		result = stats[0] if stats else {}
		
		return {
			"total_bookings": int(result.get("total_bookings") or 0),
			"total_approved": int(result.get("total_approved") or 0),
			"total_pending": int(result.get("total_pending") or 0),
			"total_rejected": int(result.get("total_rejected") or 0)
		}

	except Exception as e:
		frappe.log_error(title="Booking Stats Error", message=str(e))
		frappe.local.response['http_status_code'] = 500
		return {
			"error": "An error occurred while fetching booking statistics.",
			"details": str(e)
		}

@frappe.whitelist()
def get_booking_list(page_number=1, page_length=20, academy=None, hall=None, status=None, search_name=None):
	"""
	Fetch list of bookings for the current user with pagination and filters using Frappe ORM.
	Args:
		page_number (int): Page number (default 1)
		page_length (int): Items per page (default 20)
		academy (str): Filter by Academy (optional)
		hall (str): Filter by Hall (optional)
		status (str): Filter by Event Status (optional)
		search_name (str): Search by Booking ID (optional)
	"""
	try:
		user = frappe.session.user
		
		# Validation
		page_number = int(page_number)
		page_length = int(page_length)
		start = (page_number - 1) * page_length

		# Base filters
		filters = [
			["Booking", "owner", "=", user]
		]

		if academy and academy != "all":
			filters.append(["Booking", "academy", "=", academy])

		if status and status != "all":
			filters.append(["Booking", "event_status", "=", status])

		if search_name:
			filters.append(["Booking", "booking_id", "like", f"%{search_name}%"])

		# Hall Filter (Child Table)
		# Optimized: We first find bookings that have this hall using get_all on the child table
		# This avoids a potentially expensive subquery in Python if not handled well, 
		# but is the standard ORM way to filter by child table.
		if hall and hall != "all":
			# Fetch parent booking names that have the specific hall
			booking_names_with_hall = frappe.get_all(
				"Event Planning Child", 
				filters={"hall": hall}, 
				pluck="parent",
				distinct=True
			)
			
			if not booking_names_with_hall:
				# If no bookings found for this hall, return empty immediately
				return {
					"data": [],
					"total_count": 0,
					"page_length": page_length,
					"page_number": page_number,
					"total_pages": 0
				}
			
			filters.append(["Booking", "name", "in", booking_names_with_hall])


		# Fetch Data using ORM
		data = frappe.get_list(
			"Booking",
			filters=filters,
			fields=[
				"name", "booking_id", "academy", "event_title", "event_status",
				"event_start_date", "event_end_date", "overall_status", "creation", "owner"
			],
			order_by="creation desc",
			start=start,
			page_length=page_length
		)

		# Function to get full name (optimization: all rows have same owner currently)
		user_full_name = frappe.utils.get_fullname(user)
		for row in data:
			row["owner"] = user_full_name


		# Fetch Total Count using ORM
		total_count = frappe.db.count("Booking", filters=filters)

		return {
			"data": data,
			"total_count": total_count,
			"page_length": page_length,
			"page_number": page_number,
			"total_pages": (total_count + page_length - 1) // page_length
		}

	except Exception as e:
		frappe.log_error(title="Booking List Error", message=str(e))
		frappe.local.response['http_status_code'] = 500
		return {
			"error": "An error occurred while fetching the booking list.",
			"details": str(e)
		}

@frappe.whitelist()
def get_booking_details(booking_id=None):
	"""
	Fetch full details of a booking by Booking ID.
	Includes all fields, flags, and child tables (e.g., event_planning).
	Accepts either booking_id (snake_case) or bookingId (camelCase).
	"""
	try:
		# Support both snake_case and camelCase argument
		bid = booking_id or frappe.form_dict.get("bookingId")
		if not bid:
			frappe.local.response['http_status_code'] = 400
			return {"message": "Booking ID is required."}

		if not frappe.db.exists("Booking", bid):
			frappe.local.response['http_status_code'] = 404
			return {"message": "Booking not found"}

		doc = frappe.get_doc("Booking", bid)
		
		# Ensure the user has permission to view this document
		user = frappe.session.user
		if user != "Administrator" and user != doc.owner:
			roles = frappe.get_roles(user)
			if "Academy Admin" not in roles and "System Manager" not in roles:
				frappe.local.response['http_status_code'] = 403
				return {"message": "You are not authorized to view this booking."}

		doc_dict = doc.as_dict()
		
		# Calculate can_approve flag
		# Logic: User is in the 'approver' child table AND their specific row status is 'Awaiting'
		can_approve = False
		if doc.approver:
			for approver_row in doc.approver:
				if approver_row.approver_name == user and approver_row.approver_status == "Awaiting":
					can_approve = True
					break
		
		doc_dict["can_approve"] = can_approve

		if "approver" in doc_dict:
			del doc_dict["approver"]

		return {
			"data": doc_dict
		}

	except Exception as e:
		frappe.log_error(title="Booking Details Error", message=str(e))
		frappe.local.response['http_status_code'] = 500
		return {
			"error": "An error occurred while fetching booking details.",
			"details": str(e)
		}

@frappe.whitelist(allow_guest=True)
def get_calendar_bookings(start_date=None, end_date=None, academy=None, hall=None):
	"""
	Fetch bookings for calendar view within a date range.
	"""
	try:
		if not start_date or not end_date:
			return []

		filters = [
			["event_start_date", "<=", end_date],
			["event_end_date", ">=", start_date]
		]

		if academy and academy != "all":
			filters.append(["academy", "=", academy])

		if hall and hall != "all":
			# Get bookings that have this hall in child table
			# Using get_all on child table is efficient for filtering parent
			booking_names = frappe.get_all(
				"Event Planning Child",
				filters={"hall": hall},
				pluck="parent",
				distinct=True
			)
			if not booking_names:
				return []
			filters.append(["name", "in", booking_names])

		bookings = frappe.get_all(
			"Booking",
			filters=filters,
			or_filters={
				"event_status": "Approved",
				"is_approved": 1
			},
			fields=[
				"name", 
				"event_title", 
				"event_start_date", 
				"event_end_date", 
				"event_status", 
				"academy", 
				"full_name", 
				"department"
			]
		)

		# Map fields to requested format
		result = []
		for b in bookings:
			result.append({
				"booking_id": b.name,
				"event_title": b.event_title,
				"event_start_date": b.event_start_date,
				"event_end_date": b.event_end_date,
				"status": b.event_status,
				"academy": b.academy,
				"full_name": b.full_name,
				"department": b.department
			})

		return result

	except Exception as e:
		frappe.log_error(title="Calendar Booking Error", message=str(e))
		return []

@frappe.whitelist()
def get_approver_stats():
	"""
	Fetch stats for a user acting as an Approver or Owner using Frappe ORM.
	1. Total Bookings: User is Owner OR User is in Approver list.
	2. Pending: User is Approver AND status is 'Awaiting' (Waiting for THIS user).
	3. Approved: User is Approver AND status is 'Approved' (Approved BY this user).
	4. Rejected: User is Approver AND status is 'Rejected' (Rejected BY this user).
	"""
	try:
		user = frappe.session.user
		
		# 1. Total Bookings (Owner OR Approver)
		# Fetch bookings where user is Owner
		owner_bookings = frappe.get_all("Booking", filters={"owner": user}, pluck="name")
		
		# Fetch bookings where user is Approver
		approver_bookings = frappe.get_all("Approver Child", filters={"approver_name": user}, pluck="parent")
		
		# Union of both sets
		total_bookings_count = len(set(owner_bookings + approver_bookings))

		# 2. Approved by User
		total_approved = frappe.db.count("Approver Child", filters={"approver_name": user, "approver_status": "Approved"})

		# 3. Rejected by User
		total_rejected = frappe.db.count("Approver Child", filters={"approver_name": user, "approver_status": "Rejected"})

		# 4. Pending (Awaiting Action from User)
		total_pending = frappe.db.count("Approver Child", filters={"approver_name": user, "approver_status": "Awaiting"})

		return {
			"total_bookings": total_bookings_count,
			"total_approved": total_approved,
			"total_rejected": total_rejected,
			"total_pending": total_pending
		}
	except Exception as e:
		frappe.log_error(title="Approver Stats Error", message=str(e))
		frappe.local.response['http_status_code'] = 500
		return {"error": str(e)}

@frappe.whitelist()
def get_approver_booking_list(page_number=1, page_length=10, status=None, search_name=None, academy=None, hall=None):
	"""
	Fetch list of bookings where current user is Owner OR Approver using Frappe ORM.
	Supported Filters: Status, Search (Booking ID), Academy, Hall.
	"""
	try:
		user = frappe.session.user
		page_number = int(page_number)
		page_length = int(page_length)
		start = (page_number - 1) * page_length

		# 1. Base Scope: Owner OR Approver
		owner_bookings = frappe.get_all("Booking", filters={"owner": user}, pluck="name")
		approver_bookings = frappe.get_all("Approver Child", filters={"approver_name": user}, pluck="parent")
		
		# Set of Booking Names visible to this user
		allowed_ids = set(owner_bookings + approver_bookings)

		if not allowed_ids:
			return {
				"data": [],
				"total_count": 0,
				"page_length": page_length,
				"page_number": page_number,
				"total_pages": 0
			}

		filters = []

		# 2. Academy Filter
		if academy and academy != "all":
			filters.append(["Booking", "academy", "=", academy])


		# 3. Status Filter
		if status and status != "all":
			if status == "Awaiting":
				# Special case: Filter bookings where THIS user has 'Awaiting' status in approver child table
				awaiting_bookings = frappe.get_all(
					"Approver Child", 
					filters={"approver_name": user, "approver_status": "Awaiting"}, 
					pluck="parent"
				)
				if not awaiting_bookings:
					return {
						"data": [], "total_count": 0, "page_length": page_length, 
						"page_number": page_number, "total_pages": 0
					}
				filters.append(["Booking", "name", "in", awaiting_bookings])
			else:
				# Standard status filter on the main Booking status
				filters.append(["Booking", "event_status", "=", status])

		# 4. Search Filter
		if search_name:
			filters.append(["Booking", "booking_id", "like", f"%{search_name}%"])

		# 5. Hall Filter (Child Table)
		if hall and hall != "all":
			# Get bookings that have this hall
			hall_bookings = frappe.get_all("Event Planning Child", filters={"hall": hall}, pluck="parent")
			
			if not hall_bookings:
				# If hall filter matches nothing, return empty
				return {
					"data": [],
					"total_count": 0,
					"page_length": page_length,
					"page_number": page_number,
					"total_pages": 0
				}
			
			# Intersect allowed IDs with Hall IDs to narrow down scope
			allowed_ids = allowed_ids.intersection(set(hall_bookings))
			
			if not allowed_ids:
				return {
					"data": [],
					"total_count": 0,
					"page_length": page_length,
					"page_number": page_number,
					"total_pages": 0
				}

		# Apply the final list of allowed booking IDs
		filters.append(["Booking", "name", "in", list(allowed_ids)])

		# Fetch Data
		data = frappe.get_list(
			"Booking",
			filters=filters,
			fields=[
				"name", "booking_id", "academy", "event_title", "event_status", 
				"event_start_date", "event_end_date", "overall_status", "creation", "owner"
			],
			order_by="creation desc",
			start=start,
			page_length=page_length
		)

		# Enrich Owner Name
		for row in data:
			row["full_name"] = frappe.utils.get_fullname(row["owner"])
		
		# Total Count
		total_count = frappe.db.count("Booking", filters=filters)

		return {
			"data": data,
			"total_count": total_count,
			"page_length": page_length,
			"page_number": page_number,
			"total_pages": (total_count + page_length - 1) // page_length
		}

	except Exception as e:
		frappe.log_error(title="Approver List Error", message=str(e))
		frappe.local.response['http_status_code'] = 500
		return {"error": str(e)}

@frappe.whitelist()
def update_booking_status(booking_id, action, remark=None):
	try:
		user = frappe.session.user
		if user == "Guest":
			frappe.local.response['http_status_code'] = 401
			return {"message": "Unauthorized"}

		if not frappe.db.exists("Booking", booking_id):
			frappe.local.response['http_status_code'] = 404
			return {"message": "Booking not found"}

		doc = frappe.get_doc("Booking", booking_id)

		found_approver = False
		current_index = -1

		# Find the current user in the approver list with status 'Awaiting'
		for idx, row in enumerate(doc.approver):
			# Parsing approver_name which is likely user ID.
			if row.approver_name == user and row.approver_status == 'Awaiting':
				found_approver = True
				current_index = idx
				
				# Update current approver row
				if action == "Approve":
					row.approver_status = "Approved"
				elif action == "Reject":
					row.approver_status = "Rejected"
				else:
					return {"message": "Invalid Action. Use 'Approve' or 'Reject'."}
				
				row.remark = remark
				break
		
		if not found_approver:
			frappe.local.response['http_status_code'] = 403
			return {"message": "You are not authorized to approve/reject this booking at this stage."}

		# Handle Cascade Logic
		if action == "Approve":
			# check if there is a next approver
			if current_index + 1 < len(doc.approver):
				# Next approver exists
				next_approver_row = doc.approver[current_index + 1]
				next_approver_row.approver_status = "Awaiting"
				
				# Get Full Name for nice message
				next_name = frappe.utils.get_fullname(next_approver_row.approver_name)
				doc.overall_status = f"Awaiting Approval from {next_name}"
			else:
				# Last approver approved
				doc.event_status = "Approved"
				doc.is_approved = 1
				approver_name = frappe.utils.get_fullname(user)
				doc.overall_status = f"Approved By {approver_name}"

		elif action == "Reject":
			# Rejected
			doc.event_status = "Rejected"
			doc.is_rejected = 1
			approver_name = frappe.utils.get_fullname(user)
			doc.overall_status = f"Rejected By {approver_name}"

		doc.save(ignore_permissions=True)
		
		return {
			"message": "Booking status updated successfully",
			"status": doc.event_status,
			"overall_status": doc.overall_status
		}

	except Exception as e:
		frappe.log_error(title="Update Booking Status Error", message=str(e))
		frappe.local.response['http_status_code'] = 500
		return {"error": str(e)}
