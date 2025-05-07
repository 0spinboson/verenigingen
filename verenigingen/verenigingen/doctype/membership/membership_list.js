frappe.listview_settings['Membership'] = {
	get_indicator: function(doc) {
		if (doc.status == 'New') {
			return [__('New'), 'blue', 'membership_status,=,New'];
		} else if (doc.status === 'Current') {
			return [__('Current'), 'green', 'membership_status,=,Current'];
		} else if (doc.status === 'Pending') {
			return [__('Pending'), 'yellow', 'membership_status,=,Pending'];
		} else if (doc.status === 'Expired') {
			return [__('Expired'), 'grey', 'membership_status,=,Expired'];
		} else {
			return [__('Cancelled'), 'red', 'membership_status,=,Cancelled'];
		}
	}
};
