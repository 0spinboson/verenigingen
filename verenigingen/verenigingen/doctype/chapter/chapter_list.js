frappe.listview_settings['Chapter'] = {
	add_fields: ["chapter_head", "region", "postal_codes"],
	get_indicator: function(doc) {
		return [__(doc.published ? "Published" : "Draft"), 
			doc.published ? "green" : "orange", "published,=," + doc.published];
	}
};