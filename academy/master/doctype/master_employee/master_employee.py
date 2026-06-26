# Copyright (c) 2025, mats and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class MasterEmployee(Document):

    def validate(self):

        self.employee_name = " ".join(
            filter(None, [
                self.first_name,
                self.middle_name,
                self.last_name
            ])
        )


    def after_insert(self):

        self.create_user_if_not_exists()


    def on_update(self):

        if not self.linked_user:
            return

        self.sync_user_fields(self.linked_user)
        self.sync_user_roles(self.linked_user)



    def create_user_if_not_exists(self):

        if not self.email:
            frappe.throw("Company Email is required")


        existing_user = frappe.db.exists(
            "User",
            self.email
        )


        if existing_user:

            self.db_set(
                "linked_user",
                existing_user
            )

            self.sync_user_fields(existing_user)
            self.sync_user_roles(existing_user)

            return



        user = frappe.get_doc({

            "doctype": "User",
            "email": self.email,
            "username": self.linked_user or self.email,

            "first_name": self.first_name,
            "middle_name": self.middle_name,
            "last_name": self.last_name,

            "enabled": 1,
            "send_welcome_email": 0,
            "user_type": "System User"

        })


        user.insert(
            ignore_permissions=True
        )


        user.new_password = "Meril@123"


        user.save(
            ignore_permissions=True
        )


        self.db_set(
            "linked_user",
            user.name
        )

        self.sync_user_fields(user.name)
        self.sync_user_roles(user.name)




    def sync_user_fields(self, user_name):

        user = frappe.get_doc(
            "User",
            user_name
        )


        user.first_name = self.first_name
        user.middle_name = self.middle_name
        user.last_name = self.last_name
        user.save(
            ignore_permissions=True
        )




    def sync_user_roles(self, user_name):

        user = frappe.get_doc(
            "User",
            user_name
        )

        role_profile = None

        # Employee role field contains Role Profile
        if self.role:
            role_profile = self.role



        if role_profile and frappe.db.exists(
            "Role Profile",
            role_profile
        ):

            user.role_profile_name = role_profile


            user.save(
                ignore_permissions=True
            )