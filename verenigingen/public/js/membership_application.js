$(document).ready(function() {
    // ========================================
    // GLOBAL VARIABLES - Fixed Scope Issues
    // ========================================
    
    // Make variables persistent and accessible throughout the application
    window.membershipApp = {
        currentStep: 1,
        maxSteps: 5,
        formData: {},
        membershipTypes: [],
        paymentMethods: [],
        selectedPaymentMethod: null,
        
        // Helper methods for consistent access
        setPaymentMethod: function(method) {
            this.selectedPaymentMethod = method;
            this.formData.payment_method = method;
            console.log('Payment method set to:', method);
        },
        
        getPaymentMethod: function() {
            return this.selectedPaymentMethod || this.formData.payment_method || $('#payment_method').val();
        },
        
        debug: function() {
            console.log('=== MEMBERSHIP APP DEBUG ===');
            console.log('Current step:', this.currentStep);
            console.log('Selected payment method:', this.selectedPaymentMethod);
            console.log('Form data payment method:', this.formData.payment_method);
            console.log('Dropdown value:', $('#payment_method').val());
            console.log('============================');
        }
    };
    
    // Create shortcuts for backward compatibility
    let currentStep = window.membershipApp.currentStep;
    let maxSteps = window.membershipApp.maxSteps;
    let formData = window.membershipApp.formData;
    let membershipTypes = window.membershipApp.membershipTypes;
    let paymentMethods = window.membershipApp.paymentMethods;
    
    console.log('Membership application initialized');
    
    // ========================================
    // INITIALIZATION
    // ========================================
    
    loadFormData();

    function loadFormData() {
        frappe.call({
            method: 'verenigingen.api.membership_application.get_application_form_data',
            callback: function(r) {
                if (r.message) {
                    window.membershipApp.membershipTypes = r.message.membership_types;
                    membershipTypes = window.membershipApp.membershipTypes; // Update reference
                    
                    renderMembershipTypes();
                    loadCountries(r.message.countries);
                    loadVolunteerAreas(r.message.volunteer_areas);
                    loadChapters(r.message.chapters);
                    loadPaymentMethods();
                }
            }
        });
    }

    // ========================================
    // MEMBERSHIP TYPE HANDLING
    // ========================================

    function renderMembershipTypes() {
        const container = $('#membership-types');
        container.empty();

        // Get detailed information for each membership type
        const loadPromises = window.membershipApp.membershipTypes.map(type => {
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

                // Build the card HTML using string concatenation to avoid nested template literal issues
                let cardHTML = '<div class="membership-type-card" data-type="' + type.name + '" data-amount="' + type.amount + '">';
                cardHTML += '<h5>' + type.membership_type_name + '</h5>';
                cardHTML += '<div class="membership-price">';
                cardHTML += frappe.format(type.amount, {fieldtype: 'Currency'}) + ' / ' + type.subscription_period;
                cardHTML += '</div>';
                cardHTML += '<p class="membership-description">' + (type.description || '') + '</p>';
                
                // Add custom amount section if allowed
                if (type.allow_custom_amount) {
                    cardHTML += '<div class="custom-amount-section" style="display: none;">';
                    cardHTML += '<label>Choose Your Contribution:</label>';
                    cardHTML += '<div class="amount-suggestion-pills">';
                    
                    if (type.suggested_amounts && type.suggested_amounts.length > 0) {
                        type.suggested_amounts.forEach(function(suggestion) {
                            cardHTML += '<span class="amount-pill" data-amount="' + suggestion.amount + '">';
                            cardHTML += frappe.format(suggestion.amount, {fieldtype: 'Currency'});
                            cardHTML += '<br><small>' + suggestion.label + '</small>';
                            cardHTML += '</span>';
                        });
                    }
                    
                    cardHTML += '</div>';
                    cardHTML += '<div class="mt-3">';
                    cardHTML += '<label>Or enter custom amount:</label>';
                    cardHTML += '<input type="number" class="form-control custom-amount-input" ';
                    cardHTML += 'min="' + type.minimum_amount + '" step="0.01" placeholder="Enter amount">';
                    cardHTML += '<small class="text-muted">Minimum: ' + frappe.format(type.minimum_amount, {fieldtype: 'Currency'}) + '</small>';
                    cardHTML += '</div>';
                    cardHTML += '</div>';
                }
                
                // Add button group
                cardHTML += '<div class="btn-group mt-3">';
                cardHTML += '<button type="button" class="btn btn-primary select-membership">';
                cardHTML += 'Select' + (type.allow_custom_amount ? ' Standard' : '');
                cardHTML += '</button>';
                
                if (type.allow_custom_amount) {
                    cardHTML += '<button type="button" class="btn btn-outline-secondary toggle-custom">';
                    cardHTML += 'Choose Amount';
                    cardHTML += '</button>';
                }
                cardHTML += '</div>';
                
                // Add note if custom amounts are allowed
                if (type.allow_custom_amount && type.custom_amount_note) {
                    cardHTML += '<div class="mt-2">';
                    cardHTML += '<small class="text-muted">' + type.custom_amount_note + '</small>';
                    cardHTML += '</div>';
                }
                
                cardHTML += '</div>';
                
                const card = $(cardHTML);
                container.append(card);
            });

            bindMembershipTypeEvents();
        });
    }

    function bindMembershipTypeEvents() {
        // Standard selection
        $('.select-membership').off('click').on('click', function() {
            const card = $(this).closest('.membership-type-card');
            selectMembershipType(card, false);
        });

        // Toggle custom amount section
        $('.toggle-custom').off('click').on('click', function() {
            const card = $(this).closest('.membership-type-card');
            const customSection = card.find('.custom-amount-section');
            const button = $(this);

            if (customSection.is(':visible')) {
                customSection.hide();
                button.text('Choose Amount');
                card.find('.custom-amount-input').val('');
                card.find('.amount-pill').removeClass('selected');
            } else {
                $('.custom-amount-section').hide();
                $('.toggle-custom').text('Choose Amount');
                
                customSection.show();
                button.text('Standard Amount');
                
                const standardAmount = card.data('amount');
                card.find(`.amount-pill[data-amount="${standardAmount}"]`).addClass('selected');
            }
        });

        // Amount pill selection
        $(document).off('click', '.amount-pill').on('click', '.amount-pill', function() {
            const card = $(this).closest('.membership-type-card');
            const amount = $(this).data('amount');
            
            card.find('.amount-pill').removeClass('selected');
            $(this).addClass('selected');
            
            card.find('.custom-amount-input').val(amount);
            selectMembershipType(card, true, amount);
        });

        // Custom amount input
        $('.custom-amount-input').off('input blur').on('input blur', function() {
            const card = $(this).closest('.membership-type-card');
            const amount = parseFloat($(this).val());
            const minAmount = parseFloat($(this).attr('min'));

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

        $('.membership-type-card').removeClass('selected');
        card.addClass('selected');

        // Store in app state
        window.membershipApp.formData.selected_membership_type = membershipType;
        window.membershipApp.formData.membership_amount = finalAmount;
        window.membershipApp.formData.uses_custom_amount = isCustom && (customAmount !== standardAmount);

        updateMembershipFeeDisplay();
        $('#membership-type-error').hide();

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
        const formData = window.membershipApp.formData;

        if (formData.selected_membership_type && formData.membership_amount) {
            const membershipType = window.membershipApp.membershipTypes.find(t => t.name === formData.selected_membership_type);
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
                content += '<strong>Standard Amount:</strong> ' + frappe.format(membershipType.amount, {fieldtype: 'Currency'}) + '<br>';
                content += '<strong>Your Contribution:</strong> ';
                content += '<span class="' + (difference > 0 ? 'text-success' : 'text-warning') + '">';
                content += (difference > 0 ? '+' : '') + frappe.format(difference, {fieldtype: 'Currency'}) + ' ';
                content += '(' + (percentageDiff > 0 ? '+' : '') + percentageDiff + '%)';
                content += '</span>';
            } else {
                content += '<em>Standard membership amount</em>';
            }

            content += `</div></div>`;
            details.html(content);
            display.show();
        } else {
            display.hide();
        }
    }

    // ========================================
    // PAYMENT METHOD HANDLING - FIXED
    // ========================================

    function loadPaymentMethods() {
        const container = $('#payment-methods-list');
        const fallback = $('#payment-method-fallback');
        
        container.html('<div class="text-center p-4"><i class="fa fa-spinner fa-spin"></i> Loading payment methods...</div>');
        
        frappe.call({
            method: 'verenigingen.api.membership_application.get_payment_methods',
            callback: function(r) {
                if (r.message && r.message.payment_methods && r.message.payment_methods.length > 0) {
                    window.membershipApp.paymentMethods = r.message.payment_methods;
                    paymentMethods = window.membershipApp.paymentMethods; // Update reference
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
    
        if (!window.membershipApp.paymentMethods || window.membershipApp.paymentMethods.length === 0) {
            showPaymentMethodFallback();
            return;
        }
    
        window.membershipApp.paymentMethods.forEach(function(method) {
            // Build payment method card HTML using string concatenation
            let methodCardHTML = '<div class="payment-method-option" data-method="' + method.name + '">';
            methodCardHTML += '<div class="d-flex align-items-center">';
            methodCardHTML += '<div class="payment-method-icon">';
            methodCardHTML += '<i class="fa ' + (method.icon || 'fa-credit-card') + '"></i>';
            methodCardHTML += '</div>';
            methodCardHTML += '<div class="payment-method-info flex-grow-1">';
            methodCardHTML += '<h6>' + method.name + '</h6>';
            methodCardHTML += '<div class="text-muted">';
            methodCardHTML += method.description + '<br>';
            methodCardHTML += '<small><strong>Processing:</strong> ' + method.processing_time + '</small>';
            
            if (method.requires_mandate) {
                methodCardHTML += '<br><small class="text-warning"><strong>Note:</strong> ' + method.note + '</small>';
            }
            
            methodCardHTML += '</div>';
            methodCardHTML += '</div>';
            methodCardHTML += '<div class="payment-method-selector">';
            methodCardHTML += '<div class="form-check">';
            
            const radioId = 'payment_' + method.name.replace(/\s+/g, '_').toLowerCase();
            methodCardHTML += '<input class="form-check-input payment-method-radio" type="radio" ';
            methodCardHTML += 'name="payment_method_selection" value="' + method.name + '" id="' + radioId + '">';
            methodCardHTML += '<label class="form-check-label" for="' + radioId + '">';
            methodCardHTML += 'Select';
            methodCardHTML += '</label>';
            methodCardHTML += '</div>';
            methodCardHTML += '</div>';
            methodCardHTML += '</div>';
            methodCardHTML += '</div>';
            
            const methodCard = $(methodCardHTML);
            container.append(methodCard);
        });
    
        // Bind payment method selection with proper scope
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
        if (window.membershipApp.paymentMethods.length > 0) {
            selectPaymentMethod(window.membershipApp.paymentMethods[0].name);
        }
    }

    function selectPaymentMethod(methodName) {
        if (!methodName) return;
        
        // Use the app state to store payment method
        window.membershipApp.setPaymentMethod(methodName);
        
        console.log('Selected payment method:', methodName);
        
        // Update UI
        if ($('#payment-method-fallback').is(':visible')) {
            const select = $('#payment_method');
            select.val(methodName);
            select.removeClass('is-invalid').addClass('is-valid');
        } else {
            $('.payment-method-option').removeClass('selected');
            $(`.payment-method-option[data-method="${methodName}"]`).addClass('selected');
            $(`.payment-method-radio[value="${methodName}"]`).prop('checked', true);
        }
        
        // Show method details
        const method = window.membershipApp.paymentMethods.find(m => m.name === methodName);
        if (method) {
            showPaymentMethodDetails(method);
        }
        
        // Show/hide SEPA mandate notice
        if (methodName === 'Direct Debit') {
            $('#sepa-mandate-notice').show();
        } else {
            $('#sepa-mandate-notice').hide();
        }
        
        console.log('Payment method selection complete:', methodName);
    }

    function showPaymentMethodDetails(method) {
        const detailsContainer = $('#payment-method-details');
        const contentContainer = $('#payment-details-content');
        
        // Build content HTML using string concatenation
        let content = '<div class="selected-method-info">';
        content += '<div class="d-flex align-items-center mb-2">';
        content += '<i class="fa ' + (method.icon || 'fa-credit-card') + ' me-2"></i>';
        content += '<strong>' + method.name + '</strong>';
        content += '</div>';
        content += '<p class="mb-2">' + method.description + '</p>';
        content += '<div class="method-details">';
        content += '<small><strong>Processing Time:</strong> ' + method.processing_time + '</small>';
        content += '</div>';
        
        if (method.requires_mandate) {
            content += '<div class="alert alert-info mt-2 mb-0">';
            content += '<small><i class="fa fa-info-circle"></i> ' + method.note + '</small>';
            content += '</div>';
        }
        
        content += '</div>';
        
        contentContainer.html(content);
        detailsContainer.show();
    }

    function showPaymentMethodFallback() {
        console.log('Showing payment method fallback');
        const container = $('#payment-methods-list');
        const fallback = $('#payment-method-fallback');
        
        container.hide();
        fallback.show();
        
        const select = $('#payment_method');
        select.empty();
        
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
        
        // Store fallback methods
        window.membershipApp.paymentMethods = fallbackMethods;
        paymentMethods = fallbackMethods; // Update reference
        
        fallbackMethods.forEach(function(method) {
            select.append(`<option value="${method.name}">${method.name} - ${method.description}</option>`);
        });
        
        // Bind change event
        select.off('change').on('change', function() {
            const selectedMethod = $(this).val();
            console.log('Dropdown changed to:', selectedMethod);
            if (selectedMethod) {
                selectPaymentMethod(selectedMethod);
            }
        });
        
        // Auto-select first option
        if (fallbackMethods.length > 0) {
            const defaultMethod = fallbackMethods[0].name;
            select.val(defaultMethod);
            selectPaymentMethod(defaultMethod);
            console.log('Auto-selected payment method:', defaultMethod);
        }
    }

    // ========================================
    // OTHER LOADING FUNCTIONS
    // ========================================

    function loadCountries(countries) {
        const select = $('#country');
        select.empty().append('<option value="">Select Country...</option>');
        
        countries.forEach(function(country) {
            select.append(`<option value="${country.name}">${country.name}</option>`);
        });
        
        select.val('Netherlands');
    }

    function loadVolunteerAreas(areas) {
        const container = $('#volunteer-interests');
        container.empty();
        
        areas.forEach(function(area) {
            // Build checkbox HTML using string concatenation
            const checkboxId = 'interest_' + area.name.replace(/\s+/g, '_');
            let checkboxHTML = '<div class="form-check">';
            checkboxHTML += '<input class="form-check-input" type="checkbox" ';
            checkboxHTML += 'value="' + area.name + '" id="' + checkboxId + '">';
            checkboxHTML += '<label class="form-check-label" for="' + checkboxId + '">';
            checkboxHTML += area.name;
            
            if (area.description) {
                checkboxHTML += '<small class="text-muted d-block">' + area.description + '</small>';
            }
            
            checkboxHTML += '</label>';
            checkboxHTML += '</div>';
            
            const checkbox = $(checkboxHTML);
            container.append(checkbox);
        });
    }

    function loadChapters(chapters) {
        const select = $('#selected_chapter');
        select.empty().append('<option value="">Select a chapter...</option>');
        
        chapters.forEach(function(chapter) {
            select.append(`<option value="${chapter.name}">${chapter.name} - ${chapter.region}</option>`);
        });
        
        if (chapters.length > 0) {
            $('#chapter-selection').show();
        }
    }

    // ========================================
    // STEP NAVIGATION - FIXED
    // ========================================

    $('#next-btn').off('click').on('click', function() {
        if (validateCurrentStep()) {
            if (window.membershipApp.currentStep < window.membershipApp.maxSteps) {
                window.membershipApp.currentStep++;
                currentStep = window.membershipApp.currentStep; // Update reference
                showStep(window.membershipApp.currentStep);
            }
        }
    });

    $('#prev-btn').off('click').on('click', function() {
        if (window.membershipApp.currentStep > 1) {
            window.membershipApp.currentStep--;
            currentStep = window.membershipApp.currentStep; // Update reference
            showStep(window.membershipApp.currentStep);
        }
    });

    function showStep(step) {
        // Update app state
        window.membershipApp.currentStep = step;
        
        // Hide all steps
        $('.form-step').hide().removeClass('active');
        
        // Show current step
        $(`.form-step[data-step="${step}"]`).show().addClass('active');
        
        // Update progress bar
        const progress = (step / window.membershipApp.maxSteps) * 100;
        $('#form-progress').css('width', progress + '%');
        
        // Update step indicators
        $('.step').removeClass('active completed');
        for (let i = 1; i < step; i++) {
            $(`.step[data-step="${i}"]`).addClass('completed');
        }
        $(`.step[data-step="${step}"]`).addClass('active');
        
        // Update navigation buttons
        $('#prev-btn').toggle(step > 1);
        $('#next-btn').toggle(step < window.membershipApp.maxSteps);
        $('#submit-btn').toggle(step === window.membershipApp.maxSteps);

        // Step-specific actions
        if (step === 2) {
            $('#postal_code').off('blur').on('blur', function() {
                suggestChapterFromPostalCode($(this).val());
            });
        }

        if (step === 4) {
            $('#interested_in_volunteering').off('change').on('change', function() {
                $('#volunteer-details').toggle($(this).is(':checked'));
            });

            $('#application_source').off('change').on('change', function() {
                $('#source-details-container').toggle($(this).val() === 'Other');
            });
        }

        if (step === 5) {
            console.log('Initializing step 5');
            
            // Clear validation errors
            $('.invalid-feedback').remove();
            $('.is-invalid').removeClass('is-invalid');
            
            // Load payment methods if needed
            if (!window.membershipApp.paymentMethods || window.membershipApp.paymentMethods.length === 0) {
                console.log('Loading payment methods for step 5');
                loadPaymentMethods();
            }
            
            updateApplicationSummary();
            initializeFormSubmission();
        }

        if (step === window.membershipApp.maxSteps) {
            updateApplicationSummary();
        }
    }

    // ========================================
    // VALIDATION - FIXED
    // ========================================

    function validateCurrentStep() {
        const step = window.membershipApp.currentStep;
        let isValid = true;
        
        // Clear previous validation
        $('.is-invalid').removeClass('is-invalid');
        $('.invalid-feedback').hide();
        
        if (step === 5) {
            return validateStep5();
        }

        if (step === 3) {
            if (!window.membershipApp.formData.selected_membership_type) {
                $('#membership-type-error').show().text('Please select a membership type');
                isValid = false;
            } else {
                $('#membership-type-error').hide();
            }
            
            if (window.membershipApp.formData.uses_custom_amount && window.membershipApp.formData.membership_amount) {
                const membershipType = window.membershipApp.membershipTypes.find(t => t.name === window.membershipApp.formData.selected_membership_type);
                if (membershipType) {
                    const minAmount = membershipType.amount * 0.5;
                    if (window.membershipApp.formData.membership_amount < minAmount) {
                        $('#membership-type-error').show().text(`Amount must be at least ${frappe.format(minAmount, {fieldtype: 'Currency'})}`);
                        isValid = false;
                    }
                }
            }
        }

        if (step === 1) {
            const requiredFields = ['first_name', 'last_name', 'email', 'birth_date'];
            requiredFields.forEach(function(field) {
                const input = $(`#${field}`);
                if (!input.val().trim()) {
                    markFieldInvalid(input, `${field.replace('_', ' ')} is required`);
                    isValid = false;
                }
            });

            const email = $('#email').val();
            if (email && !isValidEmail(email)) {
                markFieldInvalid($('#email'), 'Please enter a valid email address');
                isValid = false;
            }

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

    function validateStep5() {
        console.log('Validating step 5');
        let isValid = true;
        
        // Clear previous validation
        $('.invalid-feedback').remove();
        $('.is-invalid').removeClass('is-invalid');
        $('.is-valid').removeClass('is-valid');
        
        // Get payment method using app state
        const finalSelection = window.membershipApp.getPaymentMethod();
        
        console.log('Payment method validation:', {
            appState: window.membershipApp.selectedPaymentMethod,
            formData: window.membershipApp.formData.payment_method,
            dropdown: $('#payment_method').val(),
            final: finalSelection
        });
        
        if (!finalSelection) {
            console.log('No payment method selected - showing error');
            if ($('#payment-method-fallback').is(':visible')) {
                const select = $('#payment_method');
                select.addClass('is-invalid');
                select.after('<div class="invalid-feedback">Please select a payment method</div>');
            } else {
                const errorDiv = $('<div class="invalid-feedback d-block text-danger mb-3">Please select a payment method</div>');
                $('#payment-methods-list').after(errorDiv);
            }
            isValid = false;
        } else {
            // Store the selection
            window.membershipApp.setPaymentMethod(finalSelection);
            
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

    function markFieldInvalid(field, message) {
        field.addClass('is-invalid');
        let feedback = field.siblings('.invalid-feedback');
        if (feedback.length === 0) {
            feedback = $('<div class="invalid-feedback"></div>');
            field.after(feedback);
        }
        feedback.text(message).show();
    }

    // ========================================
    // FORM SUBMISSION - FIXED
    // ========================================

    function initializeFormSubmission() {
        $('#membership-application-form').off('submit').on('submit', function(e) {
            e.preventDefault();
            console.log('Form submission triggered');
            
            if (!validateStep5()) {
                console.log('Step 5 validation failed - stopping submission');
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

    function collectFormData() {
        // Use app state for payment method
        const paymentMethod = window.membershipApp.getPaymentMethod();
        
        console.log('Collecting form data with payment method:', paymentMethod);
        
        const applicationData = {
            // Personal info
            first_name: $('#first_name').val() || '',
            middle_name: $('#middle_name').val() || '',
            last_name: $('#last_name').val() || '',
            email: $('#email').val() || '',
            mobile_no: $('#mobile_no').val() || '',
            phone: $('#phone').val() || '',
            birth_date: $('#birth_date').val() || '',
            pronouns: $('#pronouns').val() || '',

            // Address
            address_line1: $('#address_line1').val() || '',
            address_line2: $('#address_line2').val() || '',
            city: $('#city').val() || '',
            state: $('#state').val() || '',
            postal_code: $('#postal_code').val() || '',
            country: $('#country').val() || '',

            // Membership
            selected_membership_type: window.membershipApp.formData.selected_membership_type || '',
            membership_amount: window.membershipApp.formData.membership_amount || 0,
            uses_custom_amount: window.membershipApp.formData.uses_custom_amount || false,
            selected_chapter: $('#selected_chapter').val() || '',

            // Volunteer
            interested_in_volunteering: $('#interested_in_volunteering').is(':checked'),
            volunteer_availability: $('#volunteer_availability').val() || '',
            volunteer_experience_level: $('#volunteer_experience_level').val() || '',
            volunteer_interests: getSelectedVolunteerInterests(),

            // Communication
            newsletter_opt_in: $('#newsletter_opt_in').is(':checked'),
            application_source: $('#application_source').val() || '',
            application_source_details: $('#application_source_details').val() || '',

            // Payment - ensure we have this
            payment_method: paymentMethod,

            // Additional
            additional_notes: $('#additional_notes').val() || '',
            terms: $('#terms').is(':checked'),
            gdpr_consent: $('#gdpr_consent').is(':checked')
        };

        return applicationData;
    }

    function handleSubmissionSuccess(response) {
        // Build success HTML using string concatenation
        let successHTML = '<div class="text-center py-5">';
        successHTML += '<div class="success-icon mb-4">';
        successHTML += '<i class="fa fa-check-circle text-success" style="font-size: 4rem;"></i>';
        successHTML += '</div>';
        successHTML += '<h2 class="text-success">Application Submitted Successfully!</h2>';
        successHTML += '<p class="lead">Thank you for your application. You will be redirected to complete payment.</p>';
        successHTML += '<div class="mt-4">';
        successHTML += '<div class="spinner-border text-primary" role="status">';
        successHTML += '<span class="sr-only">Loading...</span>';
        successHTML += '</div>';
        successHTML += '</div>';
        successHTML += '</div>';
        
        $('.membership-application-form').html(successHTML);
        
        // Redirect after 2 seconds
        setTimeout(() => {
            window.location.href = response.payment_url || `/application-success?id=${response.member_id}`;
        }, 2000);
    }

    function handleSubmissionError(error) {
        const errorMsg = typeof error === 'string' ? error : (error.message || 'An error occurred');
        
        frappe.msgprint({
            title: 'Application Error',
            message: errorMsg,
            indicator: 'red'
        });
    }

    // ========================================
    // HELPER FUNCTIONS
    // ========================================

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
        const formData = window.membershipApp.formData;
        
        // Build summary HTML using string concatenation
        let content = '<div class="row">';
        content += '<div class="col-md-6">';
        content += '<h6>Personal Information</h6>';
        content += '<p><strong>Name:</strong> ' + $('#first_name').val() + ' ' + $('#last_name').val() + '</p>';
        content += '<p><strong>Email:</strong> ' + $('#email').val() + '</p>';
        content += '<p><strong>Age:</strong> ' + calculateAge($('#birth_date').val()) + ' years</p>';
        content += '</div>';
        content += '<div class="col-md-6">';
        content += '<h6>Membership</h6>';
        content += '<p><strong>Type:</strong> ' + getMembershipTypeName(formData.selected_membership_type) + '</p>';
        content += '<p><strong>Amount:</strong> ' + frappe.format(formData.membership_amount, {fieldtype: 'Currency'}) + '</p>';
        
        if (formData.uses_custom_amount) {
            content += '<p><em>Custom contribution selected</em></p>';
        }
        
        content += '</div>';
        content += '</div>';

        if ($('#selected_chapter').val()) {
            content += '<p><strong>Chapter:</strong> ' + $('#selected_chapter option:selected').text() + '</p>';
        }

        if ($('#interested_in_volunteering').is(':checked')) {
            content += '<p><strong>Interested in volunteering:</strong> Yes</p>';
        }

        const paymentMethod = window.membershipApp.getPaymentMethod();
        if (paymentMethod) {
            content += '<p><strong>Payment Method:</strong> ' + paymentMethod + '</p>';
        }

        summary.html(content);
    }

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
        const type = window.membershipApp.membershipTypes.find(t => t.name === typeId);
        return type ? type.membership_type_name : typeId;
    }

    function getSelectedVolunteerInterests() {
        const interests = [];
        $('#volunteer-interests input[type="checkbox"]:checked').each(function() {
            interests.push($(this).val());
        });
        return interests;
    }

    // ========================================
    // ADDITIONAL FEATURES
    // ========================================

    // Auto-save functionality
    let autoSaveTimer;
    function autoSaveForm() {
        clearTimeout(autoSaveTimer);
        autoSaveTimer = setTimeout(() => {
            const draftData = {
                step: window.membershipApp.currentStep,
                formData: window.membershipApp.formData,
                selectedPaymentMethod: window.membershipApp.selectedPaymentMethod,
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

    // ========================================
    // KEYBOARD NAVIGATION
    // ========================================

    $(document).keydown(function(e) {
        if (e.ctrlKey || e.metaKey) return; // Allow Ctrl shortcuts
        
        switch(e.which) {
            case 37: // Left arrow
                if (window.membershipApp.currentStep > 1) {
                    $('#prev-btn').click();
                }
                break;
            case 39: // Right arrow
                if (window.membershipApp.currentStep < window.membershipApp.maxSteps) {
                    $('#next-btn').click();
                }
                break;
            case 13: // Enter
                if (window.membershipApp.currentStep === window.membershipApp.maxSteps) {
                    $('#submit-btn').click();
                } else {
                    $('#next-btn').click();
                }
                e.preventDefault();
                break;
        }
    });

    // ========================================
    // DEBUGGING FUNCTIONS
    // ========================================

    // Global debug function
    window.debugMembershipApp = function() {
        console.log('=== MEMBERSHIP APP DEBUG ===');
        console.log('App state:', window.membershipApp);
        console.log('Current step:', window.membershipApp.currentStep);
        console.log('Selected payment method:', window.membershipApp.selectedPaymentMethod);
        console.log('Form data:', window.membershipApp.formData);
        console.log('Payment methods available:', window.membershipApp.paymentMethods);
        console.log('============================');
        return window.membershipApp;
    };

    // Initialize the application
    console.log('Membership application JavaScript loaded successfully');
    showStep(1);

    // Add loading states
    function showLoading(element) {
        element.addClass('loading');
    }

    function hideLoading(element) {
        element.removeClass('loading');
    }

    // ========================================
    // CSS FOR VALIDATION STATES
    // ========================================

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

    .loading {
        position: relative;
        pointer-events: none;
    }

    .loading::after {
        content: '';
        position: absolute;
        top: 50%;
        left: 50%;
        width: 20px;
        height: 20px;
        margin: -10px 0 0 -10px;
        border: 2px solid #f3f3f3;
        border-top: 2px solid #007bff;
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }

    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    </style>
    `;

    // Inject the CSS if not already present
    if (!$('#membership-app-styles').length) {
        $('head').append(validationCSS);
        $('head').append('<meta id="membership-app-styles" />');
    }
});
