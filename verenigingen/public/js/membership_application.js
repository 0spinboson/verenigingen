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
            // Load form data (membership types, chapters, etc.)
            frappe.call({
                method: 'verenigingen.api.membership_application.get_application_form_data',
                callback: (r) => {
                    if (r.message && r.message.success) {
                        this.settings = r.message.settings;
                        this.populateFormOptions(r.message);
                    } else {
                        frappe.msgprint(__('Error loading form data. Please refresh the page.'));
                    }
                }
            });
        },
        
        populateFormOptions: function(data) {
            // Populate countries
            const countrySelect = $('#country');
            countrySelect.empty().append('<option value="">Select Country...</option>');
            data.countries.forEach(country => {
                countrySelect.append(`<option value="${country.name}">${country.name}</option>`);
            });
            // Set default country if available
            if (data.settings.default_country) {
                countrySelect.val(data.settings.default_country);
            }
            
            // Populate chapters if enabled
            if (data.settings.enable_chapter_management && data.chapters.length > 0) {
                $('#chapter-selection').show();
                const chapterSelect = $('#selected_chapter');
                chapterSelect.empty().append('<option value="">Select a chapter...</option>');
                data.chapters.forEach(chapter => {
                    chapterSelect.append(`<option value="${chapter.name}">${chapter.name}${chapter.region ? ' - ' + chapter.region : ''}</option>`);
                });
            }
            
            // Populate membership types
            const membershipTypesDiv = $('#membership-types');
            membershipTypesDiv.empty();
            data.membership_types.forEach(type => {
                const card = `
                    <div class="membership-type-card" data-type="${type.name}" data-amount="${type.amount}">
                        <h5>${type.membership_type_name}</h5>
                        <p class="mb-2">${type.description || ''}</p>
                        <p class="mb-0"><strong>${frappe.format(type.amount, {fieldtype: 'Currency'})} / ${this.getPeriodText(type)}</strong></p>
                    </div>
                `;
                membershipTypesDiv.append(card);
            });
            
            // Populate volunteer interest areas
            const volunteerInterestsDiv = $('#volunteer-interests');
            volunteerInterestsDiv.empty();
            data.volunteer_areas.forEach(area => {
                const checkbox = `
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" name="volunteer_interests[]" 
                               value="${area.name}" id="interest_${area.name.replace(/\s+/g, '_')}">
                        <label class="form-check-label" for="interest_${area.name.replace(/\s+/g, '_')}">
                            ${area.name}
                        </label>
                    </div>
                `;
                volunteerInterestsDiv.append(checkbox);
            });
            
            // Populate payment methods
            const paymentSelect = $('#payment_method');
            paymentSelect.empty().append('<option value="">Select payment method...</option>');
            data.payment_methods.forEach(method => {
                paymentSelect.append(`<option value="${method.name}">${method.name}</option>`);
            });
        },
        
        getPeriodText: function(membershipType) {
            if (membershipType.subscription_period === 'Custom' && membershipType.subscription_period_in_months) {
                return `${membershipType.subscription_period_in_months} months`;
            }
            return membershipType.subscription_period.toLowerCase();
        },
        
        bindEvents: function() {
            // Navigation buttons
            $('#next-btn').click(() => this.nextStep());
            $('#prev-btn').click(() => this.prevStep());
            $('#submit-btn').click((e) => {
                e.preventDefault();
                this.submitApplication();
            });
            
            // Birth date validation
            $('#birth_date').change((e) => {
                this.validateAge(e.target.value);
            });
            
            // Email validation
            $('#email').blur((e) => {
                this.validateEmail(e.target.value);
            });
            
            // Postal code chapter suggestion
            $('#postal_code').blur(() => {
                if ($('#postal_code').val() && this.settings.enable_chapter_management) {
                    this.suggestChapter();
                }
            });
            
            // Membership type selection
            $(document).on('click', '.membership-type-card', function() {
                $('.membership-type-card').removeClass('selected');
                $(this).addClass('selected');
                const amount = $(this).data('amount');
                const type = $(this).data('type');
                $('#membership-fee-display').show();
                $('#fee-details').html(`Amount: ${frappe.format(amount, {fieldtype: 'Currency'})}`);
            });
            
            // Volunteer interest toggle
            $('#interested_in_volunteering').change(function() {
                $('#volunteer-details').toggle(this.checked);
            });
            
            // Add skill row
            $(document).on('click', '.add-skill', () => {
                this.addSkillRow();
            });
            
            // Remove skill row
            $(document).on('click', '.remove-skill', function() {
                $(this).closest('.skill-row').remove();
            });
            
            // Application source change
            $('#application_source').change(function() {
                $('#source-details-container').toggle($(this).val() === 'Other');
            });
            
            // Accept chapter suggestion
            $('#accept-suggestion').click(() => {
                const suggestedChapter = $('#suggested-chapter-name').text();
                $('#selected_chapter').val(suggestedChapter);
                $('#suggested-chapter').hide();
            });
        },
        
        setupValidation: function() {
            // Add Bootstrap validation classes
            const form = document.getElementById('membership-application-form');
            form.classList.add('needs-validation');
            form.setAttribute('novalidate', true);
        },
        
        validateAge: function(birthDate) {
            if (!birthDate) return;
            
            frappe.call({
                method: 'verenigingen.api.membership_application.validate_birth_date',
                args: { birth_date: birthDate },
                callback: (r) => {
                    if (r.message) {
                        if (r.message.warning) {
                            $('#age-warning').show().text(r.message.message);
                        } else {
                            $('#age-warning').hide();
                        }
                        
                        if (!r.message.success) {
                            $('#birth_date').addClass('is-invalid');
                            $('#birth_date').siblings('.invalid-feedback').text(r.message.message);
                        } else {
                            $('#birth_date').removeClass('is-invalid');
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
                    if (r.message) {
                        if (r.message.exists) {
                            $('#email').addClass('is-invalid');
                            $('#email').siblings('.invalid-feedback').text(r.message.message);
                        } else {
                            $('#email').removeClass('is-invalid');
                        }
                    }
                }
            });
        },
        
        suggestChapter: function() {
            const postalCode = $('#postal_code').val();
            const city = $('#city').val();
            const country = $('#country').val();
            
            frappe.call({
                method: 'verenigingen.api.membership_application.suggest_chapter',
                args: {
                    postal_code: postalCode,
                    city: city,
                    country: country
                },
                callback: (r) => {
                    if (r.message && r.message.success && r.message.suggested_chapter) {
                        $('#suggested-chapter').show();
                        $('#suggested-chapter-name').text(r.message.suggested_chapter.name);
                    }
                }
            });
        },
        
        addSkillRow: function() {
            const skillRow = `
                <div class="skill-row mb-2">
                    <div class="row">
                        <div class="col-md-6">
                            <input type="text" class="form-control" placeholder="Skill name" name="skill_name[]">
                        </div>
                        <div class="col-md-4">
                            <select class="form-control" name="skill_level[]">
                                <option value="">Level</option>
                                <option value="Beginner">Beginner</option>
                                <option value="Intermediate">Intermediate</option>
                                <option value="Advanced">Advanced</option>
                                <option value="Expert">Expert</option>
                            </select>
                        </div>
                        <div class="col-md-2">
                            <button type="button" class="btn btn-sm btn-danger remove-skill">-</button>
                        </div>
                    </div>
                </div>
            `;
            $('#volunteer-skills').append(skillRow);
        },
        
        validateCurrentStep: function() {
            const currentStepDiv = $(`.form-step[data-step="${this.currentStep}"]`);
            const requiredFields = currentStepDiv.find('[required]');
            let isValid = true;
            
            requiredFields.each(function() {
                if (!this.checkValidity()) {
                    $(this).addClass('is-invalid');
                    isValid = false;
                } else {
                    $(this).removeClass('is-invalid');
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
            if (!this.validateCurrentStep()) {
                frappe.msgprint(__('Please fill in all required fields'));
                return;
            }
            
            // Save current step data
            this.saveStepData();
            
            if (this.currentStep < this.totalSteps) {
                this.currentStep++;
                this.updateStepDisplay();
            }
        },
        
        prevStep: function() {
            if (this.currentStep > 1) {
                this.currentStep--;
                this.updateStepDisplay();
            }
        },
        
        updateStepDisplay: function() {
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
            
            // Save selected membership type
            if (this.currentStep === 3) {
                const selectedType = $('.membership-type-card.selected');
                if (selectedType.length) {
                    this.formData.selected_membership_type = selectedType.data('type');
                }
            }
            
            // Process skills array
            if (this.currentStep === 4) {
                const skills = [];
                $('.skill-row').each(function() {
                    const skillName = $(this).find('input[name="skill_name[]"]').val();
                    const skillLevel = $(this).find('select[name="skill_level[]"]').val();
                    if (skillName) {
                        skills.push({
                            skill_name: skillName,
                            proficiency_level: skillLevel || 'Beginner'
                        });
                    }
                });
                this.formData.volunteer_skills = skills;
            }
        },
        
        updateApplicationSummary: function() {
            const summary = `
                <table class="table table-sm">
                    <tr>
                        <td><strong>Name:</strong></td>
                        <td>${this.formData.first_name} ${this.formData.middle_name || ''} ${this.formData.last_name}</td>
                    </tr>
                    <tr>
                        <td><strong>Email:</strong></td>
                        <td>${this.formData.email}</td>
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
            // Final validation
            if (!this.validateCurrentStep()) {
                frappe.msgprint(__('Please fill in all required fields'));
                return;
            }
            
            // Save final step data
            this.saveStepData();
            
            // Disable submit button
            $('#submit-btn').prop('disabled', true).text('Processing...');
            
            // Submit to server
            frappe.call({
                method: 'verenigingen.api.membership_application.submit_application',
                args: {
                    data: this.formData
                },
                callback: (r) => {
                    if (r.message && r.message.success) {
                        // Redirect to payment page
                        if (r.message.payment_url) {
                            window.location.href = r.message.payment_url;
                        } else {
                            // Show success message
                            frappe.msgprint({
                                title: __('Application Submitted'),
                                message: r.message.message,
                                primary_action: {
                                    label: __('OK'),
                                    action: () => {
                                        window.location.href = '/';
                                    }
                                }
                            });
                        }
                    } else {
                        frappe.msgprint(r.message.message || __('An error occurred. Please try again.'));
                        $('#submit-btn').prop('disabled', false).text('Submit Application & Pay');
                    }
                },
                error: () => {
                    frappe.msgprint(__('An error occurred. Please try again.'));
                    $('#submit-btn').prop('disabled', false).text('Submit Application & Pay');
                }
            });
        }
    };
    
    // Initialize the application
    MembershipApplication.init();
});
(document).ready(function() {
    // Load form data when page loads
    loadFormData();
});

function loadFormData() {
    frappe.call({
        method: 'verenigingen.api.membership_application.get_application_form_data',
        callback: function(r) {
            if (r.message) {
                populateCountries(r.message.countries);
                populateMembershipTypes(r.message.membership_types);
                populateChapters(r.message.chapters);
                populateVolunteerAreas(r.message.volunteer_areas);
            }
        },
        error: function(r) {
            console.error('Error loading form data:', r);
            // Fallback - load countries manually
            loadCountriesFallback();
        }
    });
}

function populateCountries(countries) {
    const countrySelect = $('#country');
    countrySelect.empty();
    countrySelect.append('<option value="">Select Country...</option>');
    
    // Add Netherlands at the top (assuming it's your primary country)
    countrySelect.append('<option value="Netherlands">Netherlands</option>');
    
    // Add other countries
    countries.forEach(function(country) {
        if (country.name !== 'Netherlands') {
            countrySelect.append(`<option value="${country.name}">${country.name}</option>`);
        }
    });
}

function loadCountriesFallback() {
    // Fallback list of common European countries if API fails
    const commonCountries = [
        'Netherlands',
        'Germany', 
        'Belgium',
        'France',
        'United Kingdom',
        'Spain',
        'Italy',
        'Austria',
        'Switzerland',
        'Denmark',
        'Sweden',
        'Norway',
        'Finland',
        'Poland',
        'Other'
    ];
    
    const countrySelect = $('#country');
    countrySelect.empty();
    countrySelect.append('<option value="">Select Country...</option>');
    
    commonCountries.forEach(function(country) {
        countrySelect.append(`<option value="${country}">${country}</option>`);
    });
}

function populateMembershipTypes(membershipTypes) {
    const container = $('#membership-types');
    container.empty();
    
    membershipTypes.forEach(function(type) {
        const card = $(`
            <div class="membership-type-card" data-type="${type.name}">
                <h5>${type.membership_type_name}</h5>
                <div class="price">${frappe.format_currency(type.amount, type.currency)}</div>
                <div class="period">${type.subscription_period}</div>
                <div class="description">${type.description || ''}</div>
            </div>
        `);
        
        card.click(function() {
            $('.membership-type-card').removeClass('selected');
            $(this).addClass('selected');
            $('#selected_membership_type').val(type.name);
            showMembershipFeeDetails(type);
        });
        
        container.append(card);
    });
}

function populateChapters(chapters) {
    const chapterSelect = $('#selected_chapter');
    chapterSelect.empty();
    chapterSelect.append('<option value="">Select a chapter...</option>');
    
    chapters.forEach(function(chapter) {
        chapterSelect.append(`<option value="${chapter.name}">${chapter.name} - ${chapter.region}</option>`);
    });
}

function populateVolunteerAreas(volunteerAreas) {
    const container = $('#volunteer-interests');
    container.empty();
    
    volunteerAreas.forEach(function(area) {
        const checkbox = $(`
            <div class="form-check">
                <input class="form-check-input" type="checkbox" value="${area.name}" id="interest_${area.name}">
                <label class="form-check-label" for="interest_${area.name}">
                    ${area.name}
                </label>
            </div>
        `);
        container.append(checkbox);
    });
}

// Postal code validation with chapter suggestion
$('#postal_code').on('blur', function() {
    const postalCode = $(this).val();
    const country = $('#country').val();
    
    if (postalCode && country) {
        frappe.call({
            method: 'verenigingen.api.membership_application.validate_postal_code',
            args: {
                postal_code: postalCode,
                country: country
            },
            callback: function(r) {
                if (r.message && r.message.valid) {
                    if (r.message.suggested_chapters && r.message.suggested_chapters.length > 0) {
                        showSuggestedChapters(r.message.suggested_chapters);
                    }
                }
            }
        });
    }
});

function showSuggestedChapters(chapters) {
    const suggestion = $('#suggested-chapter');
    const chapterName = $('#suggested-chapter-name');
    
    if (chapters.length > 0) {
        chapterName.text(chapters[0].name);
        suggestion.show();
        
        $('#accept-suggestion').off('click').on('click', function() {
            $('#selected_chapter').val(chapters[0].name);
            suggestion.hide();
        });
    }
}
