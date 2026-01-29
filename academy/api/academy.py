import frappe

@frappe.whitelist(allow_guest=True)
def get_academies_with_halls():
    try:
        # Fetch all Academies
        academies = frappe.get_all("Academy Master", fields=["name", "academy_name", "attachment"])
        
        # Fetch all Halls
        halls = frappe.get_all("Hall Master", fields=["name", "hall_name", "academy_name", "capacity", "wifi", "screen", "remote_screen"])
        
        # Fetch all Attachments for Halls (Child Table)
        # The parent of the Attachment child table is the Hall Master name
        hall_names = [h.name for h in halls]
        attachments = []
        if hall_names:
            attachments = frappe.get_all("Attachment", 
                                         filters={"parent": ["in", hall_names]}, 
                                         fields=["parent", "file"])
        
        # Map Attachments to Halls
        hall_attachments_map = {}
        for att in attachments:
            if att.parent not in hall_attachments_map:
                hall_attachments_map[att.parent] = []
            hall_attachments_map[att.parent].append(att)
            
        # Map Halls to Academies
        academy_halls_map = {}
        for hall in halls:
            # Add attachments to hall
            hall["attachments"] = hall_attachments_map.get(hall.name, [])
            
            # Add hall to academy map
            if hall.academy_name not in academy_halls_map:
                academy_halls_map[hall.academy_name] = []
            academy_halls_map[hall.academy_name].append(hall)
            
        # Assemble final response
        for academy in academies:
            # Academy Master name is the academy_name (autoname: field:academy_name)
            academy["halls"] = academy_halls_map.get(academy.name, [])
            
        return {
            "success_key": 1,
            "message": "Data Fetched Successfully",
            "data": academies
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Academy Fetch Error")
        return {
            "success_key": 0,
            "message": str(e)
        }
