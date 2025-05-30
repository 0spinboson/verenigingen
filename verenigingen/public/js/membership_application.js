frappe.ready(function() {
    // Initialize the membership application form
    const MembershipApplication = {
        currentStep: 1,
        totalSteps: 5,
        formData: {},
        settings: {},
        
        init: function() {
            this.loadFormData();
            this.bindEvents();
            this.setupValidation();
        },
        
        loadFormData: function() {
            console.log('Loading form data...');
            // Load form data (membership types, chapters, etc.)
            frappe.call({
                method: 'verenigingen.api.membership_application.get_application_form_data',
                callback: (r) => {
                    console.log('Form data response:', r);
                    if (r.message) {
                        this.populateFormOptions(r.message);
                    } else {
                        console.error('No data in response');
                        this.loadFallbackData();
                    }
                },
                error: (r) => {
                    console.error('Error loading form data:', r);
                    this.loadFallbackData();
                }
            });
        },
        
        loadFallbackData: function() {
            console.log('Loading fallback data...');
            // Load basic countries as fallback
            const fallbackCountries = [
                {name: 'Netherlands'}, {name: 'Germany'}, {name: 'Belgium'}, 
                {name: 'France'}, {name: 'United Kingdom'}, {name: 'Other'}
            ];
            
            this.populateFormOptions({
                countries: fallbackCountries,
                membership_types: [],
                chapters: [],
                volunteer_areas: []
            });
        },
        
        populateFormOptions: function(data) {
            console.log('Populating form options with data:', data);
            
            // Populate countries
            this.populateCountries(data.countries || []);
            
            // Populate membership types
            this.populateMembershipTypes(data.membership_types || []);
            
            // Populate chapters
            this.populateChapters(data.chapters || []);
            
            // Populate volunteer areas
            this.populateVolunteerAreas(data.volunteer_areas || []);
        },
        
        populateCountries: function(countries) {
            console.log('Populating countries:', countries.length);
            const countrySelect = $('#country');
            if (countrySelect.length === 0) {
                console.error('Country select not found');
                return;
            }
            
            countrySelect.empty().append('<option value="">Select Country...</option>');
            
            // Add Netherlands at the top
            countrySelect.append('<option value="Netherlands">Netherlands</option>');
            
            // Add other countries
            countries.forEach(country => {
                if (country.name !== 'Netherlands') {
                    countrySelect.append(`<option value="${country.name}">${country.name}</option>`);
                }
            });
            
            console.log('Countries populated successfully');
        },
        
        populateMembershipTypes: function(membershipTypes) {
            console.log('Populating membership types:', membershipTypes.length);
            const container = $('#membership-types');
            if (container.length === 0) {
                console.error('Membership types container not found');
                return;
            }
            
            container.empty();
            
            membershipTypes.forEach(type => {
                // Format currency properly
                const formattedAmount = this.formatCurrency(type.amount, type.currency);
                
                const card = $(`
                    <div class="membership-type-card" data-type="${type.name}" data-amount="${type.amount}">
                        <h5>${type.membership_type_name}</h5>
                        <div class="price">${formattedAmount}</div>
                        <div class="period">${type.subscription_period}</div>
                        <div class="description">${type.description || ''}</div>
                    </div>
                `);
                
                card.click(() => {
                    $('.membership-type-card').removeClass('selected');
                    card.addClass('selected');
                    this.formData.selected_membership_type = type.name;
                    this.showMembershipFeeDetails(type);
                });
                
                container.append(card);
            });
            
            console.log('Membership types populated successfully');
        },
        
        populateChapters: function(chapters) {
            console.log('Populating chapters:', chapters.length);
            const chapterSelect = $('#selected_chapter');
            if (chapterSelect.length === 0) {
                console.log('Chapter select not found - might be disabled');
                return;
            }
            
            chapterSelect.empty().append('<option value="">Select a chapter...</option>');
            
            chapters.forEach(chapter => {
                chapterSelect.append(`<option value="${chapter.name}">${chapter.name}${chapter.region ? ' - ' + chapter.region : ''}</option>`);
            });
            
            console.log('Chapters populated successfully');
        },
        
        populateVolunteerAreas: function(volunteerAreas) {
            console.log('Populating volunteer areas:', volunteerAreas.length);
            const container = $('#volunteer-interests');
            if (container.length === 0) {
                console.log('Volunteer interests container not found');
                return;
            }
            
            container.empty();
            
            volunteerAreas.forEach(area => {
                const safeId = area.name.replace(/\s+/g, '_').replace(/[^a-zA-Z0-9_]/g, '');
                const checkbox = $(`
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" value="${area.name}" id="interest_${safeId}">
                        <label class="form-check-label" for="interest_${safeId}">
                            ${area.name}
                        </label>
                    </div>
                `);
                container.append(checkbox);
            });
            
            console.log('Volunteer areas populated successfully');
        },
        
        formatCurrency: function(amount, currency = 'EUR') {
            // Simple currency formatting - replace with proper Frappe formatting if available
            if (typeof amount === 'undefined' || amount === null) return '';
            
            const formatted = parseFloat(amount).toFixed(2);
            return `${currency} ${formatted}`;
        },
        
        showMembershipFeeDetails: function(type) {
            console.log('Showing fee details for:', type);
            
            const feeDisplay = $('#membership-fee-display');
            const feeDetails = $('#fee-details');
            
            if (feeDisplay.length && feeDetails.length) {
                const formattedAmount = this.formatCurrency(type.amount, type.currency);
                feeDetails.html(
                    `<strong>${type.membership_type_name}</strong><br>` +
                    `Amount: ${formattedAmount}<br>` +
                    `Billing: ${type.subscription_period}`
                );
                feeDisplay.show();
            }
        },
        
        bindEvents: function() {
            console.log('Binding events...');
            
            // Navigation buttons
            $('#next-btn').click(() => this.nextStep());
            $('#prev-btn').click(() => this.prevStep());
            $('#submit-btn').click((e) => {
                e.preventDefault();
                this.submitApplication();
            });
            
            // Birth date validation
            $('#birth_date').change((e) => {
                this.validateBirthDate(e.target.value);
            });
            
            // Email validation
            $('#email').blur((e) => {
                this.validateEmail(e.target.value);
            });
            
            // Postal code chapter suggestion
            $('#postal_code').blur(() => {
                const postalCode = $('#postal_code').val();
                const country = $('#country').val();
                if (postalCode && country) {
                    this.validatePostalCode(postalCode, country);
                }
            });
            
            // Volunteer interest toggle
            $('#interested_in_volunteering').change(function() {
                $('#volunteer-details').toggle(this.checked);
            });
            
            // Application source change
            $('#application_source').change(function() {
                $('#source-details-container').toggle($(this).val() === 'Other');
            });
            
            console.log('Events bound successfully');
        },
        
        setupValidation: function() {
            console.log('Setting up validation...');
            const form = document.getElementById('membership-application-form');
            if (form) {
                form.classList.add('needs-validation');
                form.setAttribute('novalidate', true);
            }
        },
        
        validateBirthDate: function(birthDate) {
            if (!birthDate) return;
            
            frappe.call({
                method: 'verenigingen.api.membership_application.validate_birth_date',
                args: { birth_date: birthDate },
                callback: (r) => {
                    console.log('Birth date validation:', r);
                    if (r.message) {
                        const birthField = $('#birth_date');
                        const warningDiv = $('#age-warning');
                        
                        if (r.message.valid) {
                            birthField.removeClass('is-invalid');
                            if (r.message.message && r.message.message.length > 0) {
                                // Show warning but field is still valid
                                warningDiv.show().text(r.message.message);
                            } else {
                                warningDiv.hide();
                            }
                        } else {
                            birthField.addClass('is-invalid');
                            birthField.siblings('.invalid-feedback').text(r.message.message);
                            warningDiv.hide();
                        }
                    }
                }
            });
        },
        
        validateEmail: function(email) {
            if (!email) return;
            
            frappe.call({
                method: 'verenigingen.api.membership_application.validate_email',
                args: { email: email },
                callback: (r) => {
                    console.log('Email validation:', r);
                    if (r.message) {
                        const emailField = $('#email');
                        if (r.message.valid) {
                            emailField.removeClass('is-invalid');
                        } else {
                            emailField.addClass('is-invalid');
                            emailField.siblings('.invalid-feedback').text(r.message.message);
                        }
                    }
                }
            });
        },
        
        validatePostalCode: function(postalCode, country) {
            frappe.call({
                method: 'verenigingen.api.membership_application.validate_postal_code',
                args: {
                    postal_code: postalCode,
                    country: country
                },
                callback: (r) => {
                    console.log('Postal code validation:', r);
                    if (r.message && r.message.valid) {
                        if (r.message.suggested_chapters && r.message.suggested_chapters.length > 0) {
                            this.showSuggestedChapters(r.message.suggested_chapters);
                        }
                    }
                }
            });
        },
        
        showSuggestedChapters: function(chapters) {
            console.log('Showing suggested chapters:', chapters);
            
            const suggestion = $('#suggested-chapter');
            const chapterName = $('#suggested-chapter-name');
            
            if (chapters.length > 0 && suggestion.length && chapterName.length) {
                chapterName.text(chapters[0].name);
                suggestion.show();
                
                $('#accept-suggestion').off('click').on('click', () => {
                    $('#selected_chapter').val(chapters[0].name);
                    suggestion.hide();
                });
            }
        },
        
        validateCurrentStep: function() {
            const currentStepDiv = $(`.form-step[data-step="${this.currentStep}"]`);
            const requiredFields = currentStepDiv.find('[required]');
            let isValid = true;
            
            requiredFields.each(function() {
                const field = $(this);
                if (!this.checkValidity() || !field.val()) {
                    field.addClass('is-invalid');
                    isValid = false;
                } else {
                    field.removeClass('is-invalid');
                }
            });
            
            // Special validation for step 3 (membership type selection)
            if (this.currentStep === 3) {
                if ($('.membership-type-card.selected').length === 0) {
                    $('#membership-type-error').show().text('Please select a membership type');
                    isValid = false;
                } else {
                    $('#membership-type-error').hide();
                }
            }
            
            // Special validation for step 5 (terms acceptance)
            if (this.currentStep === 5) {
                if (!$('#terms').is(':checked')) {
                    $('#terms').addClass('is-invalid');
                    isValid = false;
                }
            }
            
            return isValid;
        },
        
        nextStep: function() {
            console.log('Moving to next step from', this.currentStep);
            
            if (!this.validateCurrentStep()) {
                console.log('Validation failed for step', this.currentStep);
                return;
            }
            
            this.saveStepData();
            
            if (this.currentStep < this.totalSteps) {
                this.currentStep++;
                this.updateStepDisplay();
            }
        },
        
        prevStep: function() {
            console.log('Moving to previous step from', this.currentStep);
            
            if (this.currentStep > 1) {
                this.currentStep--;
                this.updateStepDisplay();
            }
        },
        
        updateStepDisplay: function() {
            console.log('Updating display for step', this.currentStep);
            
            // Hide all steps
            $('.form-step').hide();
            
            // Show current step
            $(`.form-step[data-step="${this.currentStep}"]`).show();
            
            // Update progress bar
            const progress = (this.currentStep / this.totalSteps) * 100;
            $('#form-progress').css('width', progress + '%');
            
            // Update step indicators
            $('.progress-steps .step').removeClass('active');
            $(`.progress-steps .step[data-step="${this.currentStep}"]`).addClass('active');
            
            // Show/hide navigation buttons
            $('#prev-btn').toggle(this.currentStep > 1);
            $('#next-btn').toggle(this.currentStep < this.totalSteps);
            $('#submit-btn').toggle(this.currentStep === this.totalSteps);
            
            // Update summary on last step
            if (this.currentStep === this.totalSteps) {
                this.updateApplicationSummary();
            }
        },
        
        saveStepData: function() {
            console.log('Saving data for step', this.currentStep);
            
            const currentStepDiv = $(`.form-step[data-step="${this.currentStep}"]`);
            
            // Save all input values
            currentStepDiv.find('input, select, textarea').each((i, element) => {
                const $element = $(element);
                const name = $element.attr('name');
                
                if (name) {
                    if ($element.attr('type') === 'checkbox') {
                        if (name.endsWith('[]')) {
                            // Handle checkbox arrays
                            if (!this.formData[name]) {
                                this.formData[name] = [];
                            }
                            if ($element.is(':checked') && !this.formData[name].includes($element.val())) {
                                this.formData[name].push($element.val());
                            }
                        } else {
                            this.formData[name] = $element.is(':checked');
                        }
                    } else if ($element.attr('type') === 'radio') {
                        if ($element.is(':checked')) {
                            this.formData[name] = $element.val();
                        }
                    } else {
                        this.formData[name] = $element.val();
                    }
                }
            });
            
            console.log('Form data after step', this.currentStep, ':', this.formData);
        },
        
        updateApplicationSummary: function() {
            console.log('Updating application summary');
            
            const summary = `
                <table class="table table-sm">
                    <tr>
                        <td><strong>Name:</strong></td>
                        <td>${this.formData.first_name || ''} ${this.formData.middle_name || ''} ${this.formData.last_name || ''}</td>
                    </tr>
                    <tr>
                        <td><strong>Email:</strong></td>
                        <td>${this.formData.email || ''}</td>
                    </tr>
                    <tr>
                        <td><strong>Membership Type:</strong></td>
                        <td>${this.formData.selected_membership_type || 'Not selected'}</td>
                    </tr>
                    <tr>
                        <td><strong>Chapter:</strong></td>
                        <td>${this.formData.selected_chapter || 'Auto-assign based on location'}</td>
                    </tr>
                    <tr>
                        <td><strong>Volunteer Interest:</strong></td>
                        <td>${this.formData.interested_in_volunteering ? 'Yes' : 'No'}</td>
                    </tr>
                </table>
            `;
            $('#application-summary').html(summary);
        },
        
        submitApplication: function() {
            console.log('Submitting application...');
            
            // Final validation
            if (!this.validateCurrentStep()) {
                console.log('Final validation failed');
                return;
            }
            
            // Save final step data
            this.saveStepData();
            
            // Disable submit button
            $('#submit-btn').prop('disabled', true).text('Processing...');
            
            console.log('Final form data:', this.formData);
            
            // Submit to server
            frappe.call({
                method: 'verenigingen.api.membership_application.submit_application',
                args: {
                    data: this.formData
                },
                callback: (r) => {
                    console.log('Submission response:', r);
                    if (r.message && r.message.success) {
                        // Show success message
                        alert('Application submitted successfully! ' + r.message.message);
                        // You can redirect or show a success page here
                    } else {
                        alert(r.message?.message || 'An error occurred. Please try again.');
                        $('#submit-btn').prop('disabled', false).text('Submit Application');
                    }
                },
                error: (r) => {
                    console.error('Submission error:', r);
                    alert('An error occurred. Please try again.');
                    $('#submit-btn').prop('disabled', false).text('Submit Application');
                }
            });
        }
    };
    
    // Initialize the application
    MembershipApplication.init();
});
