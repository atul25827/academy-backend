import frappe

@frappe.whitelist()
def get_club_masters():
    """
    Fetch various masters for Club Bookings.
    This API is restricted to authenticated users (no allow_guest=True).
    """
    try:
        # Update the string names below if your actual DocType names differ slightly
        data = {
            "booking_for": frappe.get_all("Booking For", fields=["name"]),
            "food_preferences": frappe.get_all("Food Preferences", fields=["name"]),
            "meal_type": frappe.get_all("Meal Type", fields=["name"]),
            "service_type": frappe.get_all("Service Type", fields=["name"]),
        }
        return {
            "success_key": 1,
            "message": "Master Data Fetched Successfully",
            "data": data
        }
    except Exception as e:
        frappe.log_error(title="Club Master Data API Error", message=frappe.get_traceback())
        return {
            "success_key": 0,
            "message": f"Error fetching master data: {str(e)}"
        }

@frappe.whitelist()
def get_countries(search_name=None):
    """
    Initial 10 country load. If search_name is provided, it searches by name.
    """
    try:
        filters = {}
        if search_name:
            filters["name"] = ["like", f"%{search_name}%"]

        countries = frappe.get_all(
            "Country",
            filters=filters,
            fields=["name"],
            limit_page_length=10,
            order_by="name asc"
        )
        return {
            "success_key": 1,
            "data": countries
        }
    except Exception as e:
        frappe.log_error(title="Club Geo Countries API Error", message=frappe.get_traceback())
        return {
            "success_key": 0,
            "message": str(e)
        }

@frappe.whitelist()
def get_states(country):
    """
    Fetch states based on the selected country.
    """
    try:
        if not country:
            return {
                "success_key": 1,
                "data": []
            }
            
        states = frappe.get_all(
            "State List", # Change to your actual State/Province DocType name if different
            filters={"country": country},
            fields=["name"],
            order_by="name asc"
        )
        return {
            "success_key": 1,
            "data": states
        }
    except Exception as e:
        frappe.log_error(title="Club Geo States API Error", message=frappe.get_traceback())
        return {
            "success_key": 0,
            "message": str(e)
        }
