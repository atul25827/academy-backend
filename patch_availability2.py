import os

file_path = r'academy\api\booking.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

target = """def _check_hall_clash(hall, event_date, start_time, end_time, ignore_booking=None):
\tquery = \"\"\"
\t\tSELECT c.parent, c.hall, c.event_date, c.event_start_time, c.event_end_time
\t\tFROM 	abEvent Planning Child c
\t\tJOIN 	abBooking p ON c.parent = p.name
\t\tWHERE c.hall = %s AND c.event_date = %s
\t\tAND IFNULL(p.is_submitted, 1) = 1 
\t\tAND p.is_rejected = 0 
\t\tAND p.is_cancelled = 0
\t\tAND (
\t\t\tCAST(%s AS TIME) < c.event_end_time AND CAST(%s AS TIME) > c.event_start_time
\t\t)
\t\"\"\"
\tparams = [hall, event_date, start_time, end_time]
\t
\tif ignore_booking:
\t\tquery += " AND p.name != %s"
\t\tparams.append(ignore_booking)
\t\t
\treturn frappe.db.sql(query, tuple(params), as_dict=True)

@frappe.whitelist()
def check_hall_availability(hall, event_date, start_time, end_time, booking_id=None):
\t\"\"\"
\tAPI to check if a hall is available on a specific date and time.
\t\"\"\"
\tclashes = _check_hall_clash(hall, event_date, start_time, end_time, booking_id)"""

replacement = """def _check_hall_clash(hall, event_date, start_time, end_time, ignore_booking=None, ignore_event_planning=None):
\tquery = \"\"\"
\t\tSELECT c.parent, c.hall, c.event_date, c.event_start_time, c.event_end_time
\t\tFROM 	abEvent Planning Child c
\t\tJOIN 	abBooking p ON c.parent = p.name
\t\tWHERE c.hall = %s AND c.event_date = %s
\t\tAND IFNULL(p.is_submitted, 1) = 1 
\t\tAND p.is_rejected = 0 
\t\tAND p.is_cancelled = 0
\t\tAND IFNULL(c.is_deleted, 0) = 0
\t\tAND (
\t\t\tCAST(%s AS TIME) < c.event_end_time AND CAST(%s AS TIME) > c.event_start_time
\t\t)
\t\"\"\"
\tparams = [hall, event_date, start_time, end_time]
\t
\tif ignore_booking:
\t\tquery += " AND p.name != %s"
\t\tparams.append(ignore_booking)
\t\t
\tif ignore_event_planning:
\t\tquery += " AND c.name != %s"
\t\tparams.append(ignore_event_planning)
\t\t
\treturn frappe.db.sql(query, tuple(params), as_dict=True)

@frappe.whitelist()
def check_hall_availability(hall, event_date, start_time, end_time, booking_id=None, event_planning_name=None):
\t\"\"\"
\tAPI to check if a hall is available on a specific date and time.
\t\"\"\"
\tclashes = _check_hall_clash(hall, event_date, start_time, end_time, ignore_booking=booking_id, ignore_event_planning=event_planning_name)"""

if target in content:
    content = content.replace(target, replacement)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replaced!")
else:
    print("Target not found.")
