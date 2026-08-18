import os

file_path = r'academy\academy\doctype\booking\booking.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

target = "\tdef set_event_dates(self):\n\t\tif self.get(\"event_planning\"):\n\t\t\tdates = [row.event_date for row in self.get(\"event_planning\") if row.event_date and not getattr(row, \"is_deleted\", 0) and not row.get(\"is_deleted\")]\n\t\t\tif dates:\n\t\t\t\tself.event_start_date = min(dates)\n\t\t\t\tself.event_end_date = max(dates)"

replacement = "\tdef set_event_dates(self):\n\t\tif self.get(\"event_planning\"):\n\t\t\tdates = [row.event_date for row in self.get(\"event_planning\") if row.event_date and not int(row.get(\"is_deleted\") or 0)]\n\t\t\tif dates:\n\t\t\t\tself.event_start_date = min(dates)\n\t\t\t\tself.event_end_date = max(dates)\n\t\t\telse:\n\t\t\t\tself.event_start_date = None\n\t\t\t\tself.event_end_date = None\n\t\telse:\n\t\t\tself.event_start_date = None\n\t\t\tself.event_end_date = None"

if target in content:
    content = content.replace(target, replacement)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replaced!")
else:
    print("Target not found.")

