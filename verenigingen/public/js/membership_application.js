/**
 * Refactored Membership Application JavaScript
 * Uses modular components and services for better maintainability
 */

// Form Validator class - needed by BaseStep
class FormValidator {
    validateRequired(selector) {
        const element = $(selector);
        const value = element.val()?.trim();
        
        if (!value) {
            this.showError(selector, 'This field is required');
            return false;
        }
        
        this.showSuccess(selector);
        return true;
    }
    
    showError(selector, message) {
        const element = $(selector);
        element.addClass('is-invalid').removeClass('is-valid');
        
        let feedback = element.siblings('.invalid-feedback');
        if (feedback.length === 0) {
            feedback = $('<div class="invalid-feedback"></div>');
            element.after(feedback);
        }
        feedback.text(message).show();
    }
    
    showSuccess(selector) {
        const element = $(selector);
        element.addClass('is-valid').removeClass('is-invalid');
        element.siblings('.invalid-feedback').hide();
    }
}

// Base class for step components
class BaseStep {
    constructor(stepId) {
        this.stepId = stepId;
        this.validator = new FormValidator();
    }

    render(state) {
        // Override in subclasses
    }

    bindEvents() {
        // Override in subclasses
    }

    async validate() {
        // Override in subclasses
        return true;
    }

    getData() {
        // Override in subclasses
        return {};
    }
}

class MembershipApplication {
    constructor(config = {}) {
        this.config = {
            maxSteps: 5,
            autoSaveInterval: 30000,
            enableErrorHandling: true,
            enableAutoSave: true,
            ...config
        };
        
        // Wait for service classes to be available, then initialize
        this._initializeServices();
        
        // Legacy state for compatibility
        this.state = new ApplicationState();
        this.membershipTypes = [];
        this.paymentMethod = '';
        
        this.init();
    }
    
    _initializeServices() {
        // Initialize services when available
        if (typeof APIService !== 'undefined') {
            this.apiService = new APIService({
                timeout: 30000,
                retryCount: 3
            });
        } else {
            this.apiService = new MembershipAPI();
        }
        
        if (typeof ValidationService !== 'undefined') {
            this.validationService = new ValidationService(this.apiService);
        }
        
        if (typeof StorageService !== 'undefined') {
            this.storageService = new StorageService(this.apiService, {
                autoSaveInterval: this.config.autoSaveInterval
            });
        }
        
        if (typeof ErrorHandler !== 'undefined') {
            this.errorHandler = new ErrorHandler({
                enableLogging: true,
                enableUserFeedback: true
            });
        }
        
        if (typeof StepManager !== 'undefined' && this.validationService && this.storageService) {
            this.stepManager = new StepManager(
                this.validationService,
                this.storageService,
                {
                    totalSteps: this.config.maxSteps,
                    autoSave: this.config.enableAutoSave
                }
            );
        }
    }
    
    async init() {
        try {
            console.log('Initializing refactored membership application...');
            
            // Load initial data
            await this.loadInitialData();
            
            // Set up validation for form fields
            this.setupFieldValidation();
            
            // Bind events
            this.bindEvents();
            
            // Start auto-save if enabled
            if (this.config.enableAutoSave) {
                this.storageService.startAutoSave(() => this.getAllFormData());
            }
            
            // Try to load any existing draft
            await this.loadExistingDraft();
            
            console.log('Refactored membership application initialized successfully');
        } catch (error) {
            console.error('Failed to initialize application:', error);
            this.errorHandler.handleError(error, { context: 'initialization' });
        }
    }
    
    async loadInitialData() {
        try {
            console.log('Loading form data...');
            const data = await this.apiService.getFormData();
            
            // Store in both legacy state and new format
            this.state.setInitialData(data);
            this.membershipTypes = data.membership_types || [];
            
            console.log('Form data loaded:', data);
            
            // Load static data into form fields
            this.loadStaticData(data);
            
        } catch (error) {
            console.error('Failed to load initial data:', error);
            this.errorHandler.handleAPIError(error, 'get_application_form_data');
            throw error;
        }
    }
    
    loadStaticData(data) {
        // Load countries into address step
        const countries = data.countries || this.state.get('countries');
        if (countries && countries.length > 0) {
            const select = $('#country');
            if (select.length && select.children().length <= 1) {
                select.empty().append('<option value="">Select Country...</option>');
                
                countries.forEach(country => {
                    select.append(`<option value="${country.name}">${country.name}</option>`);
                });
                
                // Set Netherlands as default
                select.val('Netherlands');
            }
        }
        
        // Load chapters if available
        const chapters = data.chapters || this.state.get('chapters');
        if (chapters && chapters.length > 0) {
            const select = $('#selected_chapter');
            if (select.length && select.children().length <= 1) {
                select.empty().append('<option value="">Select a chapter...</option>');
                
                chapters.forEach(chapter => {
                    const displayText = chapter.region ? `${chapter.name} - ${chapter.region}` : chapter.name;
                    select.append(`<option value="${chapter.name}">${displayText}</option>`);
                });
                
                // Show chapter selection section if chapters are available
                if (chapters.length > 0) {
                    $('#chapter-selection').show();
                }
            }
        }
        
        // Load membership types
        this.loadMembershipTypes(data.membership_types || []);
        
        // Load payment methods
        this.loadPaymentMethods(data.payment_methods || []);
    }
    
    bindEvents() {
        // Navigation handled by StepManager, but we can add custom handlers
        $(document).on('step:change', (event, data) => {
            this.onStepChange(data.from, data.to);
        });
        
        $(document).on('application:submit', (event, data) => {
            this.submitApplication(data);
        });
        
        // Legacy form submit handler
        $('#membership-application-form').off('submit').on('submit', (e) => {
            e.preventDefault();
            this.stepManager.submitApplication();
        });
        
        // Custom validation events
        this.bindCustomValidationEvents();
    }
    
    // Step navigation now handled by StepManager
    onStepChange(fromStep, toStep) {
        console.log(`Step changed from ${fromStep} to ${toStep}`);
        
        // Update legacy state for compatibility
        this.state.set('currentStep', toStep);
        
        // Perform step-specific setup
        this.setupStepContent(toStep);
    }
    
    setupStepContent(stepNumber) {
        switch(stepNumber) {
            case 1:
                this.setupPersonalInfoStep();
                break;
            case 2:
                this.setupAddressStep();
                break;
            case 3:
                this.setupMembershipStep();
                break;
            case 4:
                this.setupVolunteerStep();
                break;
            case 5:
                this.setupPaymentStep();
                break;
        }
    }
    
    getCurrentStep() {
        return this.stepManager.getCurrentStep();
    }
    
    // New method to get all form data
    getAllFormData() {
        const formData = {};
        
        // Get data from step manager
        const stepData = this.stepManager.getAllData();
        Object.assign(formData, stepData);
        
        // Get additional form data not handled by step manager
        const additionalData = this.getAdditionalFormData();
        Object.assign(formData, additionalData);
        
        return formData;
    }
    
    // Legacy method for compatibility
    collectAllData() {
        return this.getAllFormData();
    }
    
    getAdditionalFormData() {
        // Collect any additional form data not handled by step manager
        return {
            selected_membership_type: this.state.get('selected_membership_type') || '',
            membership_amount: this.state.get('membership_amount') || 0,
            uses_custom_amount: this.state.get('uses_custom_amount') || false,
            payment_method: this.getPaymentMethod() || ''
        };
    }
    
