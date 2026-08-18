def run():
    import frappe
    frappe.set_user("Administrator")
    from academy.api.booking import get_approver_booking_list
    res = get_approver_booking_list(search_name="test")
    print("Response:", res)
