import os

file_path = r'academy\api\booking.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# PATCH get_booking_list
target1_count = '''\t\ttotal_count = frappe.db.count("Booking", filters=filters, or_filters=or_filters)'''
replacement1_count = '''\t\ttotal_count = len(frappe.get_all("Booking", filters=filters, or_filters=or_filters, pluck="name"))'''

if target1_count in content:
    content = content.replace(target1_count, replacement1_count)
    print("Replaced target1_count")
else:
    print("Target1_count not found")

# PATCH get_approver_booking_list
target2_count = '''\t\t# Total Count
\t\ttotal_count = frappe.db.count("Booking", filters=filters, or_filters=or_filters)'''
replacement2_count = '''\t\t# Total Count
\t\ttotal_count = len(frappe.get_all("Booking", filters=filters, or_filters=or_filters, pluck="name"))'''

if target2_count in content:
    content = content.replace(target2_count, replacement2_count)
    print("Replaced target2_count")
else:
    print("Target2_count not found")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Piecemeal replacement completed!")
