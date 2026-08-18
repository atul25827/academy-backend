import os

file_path = r'academy\api\booking.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update _check_hall_clash signature
sig_old = "def _check_hall_clash(hall, event_date, start_time, end_time, ignore_booking=None):"
sig_new = "def _check_hall_clash(hall, event_date, start_time, end_time, ignore_booking=None, ignore_event_planning=None):"
content = content.replace(sig_old, sig_new)

# 2. Update WHERE clause
where_old = """\t\tAND p.is_cancelled = 0
\t\tAND ("""
where_new = """\t\tAND p.is_cancelled = 0
\t\tAND IFNULL(c.is_deleted, 0) = 0
\t\tAND ("""
content = content.replace(where_old, where_new)

# 3. Add ignore_event_planning condition
ignore_booking_block = """\tif ignore_booking:
\t\tquery += " AND p.name != %s"
\t\tparams.append(ignore_booking)"""

ignore_event_planning_block = """\tif ignore_event_planning:
\t\tquery += " AND c.name != %s"
\t\tparams.append(ignore_event_planning)"""

if "ignore_event_planning:" not in content:
    content = content.replace(ignore_booking_block, ignore_booking_block + "\n\t\n" + ignore_event_planning_block)

# 4. Update check_hall_availability signature
av_sig_old = "def check_hall_availability(hall, event_date, start_time, end_time, booking_id=None):"
av_sig_new = "def check_hall_availability(hall, event_date, start_time, end_time, booking_id=None, event_planning_name=None):"
content = content.replace(av_sig_old, av_sig_new)

# 5. Update call inside check_hall_availability
call_old = "clashes = _check_hall_clash(hall, event_date, start_time, end_time, booking_id)"
call_new = "clashes = _check_hall_clash(hall, event_date, start_time, end_time, ignore_booking=booking_id, ignore_event_planning=event_planning_name)"
content = content.replace(call_old, call_new)

# Also try without booking_id in case my previous check was correct
call_old2 = "clashes = _check_hall_clash(hall, event_date, start_time, end_time)"
content = content.replace(call_old2, call_new)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Piecemeal replacement completed!")
