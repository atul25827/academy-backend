import os

file_path = r'academy\api\booking.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

target = "\t\t# Count unique days in event_planning\n\t\tunique_days = set()\n\t\tfor row in doc.get(\"event_planning\", []):\n\t\t\tif row.event_date:\n\t\t\t\tunique_days.add(row.event_date)"

replacement = "\t\t# Filter out deleted event_planning rows\n\t\tif \"event_planning\" in doc_dict:\n\t\t\tdoc_dict[\"event_planning\"] = [row for row in doc_dict[\"event_planning\"] if not row.get(\"is_deleted\")]\n\n\t\t# Count unique days in event_planning\n\t\tunique_days = set()\n\t\tfor row in doc_dict.get(\"event_planning\", []):\n\t\t\tif row.get(\"event_date\"):\n\t\t\t\tunique_days.add(row.get(\"event_date\"))"

if target not in content:
    print('Target not found!')
else:
    content = content.replace(target, replacement)
    print('Target replaced.')

new_api = '''
@frappe.whitelist()
def delete_event_planning(event_planning_name):
\t"""
\tDelete (soft delete) an event planning row by setting is_deleted=1.
\t"""
\ttry:
\t\tif not frappe.db.exists("Event Planning Child", event_planning_name):
\t\t\tfrappe.local.response['http_status_code'] = 404
\t\t\treturn {"message": "Event planning not found"}
\t\t\t
\t\tchild_doc = frappe.get_doc("Event Planning Child", event_planning_name)
\t\tchild_doc.db_set("is_deleted", 1)
\t\t
\t\ttry:
\t\t\tlog_booking_action(
\t\t\t\tchild_doc.parent,
\t\t\t\t"Event Planning Deleted",
\t\t\t\tcomment=f"Deleted event planning: {event_planning_name}"
\t\t\t)
\t\texcept Exception:
\t\t\tpass
\t\t\t
\t\treturn {"message": "Event planning deleted successfully"}
\t\t
\texcept Exception as e:
\t\tfrappe.log_error(title="Delete Event Planning Error", message=str(e))
\t\tfrappe.local.response['http_status_code'] = 500
\t\treturn {"error": str(e)}
'''

if 'def delete_event_planning' not in content:
    content += new_api
    print('New API appended.')
else:
    print('New API already exists.')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