    // Helper methods for state management
    setPaymentMethod(method) {
        this.paymentMethod = method;
        this.state.set('payment_method', method);
        if (this.storageService) {
            this.storageService.markDirty(); // Mark for auto-save
        }
    }
    
    getPaymentMethod() {
        return this.paymentMethod || this.state.get('payment_method') || '';
    }
    
    // Auto-save now handled by StorageService
    async saveDraft() {
        try {
            const data = this.getAllFormData();
            const result = this.storageService ? await this.storageService.saveDraft(data) : { success: false, message: 'Storage service not available' };
            console.log('Draft saved:', result);
            return result;
        } catch (error) {
            console.warn('Draft save failed:', error);
            if (this.errorHandler) {
                this.errorHandler.handleError(error, { context: 'draft_save' });
            }
            return { success: false, error: error.message };
        }
    }
    
    async loadExistingDraft() {
        if (!this.storageService) return;
        
        try {
            const result = await this.storageService.loadDraft();
            if (result.success && result.data) {
                console.log('Loading existing draft:', result);
                this.populateFormWithData(result.data);
                
                // Show notification about loaded draft
                if (result.source === 'local' && this.errorHandler) {
                    this.errorHandler.showNotification('info', 'Draft Loaded', 
                        'Your previous application progress has been restored.');
                }
            }
        } catch (error) {
            console.warn('Failed to load draft:', error);
            // Don't show error to user as this is not critical
        }
    }
    
    populateFormWithData(data) {
        // Populate form fields with loaded data
        Object.entries(data).forEach(([key, value]) => {
            const $field = $(`[name="${key}"], #${key}`);
            if ($field.length) {
                if ($field.attr('type') === 'checkbox') {
                    $field.prop('checked', Boolean(value));
                } else if ($field.attr('type') === 'radio') {
                    $field.filter(`[value="${value}"]`).prop('checked', true);
                } else {
                    $field.val(value);
                }
            }
        });
        
        // Update state
        Object.entries(data).forEach(([key, value]) => {
            this.state.set(key, value);
        });
        
        // Trigger change events to update UI
        setTimeout(() => {
            $('input, select, textarea').trigger('change');
        }, 100);
    }

    // Enhanced submit method using new services
    async submitApplication(data = null) {
        console.log('Application submission started');
        
        try {
            // Get form data
            const formData = data || this.getAllFormData();
            console.log('Submitting application data:', formData);
            
            // Show loading state
            this.showSubmissionLoading(true);
            
            // Submit via API service
            const result = await this.apiService.submitApplication(formData);
            console.log('Application submitted successfully:', result);
            
            // Handle successful submission
            this.handleSubmissionSuccess(result);
            
            // Clear draft after successful submission
            if (this.storageService) {
                this.storageService.clearAllDrafts();
            }
            
            return result;
            
        } catch (error) {
            console.error('Application submission failed:', error);
            this.handleSubmissionError(error);
            throw error;
        } finally {
            this.showSubmissionLoading(false);
        }
    }
    
    handleSubmissionSuccess(result) {
        // Store application ID
        if (result.application_id && this.storageService) {
            this.storageService.setSessionData('last_application_id', result.application_id);
        }
        
        // Show success message
        this.showSuccessMessage(result);
        
        // Redirect to payment if needed
        if (result.payment_url) {
            this.redirectToPayment(result.payment_url);
        }
    }
    
    handleSubmissionError(error) {
        if (this.errorHandler) {
            this.errorHandler.handleAPIError(error, 'submit_application', {
                onRetry: () => this.submitApplication()
            });
        } else {
            console.error('Submission error:', error);
            frappe.msgprint({
                title: 'Submission Error',
                message: error.message || 'An error occurred while submitting your application',
                indicator: 'red'
            });
        }
    }
    
    showSubmissionLoading(isLoading) {
        const $submitBtn = $('#btn-submit, #submit-btn');
        if (isLoading) {
            $submitBtn.prop('disabled', true)
                     .html('<i class="fa fa-spinner fa-spin"></i> Processing...');
        } else {
            $submitBtn.prop('disabled', false)
                     .html('Submit Application');
        }
    }
    
    showSuccessMessage(result) {
        let successHTML = '<div class="text-center py-5">';
        successHTML += '<div class="success-icon mb-4">';
        successHTML += '<i class="fa fa-check-circle text-success" style="font-size: 4rem;"></i>';
        successHTML += '</div>';
        successHTML += '<h2 class="text-success">Application Submitted Successfully!</h2>';
        
        if (result.application_id) {
            successHTML += '<div class="alert alert-info mx-auto" style="max-width: 500px;">';
            successHTML += '<h4>Your Application ID: <strong>' + result.application_id + '</strong></h4>';
            successHTML += '<p>Please save this ID for future reference.</p>';
            successHTML += '</div>';
        }
        
        successHTML += '<p class="lead">Thank you for your application.</p>';
        successHTML += '</div>';
        
        $('.membership-application-form').html(successHTML);
        window.scrollTo(0, 0);
    }
    
    redirectToPayment(paymentUrl) {
        if (this.errorHandler) {
            this.errorHandler.showNotification('info', 'Redirecting to Payment', 
                'You will be redirected to complete payment in 3 seconds.');
        }
        
        setTimeout(() => {
            window.location.href = paymentUrl;
        }, 3000);
    }
    // ====================
    // NEW METHODS FOR REFACTORED SYSTEM
    // ====================
    
    setupFieldValidation() {
        // Set up real-time validation for form fields
        const fieldMappings = {
            'first_name': 'firstName',
            'last_name': 'lastName', 
            'email': 'email',
            'birth_date': 'birthDate',
            'address_line1': 'address',
            'city': 'city',
            'postal_code': 'postalCode',
            'country': 'country',
            'mobile_no': 'phone'
        };
        
        Object.entries(fieldMappings).forEach(([fieldId, validationKey]) => {
            const $field = $(`#${fieldId}`);
            if ($field.length) {
                this.validationService.setupRealTimeValidation($field[0], validationKey, {
                    country: () => $('#country').val() || 'Netherlands'
                });
            }
        });
    }
    
    bindCustomValidationEvents() {
        // Email validation on blur
        $('#email').on('blur', async () => {
            const email = $('#email').val();
            if (email) {
                try {
                    const result = await this.apiService.validateEmail(email);
                    if (!result.valid) {
                        this.errorHandler.handleValidationError('email', result);
                    }
                } catch (error) {
                    console.warn('Email validation failed:', error);
                }
            }
        });
        
        // Postal code validation with chapter suggestion
        $('#postal_code').on('blur', async () => {
            const postalCode = $('#postal_code').val();
            const country = $('#country').val() || 'Netherlands';
            
            if (postalCode) {
                try {
                    const result = await this.apiService.validatePostalCode(postalCode, country);
                    if (result.suggested_chapters && result.suggested_chapters.length > 0) {
                        this.showChapterSuggestion(result.suggested_chapters[0]);
                    }
                } catch (error) {
                    console.warn('Postal code validation failed:', error);
                }
            }
        });
    }
    
    showChapterSuggestion(chapter) {
        $('#suggested-chapter-name').text(chapter.name);
        $('#suggested-chapter').show();
        
        $('#accept-suggestion').off('click').on('click', () => {
            $('#selected_chapter').val(chapter.name);
            $('#suggested-chapter').hide();
        });
    }
    
    setupPersonalInfoStep() {
        console.log('Setting up personal info step');
        // Any specific setup for personal info step
    }
    
