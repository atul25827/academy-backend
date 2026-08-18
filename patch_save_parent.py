import os

file_path = r'academy\api\booking.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

target = '''\t\tchild_doc = frappe.get_doc("Event Planning Child", event_planning_name)
\t\tchild_doc.db_set("is_deleted", 1)
\t\t
\t\ttry:'''

replacement = '''\t\tchild_doc = frappe.get_doc("Event Planning Child", event_planning_name)
\t\tchild_doc.db_set("is_deleted", 1)
\t\t
\t\t# Trigger parent save to update dates
\t\tparent_doc = frappe.get_doc("Booking", child_doc.parent)
\t\tparent_doc.save(ignore_permissions=True)
\t\t
\t\ttry:'''

if target in content:
    content = content.replace(target, replacement)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replaced!")
else:
    print("Target not found.")

