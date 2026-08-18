import json
import frappe
frappe.init(site='academy.localhost')
frappe.connect()

rows = frappe.db.sql("SELECT name, parent, event_date, event_start_time, event_end_time FROM 	abEvent Planning Child WHERE parent = 'FY25-00020'", as_dict=True)
for row in rows:
    row['event_date'] = str(row['event_date'])
    row['event_start_time'] = str(row['event_start_time'])
    row['event_end_time'] = str(row['event_end_time'])
print(json.dumps(rows, indent=2))
