def run():
    import frappe
    frappe.set_user("Administrator")
    from academy.api.booking import get_approver_booking_list
    try:
        res = get_approver_booking_list(search_name="test")
        print("Success!", len(res.get('data', [])))
    except Exception as e:
        print("Error caught!", str(e))
