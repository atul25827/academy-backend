def run():
    import frappe
    frappe.set_user("Administrator")
    
    # Method 1: len(get_all)
    count1 = len(frappe.get_all("Booking", filters={"owner": "Administrator"}, pluck="name"))
    
    # Method 2: count() aggregate
    count2 = frappe.get_all("Booking", filters={"owner": "Administrator"}, fields=["count(name) as count"])
    
    print("Method 1:", count1)
    print("Method 2:", count2)

