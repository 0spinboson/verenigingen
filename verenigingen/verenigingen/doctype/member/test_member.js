/* eslint-disable */
// rename this file from _test_[name] to test_[name] to activate
// and remove above this line

QUnit.test("test: Member", function (assert) {
	let done = assert.async();

	// number of asserts
	assert.expect(7);

	frappe.run_serially([
		// insert a new Member
		() => frappe.tests.make('Member', [
			// values to be set
			{first_name: 'Test'},
			{last_name: 'Member'},
			{email: 'test@example.com'},
			{mobile_no: '+31612345678'},
			{payment_method: 'Bank Transfer'}
		]),
		() => {
			assert.equal(cur_frm.doc.first_name, 'Test');
			assert.equal(cur_frm.doc.last_name, 'Member');
			assert.equal(cur_frm.doc.full_name, 'Test Member', "Full name should be automatically generated");
			assert.equal(cur_frm.doc.email, 'test@example.com');
		},
		// Test field updates
		() => frappe.tests.set_form_values(cur_frm, [
			{middle_name: 'Middle'}
		]),
		() => frappe.timeout(1),
		() => {
			assert.equal(cur_frm.doc.full_name, 'Test Middle Member', "Full name should be updated with middle name");
		},
		// Test payment method change
		() => frappe.tests.set_form_values(cur_frm, [
			{payment_method: 'Direct Debit'}
		]),
		() => frappe.timeout(1),
		() => {
			// Check if bank details section is visible
			let bankSection = $(cur_frm.fields_dict.bank_details_section.wrapper);
			assert.ok(bankSection.is(':visible'), "Bank details section should be visible for Direct Debit");
			
			// Check if IBAN field is required
			let ibanField = cur_frm.get_field('iban');
			assert.ok(ibanField.df.reqd, "IBAN should be required for Direct Debit");
		},
		() => done()
	]);
});

// Additional test for customer creation button
QUnit.test("test: Member - Customer Creation", function (assert) {
	let done = assert.async();

	// number of asserts
	assert.expect(2);

	frappe.run_serially([
		// insert a new Member
		() => frappe.tests.make('Member', [
			{first_name: 'Customer'},
			{last_name: 'Test'},
			{email: 'customer.test@example.com'}
		]),
		() => frappe.timeout(1),
		() => {
			// Check if Create Customer button exists
			let customerButton = cur_frm.page.inner_toolbar.find('.custom-actions button:contains("Create Customer")');
			assert.ok(customerButton.length, "Create Customer button should exist");
			
			// Since customer doesn't exist yet, customer field should be empty
			assert.ok(!cur_frm.doc.customer, "Customer field should be empty initially");
		},
		() => done()
	]);
});

// Test for volunteer section
QUnit.test("test: Member - Volunteer Section", function (assert) {
	let done = assert.async();

	// number of asserts
	assert.expect(2);

	frappe.run_serially([
		// insert a new Member
		() => frappe.tests.make('Member', [
			{first_name: 'Volunteer'},
			{last_name: 'Test'},
			{email: 'volunteer.test@example.com'}
		]),
		() => frappe.timeout(1),
		() => {
			// Check if Create Volunteer button exists
			let volunteerButton = cur_frm.page.inner_toolbar.find('.custom-actions button:contains("Create Volunteer")');
			assert.ok(volunteerButton.length, "Create Volunteer button should exist");
			
			// Check if volunteer details section exists
			let volunteerSection = $(cur_frm.fields_dict.volunteer_details_html.wrapper);
			assert.ok(volunteerSection.length, "Volunteer details section should exist");
		},
		() => done()
	]);
});