    setupAddressStep() {
        console.log('Setting up address step');
        // Ensure country dropdown is populated
        if ($('#country option').length <= 1) {
            const countries = this.state.get('countries');
            this.loadCountries(countries);
        }
    }
    
    setupMembershipStep() {
        console.log('Setting up membership step');
        // Ensure membership types are loaded
        if ($('.membership-type-card').length === 0) {
            this.loadMembershipTypes(this.membershipTypes);
        }
    }
    
    setupVolunteerStep() {
        console.log('Setting up volunteer step');
        // Set up volunteer interest toggle
        $('#interested_in_volunteering').off('change').on('change', function() {
            $('#volunteer-details').toggle($(this).is(':checked'));
        });
    }
    
    setupPaymentStep() {
        console.log('Setting up payment step');
        // Update summary and ensure payment methods are loaded
        this.updateApplicationSummary();
        
        if ($('.payment-method-option').length === 0) {
            const paymentMethods = this.state.get('paymentMethods');
            this.loadPaymentMethods(paymentMethods);
        }
    }
    
    loadCountries(countries) {
        if (!countries || countries.length === 0) return;
        
        const select = $('#country');
        select.empty().append('<option value="">Select Country...</option>');
        
        countries.forEach(country => {
            select.append(`<option value="${country.name}">${country.name}</option>`);
        });
        
        select.val('Netherlands');
    }
    
    loadMembershipTypes(membershipTypes) {
        if (!membershipTypes || membershipTypes.length === 0) return;
        
        const container = $('#membership-types');
        container.empty();
        
        membershipTypes.forEach(type => {
            const card = this.createMembershipCard(type);
            container.append(card);
        });
        
        this.bindMembershipEvents();
    }
    
    loadPaymentMethods(paymentMethods) {
        if (!paymentMethods || paymentMethods.length === 0) {
            this.showPaymentMethodFallback();
            return;
        }
        
        const container = $('#payment-methods-list');
        container.empty();
        
        paymentMethods.forEach(method => {
            const card = this.createPaymentMethodCard(method);
            container.append(card);
        });
        
        this.bindPaymentEvents();
    }
    
    updateApplicationSummary() {
        const summary = $('#application-summary');
        const data = this.getAllFormData();
        
        let content = '<div class="row">';
        content += '<div class="col-md-6">';
        content += '<h6>Personal Information</h6>';
        content += `<p><strong>Name:</strong> ${data.first_name || ''} ${data.last_name || ''}</p>`;
        content += `<p><strong>Email:</strong> ${data.email || ''}</p>`;
        content += '</div>';
        content += '<div class="col-md-6">';
        content += '<h6>Membership</h6>';
        
        if (data.selected_membership_type) {
            const membershipType = this.membershipTypes.find(t => t.name === data.selected_membership_type);
            if (membershipType) {
                content += `<p><strong>Type:</strong> ${membershipType.membership_type_name}</p>`;
                content += `<p><strong>Amount:</strong> ${frappe.format(data.membership_amount, {fieldtype: 'Currency'})}</p>`;
            }
        }
        
        content += '</div></div>';
        
        if (data.payment_method) {
            content += `<p><strong>Payment Method:</strong> ${data.payment_method}</p>`;
        }
        
        summary.html(content);
    }
    
    // Legacy method implementations for compatibility
    createMembershipCard(type) {
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
            cardHTML += 'min="' + (type.minimum_amount || type.amount) + '" step="0.01" placeholder="Enter amount">';
            cardHTML += '<small class="text-muted">Minimum: ' + frappe.format(type.minimum_amount || type.amount, {fieldtype: 'Currency'}) + '</small>';
            cardHTML += '</div>';
            cardHTML += '</div>';
        }
        
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
        
        if (type.allow_custom_amount && type.custom_amount_note) {
            cardHTML += '<div class="mt-2">';
            cardHTML += '<small class="text-muted">' + type.custom_amount_note + '</small>';
            cardHTML += '</div>';
        }
        
        cardHTML += '</div>';
        
        return $(cardHTML);
    }
    
    createPaymentMethodCard(method) {
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
        
        return $(methodCardHTML);
    }
    
    bindMembershipEvents() {
        console.log('Binding membership type events');
        
        // Standard selection
        $('.select-membership').off('click').on('click', (e) => {
            const card = $(e.target).closest('.membership-type-card');
            this.selectMembershipType(card, false);
        });
        
        // Toggle custom amount section
        $('.toggle-custom').off('click').on('click', (e) => {
            const card = $(e.target).closest('.membership-type-card');
            const customSection = card.find('.custom-amount-section');
            const button = $(e.target);
            
            if (customSection.is(':visible')) {
                customSection.hide();
                button.text('Choose Amount');
                card.find('.custom-amount-input').val('');
                card.find('.amount-pill').removeClass('selected');
                this.selectMembershipType(card, false);
            } else {
                $('.custom-amount-section').hide();
                $('.toggle-custom').text('Choose Amount');
                
                customSection.show();
                button.text('Standard Amount');
                
                const standardAmount = card.data('amount');
                card.find(`.amount-pill[data-amount="${standardAmount}"]`).addClass('selected');
                card.find('.custom-amount-input').val(standardAmount);
                this.selectMembershipType(card, true, standardAmount);
            }
        });
        
        // Amount pill selection
        $(document).off('click', '.amount-pill').on('click', '.amount-pill', (e) => {
            const pill = $(e.target);
            const card = pill.closest('.membership-type-card');
            const amount = parseFloat(pill.data('amount'));
            
            card.find('.amount-pill').removeClass('selected');
            pill.addClass('selected');
            card.find('.custom-amount-input').val(amount);
            
            this.selectMembershipType(card, true, amount);
        });
        
        // Custom amount input
        $('.custom-amount-input').off('input blur').on('input blur', (e) => {
            const input = $(e.target);
            const card = input.closest('.membership-type-card');
            const amount = parseFloat(input.val());
            const minAmount = parseFloat(input.attr('min'));
            
            card.find('.amount-pill').removeClass('selected');
            
            if (isNaN(amount) || amount <= 0) {
                input.addClass('is-invalid');
                input.siblings('.invalid-feedback').remove();
                input.after('<div class="invalid-feedback">Please enter a valid amount</div>');
                return;
            }
            
            if (amount < minAmount) {
                input.addClass('is-invalid');
                input.siblings('.invalid-feedback').remove();
                input.after(`<div class="invalid-feedback">Amount must be at least ${frappe.format(minAmount, {fieldtype: 'Currency'})}</div>`);
                return;
            }
            
            input.removeClass('is-invalid').addClass('is-valid');
            input.siblings('.invalid-feedback').remove();
            
            this.selectMembershipType(card, true, amount);
        });
    }
    
    selectMembershipType(card, isCustom = false, customAmount = null) {
        const membershipType = card.data('type');
        const standardAmount = parseFloat(card.data('amount'));
        let finalAmount = standardAmount;
        let usesCustomAmount = false;
        
        if (isCustom && customAmount !== null) {
            finalAmount = parseFloat(customAmount);
            usesCustomAmount = finalAmount !== standardAmount;
        }
        
        console.log('Selecting membership type:', { membershipType, finalAmount, usesCustomAmount });
        
        $('.membership-type-card').removeClass('selected');
        card.addClass('selected');
        
        // Update state - both new and legacy formats
        this.state.set('membership', {
            type: membershipType,
            amount: finalAmount,
            isCustom: usesCustomAmount
        });
        
        // Legacy compatibility
        this.state.set('selected_membership_type', membershipType);
        this.state.set('membership_amount', finalAmount);
        this.state.set('uses_custom_amount', usesCustomAmount);
        
        $('#membership-type-error').hide();
        
        if (usesCustomAmount) {
            this.validateCustomAmount(membershipType, finalAmount);
        }
    }
    
    async validateCustomAmount(membershipType, amount) {
        try {
            const result = await this.apiService.validateCustomAmount(membershipType, amount);
            if (result && !result.valid) {
                $('#membership-type-error').show().text(result.message);
            } else {
                $('#membership-type-error').hide();
            }
        } catch (error) {
            console.error('Custom amount validation error:', error);
        }
    }
    
    bindPaymentEvents() {
        $('.payment-method-option').off('click').on('click', (e) => {
            const methodName = $(e.target).closest('.payment-method-option').data('method');
            this.selectPaymentMethod(methodName);
        });
        
        $('.payment-method-radio').off('change').on('change', (e) => {
            if ($(e.target).is(':checked')) {
                this.selectPaymentMethod($(e.target).val());
            }
        });
    }
    
    selectPaymentMethod(methodName) {
        if (!methodName) return;
        
        console.log('Selecting payment method:', methodName);
        
        // Update state
        this.setPaymentMethod(methodName);
        
        // Update UI
        if ($('#payment-method-fallback').is(':visible')) {
            $('#payment_method').val(methodName);
        } else {
            $('.payment-method-option').removeClass('selected');
            $(`.payment-method-option[data-method="${methodName}"]`).addClass('selected');
            $(`.payment-method-radio[value="${methodName}"]`).prop('checked', true);
        }
        
        // Show/hide SEPA notice
        if (methodName === 'Direct Debit') {
            $('#sepa-mandate-notice').show();
        } else {
            $('#sepa-mandate-notice').hide();
        }
    }
    
    showPaymentMethodFallback() {
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
        
        fallbackMethods.forEach(method => {
            select.append(`<option value="${method.name}">${method.name} - ${method.description}</option>`);
        });
        
        // Bind change event
        select.off('change').on('change', (e) => {
            const selectedMethod = $(e.target).val();
            if (selectedMethod) {
                this.selectPaymentMethod(selectedMethod);
            }
        });
        
        // Auto-select first option
        if (fallbackMethods.length > 0) {
            const defaultMethod = fallbackMethods[0].name;
            select.val(defaultMethod);
            this.selectPaymentMethod(defaultMethod);
        }
    }
}

