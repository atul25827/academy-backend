import frappe
from frappe import _
from frappe.utils import cint
from frappe.utils.password import check_password
from frappe.auth import LoginManager

@frappe.whitelist(allow_guest=True)
def login(usr, pwd):
    try:
        login_manager = LoginManager()
        login_manager.authenticate(user=usr, pwd=pwd)
        login_manager.post_login()
    except frappe.AuthenticationError:
        frappe.clear_messages()
        frappe.local.response["http_status_code"] = 401
        return {
            "success_key": 0,
            "message": "Authentication Failed. Invalid Username or Password.",
        }

    user = frappe.get_doc("User", frappe.session.user)
    
    # Determine Roles and Role Profile
    excluded_roles = ["All", "Guest", "Desk User"]
    user_roles = [r.role for r in user.roles if r.role not in excluded_roles]
    role_profile = user.role_profile_name
    
    # Fetch Employee Code
    employee_code = None
    try:
        employee = frappe.db.get_value("Master Employee", {"linked_user": user.name}, "employee_code")
        if employee:
            employee_code = employee
    except Exception:
        pass

    # Setting Cookies
    frappe.local.cookie_manager.set_cookie("user_id", user.name)
    frappe.local.cookie_manager.set_cookie("full_name", user.full_name)
    frappe.local.cookie_manager.set_cookie("sid", frappe.session.sid)
    
    # Remove default keys added by post_login
    if "home_page" in frappe.local.response:
        del frappe.local.response["home_page"]
    if "full_name" in frappe.local.response:
        del frappe.local.response["full_name"]

    return {
        "success_key": 1,
        "message": "Logged In Successfully",
        "sid": frappe.session.sid,
        "user_id": user.name,
        "role": user_roles,
        "role_profile": role_profile,
        "full_name": user.full_name,
    }

@frappe.whitelist(allow_guest=True)
def get_logged_user():
    # 1. Verify Session
    if frappe.session.user == 'Guest':
        frappe.local.response['http_status_code'] = 401
        return {
            "success_key": 0,
            "message": "Session expired or invalid. Please login again."
        }
    
    # 2. Fetch User Details
    user = frappe.get_doc("User", frappe.session.user)
    
    excluded_roles = ["All", "Guest", "Desk User"]
    roles = [role for role in frappe.get_roles(user.name) if role not in excluded_roles]
    role_profile = user.role_profile_name
        
    # 4. Fetch Employee Code
    employee_code = None
    if frappe.db.exists("Master Employee", {"linked_user": user.name}):
        employee_code = frappe.db.get_value("Master Employee", {"linked_user": user.name}, "employee_code")
    
    return {
        "success_key": 1,
        "user_id": user.name,
        "full_name": user.full_name,
        "email": user.email,
        "role": roles,
        "role_profile": role_profile,
        "employee_code": employee_code,
        "image": user.user_image
    }
