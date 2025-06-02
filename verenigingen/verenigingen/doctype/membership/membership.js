/**
 * Debug version of membership application JavaScript
 * This will help identify the exact cause of the 500 error
 */

$(document).ready(function() {
    console.log('Debug membership application loaded');
    
    // Add debug buttons to the form
    if (!$('#debug-controls').length) {
        $('#membership-application-form').before(`
            <div id="debug-controls" class="alert alert-info">
                <h5>Debug Controls</h5>
                <button type="button" class="btn btn-sm btn-secondary" onclick="testBackendConnection()">Test Backend</button>
                <button type="button" class="btn btn-sm btn-secondary" onclick="testMemberFields()">Check Member Fields</button>
                <button type="button" class="btn btn-sm btn-secondary" onclick="testMinimalSubmission()">Test Minimal Submit</button>
                <button type="button" class="btn btn-sm btn-warning" onclick="debugCurrentFormData()">Debug Form Data</button>
            </div>
        `);
    }
    
    // Override the form submission to use debug method
    $('#membership-application-form').off('submit').on('submit', function(e) {
        e.preventDefault();
        submitApplicationDebug();
    });
});

// Test backend connection
window.testBackendConnection = async function() {
    console.log('Testing backend connection...');
    
    try {
        const result = await new Promise((resolve, reject) => {
            frappe.call({
                method: 'verenigingen.api.membership_application.test_connection',
                callback: function(r) {
                    console.log('Backend test result:', r);
                    resolve(r.message);
                },
                error: function(r) {
                    console.error('Backend test error:', r);
                    reject(r);
                }
            });
        });
        
        alert('Backend connection successful!\n' + JSON.stringify(result, null, 2));
    } catch (error) {
        alert('Backend connection failed!\n' + JSON.stringify(error, null, 2));
    }
};

// Test member fields
window.testMemberFields = async function() {
    console.log('Testing member fields...');
    
    try {
        const result = await new Promise((resolve, reject) => {
            frappe.call({
                method: 'verenigingen.api.membership_application.get_member_field_info',
                callback: function(r) {
                    console.log('Member fields result:', r);
                    resolve(r.message);
                },
                error: function(r) {
                    console.error('Member fields error:', r);
                    reject(r);
                }
            });
        });
        
        console.log('Available member fields:', result.fields);
        alert(`Member doctype has ${result.total_fields} fields. Check console for details.`);
    } catch (error) {
        alert('Member fields test failed!\n' + JSON.stringify(error, null, 2));
    }
};

// Test minimal submission
window.testMinimalSubmission = async function() {
    console.log('Testing minimal submission...');
    
    const testData = {
        first_name: 'Test',
        last_name: 'User',
        email: `test.${Date.now()}@example.com`,
        mobile_no: '0612345678',
        birth_date: '1990-01-01',
        additional_notes: 'Test submission from debug'
    };
    
    try {
        const result = await new Promise((resolve, reject) => {
            frappe.call({
                method: 'verenigingen.api.membership_application.submit_application_minimal',
                args: {
                    data: testData
                },
                callback: function(r) {
                    console.log('Minimal submission result:', r);
                    resolve(r.message);
                },
                error: function(r) {
                    console.error('Minimal submission error:', r);
                    reject(r);
                }
            });
        });
        
        if (result.success) {
            alert(`Minimal submission successful!\nMember ID: ${result.member_id}`);
        } else {
            alert(`Minimal submission failed!\nError: ${result.error}`);
        }
    } catch (error) {
        alert('Minimal submission failed!\n' + JSON.stringify(error, null, 2));
    }
};

// Debug current form data
window.debugCurrentFormData = function() {
    console.log('Debugging current form data...');
    
    const formData = {};
    
    // Collect all form fields
    $('#membership-application-form input, #membership-application-form select, #membership-application-form textarea').each(function() {
        const $field = $(this);
        const name = $field.attr('name');
        const type = $field.attr('type');
        
        if (name) {
            if (type === 'checkbox') {
                formData[name] = $field.is(':checked');
            } else if (type === 'radio') {
                if ($field.is(':checked')) {
                    formData[name] = $field.val();
                }
            } else {
                formData[name] = $field.val();
            }
        }
    });
    
    // Collect volunteer interests
    const interests = [];
    $('#volunteer-interests input[type="checkbox"]:checked').each(function() {
        interests.push($(this).val());
    });
    if (interests.length > 0) {
        formData.volunteer_interests = interests;
    }
    
    console.log('Current form data:', formData);
    
    // Show in a readable format
    const dataText = JSON.stringify(formData, null, 2);
    
    // Create a modal to show the data
    const modal = $(`
        <div class="modal fade" tabindex="-1">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Current Form Data</h5>
                        <button type="button" class="close" data-dismiss="modal">&times;</button>
                    </div>
                    <div class="modal-body">
                        <pre style="max-height: 400px; overflow-y: auto;">${dataText}</pre>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
                        <button type="button" class="btn btn-primary" onclick="copyToClipboard('${dataText.replace(/'/g, "\\'")}')">Copy</button>
                    </div>
                </div>
            </div>
        </div>
    `);
    
    $('body').append(modal);
    modal.modal('show');
    modal.on('hidden.bs.modal', function() {
        modal.remove();
    });
    
    return formData;
};