// ===================================
// 2. STATE MANAGEMENT (LEGACY COMPATIBILITY)
// ===================================

class ApplicationState {
    constructor() {
        this.data = {
            currentStep: 1,
            personalInfo: {},
            address: {},
            membership: {},
            volunteer: {},
            payment: {},
            // Legacy compatibility
            selected_membership_type: '',
            membership_amount: 0,
            uses_custom_amount: false
        };
        
        this.listeners = [];
    }
    
    subscribe(listener) {
        this.listeners.push(listener);
    }
    
    notify(change) {
        this.listeners.forEach(listener => {
            try {
                listener(change);
            } catch (error) {
                console.error('State listener error:', error);
            }
        });
    }
    
    set(key, value) {
        const oldValue = this.data[key];
        this.data[key] = value;
        this.notify({ key, oldValue, newValue: value });
    }
    
    get(key) {
        return this.data[key];
    }
    
    getData() {
        return { ...this.data };
    }
    
    setInitialData(data) {
        this.data.membershipTypes = data.membership_types || [];
        this.data.countries = data.countries || [];
        this.data.chapters = data.chapters || [];
        this.data.volunteerAreas = data.volunteer_areas || [];
        this.data.paymentMethods = data.payment_methods || [];
    }
    
    get currentStep() {
        return this.data.currentStep;
    }
    
    incrementStep() {
        if (this.data.currentStep < 5) {
            this.set('currentStep', this.data.currentStep + 1);
        }
    }
    
    decrementStep() {
        if (this.data.currentStep > 1) {
            this.set('currentStep', this.data.currentStep - 1);
        }
    }
}

// ===================================
// 3. UTILITY CLASSES FOR COMPATIBILITY
// ===================================

// FormValidator already defined at the top of the file

class PersonalInfoStep extends BaseStep {
    constructor() {
        super('personal-info');
    }
    
    render(state) {
        // Ensure age warning element exists
        if ($('#age-warning').length === 0) {
            $('#birth_date').after('<div id="age-warning" class="alert mt-2" style="display: none;"></div>');
        }
    }
    
    bindEvents() {
        $('#email').off('blur').on('blur', () => this.validateEmail());
        $('#birth_date').off('change blur').on('change blur', () => this.validateAge());
    }
    
    async validateEmail() {
        const email = $('#email').val();
        if (!email) return true;
        
        try {
            const result = await membershipApp.api.validateEmail(email);
            
            if (!result.valid) {
                this.validator.showError('#email', result.message);
                return false;
            }
            
            this.validator.showSuccess('#email');
            return true;
        } catch (error) {
            console.error('Email validation error:', error);
            return true; // Don't block on API errors
        }
    }
    
    validateAge() {
        const birthDate = $('#birth_date').val();
        if (!birthDate) return true;
        
        const age = this.calculateAge(birthDate);
        const warningDiv = $('#age-warning');
        
        // Clear previous states
        $('#birth_date').removeClass('is-invalid is-valid');
        $('#birth_date').siblings('.invalid-feedback').remove();
        warningDiv.hide().removeClass('alert-info alert-warning alert-danger');
        
        if (age < 0) {
            this.validator.showError('#birth_date', 'Birth date cannot be in the future');
            return false;
        }
        
        $('#birth_date').addClass('is-valid');
        
        // Show warnings for edge cases
        if (age < 12) {
            warningDiv
                .addClass('alert-info')
                .html('<i class="fa fa-info-circle"></i> Applicants under 12 may require parental consent')
                .show();
        } else if (age > 100) {
            warningDiv
                .addClass('alert-warning')
                .html(`<i class="fa fa-exclamation-triangle"></i> Please verify birth date - applicant would be ${age} years old`)
                .show();
        }
        
        return true;
    }
    
    calculateAge(birthDate) {
        if (!birthDate) return 0;
        
        const birth = new Date(birthDate);
        const today = new Date();
        
        if (isNaN(birth.getTime())) return -1;
        if (birth > today) return -1;
        
        let age = today.getFullYear() - birth.getFullYear();
        
        // FIXED: Proper birthday check
        if (today.getMonth() < birth.getMonth() || 
            (today.getMonth() === birth.getMonth() && today.getDate() < birth.getDate())) {
            age--;
        }
        
        return age;
    }
    
    async validate() {
        const fields = ['first_name', 'last_name', 'email', 'birth_date'];
        let valid = true;
        
        for (const field of fields) {
            if (!this.validator.validateRequired(`#${field}`)) {
                valid = false;
            }
        }
        
        if ($('#email').val() && !await this.validateEmail()) {
            valid = false;
        }
        
        if ($('#birth_date').val() && !this.validateAge()) {
            valid = false;
        }
        
        return valid;
    }
    
