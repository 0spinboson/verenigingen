// verenigingen/public/js/membership_application.js

$(document).ready(function() {
    let currentStep = 1;
    let maxSteps = 5;
    let formData = {};
    let membershipTypes = [];
    let customAmountEnabled = false;

    // Load initial form data
    loadFormData();

    function loadFormData() {
        frappe.call({
            method: 'verenigingen.api.membership_application.get_application_form_data',
            callback: function(r) {
                if (r.message) {
                    membershipTypes = r.message.membership_types;
                    renderMembershipTypes();
                    loadCountries(r.message.countries);
                    loadVolunteerAreas(r.message.volunteer_areas);
                    loadChapters(r.message.chapters);
                    loadPaymentMethods();
                }
            }
        });
    }

    function renderMembershipTypes() {
        const container = $('#membership-types');
        container.empty();

        membershipTypes.forEach(function(type) {
            const card = $(`
                <div class="membership-type-card" data-type="${type.name}" data-amount="${type.amount}">
                    <h5>${type.membership_type_name}</h5>
                    <div class="membership-price">
                        ${frappe.format(type.amount, {fieldtype: 'Currency'})} / ${type.subscription_period}
                    </div>
                    <p class="membership-description">${type.description || ''}</p>
                    <div class="custom-amount-section" style="display: none;">
                        <label>Custom Amount:</label>
                        <input type="number" class="form-control custom-amount-input" 
                               min="${type.amount * 0.5}" step="0.01" 
                               placeholder="Enter amount">
                        <small class="text-muted">Minimum: ${frappe.format(type.amount * 0.5, {fieldtype: 'Currency'})}</small>
                    </div>
                    <div class="mt-2">
                        <button type="button" class="btn btn-primary select-membership">Select</button>
                        <button type="button" class="btn btn-outline-secondary toggle-custom" style="margin-left: 10px;">Custom Amount</button>
                    </div>
                </div>
            `);
            container.append(card);
        });

        // Add event handlers
        $('.select-membership').click(function() {
            const card = $(this).closest('.membership-type-card');
            const membershipType = card.data('type');
            const standardAmount = card.data('amount');
            const customAmountInput = card.find('.custom-amount-input');
            const customAmount = customAmountInput.val();

            // Clear other selections
            $('.membership-type-card').removeClass('selected');
            card.addClass('selected');

            // Store selection
            formData.selected_membership_type = membershipType;
            
            if (customAmount && parseFloat(customAmount) !== standardAmount) {
                formData.membership_amount = parseFloat(customAmount);
                formData.uses_custom_amount = true;
            } else {
                formData.membership_amount = standardAmount;
                formData.uses_custom_amount = false;
            }

            updateMembershipFeeDisplay();
            $('#membership-type-error').hide();
        });

        $('.toggle-custom').click(function() {
            const card = $(this).closest('.membership-type-card');
            const customSection = card.find('.custom-amount-section');
            const button = $(this);

            if (customSection.is(':visible')) {
                customSection.hide();
                button.text('Custom Amount');
                card.find('.custom-amount-input').val('');
            } else {
                customSection.show();
                button.text('Standard Amount');
                // Pre-fill with standard amount
                card.find('.custom-amount-input').val(card.data('amount'));
            }
        });

        // Validate custom amounts on input
        $('.custom-amount-input').on('input', function() {
            const card = $(this).closest('.membership-type-card');
            const minAmount = card.data('amount') * 0.5;
            const enteredAmount = parseFloat($(this).val());

            if (enteredAmount < minAmount) {
                $(this).addClass('is-invalid');
                $(this).siblings('.invalid-feedback').remove();
                $(this).after(`<div class="invalid-feedback">Amount must be at least ${frappe.format(minAmount, {fieldtype: 'Currency'})}</div>`);
            } else {
                $(this).removeClass('is-invalid');
                $(this).siblings('.invalid-feedback').remove();
            }
        });
    }

    function updateMembershipFeeDisplay() {
        const display = $('#membership-fee-display');
        const details = $('#fee-details');

        if (formData.selected_membership_type && formData.membership_amount) {
            const membershipType = membershipTypes.find(t => t.name === formData.selected_membership_type);
            let content = `
                <strong>Selected:</strong> ${membershipType.membership_type_name}<br>
                <strong>Amount:</strong> ${frappe.format(formData.membership_amount, {fieldtype: 'Currency'})}
            `;

            if (formData.uses_custom_amount) {
                const difference = formData.membership_amount - membershipType.amount;
                const percentageDiff = ((difference / membershipType.amount) * 100).toFixed(1);
                content += `<br><strong>Standard Amount:</strong> ${frappe.format(membershipType.amount, {fieldtype: 'Currency'})}`;
                content += `<br><strong>Difference:</strong> ${difference > 0 ? '+' : ''}${frappe.format(difference, {fieldtype: 'Currency'})} (${percentageDiff > 0 ? '+' : ''}${percentageDiff}%)`;
            }

            details.html(content);
            display.show();
        } else {
            display.hide();
        }
    }

    function loadPaymentMethods() {
        frappe.call({
            method: 'verenigingen.api.membership_application.get_payment_methods',
            callback: function(r) {
                if (r.message && r.message.payment_methods) {
                    const select = $('#payment_method');
                    select.empty().append('<option value="">Select payment method...</option>');
                    
                    r.message.payment_methods.forEach(function(method) {
                        const option = $(`
                            <option value="${method.name}" 
                                    data-type="${method.type}" 
                                    data-processing-time="${method.processing_time || ''}"
                                    data-requires-mandate="${method.requires_mandate || false}">
                                ${method.name} - ${method.description}
                            </option>
                        `);
                        select.append(option);
                    });

                    // Set default if specified
                    if (r.message.default_method) {
                        select.val(r.message.default_method);
                    }
                }
            },
            error: function(r) {
                console.error('Error loading payment methods:', r);
                // Fallback to basic options
                const select = $('#payment_method');
                select.empty().append(`
                    <option value="">Select payment method...</option>
                    <option value="Bank Transfer">Bank Transfer</option>
                    <option value="Direct Debit">Direct Debit (SEPA)</option>
                    <option value="Credit Card">Credit Card</option>
                `);
            }
        });
    }

    function loadCountries(countries) {
        const select = $('#country');
        select.empty().append('<option value="">Select Country...</option>');
        
        countries.forEach(function(country) {
            select.append(`<option value="${country.name}">${country.name}</option>`);
        });
        
        // Set Netherlands as default
        select.val('Netherlands');
    }

    function loadVolunteerAreas(areas) {
        const container = $('#volunteer-interests');
        container.empty();
        
        areas.forEach(function(area) {
            const checkbox = $(`
                <div class="form-check">
                    <input class="form-check-input" type="checkbox" 
                           value="${area.name}" id="interest_${area.name}">
                    <label class="form-check-label" for="interest_${area.name}">
                        ${area.name}
                        ${area.description ? `<small class="text-muted d-block">${area.description}</small>` : ''}
                    </label>
                </div>
            `);
            container.append(checkbox);
        });
    }

    function loadChapters(chapters) {
        const select = $('#selected_chapter');
        select.empty().append('<option value="">Select a chapter...</option>');
        
        chapters.forEach(function(chapter) {
            select.append(`<option value="${chapter.name}">${chapter.name} - ${chapter.region}</option>`);
        });
    }

    // Step navigation
    $('#next-btn').click(function() {
        if (validateCurrentStep()) {
            if (currentStep < maxSteps) {
                currentStep++;
                showStep(currentStep);
            }
        }
    });

    $('#prev-btn').click(function() {
        if (currentStep > 1) {
            currentStep--;
            showStep(currentStep);
        }
    });

    function showStep(step) {
        // Hide all steps
        $('.form-step').hide().removeClass('active');
        
        // Show current step
        $(`.form-step[data-step="${step}"]`).show().addClass('active');
        
        // Update progress bar
        const progress = (step / maxSteps) * 100;
        $('#form-progress').css('width', progress + '%');
        
        // Update step indicators
        $('.step').removeClass('active');
        $(`.step[data-step="${step}"]`).addClass('active');
        
        // Update navigation buttons
        if (step === 1) {
            $('#prev-btn').hide();
        } else {
            $('#prev-btn').show();
        }
        
        if (step === maxSteps) {
            $('#next-btn').hide();
            $('#submit-btn').show();
            updateApplicationSummary();
        } else {
            $('#next-btn').show();
            $('#submit-btn').hide();
        }

        // Step-specific actions
        if (step === 2) {
            // Postal code suggestion
            $('#postal_code').on('blur', function() {
                suggestChapterFromPostalCode($(this).val());
            });
        }

        if (step === 4) {
            // Volunteer interest toggle
            $('#interested_in_volunteering').change(function() {
                if ($(this).is(':checked')) {
                    $('#volunteer-details').show();
                } else {
                    $('#volunteer-details').hide();
                }
            });

            // Application source details
            $('#application_source').change(function() {
                if ($(this).val() === 'Other') {
                    $('#source-details-container').show();
                } else {
                    $('#source-details-container').hide();
                }
            });
        }
    }

    function validateCurrentStep() {
        const step = currentStep;
        let isValid = true;
        
        // Clear previous validation
        $('.is-invalid').removeClass('is-invalid');
        $('.invalid-feedback').hide();

        if (step === 1) {
            // Personal information validation
            const requiredFields = ['first_name', 'last_name', 'email', 'birth_date'];
            requiredFields.forEach(function(field) {
                const input = $(`#${field}`);
                if (!input.val().trim()) {
                    markFieldInvalid(input, `${field.replace('_', ' ')} is required`);
                    isValid = false;
                }
            });

            // Email validation
            const email = $('#email').val();
            if (email && !isValidEmail(email)) {
                markFieldInvalid($('#email'), 'Please enter a valid email address');
                isValid = false;
            }

            // Age validation
            const birthDate = $('#birth_date').val();
            if (birthDate) {
                const age = calculateAge(birthDate);
                if (age < 0) {
                    markFieldInvalid($('#birth_date'), 'Birth date cannot be in the future');
                    isValid = false;
                } else if (age < 12) {
                    $('#age-warning').show().text('Applicants under 12 may require parental consent');
                }
            }
        }

        if (step === 2) {
            // Address validation
            const requiredFields = ['address_line1', 'city', 'postal_code', 'country'];
            requiredFields.forEach(function(field) {
                const input = $(`#${field}`);
                if (!input.val().trim()) {
                    markFieldInvalid(input, `${field.replace('_', ' ')} is required`);
                    isValid = false;
                }
            });
        }

        if (step === 3) {
            // Membership type validation
            if (!formData.selected_membership_type) {
                $('#membership-type-error').show().text('Please select a membership type');
                isValid = false;
            }

            // Custom amount validation
            if (formData.uses_custom_amount) {
                const membershipType = membershipTypes.find(t => t.name === formData.selected_membership_type);
                const minAmount = membershipType.amount * 0.5;
                if (formData.membership_amount < minAmount) {
                    $('#membership-type-error').show().text(`Amount must be at least ${frappe.format(minAmount, {fieldtype: 'Currency'})}`);
                    isValid = false;
                }
            }
        }

        if (step === 5) {
            // Payment method validation
            if (!$('#payment_method').val()) {
                markFieldInvalid($('#payment_method'), 'Please select a payment method');
                isValid = false;
            }

            // Terms validation
            if (!$('#terms').is(':checked')) {
                markFieldInvalid($('#terms'), 'You must accept the terms and conditions');
                isValid = false;
            }
        }

        return isValid;
    }

    function markFieldInvalid(field, message) {
        field.addClass('is-invalid');
        let feedback = field.siblings('.invalid-feedback');
        if (feedback.length === 0) {
            feedback = $('<div class="invalid-feedback"></div>');
            field.after(feedback);
        }
        feedback.text(message).show();
    }

    function suggestChapterFromPostalCode(postalCode) {
        if (!postalCode) return;

        frappe.call({
            method: 'verenigingen.api.membership_application.validate_postal_code',
            args: {
                postal_code: postalCode,
                country: $('#country').val() || 'Netherlands'
            },
            callback: function(r) {
                if (r.message && r.message.suggested_chapters && r.message.suggested_chapters.length > 0) {
                    const suggestion = r.message.suggested_chapters[0];
                    $('#suggested-chapter-name').text(suggestion.name);
                    $('#suggested-chapter').show();
                    
                    $('#accept-suggestion').off('click').on('click', function() {
                        $('#selected_chapter').val(suggestion.name);
                        $('#suggested-chapter').hide();
                    });
                } else {
                    $('#suggested-chapter').hide();
                }
            }
        });
    }

    function updateApplicationSummary() {
        const summary = $('#application-summary');
        let content = `
            <div class="row">
                <div class="col-md-6">
                    <h6>Personal Information</h6>
                    <p><strong>Name:</strong> ${$('#first_name').val()} ${$('#last_name').val()}</p>
                    <p><strong>Email:</strong> ${$('#email').val()}</p>
                    <p><strong>Age:</strong> ${calculateAge($('#birth_date').val())} years</p>
                </div>
                <div class="col-md-6">
                    <h6>Membership</h6>
                    <p><strong>Type:</strong> ${getMembershipTypeName(formData.selected_membership_type)}</p>
                    <p><strong>Amount:</strong> ${frappe.format(formData.membership_amount, {fieldtype: 'Currency'})}</p>
                    ${formData.uses_custom_amount ? '<p><em>Custom amount selected</em></p>' : ''}
                </div>
            </div>
        `;

        if ($('#selected_chapter').val()) {
            content += `<p><strong>Chapter:</strong> ${$('#selected_chapter option:selected').text()}</p>`;
        }

        if ($('#interested_in_volunteering').is(':checked')) {
            content += `<p><strong>Interested in volunteering:</strong> Yes</p>`;
        }

        summary.html(content);
    }

    // Form submission
    $('#membership-application-form').submit(function(e) {
        e.preventDefault();
        
        if (!validateCurrentStep()) {
            return;
        }

        const $btn = $('#submit-btn');
        $btn.prop('disabled', true).html('Processing...');

        // Collect all form data
        const applicationData = {
            // Personal info
            first_name: $('#first_name').val(),
            middle_name: $('#middle_name').val(),
            last_name: $('#last_name').val(),
            email: $('#email').val(),
            mobile_no: $('#mobile_no').val(),
            phone: $('#phone').val(),
            birth_date: $('#birth_date').val(),
            pronouns: $('#pronouns').val(),

            // Address
            address_line1: $('#address_line1').val(),
            address_line2: $('#address_line2').val(),
            city: $('#city').val(),
            state: $('#state').val(),
            postal_code: $('#postal_code').val(),
            country: $('#country').val(),

            // Membership
            selected_membership_type: formData.selected_membership_type,
            membership_amount: formData.membership_amount,
            uses_custom_amount: formData.uses_custom_amount,
            selected_chapter: $('#selected_chapter').val(),

            // Volunteer
            interested_in_volunteering: $('#interested_in_volunteering').is(':checked'),
            volunteer_availability: $('#volunteer_availability').val(),
            volunteer_experience_level: $('#volunteer_experience_level').val(),
            volunteer_interests: getSelectedVolunteerInterests(),

            // Communication
            newsletter_opt_in: $('#newsletter_opt_in').is(':checked'),
            application_source: $('#application_source').val(),
            application_source_details: $('#application_source_details').val(),

            // Payment
            payment_method: $('#payment_method').val(),

            // Additional
            additional_notes: $('#additional_notes').val(),
            terms: $('#terms').is(':checked')
        };

        // Submit application
        frappe.call({
            method: 'verenigingen.api.membership_application.submit_application',
            args: { data: applicationData },
            callback: function(r) {
                if (r.message && r.message.success) {
                    window.location.href = `/application-success?id=${r.message.member_id}`;
                } else {
                    frappe.msgprint(r.message || 'An error occurred. Please try again.');
                    $btn.prop('disabled', false).html('Submit Application & Pay');
                }
            },
            error: function(r) {
                frappe.msgprint('An error occurred. Please try again.');
                $btn.prop('disabled', false).html('Submit Application & Pay');
            }
        });
    });

    // Utility functions
    function isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }

    function calculateAge(birthDate) {
        const birth = new Date(birthDate);
        const today = new Date();
        let age = today.getFullYear() - birth.getFullYear();
        const monthDiff = today.getMonth() - birth.getMonth();
        
        if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birth.getDate())) {
            age--;
        }
        
        return age;
    }

    function getMembershipTypeName(typeId) {
        const type = membershipTypes.find(t => t.name === typeId);
        return type ? type.membership_type_name : typeId;
    }

    function getSelectedVolunteerInterests() {
        const interests = [];
        $('#volunteer-interests input[type="checkbox"]:checked').each(function() {
            interests.push($(this).val());
        });
        return interests;
    }

    // Initialize first step
    showStep(1);
});