// Main debug submission function
async function submitApplicationDebug() {
    console.log('=== DEBUG SUBMISSION START ===');
    
    // Get form data
    const formData = debugCurrentFormData();
    
    // Show loading
    const $submitBtn = $('#submit-btn');
    const originalText = $submitBtn.html();
    $submitBtn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i> Debugging...');
    
    try {
        console.log('Submitting to debug endpoint...');
        
        const result = await new Promise((resolve, reject) => {
            frappe.call({
                method: 'verenigingen.api.membership_application.submit_application_debug',
                args: {
                    data: formData
                },
                callback: function(r) {
                    console.log('Debug submission response:', r);
                    if (r.message) {
                        resolve(r.message);
                    } else {
                        reject(new Error('No response from server'));
                    }
                },
                error: function(r) {
                    console.error('Debug submission error:', r);
                    reject(r);
                }
            });
        });
        
        console.log('Debug result:', result);
        
        if (result.success) {
            // Success!
            alert(`Success!\nMember ID: ${result.member_id}\n\nDebug info:\n${JSON.stringify(result.debug_info || {}, null, 2)}`);
            
            // Try the enhanced version now
            tryEnhancedSubmission(formData);
        } else {
            // Show detailed error
            let errorMsg = `Submission failed!\n\nError: ${result.error}`;
            
            if (result.traceback) {
                errorMsg += `\n\nTraceback:\n${result.traceback}`;
            }
            
            if (result.debug_data) {
                errorMsg += `\n\nDebug data:\n${result.debug_data}`;
            }
            
            if (result.received_fields) {
                errorMsg += `\n\nReceived fields:\n${result.received_fields.join(', ')}`;
            }
            
            console.error('Detailed error:', result);
            alert(errorMsg);
        }
        
    } catch (error) {
        console.error('Submission error:', error);
        
        let errorMsg = 'Submission failed with error:\n';
        
        if (error.responseJSON) {
            errorMsg += JSON.stringify(error.responseJSON, null, 2);
        } else if (error.message) {
            errorMsg += error.message;
        } else {
            errorMsg += JSON.stringify(error, null, 2);
        }
        
        alert(errorMsg);
    } finally {
        // Restore button
        $submitBtn.prop('disabled', false).html(originalText);
        console.log('=== DEBUG SUBMISSION END ===');
    }
}

// Try enhanced submission after debug success
async function tryEnhancedSubmission(formData) {
    console.log('Trying enhanced submission...');
    
    try {
        const result = await new Promise((resolve, reject) => {
            frappe.call({
                method: 'verenigingen.api.membership_application.submit_application_enhanced',
                args: {
                    data: formData
                },
                callback: function(r) {
                    console.log('Enhanced submission response:', r);
                    resolve(r.message);
                },
                error: reject
            });
        });
        
        if (result.success) {
            console.log('Enhanced submission successful:', result);
            
            // Show success and redirect
            $('.membership-application-form').html(`
                <div class="alert alert-success text-center">
                    <h3><i class="fa fa-check-circle"></i> Application Submitted Successfully!</h3>
                    <p>${result.message}</p>
                    <p><strong>Member ID:</strong> ${result.member_id}</p>
                    ${result.debug_info ? `<p><small>Fields used: ${result.debug_info.fields_used.join(', ')}</small></p>` : ''}
                </div>
            `);
        } else {
            console.error('Enhanced submission failed:', result);
            alert(`Enhanced submission failed: ${result.error}`);
        }
        
    } catch (error) {
        console.error('Enhanced submission error:', error);
        alert(`Enhanced submission error: ${JSON.stringify(error, null, 2)}`);
    }
}

// Test direct API call without frappe.call
window.testDirectAPI = async function() {
    console.log('Testing direct API call...');
    
    const testData = {
        first_name: 'Direct',
        last_name: 'Test',
        email: `direct.${Date.now()}@example.com`
    };
    
    try {
        const response = await fetch('/api/method/verenigingen.api.membership_application.submit_application_debug', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-Frappe-CSRF-Token': frappe.csrf_token
            },
            body: new URLSearchParams({
                data: JSON.stringify(testData)
            })
        });
        
        const result = await response.json();
        console.log('Direct API result:', result);
        
        if (response.ok) {
            alert('Direct API call successful!\n' + JSON.stringify(result, null, 2));
        } else {
            alert('Direct API call failed!\n' + JSON.stringify(result, null, 2));
        }
        
    } catch (error) {
        console.error('Direct API error:', error);
        alert('Direct API error: ' + error.message);
    }
};

// Utility function
window.copyToClipboard = function(text) {
    navigator.clipboard.writeText(text).then(() => {
        alert('Copied to clipboard!');
    }).catch(() => {
        alert('Could not copy to clipboard');
    });
};

// Add direct API test button
$(document).ready(function() {
    setTimeout(() => {
        if ($('#debug-controls').length && !$('#debug-controls .test-direct').length) {
            $('#debug-controls').append(
                '<button type="button" class="btn btn-sm btn-info test-direct" onclick="testDirectAPI()">Test Direct API</button>'
            );
        }
    }, 1000);
});

console.log('Debug JavaScript loaded. Available functions:');
console.log('- testBackendConnection()');
console.log('- testMemberFields()');
console.log('- testMinimalSubmission()');
console.log('- debugCurrentFormData()');
console.log('- testDirectAPI()');