    getData() {
        return {
            first_name: $('#first_name').val() || '',
            middle_name: $('#middle_name').val() || '',
            last_name: $('#last_name').val() || '',
            email: $('#email').val() || '',
            mobile_no: $('#mobile_no').val() || '',
            phone: $('#phone').val() || '',
            birth_date: $('#birth_date').val() || '',
            pronouns: $('#pronouns').val() || ''
        };
    }
}

class AddressStep extends BaseStep {
    constructor() {
        super('address');
    }
    
    render(state) {
        // Load countries into dropdown
        if (state.get('countries')) {
            this.loadCountries(state.get('countries'));
        }
    }
    
    loadCountries(countries) {
        const select = $('#country');
        
        // Only populate if empty (avoid duplicate loading)
        if (select.children().length <= 1) {
            select.empty().append('<option value="">Select Country...</option>');
            
            countries.forEach(country => {
                select.append(`<option value="${country.name}">${country.name}</option>`);
            });
            
            // Set Netherlands as default
            select.val('Netherlands');
        }
    }
    
    bindEvents() {
        $('#postal_code').off('blur').on('blur', () => this.suggestChapter());
    }
    
    async suggestChapter() {
        const postalCode = $('#postal_code').val();
        const country = $('#country').val() || 'Netherlands';
        
        if (!postalCode) return;
        
        try {
            const result = await membershipApp.api.validatePostalCode(postalCode, country);
            
            if (result.suggested_chapters && result.suggested_chapters.length > 0) {
                const suggestion = result.suggested_chapters[0];
                $('#suggested-chapter-name').text(suggestion.name);
                $('#suggested-chapter').show();
                
                $('#accept-suggestion').off('click').on('click', function() {
                    $('#selected_chapter').val(suggestion.name);
                    $('#suggested-chapter').hide();
                });
            } else {
                $('#suggested-chapter').hide();
            }
        } catch (error) {
            console.error('Chapter suggestion error:', error);
        }
    }
    
    async validate() {
        const fields = ['address_line1', 'city', 'postal_code', 'country'];
        let valid = true;
        
        for (const field of fields) {
            if (!this.validator.validateRequired(`#${field}`)) {
                valid = false;
            }
        }
        
        return valid;
    }
    
    getData() {
        return {
            address_line1: $('#address_line1').val() || '',
            address_line2: $('#address_line2').val() || '',
            city: $('#city').val() || '',
            state: $('#state').val() || '',
            postal_code: $('#postal_code').val() || '',
            country: $('#country').val() || '',
            selected_chapter: $('#selected_chapter').val() || ''
        };
    }
}

class MembershipStep extends BaseStep {
    constructor() {
        super('membership');
    }
    
    render(state) {
        if (state.get('membershipTypes')) {
            this.renderMembershipTypes(state.get('membershipTypes'));
        }
    }
    
    renderMembershipTypes(membershipTypes) {
        const container = $('#membership-types');
        container.empty();
        
        // Get detailed information for each membership type
        const loadPromises = membershipTypes.map(type => {
            return new Promise((resolve) => {
                frappe.call({
                    method: 'verenigingen.api.membership_application.get_membership_type_details',
                    args: { membership_type: type.name },
                    callback: function(r) {
                        resolve(r.message || type);
                    },
                    error: function() {
                        resolve(type); // Fallback to basic type data
                    }
                });
            });
        });
        
        Promise.all(loadPromises).then(detailedTypes => {
            detailedTypes.forEach(type => {
                if (type.error) {
                    console.error('Error loading membership type:', type.error);
                    return;
                }
                
                const card = this.createMembershipCard(type);
                container.append(card);
            });
            
            this.bindMembershipEvents();
        });
    }
    
    createMembershipCard(type) {
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
            cardHTML += 'min="' + (type.minimum_amount || type.amount) + '" step="0.01" placeholder="Enter amount">';
            cardHTML += '<small class="text-muted">Minimum: ' + frappe.format(type.minimum_amount || type.amount, {fieldtype: 'Currency'}) + '</small>';
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
        
        return $(cardHTML);
    }
    
    bindEvents() {
        // This will be called after types are rendered
    }
    
    bindMembershipEvents() {
        console.log('Binding membership type events');
        
        // Standard selection
        $('.select-membership').off('click').on('click', (e) => {
            const card = $(e.target).closest('.membership-type-card');
            this.selectMembershipType(card, false);
        });
        
        // Toggle custom amount section
        $('.toggle-custom').off('click').on('click', (e) => {
            const card = $(e.target).closest('.membership-type-card');
            const customSection = card.find('.custom-amount-section');
            const button = $(e.target);
            
            if (customSection.is(':visible')) {
                customSection.hide();
                button.text('Choose Amount');
                card.find('.custom-amount-input').val('');
                card.find('.amount-pill').removeClass('selected');
                this.selectMembershipType(card, false);
            } else {
                $('.custom-amount-section').hide();
                $('.toggle-custom').text('Choose Amount');
                
                customSection.show();
                button.text('Standard Amount');
                
                const standardAmount = card.data('amount');
                card.find(`.amount-pill[data-amount="${standardAmount}"]`).addClass('selected');
                card.find('.custom-amount-input').val(standardAmount);
                this.selectMembershipType(card, true, standardAmount);
            }
        });
        
        // Amount pill selection
        $(document).off('click', '.amount-pill').on('click', '.amount-pill', (e) => {
            const pill = $(e.target);
            const card = pill.closest('.membership-type-card');
            const amount = parseFloat(pill.data('amount'));
            
            card.find('.amount-pill').removeClass('selected');
            pill.addClass('selected');
            card.find('.custom-amount-input').val(amount);
            
            this.selectMembershipType(card, true, amount);
        });
        
        // Custom amount input
        $('.custom-amount-input').off('input blur').on('input blur', (e) => {
            const input = $(e.target);
            const card = input.closest('.membership-type-card');
            const amount = parseFloat(input.val());
            const minAmount = parseFloat(input.attr('min'));
            
            card.find('.amount-pill').removeClass('selected');
            
            if (isNaN(amount) || amount <= 0) {
                input.addClass('is-invalid');
                input.siblings('.invalid-feedback').remove();
                input.after('<div class="invalid-feedback">Please enter a valid amount</div>');
                return;
            }
            
            if (amount < minAmount) {
                input.addClass('is-invalid');
                input.siblings('.invalid-feedback').remove();
                input.after(`<div class="invalid-feedback">Amount must be at least ${frappe.format(minAmount, {fieldtype: 'Currency'})}</div>`);
                return;
            }
            
            input.removeClass('is-invalid').addClass('is-valid');
            input.siblings('.invalid-feedback').remove();
            
            this.selectMembershipType(card, true, amount);
        });
    }
    
    selectMembershipType(card, isCustom = false, customAmount = null) {
        const membershipType = card.data('type');
        const standardAmount = parseFloat(card.data('amount'));
        let finalAmount = standardAmount;
        let usesCustomAmount = false;
        
        if (isCustom && customAmount !== null) {
            finalAmount = parseFloat(customAmount);
            usesCustomAmount = finalAmount !== standardAmount;
        }
        
        console.log('Selecting membership type:', { membershipType, finalAmount, usesCustomAmount });
        
        $('.membership-type-card').removeClass('selected');
        card.addClass('selected');
        
        // Update state - both new and legacy formats
        membershipApp.state.set('membership', {
            type: membershipType,
            amount: finalAmount,
            isCustom: usesCustomAmount
        });
        
        // Legacy compatibility
        membershipApp.state.set('selected_membership_type', membershipType);
        membershipApp.state.set('membership_amount', finalAmount);
        membershipApp.state.set('uses_custom_amount', usesCustomAmount);
        
        this.updateFeeDisplay();
        $('#membership-type-error').hide();
        
        if (usesCustomAmount) {
            this.validateCustomAmount(membershipType, finalAmount);
        }
    }
    
