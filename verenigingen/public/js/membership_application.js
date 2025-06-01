$(document).ready(function() {
    let currentStep = 1;
    let maxSteps = 5;
    let formData = {};
    let membershipTypes = [];
    let paymentMethods = [];
    let selectedPaymentMethod = null;

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

        // First, get detailed information for each membership type
        const loadPromises = membershipTypes.map(type => {
            return new Promise((resolve) => {
                frappe.call({
                    method: 'verenigingen.api.membership_application.get_membership_type_details',
                    args: { membership_type: type.name },
                    callback: function(r) {
                        resolve(r.message || type);
                    }
                });
            });
        });

        Promise.all(loadPromises).then(detailedTypes => {
            detailedTypes.forEach(function(type) {
                if (type.error) {
                    console.error('Error loading membership type:', type.error);
                    return;
                }

                const card = $(`
                    <div class="membership-type-card" data-type="${type.name}" data-amount="${type.amount}">
                        <h5>${type.membership_type_name}</h5>
                        <div class="membership-price">
                            ${frappe.format(type.amount, {fieldtype: 'Currency'})} / ${type.subscription_period}
                        </div>
                        <p class="membership-description">${type.description || ''}</p>
                        
                        ${type.allow_custom_amount ? `
                            <div class="custom-amount-section" style="display: none;">
                                <label>Choose Your Contribution:</label>
                                <div class="amount-suggestion-pills">
                                    ${type.suggested_amounts.map(suggestion => `
                                        <span class="amount-pill" data-amount="${suggestion.amount}">
                                            ${frappe.format(suggestion.amount, {fieldtype: 'Currency'})}
                                            <br><small>${suggestion.label}</small>
                                        </span>
                                    `).join('')}
                                </div>
                                <div class="mt-3">
                                    <label>Or enter custom amount:</label>
                                    <input type="number" class="form-control custom-amount-input" 
                                           min="${type.minimum_amount}" step="0.01" 
                                           placeholder="Enter amount">
                                    <small class="text-muted">Minimum: ${frappe.format(type.minimum_amount, {fieldtype: 'Currency'})}</small>
                                </div>
                            </div>
                        ` : ''}
                        
                        <div class="btn-group mt-3">
                            <button type="button" class="btn btn-primary select-membership">
                                Select ${type.allow_custom_amount ? 'Standard' : ''}
                            </button>
                            ${type.allow_custom_amount ? `
                                <button type="button" class="btn btn-outline-secondary toggle-custom">
                                    Choose Amount
                                </button>
                            ` : ''}
                        </div>
                        
                        ${type.allow_custom_amount ? `
                            <div class="mt-2">
                                <small class="text-muted">${type.custom_amount_note || ''}</small>
                            </div>
                        ` : ''}
                    </div>
                `);
                container.append(card);
            });

            // Bind event handlers after all cards are rendered
            bindMembershipTypeEvents();
        });
    }

    function bindMembershipTypeEvents() {
        // Standard selection
        $('.select-membership').click(function() {
            const card = $(this).closest('.membership-type-card');
            selectMembershipType(card, false);
        });

        // Toggle custom amount section
        $('.toggle-custom').click(function() {
            const card = $(this).closest('.membership-type-card');
            const customSection = card.find('.custom-amount-section');
            const button = $(this);

            if (customSection.is(':visible')) {
                customSection.hide();
                button.text('Choose Amount');
                card.find('.custom-amount-input').val('');
                card.find('.amount-pill').removeClass('selected');
            } else {
                // Hide other custom sections
                $('.custom-amount-section').hide();
                $('.toggle-custom').text('Choose Amount');
                
                // Show this one
                customSection.show();
                button.text('Standard Amount');
                
                // Pre-select the standard amount pill
                const standardAmount = card.data('amount');
                card.find(`.amount-pill[data-amount="${standardAmount}"]`).addClass('selected');
            }
        });

        // Amount pill selection
        $(document).on('click', '.amount-pill', function() {
            const card = $(this).closest('.membership-type-card');
            const amount = $(this).data('amount');
            
            // Update pill selection
            card.find('.amount-pill').removeClass('selected');
            $(this).addClass('selected');
            
            // Update input
            card.find('.custom-amount-input').val(amount);
            
            // Auto-select this membership type
            selectMembershipType(card, true, amount);
        });

        // Custom amount input
        $('.custom-amount-input').on('input blur', function() {
            const card = $(this).closest('.membership-type-card');
            const amount = parseFloat($(this).val());
            const minAmount = parseFloat($(this).attr('min'));

            // Clear pill selections
            card.find('.amount-pill').removeClass('selected');

            if (amount && amount >= minAmount) {
                $(this).removeClass('is-invalid');
                $(this).siblings('.invalid-feedback').remove();
                selectMembershipType(card, true, amount);
            } else if (amount && amount < minAmount) {
                $(this).addClass('is-invalid');
                $(this).siblings('.invalid-feedback').remove();
                $(this).after(`<div class="invalid-feedback">Amount must be at least ${frappe.format(minAmount, {fieldtype: 'Currency'})}</div>`);
            }
        });
    }

    function selectMembershipType(card, isCustom = false, customAmount = null) {
        const membershipType = card.data('type');
        const standardAmount = card.data('amount');
        const finalAmount = customAmount || standardAmount;

        // Clear other selections
        $('.membership-type-card').removeClass('selected');
        card.addClass('selected');

        // Store selection
        formData.selected_membership_type = membershipType;
        formData.membership_amount = finalAmount;
        formData.uses_custom_amount = isCustom && (customAmount !== standardAmount);

        updateMembershipFeeDisplay();
        $('#membership-type-error').hide();

        // Validate custom amount if applicable
        if (isCustom && customAmount) {
            frappe.call({
                method: 'verenigingen.api.membership_application.validate_custom_amount',
                args: {
                    membership_type: membershipType,
                    amount: customAmount
                },
                callback: function(r) {
                    if (r.message && !r.message.valid) {
                        $('#membership-type-error').show().text(r.message.message);
                        card.find('.custom-amount-input').addClass('is-invalid');
                    }
                }
            });
        }
    }

    function updateMembershipFeeDisplay() {
        const display = $('#membership-fee-display');
        const details = $('#fee-details');

        if (formData.selected_membership_type && formData.membership_amount) {
            const membershipType = membershipTypes.find(t => t.name === formData.selected_membership_type);
            let content = `
                <div class="row">
                    <div class="col-md-6">
                        <strong>Selected:</strong> ${membershipType.membership_type_name}<br>
                        <strong>Amount:</strong> ${frappe.format(formData.membership_amount, {fieldtype: 'Currency'})}
                    </div>
                    <div class="col-md-6">
            `;

            if (formData.uses_custom_amount) {
                const difference = formData.membership_amount - membershipType.amount;
                const percentageDiff = ((difference / membershipType.amount) * 100).toFixed(1);
                content += `
                    <strong>Standard Amount:</strong> ${frappe.format(membershipType.amount, {fieldtype: 'Currency'})}<br>
                    <strong>Your Contribution:</strong> 
                    <span class="${difference > 0 ? 'text-success' : 'text-warning'}">
                        ${difference > 0 ? '+' : ''}${frappe.format(difference, {fieldtype: 'Currency'})} 
                        (${percentageDiff > 0 ? '+' : ''}${percentageDiff}%)
                    </span>
                `;
            } else {
                content += `<em>Standard membership amount</em>`;
            }

            content += `</div></div>`;
            details.html(content);
            display.show();
        } else {
            display.hide();
        }
    }

    function loadPaymentMethods() {
        const container = $('#payment-methods-list');
        const fallback = $('#payment-method-fallback');
        
        // Show loading state
        container.html('<div class="text-center p-4"><i class="fa fa-spinner fa-spin"></i> Loading payment methods...</div>');
        
        frappe.call({
            method: 'verenigingen.api.membership_application.get_payment_methods',
            callback: function(r) {
                if (r.message && r.message.payment_methods && r.message.payment_methods.length > 0) {
                    paymentMethods = r.message.payment_methods;
                    renderPaymentMethods();
                    fallback.hide();
                } else {
                    console.warn('No payment methods returned from API, using fallback');
                    showPaymentMethodFallback();
                }
            },
            error: function(r) {
                console.error('Error loading payment methods:', r);
                showPaymentMethodFallback();
            }
        });
    }

    function renderPaymentMethods() {
        const container = $('#payment-methods-list');
        container.empty();
    
        if (!paymentMethods || paymentMethods.length === 0) {
            showPaymentMethodFallback();
            return;
        }
    
        paymentMethods.forEach(function(method) {
            const methodCard = $(`
                <div class="payment-method-option" data-method="${method.name}">
                    <div class="d-flex align-items-center">
                        <div class="payment-method-icon">
                            <i class="fa ${method.icon || 'fa-credit-card'}"></i>
                        </div>
                        <div class="payment-method-info flex-grow-1">
                            <h6>${method.name}</h6>
                            <div class="text-muted">
                                ${method.description}<br>
                                <small><strong>Processing:</strong> ${method.processing_time}</small>
                                ${method.requires_mandate ? '<br><small class="text-warning"><strong>Note:</strong> ' + method.note + '</small>' : ''}
                            </div>
                        </div>
                        <div class="payment-method-selector">
                            <div class="form-check">
                                <input class="form-check-input payment-method-radio" type="radio" 
                                       name="payment_method_selection" value="${method.name}" 
                                       id="payment_${method.name.replace(/\s+/g, '_').toLowerCase()}">
                                <label class="form-check-label" for="payment_${method.name.replace(/\s+/g, '_').toLowerCase()}">
                                    Select
                                </label>
                            </div>
                        </div>
                    </div>
                </div>
            `);
            container.append(methodCard);
        });
    
        // Bind payment method selection
        $('.payment-method-option').off('click').on('click', function() {
            const methodName = $(this).data('method');
            selectPaymentMethod(methodName);
        });
    
        $('.payment-method-radio').off('change').on('change', function() {
            if ($(this).is(':checked')) {
                selectPaymentMethod($(this).val());
            }
        });
    
        // Auto-select first method
        if (paymentMethods.length > 0) {
            selectPaymentMethod(paymentMethods[0].name);
        }
    }

    function selectPaymentMethod(methodName) {
        if (!methodName) return;
        
        selectedPaymentMethod = methodName;
        console.log('Selected payment method:', methodName);
        
        // Update UI based on whether we're using cards or dropdown
        if ($('#payment-method-fallback').is(':visible')) {
            // Using dropdown fallback
            const select = $('#payment_method');
            select.val(methodName);
            
            // Clear any validation errors
            select.removeClass('is-invalid');
            select.siblings('.invalid-feedback').hide();
            
            // Mark as valid
            select.addClass('is-valid');
        } else {
            // Using card interface
            $('.payment-method-option').removeClass('selected');
            $(`.payment-method-option[data-method="${methodName}"]`).addClass('selected');
            
            // Update radio button
            $(`.payment-method-radio[value="${methodName}"]`).prop('checked', true);
        }
        
        // Show method details
        const method = paymentMethods.find(m => m.name === methodName);
        if (method) {
            showPaymentMethodDetails(method);
        }
        
        // Show/hide SEPA mandate notice
        if (methodName === 'Direct Debit') {
            $('#sepa-mandate-notice').show();
        } else {
            $('#sepa-mandate-notice').hide();
        }
        
        // Store in form data
        formData.payment_method = methodName;
        
        console.log('Payment method selection complete:', methodName);
    }

    function showPaymentMethodDetails(method) {
        const detailsContainer = $('#payment-method-details');
        const contentContainer = $('#payment-details-content');
        
        let content = `
            <div class="selected-method-info">
                <div class="d-flex align-items-center mb-2">
                    <i class="fa ${method.icon || 'fa-credit-card'} me-2"></i>
                    <strong>${method.name}</strong>
                </div>
                <p class="mb-2">${method.description}</p>
                <div class="method-details">
                    <small><strong>Processing Time:</strong> ${method.processing_time}</small>
                </div>
        `;
        
        if (method.requires_mandate) {
            content += `
                <div class="alert alert-info mt-2 mb-0">
                    <small><i class="fa fa-info-circle"></i> ${method.note}</small>
                </div>
            `;
        }
        
        content += `</div>`;
        
        contentContainer.html(content);
        detailsContainer.show();
    }

    function showPaymentMethodFallback() {
        console.log('Showing payment method fallback');
        const container = $('#payment-methods-list');
        const fallback = $('#payment-method-fallback');
        
        container.hide();
        fallback.show();
        
        // Populate fallback dropdown
        const select = $('#payment_method');
        select.empty().append('<option value="">Select payment method...</option>');
        
        const fallbackMethods = [
            { 
                name: 'Credit Card', 
                description: 'Visa, Mastercard, American Express',
                icon: 'fa-credit-card',
                processing_time: 'Immediate',
                requires_mandate: false
            },
            { 
                name: 'Bank Transfer', 
                description: 'One-time bank transfer',
                icon: 'fa-university',
                processing_time: '1-3 business days',
                requires_mandate: false
            },
            { 
                name: 'Direct Debit', 
                description: 'SEPA Direct Debit (recurring)',
                icon: 'fa-repeat',
                processing_time: '5-7 days first collection',
                requires_mandate: true
            }
        ];
        
        // Store fallback methods for later use
        paymentMethods = fallbackMethods;
        
        fallbackMethods.forEach(function(method) {
            select.append(`<option value="${method.name}">${method.name} - ${method.description}</option>`);
        });
        
        // Bind change event for fallback dropdown
        select.off('change').on('change', function() {
            const selectedMethod = $(this).val();
            console.log('Dropdown changed to:', selectedMethod);
            if (selectedMethod) {
                selectPaymentMethod(selectedMethod);
            }
        });
        
        // AUTO-SELECT FIRST OPTION - Fixed to properly set the value
        setTimeout(function() {
            if (fallbackMethods.length > 0) {
                const defaultMethod = fallbackMethods[0].name;
                select.val(defaultMethod);
                selectPaymentMethod(defaultMethod);
                
                // Remove the required attribute temporarily to avoid validation issues
                select.removeAttr('required');
                setTimeout(() => select.attr('required', 'required'), 100);
                
                console.log('Auto-selected payment method:', defaultMethod);
            }
        }, 200); // Longer delay to ensure everything is ready
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
                           value="${area.name}" id="interest_${area.name.replace(/\s+/g, '_')}">
                    <label class="form-check-label" for="interest_${area.name.replace(/\s+/g, '_')}">
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
        
        // Show chapter selection section if chapters are available
        if (chapters.length > 0) {
            $('#chapter-selection').show();
        }
    }

    // Step navigation (rest of the navigation code remains the same)
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
        $('.step').removeClass('active completed');
        for (let i = 1; i < step; i++) {
            $(`.step[data-step="${i}"]`).addClass('completed');
        }
        $(`.step[data-step="${step}"]`).addClass('active');
        
        // Update navigation buttons
        $('#prev-btn').toggle(step > 1);
        $('#next-btn').toggle(step < maxSteps);
        $('#submit-btn').toggle(step === maxSteps);

        // Step-specific actions
        if (step === 2) {
            $('#postal_code').on('blur', function() {
                suggestChapterFromPostalCode($(this).val());
            });
        }

        if (step === 4) {
            $('#interested_in_volunteering').change(function() {
                $('#volunteer-details').toggle($(this).is(':checked'));
            });

            $('#application_source').change(function() {
                $('#source-details-container').toggle($(this).val() === 'Other');
            });
        }

        if (step === maxSteps) {
            updateApplicationSummary();
        }
    }

    function validateCurrentStep() {
        const step = currentStep;
        let isValid = true;
        
        // Clear previous validation
        $('.is-invalid').removeClass('is-invalid');
        $('.invalid-feedback').hide();

        if (step === 3) {
            if (!formData.selected_membership_type) {
                        $('#membership-type-error').show().text('Please select a membership type');
                        isValid = false;
                    } else {
                        $('#membership-type-error').hide();
                    }
            
                    // Custom amount validation
                    if (formData.uses_custom_amount && formData.membership_amount) {
                        const membershipType = membershipTypes.find(t => t.name === formData.selected_membership_type);
                        if (membershipType) {
                            const minAmount = membershipType.amount * 0.5; // Assuming 50% minimum
                            if (formData.membership_amount < minAmount) {
                                $('#membership-type-error').show().text(`Amount must be at least ${frappe.format(minAmount, {fieldtype: 'Currency'})}`);
                                isValid = false;
                            }
                        }
                    }
            }
        }

        if (step === 5) {
            // Payment method validation
            return validateStep5();
        }

        // Standard validation for other steps
        if (step === 1) {
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
            const requiredFields = ['address_line1', 'city', 'postal_code', 'country'];
            requiredFields.forEach(function(field) {
                const input = $(`#${field}`);
                if (!input.val().trim()) {
                    markFieldInvalid(input, `${field.replace('_', ' ')} is required`);
                    isValid = false;
                }
            });
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
                    ${formData.uses_custom_amount ? '<p><em>Custom contribution selected</em></p>' : ''}
                </div>
            </div>
        `;

        if ($('#selected_chapter').val()) {
            content += `<p><strong>Chapter:</strong> ${$('#selected_chapter option:selected').text()}</p>`;
        }

        if ($('#interested_in_volunteering').is(':checked')) {
            content += `<p><strong>Interested in volunteering:</strong> Yes</p>`;
        }

        if (selectedPaymentMethod) {
            content += `<p><strong>Payment Method:</strong> ${selectedPaymentMethod}</p>`;
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
        $btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i> Processing...');

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
            payment_method: selectedPaymentMethod,

            // Additional
            additional_notes: $('#additional_notes').val(),
            terms: $('#terms').is(':checked'),
            gdpr_consent: $('#gdpr_consent').is(':checked')
        };

        // Submit application
        frappe.call({
            method: 'verenigingen.api.membership_application.submit_application',
            args: { data: applicationData },
            callback: function(r) {
                if (r.message && r.message.success) {
                    // Show success message and redirect
                    const successUrl = `/application-success?id=${r.message.member_id}`;
                    
                    // Show success animation
                    $('.membership-application-form').html(`
                        <div class="text-center py-5">
                            <div class="success-icon mb-4">
                                <i class="fa fa-check-circle text-success" style="font-size: 4rem;"></i>
                            </div>
                            <h2 class="text-success">Application Submitted Successfully!</h2>
                            <p class="lead">Thank you for your application. You will be redirected shortly.</p>
                            <div class="mt-4">
                                <div class="spinner-border text-primary" role="status">
                                    <span class="sr-only">Loading...</span>
                                </div>
                            </div>
                        </div>
                    `);
                    
                    // Redirect after 2 seconds
                    setTimeout(() => {
                        window.location.href = successUrl;
                    }, 2000);
                } else {
                    frappe.msgprint({
                        title: 'Application Error',
                        message: r.message || 'An error occurred. Please try again.',
                        indicator: 'red'
                    });
                    $btn.prop('disabled', false).html('Submit Application & Pay');
                }
            },
            error: function(r) {
                console.error('Application submission error:', r);
                frappe.msgprint({
                    title: 'Submission Failed',
                    message: 'An error occurred while submitting your application. Please try again.',
                    indicator: 'red'
                });
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
        if (!birthDate) return 0;
        
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

    // Auto-save functionality (optional)
    let autoSaveTimer;
    function autoSaveForm() {
        clearTimeout(autoSaveTimer);
        autoSaveTimer = setTimeout(() => {
            const draftData = {
                step: currentStep,
                formData: formData,
                selectedPaymentMethod: selectedPaymentMethod,
                // Add other form values as needed
            };
            
            frappe.call({
                method: 'verenigingen.api.membership_application.save_draft_application',
                args: { data: draftData },
                callback: function(r) {
                    if (r.message && r.message.success) {
                        console.log('Form auto-saved');
                    }
                }
            });
        }, 30000); // Auto-save every 30 seconds
    }

    // Bind auto-save to form changes
    $('#membership-application-form').on('change input', function() {
        autoSaveForm();
    });

    // Email validation on blur
    $('#email').on('blur', function() {
        const email = $(this).val();
        if (email && isValidEmail(email)) {
            frappe.call({
                method: 'verenigingen.api.membership_application.validate_email',
                args: { email: email },
                callback: function(r) {
                    if (r.message) {
                        if (!r.message.valid) {
                            markFieldInvalid($('#email'), r.message.message);
                        } else {
                            $('#email').removeClass('is-invalid');
                            $('#email').siblings('.invalid-feedback').hide();
                        }
                    }
                }
            });
        }
    });

    // Initialize first step
    showStep(1);

    // Add loading states
    function showLoading(element) {
        element.addClass('loading');
    }

    function hideLoading(element) {
        element.removeClass('loading');
    }

    // Keyboard navigation
    $(document).keydown(function(e) {
        if (e.ctrlKey || e.metaKey) return; // Allow Ctrl shortcuts
        
        switch(e.which) {
            case 37: // Left arrow
                if (currentStep > 1) {
                    $('#prev-btn').click();
                }
                break;
            case 39: // Right arrow
                if (currentStep < maxSteps) {
                    $('#next-btn').click();
                }
                break;
            case 13: // Enter
                if (currentStep === maxSteps) {
                    $('#submit-btn').click();
                } else {
                    $('#next-btn').click();
                }
                e.preventDefault();
                break;
        }
    });
});

function validateStep5() {
    console.log('Validating step 5');
    let isValid = true;
    
    // Clear all previous validation messages
    $('.invalid-feedback').remove();
    $('.is-invalid').removeClass('is-invalid');
    $('.is-valid').removeClass('is-valid');
    
    // Payment method validation - check both interfaces
    const selectedFromDropdown = $('#payment_method').val();
    const selectedFromCards = selectedPaymentMethod;
    const formDataMethod = formData.payment_method;
    
    console.log('Payment method validation:', {
        dropdown: selectedFromDropdown,
        cards: selectedFromCards,
        formData: formDataMethod
    });
    
    const finalSelection = selectedFromDropdown || selectedFromCards || formDataMethod;
    
    if (!finalSelection) {
        console.log('No payment method selected - showing error');
        if ($('#payment-method-fallback').is(':visible')) {
            const select = $('#payment_method');
            select.addClass('is-invalid');
            select.after('<div class="invalid-feedback">Please select a payment method</div>');
        } else {
            // Show error for card interface
            const errorDiv = $('<div class="invalid-feedback d-block text-danger mb-3">Please select a payment method</div>');
            $('#payment-methods-list').after(errorDiv);
        }
        isValid = false;
    } else {
        // Store the selection and mark as valid
        selectedPaymentMethod = finalSelection;
        formData.payment_method = finalSelection;
        
        if ($('#payment-method-fallback').is(':visible')) {
            $('#payment_method').addClass('is-valid').removeClass('is-invalid');
        }
        
        console.log('Payment method validated:', finalSelection);
    }

    // Terms validation
    const termsChecked = $('#terms').is(':checked');
    if (!termsChecked) {
        console.log('Terms not accepted');
        const termsLabel = $('label[for="terms"]');
        termsLabel.after('<div class="invalid-feedback d-block">You must accept the terms and conditions</div>');
        $('#terms').addClass('is-invalid');
        isValid = false;
    } else {
        $('#terms').addClass('is-valid').removeClass('is-invalid');
    }

    // GDPR consent validation
    const gdprChecked = $('#gdpr_consent').is(':checked');
    if (!gdprChecked) {
        console.log('GDPR consent not given');
        const gdprLabel = $('label[for="gdpr_consent"]');
        gdprLabel.after('<div class="invalid-feedback d-block">You must consent to data processing</div>');
        $('#gdpr_consent').addClass('is-invalid');
        isValid = false;
    } else {
        $('#gdpr_consent').addClass('is-valid').removeClass('is-invalid');
    }

    console.log('Step 5 validation result:', isValid);
    return isValid;
}


    $('#membership-application-form').off('submit').on('submit', function(e) {
        e.preventDefault();
        console.log('Form submission triggered');
        
        // Force validation of step 5 before submission
        if (!validateStep5()) {
            console.log('Step 5 validation failed - stopping submission');
            
            // Show user-friendly error
            frappe.msgprint({
                title: 'Form Incomplete',
                message: 'Please complete all required fields before submitting.',
                indicator: 'orange'
            });
            return false;
        }

        const $btn = $('#submit-btn');
        $btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i> Processing...');

        // Collect all form data
        const applicationData = collectFormData();
        console.log('Collected application data:', applicationData);

        // Final validation of critical data
        const criticalErrors = [];
        if (!applicationData.selected_membership_type) {
            criticalErrors.push('Membership type is missing');
        }
        if (!applicationData.payment_method) {
            criticalErrors.push('Payment method is missing');
        }
        if (!applicationData.first_name || !applicationData.last_name) {
            criticalErrors.push('Name is missing');
        }
        if (!applicationData.email) {
            criticalErrors.push('Email is missing');
        }

        if (criticalErrors.length > 0) {
            console.error('Critical validation errors:', criticalErrors);
            frappe.msgprint({
                title: 'Form Error',
                message: 'Missing required information: ' + criticalErrors.join(', '),
                indicator: 'red'
            });
            $btn.prop('disabled', false).html('Submit Application & Pay');
            return false;
        }

        // Submit application
        frappe.call({
            method: 'verenigingen.api.membership_application.submit_application',
            args: { data: applicationData },
            callback: function(r) {
                console.log('API response:', r);
                if (r.message && r.message.success) {
                    handleSubmissionSuccess(r.message);
                } else {
                    handleSubmissionError(r.message || 'Unknown error occurred');
                    $btn.prop('disabled', false).html('Submit Application & Pay');
                }
            },
            error: function(r) {
                console.error('Application submission error:', r);
                handleSubmissionError('Network error occurred. Please check your connection and try again.');
                $btn.prop('disabled', false).html('Submit Application & Pay');
            }
        });
    });
}

const validationCSS = `
<style>
.is-valid {
    border-color: #28a745;
}

.is-invalid {
    border-color: #dc3545;
}

.invalid-feedback {
    display: block !important;
    color: #dc3545;
    font-size: 0.875rem;
    margin-top: 0.25rem;
}

.invalid-feedback.d-block {
    display: block !important;
}

.text-danger {
    color: #dc3545 !important;
}
</style>
`;

// Inject the CSS
$('head').append(validationCSS);
