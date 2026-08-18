import frappe
import json

try:
    frappe.init(site='academy.localhost')
    frappe.connect()

    search_name = "test"
    or_filters = [
        ["Booking", "booking_id", "like", f"%{search_name}%"],
        ["Booking", "academy", "like", f"%{search_name}%"],
        ["Booking", "event_title", "like", f"%{search_name}%"],
        ["Booking", "full_name", "like", f"%{search_name}%"]
    ]

    data = frappe.get_list(
        "Booking",
        filters=[["Booking", "owner", "=", "Administrator"]],
        or_filters=or_filters,
        fields=["name", "booking_id", "academy", "event_title"],
        limit=1
    )
    print("Success! Data:", data)
except Exception as e:
    print("Error:", str(e))
