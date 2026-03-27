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
			{"academy": academy, "link_doc": "Booking", "matrix_type": "Approve"}, 
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
		data['booking_status'] = "Booking Submitted"

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

		# Log Action
		# log_booking_action needs to be defined in scope or imported
		# Assuming it's in the same file now
		try:
			log_booking_action(doc.name, "Created", status="Pending", comment="Initial Request from Create Booking")
		except:
			pass

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

def log_booking_action(booking_id, action, comment=None, remark=None, status=None):
	"""
	Helper to create a Booking Log entry.
	"""
	try:
		user = frappe.session.user
		
		# Determine Role for this action
		# Simple heuristic: If Owner -> Requestor, if Admin -> Admin, if Approver -> Approver
		# But this is context sensitive. Let's just store the primary role of the user or a generic label.
		# Or pass it as an argument? Let's infer.
		
		# Fetch Booking just to check owner if needed, but logging should be fast.
		# Let's just use 'System Role' or specific if passed.
		# For now, let's fetch roles and pick the "highest" relevant one.
		roles = frappe.get_roles(user)
		user_role = "User"
		if "System Manager" in roles or "Academy Admin" in roles:
			user_role = "Admin" 
		elif "Academy User" in roles: # Assuming this role exists
			user_role = "Requestor"
		
		# Refine: If user is the owner of the booking
		try:
			owner = frappe.db.get_value("Booking", booking_id, "owner")
			if owner == user:
				user_role = "Requestor" # Override if owner
			
			# If action implies approval
			if action in ["Approved", "Rejected", "Cancellation Approved", "Cancellation Rejected"]:
				user_role = "Approver"
		except:
			pass

		log = frappe.metrics_counter = frappe.get_doc({
			"doctype": "Booking Log",
			"booking": booking_id,
			"action": action,
			"action_by": user,
			"user_role": user_role,
			"comment": comment,
			"remark": remark,
			"status": status or frappe.db.get_value("Booking", booking_id, "event_status")
		})
		log.insert(ignore_permissions=True)

	except Exception as e:
		frappe.log_error(title="Booking Log Error", message=str(e))

