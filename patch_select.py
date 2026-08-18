import os

file_path = r'academy\api\booking.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

target = """def _check_hall_clash(hall, event_date, start_time, end_time, ignore_booking=None, ignore_event_planning=None):
\tquery = \"\"\"
\t\tSELECT c.parent, c.hall, c.event_date, c.event_start_time, c.event_end_time
\t\tFROM 	abEvent Planning Child c"""

replacement = """def _check_hall_clash(hall, event_date, start_time, end_time, ignore_booking=None, ignore_event_planning=None):
\tquery = \"\"\"
\t\tSELECT c.name, c.parent, c.hall, c.event_date, c.event_start_time, c.event_end_time
\t\tFROM 	abEvent Planning Child c"""

if target in content:
    content = content.replace(target, replacement)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replaced!")
else:
    print("Target not found.")