    updateFeeDisplay() {
        const display = $('#membership-fee-display');
        const details = $('#fee-details');
        const membership = membershipApp.state.get('membership');
        
        if (!membership || !membership.type) {
            display.hide();
            return;
        }
        
        const membershipType = membershipApp.membershipTypes.find(t => t.name === membership.type);
        if (!membershipType) {
            display.hide();
            return;
        }
        
        let content = '<div class="row">';
        content += '<div class="col-md-6">';
        content += '<strong>Selected:</strong> ' + membershipType.membership_type_name + '<br>';
        content += '<strong>Amount:</strong> ' + frappe.format(membership.amount, {fieldtype: 'Currency'});
        content += '</div>';
        content += '<div class="col-md-6">';
        
        if (membership.isCustom) {
            const difference = membership.amount - membershipType.amount;
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
        
        content += '</div></div>';
        details.html(content);
        display.show();
    }
    
    async validateCustomAmount(membershipType, amount) {
        try {
            const result = await membershipApp.api.validateCustomAmount(membershipType, amount);
            if (result && !result.valid) {
                $('#membership-type-error').show().text(result.message);
            } else {
                $('#membership-type-error').hide();
            }
        } catch (error) {
            console.error('Custom amount validation error:', error);
        }
    }
    
    async validate() {
        const membership = membershipApp.state.get('membership');
        
        if (!membership || !membership.type) {
            this.validator.showError('#membership-types', 'Please select a membership type');
            $('#membership-type-error').show().text('Please select a membership type');
            return false;
        }
        
        if (!membership.amount || membership.amount <= 0) {
            this.validator.showError('#membership-types', 'Invalid membership amount');
            $('#membership-type-error').show().text('Invalid membership amount');
            return false;
        }
        
        $('#membership-type-error').hide();
        return true;
    }
    
    getData() {
        const membership = membershipApp.state.get('membership');
        return {
            selected_membership_type: membership?.type || '',
            membership_amount: membership?.amount || 0,
            uses_custom_amount: membership?.isCustom || false
        };
    }
}

class VolunteerStep extends BaseStep {
    constructor() {
        super('volunteer');
    }
    
    render(state) {
        if (state.get('volunteerAreas')) {
            this.renderVolunteerAreas(state.get('volunteerAreas'));
        }
        
        // Load chapters into dropdown
        if (state.get('chapters')) {
            this.loadChapters(state.get('chapters'));
        }
    }
    
    loadChapters(chapters) {
        const select = $('#selected_chapter');
        
        // Only populate if empty (avoid duplicate loading)
        if (select.children().length <= 1) {
            select.empty().append('<option value="">Select a chapter...</option>');
            
            chapters.forEach(chapter => {
                const displayText = chapter.region ? `${chapter.name} - ${chapter.region}` : chapter.name;
                select.append(`<option value="${chapter.name}">${displayText}</option>`);
            });
            
            // Show chapter selection section if chapters are available
            if (chapters.length > 0) {
                $('#chapter-selection').show();
            }
        }
    }
    
    renderVolunteerAreas(areas) {
        const container = $('#volunteer-interests');
        container.empty();
        
        areas.forEach(area => {
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
            
            container.append($(checkboxHTML));
        });
    }
    
    bindEvents() {
        $('#interested_in_volunteering').off('change').on('change', function() {
            $('#volunteer-details').toggle($(this).is(':checked'));
        });
        
        $('#application_source').off('change').on('change', function() {
            $('#source-details-container').toggle($(this).val() === 'Other');
        });
    }
    
    async validate() {
        // Volunteer step is mostly optional, just return true
        return true;
    }
    
    getData() {
        const interests = [];
        $('#volunteer-interests input[type="checkbox"]:checked').each(function() {
            interests.push($(this).val());
        });
        
        return {
            interested_in_volunteering: $('#interested_in_volunteering').is(':checked'),
            volunteer_availability: $('#volunteer_availability').val() || '',
            volunteer_experience_level: $('#volunteer_experience_level').val() || '',
            volunteer_interests: interests,
            newsletter_opt_in: $('#newsletter_opt_in').is(':checked'),
            application_source: $('#application_source').val() || '',
            application_source_details: $('#application_source_details').val() || ''
        };
    }
}

class PaymentStep extends BaseStep {
    constructor() {
        super('payment');
    }
    
    render(state) {
        if (state.get('paymentMethods')) {
            this.renderPaymentMethods(state.get('paymentMethods'));
        }
        this.updateSummary(state);
    }
    
    renderPaymentMethods(paymentMethods) {
        const container = $('#payment-methods-list');
        const fallback = $('#payment-method-fallback');
        
        if (!paymentMethods || paymentMethods.length === 0) {
            this.showPaymentMethodFallback();
            return;
        }
        
        container.empty().show();
        fallback.hide();
        
        paymentMethods.forEach(method => {
            const methodCard = this.createPaymentMethodCard(method);
            container.append(methodCard);
        });
        
        this.bindPaymentEvents();
        
        // Auto-select first method
        if (paymentMethods.length > 0) {
            this.selectPaymentMethod(paymentMethods[0].name);
        }
    }
    
    createPaymentMethodCard(method) {
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
        
        return $(methodCardHTML);
    }
    
    showPaymentMethodFallback() {
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
        
        fallbackMethods.forEach(method => {
            select.append(`<option value="${method.name}">${method.name} - ${method.description}</option>`);
        });
        
        // Bind change event
        select.off('change').on('change', (e) => {
            const selectedMethod = $(e.target).val();
            if (selectedMethod) {
                this.selectPaymentMethod(selectedMethod);
            }
        });
        
        // Auto-select first option
        if (fallbackMethods.length > 0) {
            const defaultMethod = fallbackMethods[0].name;
            select.val(defaultMethod);
            this.selectPaymentMethod(defaultMethod);
        }
    }
    
    bindEvents() {
        // Main binding happens in bindPaymentEvents after rendering
    }
    
    bindPaymentEvents() {
        $('.payment-method-option').off('click').on('click', (e) => {
            const methodName = $(e.target).closest('.payment-method-option').data('method');
            this.selectPaymentMethod(methodName);
        });
        
        $('.payment-method-radio').off('change').on('change', (e) => {
            if ($(e.target).is(':checked')) {
                this.selectPaymentMethod($(e.target).val());
            }
        });
    }
    
    selectPaymentMethod(methodName) {
        if (!methodName) return;
        
        console.log('Selecting payment method:', methodName);
        
        // Update state
        membershipApp.setPaymentMethod(methodName);
        
        // Update UI
        if ($('#payment-method-fallback').is(':visible')) {
            $('#payment_method').val(methodName);
        } else {
            $('.payment-method-option').removeClass('selected');
            $(`.payment-method-option[data-method="${methodName}"]`).addClass('selected');
            $(`.payment-method-radio[value="${methodName}"]`).prop('checked', true);
        }
        
        // Show/hide SEPA notice
        if (methodName === 'Direct Debit') {
            $('#sepa-mandate-notice').show();
        } else {
            $('#sepa-mandate-notice').hide();
        }
    }
    
