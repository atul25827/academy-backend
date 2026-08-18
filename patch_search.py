import os

file_path = r'academy\api\booking.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# PATCH get_booking_list
target1 = '''\t\tif search_name:
\t\t\tfilters.append(["Booking", "booking_id", "like", f"%{search_name}%"])'''

replacement1 = '''\t\tor_filters = []
\t\tif search_name:
\t\t\tor_filters = [
\t\t\t\t["Booking", "booking_id", "like", f"%{search_name}%"],
\t\t\t\t["Booking", "academy", "like", f"%{search_name}%"],
\t\t\t\t["Booking", "event_title", "like", f"%{search_name}%"],
\t\t\t\t["Booking", "full_name", "like", f"%{search_name}%"]
\t\t\t]'''

if target1 in content:
    content = content.replace(target1, replacement1)
    
target1_call = '''\t\tdata = frappe.get_list(
\t\t\t"Booking",
\t\t\tfilters=filters,
\t\t\tfields=['''
replacement1_call = '''\t\tdata = frappe.get_list(
\t\t\t"Booking",
\t\t\tfilters=filters,
\t\t\tor_filters=or_filters,
\t\t\tfields=['''

if target1_call in content:
    content = content.replace(target1_call, replacement1_call)

target1_count = '''\t\ttotal_count = frappe.db.count("Booking", filters=filters)'''
replacement1_count = '''\t\ttotal_count = frappe.db.count("Booking", filters=filters, or_filters=or_filters)'''

if target1_count in content:
    content = content.replace(target1_count, replacement1_count)

# PATCH get_approver_booking_list
target2 = '''\t\t# 4. Search Filter
\t\tif search_name:
\t\t\tfilters.append(["Booking", "booking_id", "like", f"%{search_name}%"])'''

replacement2 = '''\t\t# 4. Search Filter
\t\tor_filters = []
\t\tif search_name:
\t\t\tor_filters = [
\t\t\t\t["Booking", "booking_id", "like", f"%{search_name}%"],
\t\t\t\t["Booking", "academy", "like", f"%{search_name}%"],
\t\t\t\t["Booking", "event_title", "like", f"%{search_name}%"],
\t\t\t\t["Booking", "full_name", "like", f"%{search_name}%"]
\t\t\t]'''

if target2 in content:
    content = content.replace(target2, replacement2)

target2_call = '''\t\t# Fetch Data
\t\tdata = frappe.get_list(
\t\t\t"Booking",
\t\t\tfilters=filters,
\t\t\tfields=['''
replacement2_call = '''\t\t# Fetch Data
\t\tdata = frappe.get_list(
\t\t\t"Booking",
\t\t\tfilters=filters,
\t\t\tor_filters=or_filters,
\t\t\tfields=['''

if target2_call in content:
    content = content.replace(target2_call, replacement2_call)

target2_count = '''\t\t# Total Count
\t\ttotal_count = frappe.db.count("Booking", filters=filters)'''
replacement2_count = '''\t\t# Total Count
\t\ttotal_count = frappe.db.count("Booking", filters=filters, or_filters=or_filters)'''

if target2_count in content:
    content = content.replace(target2_count, replacement2_count)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Piecemeal replacement completed!")
