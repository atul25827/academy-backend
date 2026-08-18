import os

file_path = r'academy\api\booking.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

target = "SELECT c.parent, c.hall, c.event_date, c.event_start_time, c.event_end_time\n\t\tFROM 	abEvent Planning Child c"
replacement = "SELECT c.name, c.parent, c.hall, c.event_date, c.event_start_time, c.event_end_time\n\t\tFROM 	abEvent Planning Child c"

if target in content:
    content = content.replace(target, replacement)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replaced select clause!")
else:
    print("Target not found.")

