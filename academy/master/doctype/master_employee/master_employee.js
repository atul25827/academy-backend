// Copyright (c) 2025, mats and contributors
// For license information, please see license.txt

frappe.ui.form.on("Master Employee", {
	// state(frm) {
    //     frm.set_query('State List', function() {
    //         return {
    //             filters: {
    //                 country: frm.doc.country || ""
    //             }
    //         };
    //     });
    // },
    
    // Fetch the country when a state is selected
    state: function(frm) {
        if (frm.doc.state) {
            frappe.db.get_value('State List', frm.doc.state, 'country', function(data) {
                if (data && data.country) {
                    // console.log(data,"this is data")
                    frm.set_value('country', data.country);
                }
            });
        }
    }
});