@frappe.whitelist()
def get_booking_audit_trail(booking_id):
	"""
	Fetch audit trail logs for a booking.
	"""
	try:
		if not frappe.db.exists("Booking", booking_id):
			return {"message": []}

		logs = frappe.get_all("Booking Log", 
			filters={"booking": booking_id},
			fields=["creation", "action", "action_by", "user_role", "comment", "status", "remark"],
			order_by="creation asc"
		)
		
		timeline = []
		for log in logs:
			full_name = frappe.utils.get_fullname(log.action_by)
			# Fetch Employee Code if needed, but Name is usually enough
			
			timeline.append({
				"timestamp": log.creation,
				"action": log.action,
				"user": full_name, # or f"{full_name} ({log.action_by})"
				"user_role": log.user_role,
				"comment": log.comment or log.remark, # Show whichever exists
				"status": log.status
			})
			
		return {"message": timeline}

	except Exception as e:
		frappe.log_error("Audit Trail Error", str(e))
		return {"message": []}

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
				SUM(CASE WHEN event_status = 'Rejected' THEN 1 ELSE 0 END) as total_rejected,
				SUM(CASE WHEN event_status = 'Cancelled' THEN 1 ELSE 0 END) as total_cancel
			FROM `tabBooking`
			WHERE owner = %s
		""", (user,), as_dict=True)

		result = stats[0] if stats else {}
		
		return {
			"total_bookings": int(result.get("total_bookings") or 0),
			"total_approved": int(result.get("total_approved") or 0),
			"total_pending": int(result.get("total_pending") or 0),
			"total_rejected": int(result.get("total_rejected") or 0),
			"total_cancel": int(result.get("total_cancel") or 0)
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

		if hall and hall != "all":
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
				"event_start_date", "event_end_date", "overall_status", "creation", "owner","booking_status"
			],
			order_by="creation desc",
			start=start,
			page_length=page_length
		)

		# Function to get full name (optimization: all rows have same owner currently)
		user_full_name = frappe.utils.get_fullname(user)
		for row in data:
			row["full_name"] = user_full_name


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
		
		# Fetch Vertical Name (Company Name)
		if doc.vertical:
			vertical_name = frappe.db.get_value("Master Company", doc.vertical, "company_name")
			doc_dict["vertical_name"] = vertical_name

		# Check Approval Permission (Regular Approval)
		can_approve = False
		if doc.approver:
			for approver_row in doc.approver:
				if approver_row.approver_name == user and approver_row.approver_status == "Awaiting":
					# Only allow regular approval if status is not Cancel Request
					if doc.event_status != "Cancel Request": 
						can_approve = True
					break
		
		doc_dict["can_approve"] = can_approve

		# Check Cancel Approval Permission
		can_cancel = False
		if doc.cancel_request and doc.cancel_approver:
			for approver_row in doc.cancel_approver:
				if approver_row.approver_name == user and approver_row.approver_status == "Awaiting":
					can_cancel = True
					break
		
		doc_dict["can_cancel"] = can_cancel

		# Attendance fields
		doc_dict["attendance_submitted"] = doc.attendence_submitted or 0
		doc_dict["attendance_files"] = [
			{"file_name": row.file.rsplit("/", 1)[-1] if row.file else "", "file_url": row.file}
			for row in (doc.attendence_attachment or [])
			if not row.is_deleted and row.file
		]

		# Can submit attendance: owner + approved + not cancelled + event ended + not already submitted
		can_submit = (
			user == doc.owner
			and doc.is_approved
			and not doc.is_cancelled
			and not doc.attendence_submitted
			and doc.event_end_date
			and getdate(doc.event_end_date) < getdate(nowdate())
		)
		doc_dict["can_submit_attendence"] = bool(can_submit)

		# Is cancellable: approved + not cancelled + no cancel request + event not started
		is_cancellable = (
			not doc.is_cancelled
			and not doc.cancel_request
			and doc.event_status == "Approved"
			and doc.event_start_date
			and getdate(doc.event_start_date) > getdate(nowdate())
		)
		doc_dict["is_cancellable"] = bool(is_cancellable)

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

@frappe.whitelist(allow_guest=True)
def get_upcoming_bookings():
	"""
	Fetch the latest 3 upcoming approved bookings.
	Returns bookings where event_start_date >= today, ordered by start date ascending.
	"""
	try:
		today = frappe.utils.nowdate()
		
		filters = [
			["event_start_date", ">=", today]
		]
		
		# Only approved bookings
		or_filters = {
			"event_status": "Approved",
			"is_approved": 1
		}

		bookings = frappe.get_all(
			"Booking",
			filters=filters,
			or_filters=or_filters,
			fields=[
				"name", "booking_id", "event_title", "event_start_date", "event_end_date", 
				"event_status", "academy", "full_name","no_of_participants"
			],
			order_by="event_start_date asc",
			limit=3
		)
		
		return bookings

	except Exception as e:
		frappe.log_error(title="Upcoming Bookings Error", message=str(e))
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
		allowed_ids = set(owner_bookings + approver_bookings)

		if not allowed_ids:
			return {
				"total_bookings": 0,
				"total_approved": 0,
				"total_rejected": 0,
				"total_pending": 0,
				"total_cancel": 0
			}

		allowed_list = list(allowed_ids)
		total_bookings_count = len(allowed_list)

		# 2. Approved
		total_approved = frappe.db.count("Booking", filters={"name": ["in", allowed_list], "event_status": "Approved"})

		# 3. Rejected
		total_rejected = frappe.db.count("Booking", filters={"name": ["in", allowed_list], "event_status": "Rejected"})

		# 4. Pending (Includes 'Pending', 'Submitted', 'Awaiting')
		total_pending = frappe.db.count("Booking", filters={"name": ["in", allowed_list], "event_status": ["in", ["Pending", "Submitted", "Awaiting", "Cancel Request"]]})

		# 5. Cancelled
		total_cancelled = frappe.db.count("Booking", filters={"name": ["in", allowed_list], "event_status": "Cancelled"})

		return {
			"total_bookings": total_bookings_count,
			"total_approved": total_approved, # Bookings that are fully approved
			"total_rejected": total_rejected, # Bookings that are fully rejected
			"total_pending": total_pending,   # Bookings In Progress
			"total_cancel": total_cancelled   # Bookings Cancelled
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
				# Special case: Filter bookings where THIS user has 'Awaiting' status in approver child table or cancel_approver table
				
				# 1. Regular Approvals
				awaiting_approval = frappe.get_all(
					"Approver Child", 
					filters={"approver_name": user, "approver_status": "Awaiting"}, 
					pluck="parent"
				)

				# 2. Cancel Approvals
				awaiting_cancellation = frappe.get_all(
					"Approver Child",
					filters={"approver_name": user, "approver_status": "Awaiting"},
					pluck="parent",
					distinct=True
				)
				
				awaiting_bookings = awaiting_approval

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
def update_booking_status(booking_id, action, remark=None, request_type="booking"):
	"""
	Approve or Reject a Booking OR a Cancellation Request.
	
	Args:
		booking_id (str): Name of the Booking.
		action (str): 'Approve' or 'Reject'.
		remark (str, optional): Comments.
		request_type (str, optional): 'booking' (default) or 'cancel_request'.
	"""
	try:
		user = frappe.session.user
		if user == "Guest":
			frappe.local.response['http_status_code'] = 401
			return {"message": "Unauthorized"}

		if not frappe.db.exists("Booking", booking_id):
			frappe.local.response['http_status_code'] = 404
			return {"message": "Booking not found"}

		doc = frappe.get_doc("Booking", booking_id)

		# --- Determine which workflow to use ---
		if request_type == "cancel_request":
			table_field = "cancel_approver"
			# For cancellation, ensure we are actually in a Cancel Request state
			if not doc.cancel_request:
				return {"message": "Booking is not in 'Cancel Request' status."}
		else:
			table_field = "approver"
			if doc.cancel_request:
				return {"message": "Booking is pending cancellation approval. Please use request_type='cancel_request'."}

		child_table = getattr(doc, table_field)
		if not child_table:
			return {"message": f"No approvers found in {table_field}."}

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
					return {"message": "Invalid Action. Use 'Approve' or 'Reject'."}
				
				row.remark = remark
				break
		
		if not found_approver:
			frappe.local.response['http_status_code'] = 403
			return {"message": "You are not authorized to approve/reject this request at this stage."}

		current_approver_name = frappe.utils.get_fullname(user)

		# --- Handle Cascade Logic ---
		if action == "Approve":
			# check if there is a next approver in this specific table
			if current_index + 1 < len(child_table):
				# Next approver exists
				next_approver_row = child_table[current_index + 1]
				next_approver_row.approver_status = "Awaiting"
				
				next_name = frappe.utils.get_fullname(next_approver_row.approver_name)
				
				if request_type == "cancel_request":
					doc.overall_status = f"Awaiting Cancellation Approval from {next_name}"
				else:
					doc.overall_status = f"Awaiting Approval from {next_name}"
			else:
				# --- Last approver approved ---
				if request_type == "cancel_request":
					# Finalize Cancellation
					doc.event_status = "Cancelled"
					doc.booking_status = "Cancellation Approved"
					doc.cancel_request = 0
					doc.is_cancelled = 1
					doc.is_approved = 0  # No longer considered 'Approved' since it's cancelled
					doc.overall_status = f"Cancellation Approved By {current_approver_name}"
				else:
					# Finalize Booking Approval
					doc.event_status = "Approved"
					doc.booking_status = "Booking Approved"
					doc.is_approved = 1
					doc.overall_status = f"Approved By {current_approver_name}"

		elif action == "Reject":
			# Rejected Logic
			if request_type == "cancel_request":
				if doc.is_approved:
					doc.event_status = "Approved"
					doc.booking_status = "Cancellation Rejected"
					doc.cancel_request = 0
					doc.overall_status = f"Cancellation Rejected By {current_approver_name}"
				else:
					# If it wasn't approved yet? Rare case for cancellation.
					doc.event_status = "Pending"
					doc.booking_status = "Cancellation Rejected"
					doc.overall_status = f"Cancellation Rejected By {current_approver_name}"
			else:
				# Booking Request Rejected
				doc.event_status = "Rejected"
				doc.is_rejected = 1
				doc.booking_status = "Booking Rejected"
				doc.overall_status = f"Rejected By {current_approver_name}"


		doc.save(ignore_permissions=True)
		
		# Log Action
		try:
			action_label = "Approved" if action == "Approve" else "Rejected"
			if request_type == "cancel_request":
				action_label = f"Cancellation {action_label}"
			
			log_booking_action(
				booking_id, 
				action_label, 
				status=doc.event_status, 
				comment=remark,
				remark=doc.overall_status # Log the overall status change in remark
			)
		except:
			pass

		return {
			"message": "Status updated successfully",
			"status": doc.event_status,
			"overall_status": doc.overall_status
		}

	except Exception as e:
		frappe.log_error(title="Update Booking Status Error", message=str(e))
		frappe.local.response['http_status_code'] = 500
		return {"error": str(e)}

@frappe.whitelist()
def get_booking_export(academy=None, hall=None, status=None, search_name=None):
	"""
	Export bookings with logic based on User Role:
	- Academy Admin / System Manager: Filter by Owner OR Approver (Approver Logic)
	- Others: Filter by Owner (User Logic)
	- Includes Event Planning child table data.
	"""
	try:
		user = frappe.session.user
		roles = frappe.get_roles(user)
		
		filters = []
		allowed_ids = None # If set, we filter by name IN allowed_ids. If None, we filter by owner=user.

		# 1. Determine Scope based on Role
		if "Academy Admin" in roles or "System Manager" in roles:
			# --- Approver Logic ---
			owner_bookings = frappe.get_all("Booking", filters={"owner": user}, pluck="name")
			approver_bookings = frappe.get_all("Approver Child", filters={"approver_name": user}, pluck="parent")
			allowed_ids = set(owner_bookings + approver_bookings)
			
			if not allowed_ids:
				return {"data": []}
		else:
			# --- Regular User Logic ---
			filters.append(["Booking", "owner", "=", user])


		# 2. Academy Filter
		if academy and academy != "all":
			filters.append(["Booking", "academy", "=", academy])

		# 3. Search Filter
		if search_name:
			filters.append(["Booking", "booking_id", "like", f"%{search_name}%"])

		# 4. Status Filter
		if status and status != "all":
			# Special "Awaiting" logic only applies if we are using Approver Logic (allowed_ids is set)
			if (allowed_ids is not None) and status == "Awaiting":
				awaiting_bookings = frappe.get_all(
					"Approver Child", 
					filters={"approver_name": user, "approver_status": "Awaiting"}, 
					pluck="parent"
				)
				if not awaiting_bookings:
					return {"data": []}
				
				# Intersect
				allowed_ids = allowed_ids.intersection(set(awaiting_bookings))
				if not allowed_ids:
					return {"data": []}
			else:
				# Standard status filter
				filters.append(["Booking", "event_status", "=", status])

		# 5. Hall Filter
		if hall and hall != "all":
			booking_names_with_hall = frappe.get_all(
				"Event Planning Child", 
				filters={"hall": hall}, 
				pluck="parent",
				distinct=True
			)
			
			if not booking_names_with_hall:
				return {"data": []}
			
			if allowed_ids is not None:
				allowed_ids = allowed_ids.intersection(set(booking_names_with_hall))
				if not allowed_ids:
					return {"data": []}
			else:
				filters.append(["Booking", "name", "in", booking_names_with_hall])

		# 6. Apply Final Allowed IDs (for Approver Logic)
		if allowed_ids is not None:
			filters.append(["Booking", "name", "in", list(allowed_ids)])

		# Fetch All Bookings matching filters 
		# Note: We fetch '*' to get all fields.
		data = frappe.get_all("Booking", filters=filters, fields=["*"], order_by="creation desc")

		if not data:
			return {"data": []}

		# ---------------------------------------------------------
		# Fetch Child Table Data (Event Planning) & Enrich
		# ---------------------------------------------------------
		booking_names = [d.name for d in data]
		
		event_planning_data = frappe.get_all(
			"Event Planning Child",
			filters={"parent": ["in", booking_names]},
			fields=["*"],
			order_by="idx asc"
		)
		
		# Helper to fetch Hall Names
		hall_ids = list(set([d.hall for d in event_planning_data if d.hall]))
		hall_map = {}
		if hall_ids:
			halls = frappe.get_all("Hall Master", filters={"name": ["in", hall_ids]}, fields=["name", "hall_name"])
			for h in halls:
				hall_map[h.name] = h.hall_name

		# Group child rows by parent and enrich
		from collections import defaultdict
		event_planning_map = defaultdict(list)
		for child in event_planning_data:
			# Enrich with Hall Name
			if child.hall and child.hall in hall_map:
				child["hall_name"] = hall_map[child.hall]
			
			event_planning_map[child.parent].append(child)
			
		# Attach child rows to parent data
		for row in data:
			row["event_planning"] = event_planning_map.get(row.name, [])
			
		return {"data": data}

	except Exception as e:
		frappe.log_error(title="Booking Export Error", message=str(e))
		frappe.local.response['http_status_code'] = 500
		return {"error": str(e)}

@frappe.whitelist()
def update_booking_event_planning(booking_id, event_planning_data, no_of_participants=None, no_of_participants_international=None):
	try:
		# 1. Permission Check
		user = frappe.session.user
		roles = frappe.get_roles(user)
		if "System Manager" not in roles and "Academy Admin" not in roles:
			frappe.local.response['http_status_code'] = 403
			return {"message": "Unauthorized. Only Admins can update event planning details."}

		if not frappe.db.exists("Booking", booking_id):
			frappe.local.response['http_status_code'] = 404
			return {"message": "Booking not found"}

		# 2. Parse Data
		import json
		if isinstance(event_planning_data, str):
			try:
				event_planning_data = json.loads(event_planning_data)
			except ValueError:
				frappe.throw(_("Invalid JSON format for event_planning_data"))

		doc = frappe.get_doc("Booking", booking_id)
		
		# Update Participant Counts if provided
		if no_of_participants is not None:
			doc.no_of_participants = no_of_participants
		
		if no_of_participants_international is not None:
			doc.no_of_participants_international = no_of_participants_international


		# Track changes for logging
		event_planning_changes = []

		# 3. Iterate and Update/Add
		for row_data in event_planning_data:
			row_name = row_data.get("name")
			
			if row_name:
				# --- UPDATE EXISTING ROW ---
				found = False
				for child in doc.event_planning:
					if child.name == row_name:
						# Log changes for this row
						changes = []
						if row_data.get("hall") and row_data.get("hall") != child.hall:
							old_hall = frappe.db.get_value("Hall Master", child.hall, "hall_name") or child.hall
							new_hall = frappe.db.get_value("Hall Master", row_data.get("hall"), "hall_name") or row_data.get("hall")
							changes.append(f"Hall changed from {old_hall} to {new_hall}")
						
						if row_data.get("booking_type") and row_data.get("booking_type") != child.booking_type:
							changes.append(f"Booking Type changed from {child.booking_type} to {row_data.get('booking_type')}")

						if row_data.get("event_end_time") and row_data.get("event_end_time") != child.event_end_time:
							changes.append(f"Event End Date changed from {child.event_end_time} to {row_data.get('event_end_time')}")

						if row_data.get("event_start_time") and row_data.get("event_start_time") != child.event_start_time:
							changes.append(f"Event Start Date changed from {child.event_start_time} to {row_data.get('event_start_time')}")	

						if changes:
							event_planning_changes.append(f"Row {child.idx}: {', '.join(changes)}")

						# Apply updates 
						child.hall = row_data.get("hall") or child.hall
						child.booking_type = row_data.get("booking_type") or child.booking_type
						child.event_start_time = row_data.get("event_start_time") or child.event_start_time
						child.event_end_time = row_data.get("event_end_time") or child.event_end_time

						found = True
						break
				if not found:
					# Edge case: row name provided but not found, treated as new
					h_name = frappe.db.get_value("Hall Master", row_data.get("hall"), "hall_name") or row_data.get("hall")
					event_planning_changes.append(f"Added new row for Hall: {h_name}")
					doc.append("event_planning", {
						"hall": row_data.get("hall"),
						"booking_type": row_data.get("booking_type"),
						"event_start_time": row_data.get("event_start_time"),
						"event_end_time": row_data.get("event_end_time")
					})
			else:
				# --- ADD NEW ROW ---
				h_name = frappe.db.get_value("Hall Master", row_data.get("hall"), "hall_name") or row_data.get("hall")
				event_planning_changes.append(f"Added new row for Hall: {h_name}")
				doc.append("event_planning", {
					"hall": row_data.get("hall"),
					"booking_type": row_data.get("booking_type"),
					"event_start_time": row_data.get("event_start_time"),
					"event_end_time": row_data.get("event_end_time")
				})


		doc.save(ignore_permissions=True)
		
		try:
			details = []
			if no_of_participants is not None:
				details.append(f"No. of Participants updated to {no_of_participants}")
			if no_of_participants_international is not None:
				details.append(f"No. of International Participants updated to {no_of_participants_international}")
			
			if event_planning_changes:
				details.extend(event_planning_changes)
			
			log_comment = "Updated Event Planning details."
			if details:
				log_comment = "\n".join(details)
				
			log_booking_action(booking_id, "Plan Updated", comment=log_comment, remark="Updated by Admin")
		except:
			pass

		return {
			"message": "Booking updated successfully.",
			"data": doc.event_planning
		}

	except Exception as e:
		frappe.log_error(title="Update Event Planning Error", message=str(e))
		frappe.local.response['http_status_code'] = 500
		return {"error": str(e)}

@frappe.whitelist()
def cancel_booking(booking_id, cancel_comment=None):
	"""
	Initiate a booking cancellation request.
	Fetches 'Cancel' type Approval Matrix and sets status to 'Cancel Request'.
	"""
	try:
		user = frappe.session.user
		
		if not frappe.db.exists("Booking", booking_id):
			frappe.local.response['http_status_code'] = 404
			return {"message": _("Booking not found")}

		doc = frappe.get_doc("Booking", booking_id)

		# Permission Check: Owner or Admin
		roles = frappe.get_roles(user)
		if doc.owner != user and "System Manager" not in roles and "Academy Admin" not in roles:
			frappe.local.response['http_status_code'] = 403
			return {"message": _("Not authorized to cancel this booking")}

		# Fetch Approval Matrix for Cancel
		approval_matrix_name = frappe.db.get_value(
			"Academy Approval Matrix",
			{"academy": doc.academy, "matrix_type": "Cancel"}, 
			"name"
		)

		if not approval_matrix_name:
			frappe.local.response['http_status_code'] = 404
			return {
				"message": _("No approvers defined in the Approval Matrix")
			}

		approval_matrix = frappe.get_doc("Academy Approval Matrix", approval_matrix_name)
		
		if not approval_matrix.approvers:
			frappe.local.response['http_status_code'] = 404
			return {
				"message": _("No approvers defined in the Approval Matrix")
			}

		# Clear & Populate Cancel Approver Table
		doc.set("cancel_approver", [])
		
		first_approver_name = None
		for idx, approver in enumerate(approval_matrix.approvers):
			status = "Awaiting" if idx == 0 else "Pending"
			if idx == 0:
				first_approver_name = approver.approver_name

			doc.append("cancel_approver", {
				"level": approver.level,
				"approver_name": approver.approver_name,
				"approver_status": status
			})
		
		# Update Status
		doc.event_status = "Cancel Request"
		doc.booking_status = "Cancellation Requested"
		doc.cancel_request = 1
		if cancel_comment:
			doc.cancel_comment = cancel_comment

		# Update Overall Status
		if first_approver_name:
			full_name = frappe.utils.get_fullname(first_approver_name)
			doc.overall_status = f"Awaiting Cancellation Approval from {full_name}"
		else:
			doc.overall_status = "Cancellation Request Approved"

		doc.save(ignore_permissions=True)
		
		try:
			log_booking_action(
				booking_id, 
				"Cancellation Requested", 
				comment=cancel_comment, 
				status="Cancel Request"
			)
		except:
			pass

		return {
			"message": "Cancellation request submitted successfully",
			"event_status": doc.event_status,
			"overall_status": doc.overall_status
		}

	except Exception as e:
		frappe.log_error(title="Cancel Booking Error", message=str(e))
		frappe.local.response['http_status_code'] = 500
		return {"error": str(e)}

@frappe.whitelist()
def upload_attendance(booking_id=None):
	"""
	POST: Upload attendance files for a booking and mark attendance as submitted.
	Accepts booking_id + multipart file uploads.
	"""
	try:
		bid = booking_id or frappe.form_dict.get("booking_id")
		if not bid:
			frappe.local.response['http_status_code'] = 400
			return {"message": "booking_id is required."}

		# Single DB hit to fetch all needed fields + permission check
		booking_meta = frappe.db.get_value(
			"Booking", bid,
			["name", "owner", "is_approved", "event_end_date", "attendence_submitted"],
			as_dict=True
		)

		if not booking_meta:
			frappe.local.response['http_status_code'] = 404
			return {"message": "Booking not found."}

		user = frappe.session.user

		# Permission: owner or admin
		# if user != "Administrator" and user != booking_meta.owner:
		# 	roles = frappe.get_roles(user)
		# 	if "Academy Admin" not in roles and "System Manager" not in roles:
		# 		frappe.local.response['http_status_code'] = 403
		# 		return {"message": "Not authorized to upload attendance for this booking."}

		# Guard: must be Approved
		if not booking_meta.is_approved:
			frappe.local.response['http_status_code'] = 400
			return {"message": "Attendance can only be uploaded for approved bookings."}

		# Guard: event must have ended
		if booking_meta.event_end_date and getdate(booking_meta.event_end_date) >= getdate(nowdate()):
			frappe.local.response['http_status_code'] = 400
			return {"message": "Attendance can only be uploaded after the event has ended."}

		# Guard: not already submitted
		if booking_meta.attendence_submitted:
			frappe.local.response['http_status_code'] = 400
			return {"message": "Attendance has already been submitted for this booking."}

		# Process uploaded files
		uploaded_files = frappe.request.files
		if not uploaded_files:
			frappe.local.response['http_status_code'] = 400
			return {"message": "No files uploaded. Please attach at least one file."}

		# Collect all files across all keys (handles same-key duplicates like files[])
		all_files = []
		for key in set(uploaded_files.keys()):
			all_files.extend(uploaded_files.getlist(key))

		doc = frappe.get_doc("Booking", bid)
		saved_files = []

		for filedata in all_files:
			content = filedata.read()
			filename = filedata.filename

			# Save via Frappe file manager
			file_doc = frappe.get_doc({
				"doctype": "File",
				"file_name": filename,
				"content": content,
				"attached_to_doctype": "Booking",
				"attached_to_name": bid,
				"is_private": 1
			})
			file_doc.save(ignore_permissions=True)

			# Append to the child table
			doc.append("attendence_attachment", {
				"file": file_doc.file_url
			})

			saved_files.append({
				"file_name": filename,
				"file_url": file_doc.file_url
			})

		# Mark attendance as submitted
		doc.attendence_submitted = 1
		doc.event_status = "Attendence Submitted"
		doc.save(ignore_permissions=True)

		# Log
		try:
			log_booking_action(
				bid,
				"Attendance Uploaded",
				comment=f"{len(saved_files)} file(s) uploaded",
				status=doc.event_status
			)
		except Exception:
			pass

		return {
			"message": "Attendance uploaded successfully.",
			"files": saved_files
		}

	except Exception as e:
		frappe.log_error(title="Upload Attendance Error", message=str(e))
		frappe.local.response['http_status_code'] = 500
		return {"error": str(e)}


@frappe.whitelist()
def check_pending_attendance():
	"""
	GET: Returns bookings owned by the current user where:
	  - event_end_date < today
	  - attendence_submitted = 0
	  - event_status = 'Approved'
	"""
	try:
		user = frappe.session.user
		if user == "Guest":
			frappe.local.response['http_status_code'] = 401
			return {"message": "Unauthorized. Please login."}

		today = nowdate()

		pending = frappe.get_all(
			"Booking",
			filters={
				"owner": user,
				"event_end_date": ["<", today],
				"attendence_submitted": 0,
				"is_approved": 1,
				"is_cancelled": 0
			},
			fields=[
				"name", "booking_id", "event_title", "academy",
				"event_start_date", "event_end_date", "event_status"
			],
			order_by="event_end_date desc"
		)

		return {"data": pending}

	except Exception as e:
		frappe.log_error(title="Check Pending Attendance Error", message=str(e))
		frappe.local.response['http_status_code'] = 500
		return {"error": str(e)}
