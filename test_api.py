import frappe
from frappe.auth import LoginManager

frappe.init(site='academy-site')
frappe.connect()

frappe.set_user("Administrator")

try:
    from academy.api.booking import get_approver_booking_list
    res = get_approver_booking_list(search_name="test")
    print("Response:", res)
except Exception as e:
    import traceback
    traceback.print_exc()
