import frappe

def create_doctypes():
    # Help Support Contact (Child Table)
    if not frappe.db.exists("DocType", "Help Support Contact"):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "name": "Help Support Contact",
            "module": "club",
            "custom": 0,
            "istable": 1,
            "editable_grid": 1,
            "fields": [
                {
                    "fieldname": "department",
                    "label": "Department",
                    "fieldtype": "Select",
                    "options": "Club House\nIT",
                    "in_list_view": 1
                },
                {
                    "fieldname": "contact_type",
                    "label": "Contact Type",
                    "fieldtype": "Select",
                    "options": "Phone\nEmail",
                    "in_list_view": 1
                },
                {
                    "fieldname": "contact_value",
                    "label": "Contact Value",
                    "fieldtype": "Data",
                    "in_list_view": 1
                },
                {
                    "fieldname": "label",
                    "label": "Label",
                    "fieldtype": "Data",
                    "description": "Club Admin / IT Support"
                },
                {
                    "fieldname": "is_primary",
                    "label": "Is Primary",
                    "fieldtype": "Check",
                    "default": "1"
                },
                {
                    "fieldname": "enabled",
                    "label": "Enabled",
                    "fieldtype": "Check",
                    "default": "1"
                },
                {
                    "fieldname": "display_order",
                    "label": "Display Order",
                    "fieldtype": "Int"
                }
            ]
        })
        doc.insert()
        print("Created DocType: Help Support Contact")
    else:
        print("DocType 'Help Support Contact' already exists.")
        doc = frappe.get_doc("DocType", "Help Support Contact")

    # Help Support Settings (Single)
    if not frappe.db.exists("DocType", "Help Support Settings"):
        doc2 = frappe.get_doc({
            "doctype": "DocType",
            "name": "Help Support Settings",
            "module": "club",
            "custom": 0,
            "issingle": 1,
            "fields": [
                {
                    "fieldname": "enabled",
                    "label": "Enabled",
                    "fieldtype": "Check",
                    "default": "1"
                },
                {
                    "fieldname": "contacts",
                    "label": "Contacts",
                    "fieldtype": "Table",
                    "options": "Help Support Contact"
                }
            ]
        })
        doc2.insert()
        print("Created DocType: Help Support Settings")
    else:
        print("DocType 'Help Support Settings' already exists.")
        doc2 = frappe.get_doc("DocType", "Help Support Settings")
    
    frappe.db.commit()
    
    # Check if export works (frappe.modules.export_module_json usually expects developer mode)
    if getattr(frappe.conf, "developer_mode", 0):
        frappe.modules.export_module_json("DocType", "Help Support Contact", "club")
        frappe.modules.export_module_json("DocType", "Help Support Settings", "club")
        print("Exported JSONs to club module.")
