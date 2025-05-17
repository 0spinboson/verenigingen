/* eslint-disable */
// rename this file from _test_[name] to test_[name] to activate
// and remove above this line

QUnit.module('Volunteer Team');

QUnit.test("test: Team Creation", function (assert) {
    let done = assert.async();

    // number of asserts
    assert.expect(3);

    frappe.run_serially([
        // Insert a new Volunteer Team
        () => frappe.tests.make('Volunteer Team', [
            // values to be set
            {team_name: 'Test JS Team'},
            {description: 'Team created for JS tests'},
            {team_type: 'Working Group'},
            {status: 'Active'},
            {start_date: frappe.datetime.get_today()}
        ]),
        () => {
            assert.equal(cur_frm.doc.team_name, 'Test JS Team', "Team name set correctly");
            assert.equal(cur_frm.doc.team_type, 'Working Group', "Team type set correctly");
            assert.equal(cur_frm.doc.status, 'Active', "Status set correctly");
        },
        () => done()
    ]);
});

QUnit.test("test: Team Members", function (assert) {
    let done = assert.async();
    
    // First we need a volunteer to add as team member
    let test_volunteer;

    // number of asserts
    assert.expect(2);

    frappe.run_serially([
        // Create a test volunteer first
        () => frappe.tests.make('Volunteer', [
            {volunteer_name: 'Team Test Volunteer'},
            {email: 'team.test@example.org'},
            {status: 'Active'}
        ]),
        (vol) => {
            test_volunteer = vol.name;
        },
        // Now create a team with this volunteer as member
        () => frappe.tests.make('Volunteer Team', [
            {team_name: 'Team Members Test'},
            {team_type: 'Committee'},
            {status: 'Active'},
            // Add team member
            {team_members: [
                [
                    {volunteer: test_volunteer},
                    {role_type: 'Team Leader'},
                    {role: 'Committee Chair'},
                    {from_date: frappe.datetime.get_today()},
                    {status: 'Active'}
                ]
            ]}
        ]),
        () => {
            assert.equal(cur_frm.doc.team_members.length, 1, "Team member added");
            assert.equal(
                cur_frm.doc.team_members[0].role, 
                'Committee Chair', 
                "Team member role set correctly"
            );
        },
        () => done()
    ]);
});

QUnit.test("test: Team Responsibilities", function (assert) {
    let done = assert.async();

    // number of asserts
    assert.expect(2);

    frappe.run_serially([
        // Create team with responsibilities
        () => frappe.tests.make('Volunteer Team', [
            {team_name: 'Responsibilities Test Team'},
            {team_type: 'Project Team'},
            {status: 'Active'},
            // Add responsibilities
            {key_responsibilities: [
                [
                    {responsibility: 'Test Task 1'},
                    {description: 'First test task description'},
                    {status: 'Pending'}
                ],
                [
                    {responsibility: 'Test Task 2'},
                    {description: 'Second test task description'},
                    {status: 'In Progress'}
                ]
            ]}
        ]),
        () => {
            assert.equal(cur_frm.doc.key_responsibilities.length, 2, "Two responsibilities added");
            
            // Check if both responsibilities are in the list
            let responsibilities = cur_frm.doc.key_responsibilities.map(r => r.responsibility);
            assert.ok(
                responsibilities.includes('Test Task 1') && responsibilities.includes('Test Task 2'),
                "Both responsibilities were added correctly"
            );
        },
        () => done()
    ]);
});