    updateSummary(state) {
        const summary = $('#application-summary');
        
        let content = '<div class="row">';
        content += '<div class="col-md-6">';
        content += '<h6>Personal Information</h6>';
        content += '<p><strong>Name:</strong> ' + ($('#first_name').val() || '') + ' ' + ($('#last_name').val() || '') + '</p>';
        content += '<p><strong>Email:</strong> ' + ($('#email').val() || '') + '</p>';
        
        const age = this.calculateAge($('#birth_date').val());
        if (age > 0) {
            content += '<p><strong>Age:</strong> ' + age + ' years</p>';
        }
        
        content += '</div>';
        content += '<div class="col-md-6">';
        content += '<h6>Membership</h6>';
        
        const membership = state.get('membership');
        if (membership && membership.type) {
            const membershipType = membershipApp.membershipTypes.find(t => t.name === membership.type);
            if (membershipType) {
                content += '<p><strong>Type:</strong> ' + membershipType.membership_type_name + '</p>';
                content += '<p><strong>Amount:</strong> ' + frappe.format(membership.amount, {fieldtype: 'Currency'}) + '</p>';
                if (membership.isCustom) {
                    content += '<p><em>Custom contribution selected</em></p>';
                }
            }
        }
        
        content += '</div>';
        content += '</div>';
        
        if ($('#selected_chapter').val()) {
            content += '<p><strong>Chapter:</strong> ' + $('#selected_chapter option:selected').text() + '</p>';
        }
        
        if ($('#interested_in_volunteering').is(':checked')) {
            content += '<p><strong>Interested in volunteering:</strong> Yes</p>';
        }
        
        const paymentMethod = membershipApp.getPaymentMethod();
        if (paymentMethod) {
            content += '<p><strong>Payment Method:</strong> ' + paymentMethod + '</p>';
        }
        
        summary.html(content);
    }
    
    calculateAge(birthDate) {
        if (!birthDate) return 0;
        
        const birth = new Date(birthDate);
        const today = new Date();
        
        if (isNaN(birth.getTime())) return 0;
        
        let age = today.getFullYear() - birth.getFullYear();
        
        if (today.getMonth() < birth.getMonth() || 
            (today.getMonth() === birth.getMonth() && today.getDate() < birth.getDate())) {
            age--;
        }
        
        return age;
    }
    
    async validate() {
        let valid = true;
        
        // Clear previous validation
        $('.invalid-feedback').remove();
        $('.is-invalid').removeClass('is-invalid');
        
        // Payment method validation
        const paymentMethod = membershipApp.getPaymentMethod();
        if (!paymentMethod) {
            if ($('#payment-method-fallback').is(':visible')) {
                $('#payment_method').addClass('is-invalid');
                $('#payment_method').after('<div class="invalid-feedback">Please select a payment method</div>');
            } else {
                const errorDiv = $('<div class="invalid-feedback d-block text-danger mb-3">Please select a payment method</div>');
                $('#payment-methods-list').after(errorDiv);
            }
            valid = false;
        }
        
        // Terms validation
        if (!$('#terms').is(':checked')) {
            const termsLabel = $('label[for="terms"]');
            termsLabel.after('<div class="invalid-feedback d-block">You must accept the terms and conditions</div>');
            $('#terms').addClass('is-invalid');
            valid = false;
        }
        
        // GDPR consent validation
        if (!$('#gdpr_consent').is(':checked')) {
            const gdprLabel = $('label[for="gdpr_consent"]');
            gdprLabel.after('<div class="invalid-feedback d-block">You must consent to data processing</div>');
            $('#gdpr_consent').addClass('is-invalid');
            valid = false;
        }
        
        return valid;
    }
    
    getData() {
        return {
            payment_method: membershipApp.getPaymentMethod() || '',
            additional_notes: $('#additional_notes').val() || '',
            terms: $('#terms').is(':checked'),
            gdpr_consent: $('#gdpr_consent').is(':checked')
        };
    }
}

// ===================================
// 4. UTILITY CLASSES
// ===================================

// FormValidator already defined above

class MembershipAPI {
    async getFormData() {
        return await this.call('verenigingen.api.membership_application.get_application_form_data');
    }
    
    async validateEmail(email) {
        return await this.call('verenigingen.api.membership_application.validate_email', { email });
    }
    
    async validatePostalCode(postalCode, country) {
        return await this.call('verenigingen.api.membership_application.validate_postal_code', {
            postal_code: postalCode,
            country: country
        });
    }
    
    async validateCustomAmount(membershipType, amount) {
        return await this.call('verenigingen.api.membership_application.validate_custom_amount', {
            membership_type: membershipType,
            amount: amount
        });
    }

    async submitApplication(data) {
        return new Promise((resolve, reject) => {
            console.log('Submitting application data:', data);
            
            frappe.call({
                method: 'verenigingen.api.membership_application.submit_application_with_tracking',
                args: {
                    data: data  // Pass as an argument in the args object
                },
                callback: function(r) {
                    if (r.message && r.message.success) {
                        resolve(r.message);
                    } else {
                        reject(new Error(r.message?.error || 'Unknown error'));
                    }
                },
                error: function(r) {
                    console.error('Submission error:', r);
                    let errorMsg = 'Network error occurred';
                    
                    if (r.responseJSON && r.responseJSON.exc) {
                        errorMsg = r.responseJSON.exc;
                    } else if (r.statusText) {
                        errorMsg = `Server error: ${r.status} ${r.statusText}`;
                    } else if (r.message) {
                        errorMsg = r.message;
                    }
                    
                    reject(new Error(errorMsg));
                }
            });
        });
    }
    
    async saveDraft(data) {
        return await this.call('verenigingen.api.membership_application.save_draft_application', { data });
    }
    
    async call(method, args = {}) {
        return new Promise((resolve, reject) => {
            // Add timeout to prevent hanging requests
            const timeoutId = setTimeout(() => {
                reject(new Error('Request timeout - server did not respond'));
            }, 30000); // 30 second timeout
            
            frappe.call({
                method,
                args,
                callback: (r) => {
                    clearTimeout(timeoutId);
                    
                    if (r.message !== undefined) {
                        resolve(r.message);
                    } else if (r.exc) {
                        reject(new Error(r.exc));
                    } else {
                        // Sometimes frappe returns success with no message
                        resolve(r);
                    }
                },
                error: (r) => {
                    clearTimeout(timeoutId);
                    console.error('API call error:', r);
                    
                    let errorMsg = 'Network error';
                    if (r.responseJSON?.exc) {
                        errorMsg = r.responseJSON.exc;
                    } else if (r.statusText) {
                        errorMsg = `${r.status}: ${r.statusText}`;
                    } else if (r.message) {
                        errorMsg = r.message;
                    }
                    
                    reject(new Error(errorMsg));
                }
            });
        });
    }
    
