// Copyright (c) 2026, Meril and contributors
// For license information, please see license.txt

frappe.ui.form.on("Academy Approval Matrix", {
    refresh(frm) {
        frm.set_query("approver_name", "approvers", function () {
            return {
                filters: {
                    role_profile_name: "Academy Admin"
                }
            };
        });
    }
});
