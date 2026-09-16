import frappe
from frappe import _

@frappe.whitelist()
def get_help_support_settings(app_name=None):
    """
    API to fetch Help & Support Settings based on app_name.
    Path: /api/method/academy.api.support.get_help_support_settings
    """
    
    if not app_name:
        frappe.throw(_("app_name is required"))

    settings = frappe.get_doc("Help Support Settings")

    if not settings.enabled:
        return {
            "status": "error",
            "message": "Help Support Settings is disabled"
        }

    if settings.app_name != app_name:
        return {
            "status": "error",
            "message": f"Help Support Settings not found for app: {app_name}"
        }

    contacts = []
    for contact in settings.contacts:
        if contact.enabled:
            contacts.append({
                "department": contact.department,
                "contact_type": contact.contact_type,
                "contact_value": contact.contact_value,
                "label": contact.label,
                "is_primary": contact.is_primary,
                "display_order": contact.display_order
            })
            
    # Sort contacts by display_order
    contacts = sorted(contacts, key=lambda k: k['display_order'] or 0)

    return {
        "status": "success",
        "data": {
            "app_name": settings.app_name,
            "contacts": contacts
        }
    }

@frappe.whitelist()
def fetch_tutorial_videos():
    """
    API to fetch Tutorial Videos
    Path: /api/method/academy.api.support.fetch_tutorial_videos
    """
    try:
        doc = frappe.get_all(
            "Tutorial Videos",
            filters={"is_deleted": 0},
            fields=["title", "description", "video_attachment"]
        )
        
        for d in doc:
            if d.get("video_attachment"):
                d["video_attachment"] = frappe.utils.get_url(d["video_attachment"])

        return {
            "status": "success",
            "data": doc
        }
    except Exception as e:
        frappe.log_error(title="Fetch Tutorial Videos Error", message=frappe.get_traceback())
        frappe.local.response['http_status_code'] = 500
        return {
            "status": "error",
            "message": "Failed to fetch tutorial videos. Please try again later.",
            "error": str(e)
        }