    // Alternative submit method using direct AJAX if frappe.call continues to fail
    async submitApplicationDirect(data) {
        return new Promise((resolve, reject) => {
            console.log('Using direct AJAX submission');
            
            $.ajax({
                url: '/api/method/verenigingen.api.membership_application.submit_application_with_tracking',
                type: 'POST',
                data: {
                    data: JSON.stringify(data)
                },
                headers: {
                    'X-Frappe-CSRF-Token': frappe.csrf_token
                },
                success: function(response) {
                    console.log('Direct AJAX response:', response);
                    
                    // Check if response contains an error message (even in "success" response)
                    if (response.error_message || (response.server_messages && response.server_messages.includes('does not have permission'))) {
                        let errorMsg = response.error_message || 'Permission denied';
                        
                        // Try to extract clean error from server_messages
                        if (response.server_messages) {
                            try {
                                const messages = JSON.parse(response.server_messages);
                                if (messages && messages.length > 0) {
                                    const firstMessage = typeof messages[0] === 'string' ? JSON.parse(messages[0]) : messages[0];
                                    if (firstMessage.message) {
                                        errorMsg = firstMessage.message.replace(/<[^>]*>/g, ''); // Strip HTML
                                    }
                                }
                            } catch (e) {
                                console.warn('Could not parse server messages:', e);
                            }
                        }
                        
                        reject(new Error(errorMsg));
                        return;
                    }
                    
                    if (response.message && response.message.success) {
                        resolve(response.message);
                    } else if (response.message && response.message.error) {
                        reject(new Error(response.message.message || response.message.error));
                    } else {
                        reject(new Error(response.message || 'Unknown error occurred'));
                    }
                },
                error: function(xhr, status, error) {
                    console.error('Direct AJAX error:', xhr, status, error);
                    let errorMsg = `Server error: ${xhr.status}`;
                    
                    if (xhr.responseJSON) {
                        if (xhr.responseJSON.exc) {
                            errorMsg = xhr.responseJSON.exc;
                        } else if (xhr.responseJSON.error_message) {
                            errorMsg = xhr.responseJSON.error_message;
                        } else if (xhr.responseJSON.message && xhr.responseJSON.message.error) {
                            errorMsg = xhr.responseJSON.message.error;
                        }
                    } else if (error) {
                        errorMsg = error;
                    }
                    
                    reject(new Error(errorMsg));
                }
            });
        });
    }
}

class UIManager {
    hideAllSteps() {
        $('.form-step').hide().removeClass('active');
    }
    
    showStep(stepNumber) {
        $(`.form-step[data-step="${stepNumber}"]`).show().addClass('active');
    }
    
    updateProgress(current, total) {
        const progress = (current / total) * 100;
        $('#form-progress').css('width', `${progress}%`);
        
        $('.step').removeClass('active completed');
        for (let i = 1; i < current; i++) {
            $(`.step[data-step="${i}"]`).addClass('completed');
        }
        $(`.step[data-step="${current}"]`).addClass('active');
    }
    
    updateNavigation(current, total) {
        $('#prev-btn').toggle(current > 1);
        $('#next-btn').toggle(current < total);
        $('#submit-btn').toggle(current === total);
    }
    
    setSubmitting(isSubmitting) {
        const btn = $('#submit-btn');
        if (isSubmitting) {
            btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i> Processing...');
        } else {
            btn.prop('disabled', false).html('Submit Application & Pay');
        }
    }
    
    showSuccess(result) {
        // Create success message with application ID prominently displayed
        let successHTML = '<div class="text-center py-5">';
        successHTML += '<div class="success-icon mb-4">';
        successHTML += '<i class="fa fa-check-circle text-success" style="font-size: 4rem;"></i>';
        successHTML += '</div>';
        successHTML += '<h2 class="text-success">Application Submitted Successfully!</h2>';
        
        // Display application ID if available
        if (result.application_id) {
            successHTML += '<div class="alert alert-info mx-auto" style="max-width: 500px;">';
            successHTML += '<h4>Your Application ID: <strong>' + result.application_id + '</strong></h4>';
            successHTML += '<p>Please save this ID for future reference.</p>';
            successHTML += '</div>';
        }
        
        successHTML += '<p class="lead">Thank you for your application. ';
        
        if (result.payment_url) {
            successHTML += 'You will be redirected to complete payment.</p>';
            successHTML += '<div class="mt-4">';
            successHTML += '<div class="spinner-border text-primary" role="status">';
            successHTML += '<span class="sr-only">Loading...</span>';
            successHTML += '</div>';
            successHTML += '</div>';
        } else {
            successHTML += 'You will receive an email with next steps.</p>';
            successHTML += '<div class="mt-4">';
            successHTML += '<a href="/application-status?id=' + result.application_id + '" class="btn btn-primary">';
            successHTML += 'Check Application Status';
            successHTML += '</a>';
            successHTML += '</div>';
        }
        
        successHTML += '</div>';
        
        $('.membership-application-form').html(successHTML);
        
        // Scroll to top
        window.scrollTo(0, 0);
    }
    
    showError(title, error) {
        const message = error.message || error.toString();
        frappe.msgprint({
            title: title,
            message: message,
            indicator: 'red'
        });
    }
}

// ===================================
// 5. INITIALIZATION
// ===================================

$(document).ready(function() {
    console.log('Initializing refactored membership application...');
    
    // Initialize the application
    window.membershipApp = new MembershipApplication({
        maxSteps: 5,
        autoSaveInterval: 30000
    });
    
    // Global debug functions for beta testing
    window.debugApp = () => {
        console.log('=== APPLICATION DEBUG ===');
        console.log('State:', membershipApp.state.getData());
        console.log('Current step:', membershipApp.state.currentStep);
        console.log('Selected membership:', membershipApp.state.get('membership'));
        console.log('Payment method:', membershipApp.getPaymentMethod());
        console.log('========================');
        return membershipApp.state.getData();
    };
    
    window.debugMembershipSelection = () => {
        console.log('=== MEMBERSHIP SELECTION DEBUG ===');
        const membership = membershipApp.state.get('membership');
        console.log('Membership data:', membership);
        console.log('Legacy compatibility:');
        console.log('  - selected_membership_type:', membershipApp.state.get('selected_membership_type'));
        console.log('  - membership_amount:', membershipApp.state.get('membership_amount'));
        console.log('  - uses_custom_amount:', membershipApp.state.get('uses_custom_amount'));
        
        // Check visible custom sections
        $('.custom-amount-section:visible').each(function() {
            const card = $(this).closest('.membership-type-card');
            console.log('Visible custom section for:', card.data('type'));
            console.log('Input value:', $(this).find('.custom-amount-input').val());
        });
        
        console.log('=================================');
        return membership;
    };
    
    window.debugAge = (birthDate) => {
        const step = membershipApp.steps[0]; // PersonalInfoStep
        const age = step.calculateAge(birthDate || $('#birth_date').val());
        console.log('Age calculation:', { birthDate: birthDate || $('#birth_date').val(), age });
        
        if (age > 100) {
            console.log('Should show >100 warning');
        } else if (age < 12) {
            console.log('Should show <12 warning');
        } else {
            console.log('No age warning needed');
        }
        
        return age;
    };
    
    console.log('Refactored membership application initialized successfully');
    console.log('Available debug commands:');
    console.log('- debugApp() - Show full application state');
    console.log('- debugMembershipSelection() - Check membership selection');
    console.log('- debugAge(birthDate) - Test age validation');
});

// Add this debug function to test the backend method
window.testBackendMethod = async function() {
    console.log('Testing backend method availability...');
    
    try {
        const result = await new Promise((resolve, reject) => {
            frappe.call({
                method: 'verenigingen.api.membership_application.get_application_form_data',
                callback: (r) => {
                    if (r.message !== undefined) {
                        resolve(r.message);
                    } else {
                        reject(new Error('No response'));
                    }
                },
                error: reject
            });
        });
        
        console.log('Backend method test successful:', result);
        return result;
    } catch (error) {
        console.error('Backend method test failed:', error);
        return null;
    }
};
