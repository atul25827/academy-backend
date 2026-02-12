# Copyright (c) 2026, Meril and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname

class HallMaster(Document):
    def autoname(self):
        prefix = f"{self.academy_name}-{self.hall_name}-"
        self.name = make_autoname(prefix + ".####")
