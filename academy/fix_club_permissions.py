import frappe

def fix_permissions():
    doctypes = ["Help Support Contact", "Help Support Settings"]
    
    for dt in doctypes:
        if frappe.db.exists("DocType", dt):
            doc = frappe.get_doc("DocType", dt)
            
            # Check if System Manager role exists in permissions
            has_system_manager = False
            for perm in doc.permissions:
                if perm.role == "System Manager":
                    has_system_manager = True
                    break
                    
            if not has_system_manager:
                doc.append("permissions", {
                    "role": "System Manager",
                    "read": 1,
                    "write": 1,
                    "create": 1,
                    "delete": 1,
                    "email": 1,
                    "print": 1,
                    "export": 1,
                    "report": 1,
                    "share": 1
                })
                doc.save()
                print(f"Added System Manager permission to {dt}")
        
    frappe.db.commit()
