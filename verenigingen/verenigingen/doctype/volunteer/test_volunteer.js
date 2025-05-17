/* eslint-disable */
// rename this file from _test_[name] to test_[name] to activate
// and remove above this line

QUnit.module('Volunteer');

QUnit.test("test: Volunteer Creation", function (assert) {
    let done = assert.async();

    // number of asserts
    assert.expect(3);

    frappe.run_serially([
        // Insert a new Volunteer
        () => frappe.tests.make('Volunteer', [
            // values to be set
            {volunteer_name: 'Test Volunteer JS'},
            {email: 'test.volunteer.js@example.org'},
            {status: 'Active'},
            {start_date: frappe.datetime.get_today()},
            {commitment_level: 'Regular (Monthly)'},
            {experience_level: 'Intermediate'},
            {preferred_work_style: 'Hybrid'}
        ]),
        () => {
            assert.equal(cur_frm.doc.volunteer_name, 'Test Volunteer JS', "Volunteer name set correctly");
            assert.equal(cur_frm.doc.status, 'Active', "Status set correctly");
            assert.equal(cur_frm.doc.commitment_level, 'Regular (Monthly)', "Commitment level set correctly");
        },
        () => done()
    ]);
});

QUnit.test("test: Volunteer Skills", function (assert) {
    let done = assert.async();

    // number of asserts
    assert.expect(2);

    frappe.run_serially([
        // Insert a new Volunteer
        () => frappe.tests.make('Volunteer', [
            // values to be set
            {volunteer_name: 'Skills Test Volunteer'},
            {email: 'skills.test@example.org'},
            {status: 'Active'},
            // Add skills
            {skills_and_qualifications: [
                [
                    {skill_category: 'Technical'},
                    {volunteer_skill: 'Python Programming'},
                    {proficiency_level: '4 - Advanced'}
                ],
                [
                    {skill_category: 'Communication'},
                    {volunteer_skill: 'Public Speaking'},
                    {proficiency_level: '3 - Intermediate'}
                ]
            ]}
        ]),
        () => {
            assert.equal(cur_frm.doc.skills_and_qualifications.length, 2, "Two skills added");
            assert.equal(
                cur_frm.doc.skills_and_qualifications[0].volunteer_skill, 
                'Python Programming', 
                "Skill name set correctly"
            );
        },
        () => done()
    ]);
});

QUnit.test("test: Volunteer Assignments", function (assert) {
    let done = assert.async();

    // number of asserts
    assert.expect(3);

    frappe.run_serially([
        // Insert a new Volunteer
        () => frappe.tests.make('Volunteer', [
            // values to be set
            {volunteer_name: 'Assignment Test Volunteer'},
            {email: 'assignment.test@example.org'},
            {status: 'Active'},
            // Add an assignment
            {active_assignments: [
                [
                    {assignment_type: 'Team'},
                    {reference_doctype: 'Volunteer Team'},
                    {reference_name: 'Test Team'},
                    {role: 'Team Member'},
                    {start_date: frappe.datetime.get_today()},
                    {status: 'Active'}
                ]
            ]}
        ]),
        () => {
            assert.equal(cur_frm.doc.active_assignments.length, 1, "Assignment added");
            assert.equal(cur_frm.doc.active_assignments[0].role, 'Team Member', "Role set correctly");
            assert.equal(cur_frm.doc.active_assignments[0].status, 'Active', "Status set correctly");
        },
        () => done()
    ]);
});
