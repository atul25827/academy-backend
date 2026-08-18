import os

file_path = r'academy\api\booking.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

target = '''\t\t\tlog_booking_action(
\t\t\t\tchild_doc.parent,
\t\t\t\t"Event Planning Deleted",
\t\t\t\tcomment=f"Deleted event planning: {event_planning_name}"
\t\t\t)'''

replacement = '''\t\t\tevent_date = child_doc.get("event_date")
\t\t\thall = child_doc.get("hall")
\t\t\tlog_booking_action(
\t\t\t\tchild_doc.parent,
\t\t\t\t"Event Planning Deleted",
\t\t\t\tcomment=f"Deleted event planning for date {event_date} for hall {hall}"
\t\t\t)'''

if target in content:
    content = content.replace(target, replacement)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replaced!")
else:
    print("Target not found.")
