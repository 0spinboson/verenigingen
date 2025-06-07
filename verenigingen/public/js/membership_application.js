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
            maxSteps: 6,
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
    
    initializeSteps() {
        // Initialize step classes for form validation and interaction
        this.steps = [
            new PersonalInfoStep(),
            new AddressStep(),
            new MembershipStep(),
            new VolunteerStep(),
            new PaymentStep(),
            new ConfirmationStep()
        ];
        
        // Bind events for all steps
        this.steps.forEach(step => {
            try {
                step.bindEvents();
                step.render(this.state);
            } catch (error) {
                console.warn(`Failed to initialize step ${step.stepId}:`, error);
            }
        });
        
        console.log('Initialized', this.steps.length, 'form steps');
    }
    
    async init() {
        try {
            console.log('Initializing refactored membership application...');
            
            // Initialize step classes
            this.initializeSteps();
            
            // Load initial data
            await this.loadInitialData();
            
            // Set up validation for form fields
            this.setupFieldValidation();
            
            // Bind events
            this.bindEvents();
            
            // Start auto-save if enabled
            if (this.config.enableAutoSave && this.storageService && typeof this.storageService.startAutoSave === 'function') {
                this.storageService.startAutoSave(() => this.getAllFormData());
            }
            
            // Try to load any existing draft
            await this.loadExistingDraft();
            
            console.log('Refactored membership application initialized successfully');
        } catch (error) {
            console.error('Failed to initialize application:', error);
            if (this.errorHandler && typeof this.errorHandler.handleError === 'function') {
                this.errorHandler.handleError(error, { context: 'initialization' });
            } else {
                console.warn('ErrorHandler not available, showing basic error message');
                // Show a simple error message to the user
                if (typeof frappe !== 'undefined' && frappe.msgprint) {
                    frappe.msgprint({
                        title: 'Initialization Error',
                        message: 'Failed to initialize the membership application form. Please refresh the page.',
                        indicator: 'red'
                    });
                }
            }
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
            if (this.errorHandler && typeof this.errorHandler.handleAPIError === 'function') {
                this.errorHandler.handleAPIError(error, 'get_application_form_data');
            }
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
            if (this.stepManager && typeof this.stepManager.submitApplication === 'function') {
                this.stepManager.submitApplication();
            } else {
                this.submitApplication();
            }
        });
        
        // Bind step navigation buttons
        this.bindStepNavigation();
        
        // Custom validation events
        this.bindCustomValidationEvents();
        
        // Direct binding for age calculation since step system might not be working
        this.bindAgeCalculation();
    }
    
    bindStepNavigation() {
        // Initialize step navigation
        this.currentStep = 1;
        this.maxSteps = 5;
        
        // Show first step
        this.showStep(1);
        
        // Next button
        $('#next-btn').off('click').on('click', (e) => {
            e.preventDefault();
            console.log('Next button clicked, current step:', this.currentStep);
            this.nextStep();
        });
        
        // Previous button  
        $('#prev-btn').off('click').on('click', (e) => {
            e.preventDefault();
            console.log('Previous button clicked, current step:', this.currentStep);
            this.prevStep();
        });
        
        // Submit button
        $('#submit-btn').off('click').on('click', (e) => {
            e.preventDefault();
            console.log('Submit button clicked');
            this.submitApplication();
        });
    }
    
    nextStep() {
        if (this.validateCurrentStep() && this.currentStep < this.maxSteps) {
            this.currentStep++;
            this.showStep(this.currentStep);
        }
    }
    
    prevStep() {
        if (this.currentStep > 1) {
            this.currentStep--;
            this.showStep(this.currentStep);
        }
    }
    
    showStep(step) {
        console.log('Showing step:', step);
        
        // Hide all steps
        $('.form-step').hide().removeClass('active');
        
        // Show current step
        $(`.form-step[data-step="${step}"]`).show().addClass('active');
        
        // Update navigation buttons
        $('#prev-btn').toggle(step > 1);
        $('#next-btn').toggle(step < this.maxSteps);
        $('#submit-btn').toggle(step === this.maxSteps);
        
        // Update progress bar
        const progress = (step / this.maxSteps) * 100;
        $('#form-progress').css('width', `${progress}%`);
        
        // Update step indicators
        $('.step').removeClass('active completed');
        for (let i = 1; i < step; i++) {
            $(`.step[data-step="${i}"]`).addClass('completed');
        }
        $(`.step[data-step="${step}"]`).addClass('active');
        
        // Update internal state
        this.state.set('currentStep', step);
        
        // Set up step-specific content
        this.setupStepContent(step);
        
        // Scroll to top
        window.scrollTo(0, 0);
    }
    
    validateCurrentStep() {
        console.log('Validating step:', this.currentStep);
        
        // Try to use step-specific validation if available
        if (this.steps && this.steps[this.currentStep - 1]) {
            try {
                return this.steps[this.currentStep - 1].validate();
            } catch (error) {
                console.warn('Step validation failed:', error);
            }
        }
        
        // Fallback to basic validation
        return this.validateStepBasic(this.currentStep);
    }
    
    validateStepBasic(step) {
        let isValid = true;
        
        // Clear previous errors
        $('.is-invalid').removeClass('is-invalid');
        $('.invalid-feedback').hide();
        
        switch(step) {
            case 1: // Personal info
                const requiredFields = ['#first_name', '#last_name', '#email', '#birth_date'];
                requiredFields.forEach(field => {
                    const $field = $(field);
                    if (!$field.val() || $field.val().trim() === '') {
                        $field.addClass('is-invalid');
                        let feedback = $field.siblings('.invalid-feedback');
                        if (feedback.length === 0) {
                            $field.after('<div class="invalid-feedback">This field is required</div>');
                        }
                        $field.siblings('.invalid-feedback').show();
                        isValid = false;
                    }
                });
                
                // Email validation
                const email = $('#email').val();
                if (email && !this.isValidEmail(email)) {
                    $('#email').addClass('is-invalid');
                    $('#email').siblings('.invalid-feedback').text('Please enter a valid email').show();
                    isValid = false;
                }
                break;
                
            case 2: // Address
                const addressFields = ['#address_line1', '#city', '#postal_code', '#country'];
                addressFields.forEach(field => {
                    const $field = $(field);
                    if (!$field.val() || $field.val().trim() === '') {
                        $field.addClass('is-invalid');
                        let feedback = $field.siblings('.invalid-feedback');
                        if (feedback.length === 0) {
                            $field.after('<div class="invalid-feedback">This field is required</div>');
                        }
                        $field.siblings('.invalid-feedback').show();
                        isValid = false;
                    }
                });
                break;
                
            case 3: // Membership type
                const selectedType = this.state.get('selected_membership_type');
                const membership = this.state.get('membership');
                
                if (!selectedType && (!membership || !membership.type)) {
                    $('#membership-type-error').text('Please select a membership type').show();
                    isValid = false;
                } else {
                    // Check if custom amount is valid when used
                    const membershipAmount = this.state.get('membership_amount') || (membership && membership.amount);
                    const usesCustomAmount = this.state.get('uses_custom_amount') || (membership && membership.isCustom);
                    
                    if (usesCustomAmount && (!membershipAmount || membershipAmount <= 0)) {
                        $('#membership-type-error').text('Please enter a valid membership amount').show();
                        isValid = false;
                    }
                }
                break;
                
            case 4: // Volunteer (optional)
                // No required fields
                break;
                
            case 5: // Payment
                const paymentMethod = this.getPaymentMethod();
                if (!paymentMethod) {
                    if (typeof frappe !== 'undefined' && frappe.msgprint) {
                        frappe.msgprint('Please select a payment method');
                    }
                    isValid = false;
                }
                
                if (!$('#terms').is(':checked')) {
                    if (typeof frappe !== 'undefined' && frappe.msgprint) {
                        frappe.msgprint('Please accept the terms and conditions');
                    }
                    isValid = false;
                }
                
                if (!$('#gdpr_consent').is(':checked')) {
                    if (typeof frappe !== 'undefined' && frappe.msgprint) {
                        frappe.msgprint('Please consent to data processing');
                    }
                    isValid = false;
                }
                break;
        }
        
        return isValid;
    }
    
    isValidEmail(email) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
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
            case 6:
                this.setupConfirmationStep();
                break;
        }
    }
    
    getCurrentStep() {
        if (this.stepManager && typeof this.stepManager.getCurrentStep === 'function') {
            return this.stepManager.getCurrentStep();
        }
        return this.currentStep || 1;
    }
    
    // New method to get all form data
    getAllFormData() {
        const formData = {};
        
        // Get data from step manager if available
        if (this.stepManager && typeof this.stepManager.getAllData === 'function') {
            try {
                const stepData = this.stepManager.getAllData();
                Object.assign(formData, stepData);
            } catch (error) {
                console.warn('StepManager.getAllData failed:', error);
            }
        }
        
        // Collect data directly from form fields (fallback and primary method)
        const directFormData = this.collectFormDataDirectly();
        Object.assign(formData, directFormData);
        
        // Get additional form data not handled by step manager
        const additionalData = this.getAdditionalFormData();
        Object.assign(formData, additionalData);
        
        return formData;
    }
    
    collectFormDataDirectly() {
        // Collect data directly from form fields
        return {
            // Step 1: Personal Information
            first_name: $('#first_name').val() || '',
            middle_name: $('#middle_name').val() || '',
            last_name: $('#last_name').val() || '',
            email: $('#email').val() || '',
            contact_number: $('#contact_number').val() || '',
            birth_date: $('#birth_date').val() || '',
            pronouns: $('#pronouns').val() || '',
            
            // Step 2: Address Information
            address_line1: $('#address_line1').val() || '',
            address_line2: $('#address_line2').val() || '',
            city: $('#city').val() || '',
            state: $('#state').val() || '',
            postal_code: $('#postal_code').val() || '',
            country: $('#country').val() || '',
            
            // Step 3: Membership and Chapter selection
            selected_membership_type: this.state.get('selected_membership_type') || '',
            membership_amount: this.state.get('membership_amount') || 0,
            uses_custom_amount: this.state.get('uses_custom_amount') || false,
            selected_chapter: $('#selected_chapter').val() || '',
            
            // Step 4: Volunteer Information
            interested_in_volunteering: $('#interested_in_volunteering').is(':checked'),
            volunteer_availability: $('#volunteer_availability').val() || '',
            volunteer_experience_level: $('#volunteer_experience_level').val() || '',
            newsletter_opt_in: $('#newsletter_opt_in').is(':checked'),
            application_source: $('#application_source').val() || '',
            application_source_details: $('#application_source_details').val() || '',
            
            // Step 5: Payment Details
            payment_method: $('input[name="payment_method_selection"]:checked').val() || $('#payment_method').val() || '',
            
            // Credit Card Details
            card_number: $('#card_number').val() || '',
            card_holder_name: $('#card_holder_name').val() || '',
            expiry_month: $('#expiry_month').val() || '',
            expiry_year: $('#expiry_year').val() || '',
            cvv: $('#cvv').val() || '',
            
            // Bank Account Details (Direct Debit)
            iban: $('#iban').val() || '',
            bic: $('#bic').val() || '',
            bank_account_name: $('#bank_account_name').val() || '',
            
            // Bank Transfer Account Details (for payment matching)
            // Note: These should map to the member IBAN fields when payment_method is 'Bank Transfer'
            transfer_iban: $('#transfer_iban').val() || '',
            transfer_bic: $('#transfer_bic').val() || '',
            transfer_account_name: $('#transfer_account_name').val() || '',
            
            // Step 6: Final Confirmation
            additional_notes: $('#additional_notes').val() || '',
            terms: $('#terms').is(':checked'),
            gdpr_consent: $('#gdpr_consent').is(':checked'),
            confirm_accuracy: $('#confirm_accuracy').is(':checked'),
            
            // Collect volunteer interests
            volunteer_interests: this.getSelectedVolunteerInterests()
        };
    }
    
    getSelectedVolunteerInterests() {
        const interests = [];
        $('#volunteer-interests input[type="checkbox"]:checked').each(function() {
            interests.push($(this).val());
        });
        return interests;
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
            if (this.errorHandler && typeof this.errorHandler.handleError === 'function') {
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
                if (result.source === 'local' && this.errorHandler && typeof this.errorHandler.showNotification === 'function') {
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
            
            // Validate we have required data
            if (!formData.first_name || !formData.last_name || !formData.email) {
                throw new Error('Missing required fields: name and email are required');
            }
            
            if (!formData.selected_membership_type) {
                throw new Error('No membership type selected');
            }
            
            console.log('Form data validation passed. API Service:', this.apiService);
            
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
        if (this.errorHandler && typeof this.errorHandler.handleAPIError === 'function') {
            this.errorHandler.handleAPIError(error, 'submit_application', {
                onRetry: () => this.submitApplication()
            });
        } else {
            console.error('Submission error:', error);
            if (typeof frappe !== 'undefined' && frappe.msgprint) {
                frappe.msgprint({
                    title: 'Submission Error',
                    message: error.message || 'An error occurred while submitting your application',
                    indicator: 'red'
                });
            }
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
        if (this.errorHandler && typeof this.errorHandler.showNotification === 'function') {
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
        if (!this.validationService || typeof this.validationService.setupRealTimeValidation !== 'function') {
            console.log('ValidationService not available, skipping real-time validation setup');
            return;
        }
        
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
                try {
                    this.validationService.setupRealTimeValidation($field[0], validationKey, {
                        country: () => $('#country').val() || 'Netherlands'
                    });
                } catch (error) {
                    console.warn(`Failed to setup validation for ${fieldId}:`, error);
                }
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
                        if (this.errorHandler && typeof this.errorHandler.handleValidationError === 'function') {
                            this.errorHandler.handleValidationError('email', result);
                        } else {
                            console.warn('Email validation failed:', result);
                        }
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
    
    bindAgeCalculation() {
        // Direct binding for birth date age calculation
        $(document).on('change blur', '#birth_date', () => {
            console.log('Birth date changed, calculating age...');
            this.validateAndShowAge();
        });
    }
    
    validateAndShowAge() {
        const birthDateField = $('#birth_date');
        if (birthDateField.length === 0) {
            console.warn('Birth date field not found');
            return;
        }
        
        const birthDate = birthDateField.val();
        if (!birthDate) {
            // Clear any existing warning
            $('#age-warning').hide();
            return;
        }
        
        const age = this.calculateAge(birthDate);
        let warningDiv = $('#age-warning');
        
        // Create warning div if it doesn't exist
        if (warningDiv.length === 0) {
            birthDateField.after('<div id="age-warning" class="alert mt-2" style="display: none;"></div>');
            warningDiv = $('#age-warning');
        }
        
        // Clear previous states
        birthDateField.removeClass('is-invalid is-valid');
        birthDateField.siblings('.invalid-feedback').remove();
        warningDiv.hide().removeClass('alert-info alert-warning alert-danger');
        
        if (age < 0) {
            birthDateField.addClass('is-invalid');
            birthDateField.after('<div class="invalid-feedback">Birth date cannot be in the future</div>');
            return;
        }
        
        birthDateField.addClass('is-valid');
        
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
        
        console.log(`Age calculated: ${age} years`);
    }
    
    calculateAge(birthDate) {
        if (!birthDate) return 0;
        
        try {
            const birth = new Date(birthDate);
            const today = new Date();
            
            // Check for invalid dates
            if (isNaN(birth.getTime())) {
                console.warn('Invalid birth date:', birthDate);
                return -1;
            }
            
            if (birth > today) {
                return -1; // Future date
            }
            
            let age = today.getFullYear() - birth.getFullYear();
            
            // Adjust for birthday not yet reached this year
            if (today.getMonth() < birth.getMonth() || 
                (today.getMonth() === birth.getMonth() && today.getDate() < birth.getDate())) {
                age--;
            }
            
            return Math.max(0, age); // Ensure non-negative age
        } catch (error) {
            console.error('Error calculating age:', error);
            return 0;
        }
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
        // Setup payment method selection and bind events for showing/hiding payment details
        this.bindPaymentMethodEvents();
        
        if ($('.payment-method-option').length === 0) {
            const paymentMethods = this.state.get('paymentMethods');
            this.loadPaymentMethods(paymentMethods);
        }
        
        // Add a small delay to ensure DOM is ready, then set up field switching
        setTimeout(() => {
            console.log('SetupPaymentStep: Checking for existing elements');
            console.log('SetupPaymentStep: Payment method radios found:', $('input[name="payment_method_selection"]').length);
            console.log('SetupPaymentStep: Payment method options found:', $('.payment-method-option').length);
            console.log('SetupPaymentStep: Credit card details section found:', $('#credit-card-details').length);
            console.log('SetupPaymentStep: Bank account details section found:', $('#bank-account-details').length);
            console.log('SetupPaymentStep: Bank transfer notice section found:', $('#bank-transfer-notice').length);
            console.log('SetupPaymentStep: Bank transfer details section found:', $('#bank-transfer-details').length);
            
            // Ensure any pre-selected payment method shows the correct form fields
            const selectedMethod = $('input[name="payment_method_selection"]:checked').val() || $('#payment_method').val();
            if (selectedMethod) {
                console.log('Setting up payment step with pre-selected method:', selectedMethod);
                // Use the new handlePaymentMethodChange method for consistency
                this.handlePaymentMethodChange(selectedMethod);
            } else {
                console.log('SetupPaymentStep: No pre-selected payment method found');
            }
        }, 100);
    }
    
    setupConfirmationStep() {
        // Update complete application summary for final review
        this.updateFinalApplicationSummary();
        
        // Ensure the summary is updated after a short delay to handle any async state updates
        setTimeout(() => {
            this.updateFinalApplicationSummary();
        }, 100);
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
        
        // Load detailed membership type information with custom amount support
        const loadPromises = membershipTypes.map(type => {
            return new Promise((resolve) => {
                if (this.apiService && typeof this.apiService.call === 'function') {
                    this.apiService.call('verenigingen.api.membership_application.get_membership_type_details', { membership_type: type.name })
                        .then(result => resolve(result || type))
                        .catch(() => resolve(type)); // Fallback to basic type data
                } else {
                    // Fallback - enhance basic type with custom amount support
                    const baseAmount = parseFloat(type.amount) || 50; // fallback to 50 if amount is invalid
                    const enhancedType = {
                        ...type,
                        allow_custom_amount: true,
                        minimum_amount: baseAmount * 0.5,
                        maximum_amount: baseAmount * 5,
                        suggested_amounts: [
                            { amount: baseAmount, label: "Standard" },
                            { amount: baseAmount * 1.5, label: "Supporter" },
                            { amount: baseAmount * 2, label: "Patron" },
                            { amount: baseAmount * 3, label: "Benefactor" }
                        ]
                    };
                    console.log('Enhanced type with suggested amounts:', enhancedType);
                    resolve(enhancedType);
                }
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
            console.log('Loaded', detailedTypes.length, 'membership types with custom amount support');
        });
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
        
        // Also bind the payment method field switching events after DOM is updated
        console.log('Main app: Re-binding payment method events after loading methods');
        this.bindPaymentMethodEvents();
        
        // Auto-select first method to show appropriate fields
        if (paymentMethods.length > 0) {
            console.log('Main app: Auto-selecting first payment method:', paymentMethods[0].name);
            this.selectPaymentMethod(paymentMethods[0].name);
        }
    }
    
    updateApplicationSummary() {
        const summary = $('#application-summary');
        if (summary.length === 0) {
            console.warn('Application summary element not found');
            return;
        }
        
        const data = this.getAllFormData();
        
        let content = '<div class="row">';
        
        // Personal Information Column
        content += '<div class="col-md-6">';
        content += '<h6>Personal Information</h6>';
        content += `<p><strong>Name:</strong> ${data.first_name || ''} ${data.last_name || ''}</p>`;
        content += `<p><strong>Email:</strong> ${data.email || ''}</p>`;
        
        if (data.birth_date) {
            content += `<p><strong>Birth Date:</strong> ${data.birth_date}</p>`;
        }
        
        if (data.contact_number) {
            content += `<p><strong>Contact:</strong> ${data.contact_number}</p>`;
        }
        content += '</div>';
        
        // Address Information Column
        content += '<div class="col-md-6">';
        content += '<h6>Address</h6>';
        if (data.address_line1) {
            content += `<p><strong>Address:</strong> ${data.address_line1}</p>`;
            content += `<p>${data.city || ''} ${data.postal_code || ''}</p>`;
            content += `<p>${data.country || ''}</p>`;
        }
        content += '</div>';
        
        content += '</div>';
        
        // Membership Information Row
        content += '<div class="row mt-3">';
        content += '<div class="col-md-6">';
        content += '<h6>Membership</h6>';
        
        if (data.selected_membership_type) {
            const membershipType = this.membershipTypes && this.membershipTypes.find(t => t.name === data.selected_membership_type);
            
            if (membershipType) {
                const typeName = membershipType.membership_type_name || membershipType.name;
                content += `<p><strong>Type:</strong> ${typeName}</p>`;
                
                // Format amount with billing period
                const amount = data.membership_amount || membershipType.amount;
                const period = membershipType.subscription_period || 'year';
                // Use simple currency formatting to avoid HTML structure issues
                const currency = membershipType.currency || 'EUR';
                const formattedAmount = `${currency} ${parseFloat(amount).toFixed(2)}`;
                const periodText = period.toLowerCase() === 'quarterly' ? 'Quarterly' : `per ${period}`;
                content += `<p><strong>Amount:</strong> ${formattedAmount} ${periodText}</p>`;
                
                if (data.uses_custom_amount) {
                    content += `<p><em>Custom contribution amount</em></p>`;
                }
            } else {
                content += `<p><strong>Type:</strong> ${data.selected_membership_type}</p>`;
                if (data.membership_amount) {
                    const formattedAmount = `EUR ${parseFloat(data.membership_amount).toFixed(2)}`;
                    content += `<p><strong>Amount:</strong> ${formattedAmount}</p>`;
                }
            }
        } else {
            content += `<p><em>No membership type selected</em></p>`;
        }
        
        if (data.selected_chapter) {
            content += `<p><strong>Chapter:</strong> ${data.selected_chapter}</p>`;
        }
        content += '</div>';
        
        // Volunteer and Payment Information Column
        content += '<div class="col-md-6">';
        content += '<h6>Additional Information</h6>';
        
        if (data.interested_in_volunteering) {
            content += `<p><strong>Volunteering:</strong> Yes</p>`;
            if (data.volunteer_availability) {
                content += `<p><strong>Availability:</strong> ${data.volunteer_availability}</p>`;
            }
        }
        
        if (data.payment_method) {
            content += `<p><strong>Payment Method:</strong> ${data.payment_method}</p>`;
            
            // Show bank details for Direct Debit
            if (data.payment_method === 'Direct Debit') {
                if (data.iban) {
                    content += `<p><strong>IBAN:</strong> ${data.iban}</p>`;
                }
                if (data.bank_account_name) {
                    content += `<p><strong>Account Holder:</strong> ${data.bank_account_name}</p>`;
                }
                if (data.bic) {
                    content += `<p><strong>BIC:</strong> ${data.bic}</p>`;
                }
            }
            
            // Show bank transfer account details for Bank Transfer
            if (data.payment_method === 'Bank Transfer') {
                if (data.transfer_iban) {
                    content += `<p><strong>Transfer Account (IBAN):</strong> ${data.transfer_iban}</p>`;
                }
                if (data.transfer_account_name) {
                    content += `<p><strong>Account Holder:</strong> ${data.transfer_account_name}</p>`;
                }
                if (data.transfer_bic) {
                    content += `<p><strong>BIC:</strong> ${data.transfer_bic}</p>`;
                }
                if (!data.transfer_iban && !data.transfer_account_name) {
                    content += `<p><em>Account details will be provided via email</em></p>`;
                }
            }
            
            // Show credit card info for Credit Card
            if (data.payment_method === 'Credit Card' && data.credit_card_number) {
                content += `<p><strong>Card (last 4 digits):</strong> ****${data.credit_card_number}</p>`;
            }
        } else {
            content += `<p><em>No payment method selected</em></p>`;
        }
        
        content += '</div>';
        content += '</div>';
        
        summary.html(content);
    }
    
    bindPaymentMethodEvents() {
        console.log('Main app: Binding payment method events');
        
        // Bind events for payment method selection to show/hide appropriate form sections
        // Use a more robust selector to catch all payment method radio buttons
        const self = this;
        $(document).off('change', 'input[name="payment_method_selection"], .payment-method-radio').on('change', 'input[name="payment_method_selection"], .payment-method-radio', function() {
            const selectedMethod = $(this).val();
            console.log('Main app: Payment method selection changed to:', selectedMethod);
            
            // Use the new handlePaymentMethodChange method for consistent behavior
            self.handlePaymentMethodChange(selectedMethod);
        });
        
        // Format card number input
        $('#card_number').off('input').on('input', function() {
            let value = $(this).val().replace(/\s+/g, '').replace(/[^0-9]/gi, '');
            let formattedValue = value.match(/.{1,4}/g)?.join(' ') || value;
            $(this).val(formattedValue);
        });
        
        // Format IBAN inputs (for both direct debit and bank transfer) and auto-derive BIC
        $('#iban, #transfer_iban').off('input').on('input', function() {
            let value = $(this).val().replace(/\s+/g, '').toUpperCase();
            let formattedValue = value.match(/.{1,4}/g)?.join(' ') || value;
            $(this).val(formattedValue);
            
            // Auto-derive BIC from IBAN
            const bicField = $(this).attr('id') === 'iban' ? '#bic' : '#transfer_bic';
            const derivedBic = getBicFromIban(value);
            if (derivedBic) {
                $(bicField).val(derivedBic);
            }
        });
        
        // Format BIC inputs
        $('#bic, #transfer_bic').off('input').on('input', function() {
            let value = $(this).val().replace(/[^A-Z0-9]/gi, '').toUpperCase();
            if (value.length <= 11) {
                $(this).val(value);
            }
        });
    }
    
    updateFinalApplicationSummary() {
        const summary = $('#final-application-summary');
        if (summary.length === 0) {
            console.warn('Final application summary element not found');
            return;
        }
        
        const data = this.getAllFormData();
        
        let content = '<div class="row">';
        
        // Personal Information Column
        content += '<div class="col-md-6">';
        content += '<h6>Personal Information</h6>';
        content += `<p><strong>Name:</strong> ${data.first_name || ''} ${data.last_name || ''}</p>`;
        content += `<p><strong>Email:</strong> ${data.email || ''}</p>`;
        
        if (data.birth_date) {
            content += `<p><strong>Birth Date:</strong> ${data.birth_date}</p>`;
        }
        
        if (data.contact_number) {
            content += `<p><strong>Contact:</strong> ${data.contact_number}</p>`;
        }
        content += '</div>';
        
        // Address Information Column
        content += '<div class="col-md-6">';
        content += '<h6>Address</h6>';
        if (data.address_line1) {
            content += `<p><strong>Address:</strong> ${data.address_line1}</p>`;
            content += `<p>${data.city || ''} ${data.postal_code || ''}</p>`;
            content += `<p>${data.country || ''}</p>`;
        }
        content += '</div>';
        
        content += '</div>';
        
        // Membership Information Row
        content += '<div class="row mt-3">';
        content += '<div class="col-md-6">';
        content += '<h6>Membership</h6>';
        
        if (data.selected_membership_type) {
            const membershipType = this.membershipTypes && this.membershipTypes.find(t => t.name === data.selected_membership_type);
            
            if (membershipType) {
                const typeName = membershipType.membership_type_name || membershipType.name;
                content += `<p><strong>Type:</strong> ${typeName}</p>`;
                
                // Format amount with billing period
                const amount = data.membership_amount || membershipType.amount;
                const period = membershipType.subscription_period || 'year';
                const currency = membershipType.currency || 'EUR';
                const formattedAmount = `${currency} ${parseFloat(amount).toFixed(2)}`;
                const periodText = period.toLowerCase() === 'quarterly' ? 'Quarterly' : `per ${period}`;
                content += `<p><strong>Amount:</strong> ${formattedAmount} ${periodText}</p>`;
                
                if (data.uses_custom_amount) {
                    content += `<p><em>Custom contribution amount</em></p>`;
                }
            } else {
                content += `<p><strong>Type:</strong> ${data.selected_membership_type}</p>`;
                if (data.membership_amount) {
                    const formattedAmount = `EUR ${parseFloat(data.membership_amount).toFixed(2)}`;
                    content += `<p><strong>Amount:</strong> ${formattedAmount}</p>`;
                }
            }
        } else {
            content += `<p><em>No membership type selected</em></p>`;
        }
        
        if (data.selected_chapter) {
            content += `<p><strong>Chapter:</strong> ${data.selected_chapter}</p>`;
        }
        content += '</div>';
        
        // Payment Information Column
        content += '<div class="col-md-6">';
        content += '<h6>Payment Information</h6>';
        
        if (data.payment_method) {
            content += `<p><strong>Payment Method:</strong> ${data.payment_method}</p>`;
            
            // Show relevant payment details (masked for security)
            if (data.payment_method === 'Credit Card' && data.card_number) {
                const maskedCard = '**** **** **** ' + data.card_number.slice(-4);
                content += `<p><strong>Card:</strong> ${maskedCard}</p>`;
            } else if (data.payment_method === 'Direct Debit' && data.iban) {
                const maskedIban = data.iban.slice(0, 4) + ' **** **** ' + data.iban.slice(-4);
                content += `<p><strong>IBAN:</strong> ${maskedIban}</p>`;
            }
        } else {
            content += `<p><em>No payment method selected</em></p>`;
        }
        content += '</div>';
        
        content += '</div>';
        
        // Additional Information
        if (data.interested_in_volunteering) {
            content += `<div class="row mt-3"><div class="col-12">`;
            content += `<h6>Volunteer Information</h6>`;
            content += `<p><strong>Interested in volunteering:</strong> Yes</p>`;
            if (data.volunteer_availability) {
                content += `<p><strong>Availability:</strong> ${data.volunteer_availability}</p>`;
            }
            content += `</div></div>`;
        }
        
        summary.html(content);
    }
    
    // Legacy method implementations for compatibility
    createMembershipCard(type) {
        // Ensure we have a valid amount
        const amount = type.amount || 0;
        const membershipTypeName = type.membership_type_name || type.name || 'Unknown';
        const subscriptionPeriod = type.subscription_period || 'year';
        
        console.log('Creating membership card for:', { name: type.name, amount, type });
        
        let cardHTML = '<div class="membership-type-card" data-type="' + (type.name || '') + '" data-amount="' + amount + '">';
        cardHTML += '<h5>' + membershipTypeName + '</h5>';
        cardHTML += '<div class="membership-price">';
        cardHTML += frappe.format(amount, {fieldtype: 'Currency'}) + ' / ' + subscriptionPeriod;
        cardHTML += '</div>';
        cardHTML += '<p class="membership-description">' + (type.description || '') + '</p>';
        
        // Add custom amount section if allowed
        if (type.allow_custom_amount) {
            cardHTML += '<div class="custom-amount-section" style="display: none;">';
            cardHTML += '<label>Choose Your Contribution:</label>';
            cardHTML += '<div class="amount-suggestion-pills">';
            
            if (type.suggested_amounts && type.suggested_amounts.length > 0) {
                type.suggested_amounts.forEach(function(suggestion) {
                    const suggestionAmount = parseFloat(suggestion.amount) || 0;
                    console.log('Creating amount pill:', { label: suggestion.label, amount: suggestionAmount });
                    cardHTML += '<span class="amount-pill" data-amount="' + suggestionAmount + '">';
                    cardHTML += frappe.format(suggestionAmount, {fieldtype: 'Currency'});
                    cardHTML += '<br><small>' + suggestion.label + '</small>';
                    cardHTML += '</span>';
                });
            }
            
            cardHTML += '</div>';
            cardHTML += '<div class="mt-3">';
            cardHTML += '<label>Or enter custom amount:</label>';
            const minAmount = type.minimum_amount || amount;
            cardHTML += '<input type="number" class="form-control custom-amount-input" ';
            cardHTML += 'min="' + minAmount + '" step="0.01" placeholder="Enter amount">';
            cardHTML += '<small class="text-muted">Minimum: ' + frappe.format(minAmount, {fieldtype: 'Currency'}) + '</small>';
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
        console.log('Binding membership type events - START');
        console.trace('bindMembershipEvents called from:');
        
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
                
                const standardAmount = parseFloat(card.data('amount'));
                if (!isNaN(standardAmount) && standardAmount > 0) {
                    card.find(`.amount-pill[data-amount="${standardAmount}"]`).addClass('selected');
                    card.find('.custom-amount-input').val(standardAmount);
                    this.selectMembershipType(card, true, standardAmount);
                }
            }
        });
        
        // Amount pill selection
        $(document).off('click', '.amount-pill').on('click', '.amount-pill', (e) => {
            e.preventDefault();
            e.stopPropagation();
            
            console.log('Amount pill clicked');
            const pill = $(e.target).closest('.amount-pill'); // Use closest to handle clicks on nested elements
            const card = pill.closest('.membership-type-card');
            const rawAmount = pill.data('amount');
            const amount = parseFloat(rawAmount);
            
            console.log('Pill selection details:', { 
                pillText: pill.text().trim(), 
                rawAmount, 
                parsedAmount: amount, 
                isValid: !isNaN(amount),
                cardType: card.data('type'),
                pillHtml: pill[0].outerHTML
            });
            
            if (isNaN(amount) || amount <= 0) {
                console.error('Invalid amount from pill:', rawAmount, 'pill:', pill[0]);
                return;
            }
            
            card.find('.amount-pill').removeClass('selected');
            pill.addClass('selected');
            
            // Set input value with the valid amount
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
        const cardAmount = card.data('amount');
        
        console.log('selectMembershipType called with:', { 
            membershipType, 
            cardAmount, 
            isCustom, 
            customAmount 
        });
        
        // Handle null/undefined amounts
        if (!cardAmount && cardAmount !== 0) {
            console.error('Card amount is null/undefined for type:', membershipType);
            return;
        }
        
        const standardAmount = parseFloat(cardAmount);
        if (isNaN(standardAmount)) {
            console.error('Invalid standard amount for type:', membershipType, 'amount:', cardAmount);
            return;
        }
        
        let finalAmount = standardAmount;
        let usesCustomAmount = false;
        
        if (isCustom && customAmount !== null && customAmount !== undefined) {
            const parsedCustomAmount = parseFloat(customAmount);
            if (!isNaN(parsedCustomAmount) && parsedCustomAmount > 0) {
                finalAmount = parsedCustomAmount;
                usesCustomAmount = finalAmount !== standardAmount;
            } else {
                console.error('Invalid custom amount:', customAmount, 'parsed:', parsedCustomAmount);
                console.error('Falling back to standard amount:', standardAmount);
                // Fall back to standard amount instead of returning early
                finalAmount = standardAmount;
                usesCustomAmount = false;
            }
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
        
        // Update membership fee display
        this.updateMembershipFeeDisplay(membershipType, finalAmount, usesCustomAmount);
        
        if (usesCustomAmount) {
            this.validateCustomAmount(membershipType, finalAmount);
        }
    }
    
    updateMembershipFeeDisplay(membershipType, amount, isCustom) {
        const feeDisplay = $('#membership-fee-display');
        const feeDetails = $('#fee-details');
        
        if (!membershipType || !amount) {
            feeDisplay.hide();
            return;
        }
        
        // Find the membership type details
        const membershipTypeDetails = this.membershipTypes && this.membershipTypes.find(t => t.name === membershipType);
        const membershipTypeName = membershipTypeDetails ? 
            (membershipTypeDetails.membership_type_name || membershipTypeDetails.name) : 
            membershipType;
        
        const subscriptionPeriod = membershipTypeDetails ? 
            (membershipTypeDetails.subscription_period || 'year') : 
            'year';
        
        const periodText = subscriptionPeriod.toLowerCase() === 'quarterly' ? 'Quarterly' : `per ${subscriptionPeriod}`;
        
        // Format the amount
        const formattedAmount = `EUR ${parseFloat(amount).toFixed(2)}`;
        
        // Build the display content
        let content = `<p><strong>Type:</strong> ${membershipTypeName}</p>`;
        content += `<p><strong>Amount:</strong> ${formattedAmount} ${periodText}`;
        
        if (isCustom) {
            content += ` <span class="badge badge-secondary">Custom Amount</span>`;
        }
        
        content += `</p>`;
        
        if (membershipTypeDetails && membershipTypeDetails.description) {
            content += `<p><strong>Description:</strong> ${membershipTypeDetails.description}</p>`;
        }
        
        feeDetails.html(content);
        feeDisplay.show();
        
        console.log('Updated membership fee display:', { membershipType, amount, isCustom });
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
            
            // Update radio button and trigger change event for field switching
            const radioButton = $(`.payment-method-radio[value="${methodName}"]`);
            console.log('Main app: Found radio button for', methodName, ':', radioButton.length);
            radioButton.prop('checked', true).trigger('change');
        }
        
        // Apply the working pattern from member doctype for dynamic field switching
        this.handlePaymentMethodChange(methodName);
        
        // Show/hide SEPA notice
        if (methodName === 'Direct Debit') {
            $('#sepa-mandate-notice').show();
        } else {
            $('#sepa-mandate-notice').hide();
        }
    }
    
    // Implement payment method field switching similar to member doctype UIUtils.handle_payment_method_change
    handlePaymentMethodChange(methodName) {
        const is_direct_debit = methodName === 'Direct Debit';
        const is_credit_card = methodName === 'Credit Card';
        const is_bank_transfer = methodName === 'Bank Transfer';
        const show_bank_details = ['Direct Debit', 'Bank Transfer'].includes(methodName);
        
        console.log('Main app: Handling payment method change to:', methodName);
        console.log('Main app: is_direct_debit:', is_direct_debit, 'is_credit_card:', is_credit_card, 'is_bank_transfer:', is_bank_transfer);
        
        // Hide all payment detail sections first
        $('#credit-card-details').hide();
        $('#bank-account-details').hide();
        $('#bank-transfer-notice').hide();
        $('#bank-transfer-details').hide();
        
        // Show appropriate section based on payment method
        if (is_credit_card) {
            console.log('Main app: Showing credit card details');
            $('#credit-card-details').show();
            
            // Set required attributes for credit card fields
            $('#card_number, #card_holder_name, #expiry_month, #expiry_year, #cvv').prop('required', true);
            $('#iban, #bank_account_name').prop('required', false);
        } else if (is_direct_debit) {
            console.log('Main app: Showing bank account details for Direct Debit');
            $('#bank-account-details').show();
            
            // Set required attributes for bank account fields
            $('#iban, #bank_account_name').prop('required', true);
            $('#bic').prop('required', false); // BIC is optional
            $('#card_number, #card_holder_name, #expiry_month, #expiry_year, #cvv').prop('required', false);
        } else if (is_bank_transfer) {
            console.log('Main app: Showing bank transfer details with account fields');
            $('#bank-transfer-details').show();
            
            // Bank transfer fields are optional (for payment matching purposes)
            $('#card_number, #card_holder_name, #expiry_month, #expiry_year, #cvv').prop('required', false);
            $('#iban, #bank_account_name, #bic').prop('required', false);
            $('#transfer_iban, #transfer_account_name, #transfer_bic').prop('required', false);
        }
        
        // Clear validation errors when switching payment methods
        $('#credit-card-details input, #bank-account-details input, #bank-transfer-details input').removeClass('is-invalid is-valid');
        $('.invalid-feedback').hide();
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
// BIC DERIVATION UTILITY FUNCTION
// ===================================

function getBicFromIban(iban) {
    /**
     * Derive BIC from IBAN using the same logic as the backend
     * This matches the get_bic_from_iban() function in direct_debit_batch.py
     */
    if (!iban || iban.length < 8) {
        return null;
    }
    
    try {
        // Remove spaces and convert to uppercase
        iban = iban.replace(/\s+/g, '').toUpperCase();
        
        // Dutch IBAN - extract bank code
        if (iban.startsWith('NL')) {
            const bankCode = iban.substring(4, 8);
            
            // Common Dutch bank codes (matching backend)
            const bankCodes = {
                'INGB': 'INGBNL2A',  // ING Bank
                'ABNA': 'ABNANL2A',  // ABN AMRO
                'RABO': 'RABONL2U',  // Rabobank
                'TRIO': 'TRIONL2U',  // Triodos Bank
                'SNSB': 'SNSBNL2A',  // SNS Bank
                'ASNB': 'ASNBNL21',  // ASN Bank
                'KNAB': 'KNABNL2H'   // Knab
            };
            
            return bankCodes[bankCode] || null;
        }
        
        // For other countries, we would need a more extensive mapping
        return null;
    } catch (error) {
        console.error('Error determining BIC from IBAN:', iban, error);
        return null;
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
        // Ensure age warning element exists only if birth_date field exists
        const birthDateField = $('#birth_date');
        if (birthDateField.length > 0 && $('#age-warning').length === 0) {
            birthDateField.after('<div id="age-warning" class="alert mt-2" style="display: none;"></div>');
        }
    }
    
    bindEvents() {
        // Use delegated event handlers to avoid null reference errors
        $(document).off('blur', '#email').on('blur', '#email', () => this.validateEmail());
        $(document).off('change blur', '#birth_date').on('change blur', '#birth_date', () => this.validateAge());
    }
    
    async validateEmail() {
        const emailField = $('#email');
        if (emailField.length === 0) {
            console.warn('Email field not found');
            return true;
        }
        
        const email = emailField.val();
        if (!email) return true;
        
        try {
            // Check if membershipApp and its API are available
            if (typeof membershipApp === 'undefined' || !membershipApp.apiService) {
                console.warn('MembershipApp API not available, skipping email validation');
                return true;
            }
            
            const result = await membershipApp.apiService.validateEmail(email);
            
            if (!result.valid) {
                if (this.validator) {
                    this.validator.showError('#email', result.message);
                }
                return false;
            }
            
            if (this.validator) {
                this.validator.showSuccess('#email');
            }
            return true;
        } catch (error) {
            console.error('Email validation error:', error);
            return true; // Don't block on API errors
        }
    }
    
    validateAge() {
        const birthDateField = $('#birth_date');
        if (birthDateField.length === 0) {
            console.warn('Birth date field not found');
            return true;
        }
        
        const birthDate = birthDateField.val();
        if (!birthDate) return true;
        
        const age = this.calculateAge(birthDate);
        let warningDiv = $('#age-warning');
        
        // Create warning div if it doesn't exist
        if (warningDiv.length === 0) {
            birthDateField.after('<div id="age-warning" class="alert mt-2" style="display: none;"></div>');
            warningDiv = $('#age-warning');
        }
        
        // Clear previous states
        birthDateField.removeClass('is-invalid is-valid');
        birthDateField.siblings('.invalid-feedback').remove();
        warningDiv.hide().removeClass('alert-info alert-warning alert-danger');
        
        if (age < 0) {
            if (this.validator) {
                this.validator.showError('#birth_date', 'Birth date cannot be in the future');
            }
            return false;
        }
        
        birthDateField.addClass('is-valid');
        
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
        
        try {
            const birth = new Date(birthDate);
            const today = new Date();
            
            // Check for invalid dates
            if (isNaN(birth.getTime())) {
                console.warn('Invalid birth date:', birthDate);
                return -1;
            }
            
            if (birth > today) {
                return -1; // Future date
            }
            
            let age = today.getFullYear() - birth.getFullYear();
            
            // Adjust for birthday not yet reached this year
            if (today.getMonth() < birth.getMonth() || 
                (today.getMonth() === birth.getMonth() && today.getDate() < birth.getDate())) {
                age--;
            }
            
            return Math.max(0, age); // Ensure non-negative age
        } catch (error) {
            console.error('Error calculating age:', error);
            return 0;
        }
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
            if (typeof membershipApp === 'undefined' || !membershipApp.apiService) {
                console.warn('MembershipApp API not available, skipping postal code validation');
                return;
            }
            
            const result = await membershipApp.apiService.validatePostalCode(postalCode, country);
            
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
        
        // Also ensure main app payment method events are bound after DOM update
        if (typeof membershipApp !== 'undefined' && membershipApp.bindPaymentMethodEvents) {
            console.log('PaymentStep: Re-binding main app payment method events after loading methods');
            membershipApp.bindPaymentMethodEvents();
        }
        
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
        console.log('PaymentStep: Binding payment events');
        
        $('.payment-method-option').off('click').on('click', (e) => {
            const target = $(e.target).closest('.payment-method-option');
            const methodName = target.data('method');
            console.log('PaymentStep: Payment method clicked:', methodName, 'Target:', target);
            this.selectPaymentMethod(methodName);
        });
        
        $('.payment-method-radio').off('change').on('change', (e) => {
            if ($(e.target).is(':checked')) {
                console.log('PaymentStep: Payment method radio changed:', $(e.target).val());
                this.selectPaymentMethod($(e.target).val());
            }
        });
        
        // Also bind to the main app's payment method events for field switching
        if (typeof membershipApp !== 'undefined' && membershipApp.bindPaymentMethodEvents) {
            console.log('PaymentStep: Calling main app bindPaymentMethodEvents');
            membershipApp.bindPaymentMethodEvents();
        }
        
        console.log('PaymentStep: Found payment method options:', $('.payment-method-option').length);
        console.log('PaymentStep: Found payment method radios:', $('.payment-method-radio').length);
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
            
            // Update radio button and trigger change event
            const radioButton = $(`.payment-method-radio[value="${methodName}"]`);
            console.log('PaymentStep: Found radio button for', methodName, ':', radioButton.length);
            radioButton.prop('checked', true).trigger('change');
        }
        
        // Use the main app's handlePaymentMethodChange for consistent behavior
        if (typeof membershipApp !== 'undefined' && membershipApp.handlePaymentMethodChange) {
            console.log('PaymentStep: Using main app handlePaymentMethodChange for:', methodName);
            membershipApp.handlePaymentMethodChange(methodName);
        } else {
            // Fallback for standalone operation
            console.log('PaymentStep: Fallback - showing fields for payment method:', methodName);
            $('#credit-card-details').hide();
            $('#bank-account-details').hide();
            $('#bank-transfer-notice').hide();
            $('#bank-transfer-details').hide();
            
            if (methodName === 'Credit Card') {
                console.log('PaymentStep: Showing credit card fields');
                $('#credit-card-details').show();
            } else if (methodName === 'Direct Debit') {
                console.log('PaymentStep: Showing bank account fields');
                $('#bank-account-details').show();
            } else if (methodName === 'Bank Transfer') {
                console.log('PaymentStep: Showing bank transfer details with account fields');
                $('#bank-transfer-details').show();
            }
        }
    }
    
    updateSummary(state) {
        // Use the main application's comprehensive updateApplicationSummary method
        // which includes detailed financial information and proper data handling
        if (typeof membershipApp !== 'undefined' && membershipApp.updateApplicationSummary) {
            membershipApp.updateApplicationSummary();
        } else {
            // Fallback to basic summary if main app method is not available
            this.updateBasicSummary(state);
        }
    }
    
    updateBasicSummary(state) {
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
            const membershipTypes = state.get('membershipTypes') || [];
            const membershipType = membershipTypes.find(t => t.name === membership.type);
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
        
        const paymentMethod = $('input[name="payment_method_selection"]:checked').val() || $('#payment_method').val();
        if (paymentMethod) {
            content += '<p><strong>Payment Method:</strong> ' + paymentMethod + '</p>';
        }
        
        summary.html(content);
    }
    
    calculateAge(birthDate) {
        if (!birthDate) return 0;
        
        try {
            const birth = new Date(birthDate);
            const today = new Date();
            
            if (isNaN(birth.getTime())) {
                console.warn('Invalid birth date in PaymentStep:', birthDate);
                return 0;
            }
            
            let age = today.getFullYear() - birth.getFullYear();
            
            if (today.getMonth() < birth.getMonth() || 
                (today.getMonth() === birth.getMonth() && today.getDate() < birth.getDate())) {
                age--;
            }
            
            return Math.max(0, age);
        } catch (error) {
            console.error('Error calculating age in PaymentStep:', error);
            return 0;
        }
    }
    
    async validate() {
        let valid = true;
        
        // Clear previous validation
        $('.invalid-feedback').remove();
        $('.is-invalid').removeClass('is-invalid');
        
        // Payment method validation
        const paymentMethod = $('input[name="payment_method_selection"]:checked').val() || $('#payment_method').val();
        if (!paymentMethod) {
            if ($('#payment-method-fallback').is(':visible')) {
                $('#payment_method').addClass('is-invalid');
                $('#payment_method').after('<div class="invalid-feedback">Please select a payment method</div>');
            } else {
                const errorDiv = $('<div class="invalid-feedback d-block text-danger mb-3">Please select a payment method</div>');
                $('#payment-methods-list').after(errorDiv);
            }
            valid = false;
        } else {
            // Validate payment-specific fields based on selected method
            if (paymentMethod === 'Credit Card') {
                // Credit card validation
                if (!$('#card_number').val()) {
                    $('#card_number').addClass('is-invalid');
                    $('#card_number').after('<div class="invalid-feedback">Card number is required</div>');
                    valid = false;
                }
                
                if (!$('#card_holder_name').val()) {
                    $('#card_holder_name').addClass('is-invalid');
                    $('#card_holder_name').after('<div class="invalid-feedback">Cardholder name is required</div>');
                    valid = false;
                }
                
                if (!$('#expiry_month').val()) {
                    $('#expiry_month').addClass('is-invalid');
                    $('#expiry_month').after('<div class="invalid-feedback">Expiry month is required</div>');
                    valid = false;
                }
                
                if (!$('#expiry_year').val()) {
                    $('#expiry_year').addClass('is-invalid');
                    $('#expiry_year').after('<div class="invalid-feedback">Expiry year is required</div>');
                    valid = false;
                }
                
                if (!$('#cvv').val()) {
                    $('#cvv').addClass('is-invalid');
                    $('#cvv').after('<div class="invalid-feedback">CVV is required</div>');
                    valid = false;
                }
                
                // Basic card number validation (length and digits only)
                const cardNumber = $('#card_number').val().replace(/\s/g, '');
                if (cardNumber && (cardNumber.length < 13 || cardNumber.length > 19 || !/^\d+$/.test(cardNumber))) {
                    $('#card_number').addClass('is-invalid');
                    $('#card_number').after('<div class="invalid-feedback">Please enter a valid card number</div>');
                    valid = false;
                }
                
            } else if (paymentMethod === 'Direct Debit') {
                // Bank account validation
                if (!$('#iban').val()) {
                    $('#iban').addClass('is-invalid');
                    $('#iban').after('<div class="invalid-feedback">IBAN is required</div>');
                    valid = false;
                }
                
                if (!$('#bank_account_name').val()) {
                    $('#bank_account_name').addClass('is-invalid');
                    $('#bank_account_name').after('<div class="invalid-feedback">Account holder name is required</div>');
                    valid = false;
                }
                
                // Basic IBAN validation (at least country code + 2 check digits + account identifier)
                const iban = $('#iban').val().replace(/\s/g, '');
                if (iban && (iban.length < 15 || iban.length > 34 || !/^[A-Z]{2}[0-9]{2}[A-Z0-9]+$/i.test(iban))) {
                    $('#iban').addClass('is-invalid');
                    $('#iban').after('<div class="invalid-feedback">Please enter a valid IBAN</div>');
                    valid = false;
                }
            }
            // Bank Transfer doesn't require additional fields
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
            
            // Use direct AJAX call instead of frappe.call to avoid URL issues
            $.ajax({
                url: '/api/method/verenigingen.api.membership_application.submit_application_with_tracking',
                type: 'POST',
                data: {
                    data: JSON.stringify(data)
                },
                headers: {
                    'X-Frappe-CSRF-Token': frappe.csrf_token || ''
                },
                dataType: 'json',
                success: function(response) {
                    console.log('Direct AJAX response:', response);
                    if (response.message && response.message.success) {
                        resolve(response.message);
                    } else if (response.message) {
                        console.log('Full error response:', response.message);
                        const errorMsg = response.message.message || response.message.error || 'Submission failed';
                        reject(new Error(errorMsg));
                    } else {
                        reject(new Error('Unknown response format'));
                    }
                },
                error: function(xhr, status, error) {
                    console.error('Direct AJAX error:', {xhr, status, error});
                    let errorMsg = 'Network error occurred';
                    
                    if (xhr.responseJSON && xhr.responseJSON.exc) {
                        errorMsg = xhr.responseJSON.exc;
                    } else if (xhr.responseText) {
                        try {
                            const parsed = JSON.parse(xhr.responseText);
                            errorMsg = parsed.message || parsed.exc || errorMsg;
                        } catch (e) {
                            errorMsg = `Server error: ${xhr.status} ${xhr.statusText}`;
                        }
                    } else {
                        errorMsg = `Server error: ${xhr.status} ${xhr.statusText}`;
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

// Global debug functions for beta testing (available after initialization)
window.debugApp = () => {
    if (!window.membershipApp) {
        console.error('membershipApp not initialized yet');
        return null;
    }
    console.log('=== APPLICATION DEBUG ===');
    console.log('State:', window.membershipApp.state.getData());
    console.log('Current step:', window.membershipApp.state.currentStep);
    console.log('Selected membership:', window.membershipApp.state.get('membership'));
    console.log('========================');
    return window.membershipApp.state.getData();
};
    
window.debugMembershipSelection = () => {
    if (!window.membershipApp) {
        console.error('membershipApp not initialized yet');
        return;
    }
    console.log('=== MEMBERSHIP SELECTION DEBUG ===');
    const membership = window.membershipApp.state.get('membership');
        console.log('Membership data:', membership);
        console.log('Legacy compatibility:');
    console.log('  - selected_membership_type:', window.membershipApp.state.get('selected_membership_type'));
    console.log('  - membership_amount:', window.membershipApp.state.get('membership_amount'));
    console.log('  - uses_custom_amount:', window.membershipApp.state.get('uses_custom_amount'));
        
        // Check visible custom sections
        $('.custom-amount-section:visible').each(function() {
            const card = $(this).closest('.membership-type-card');
            console.log('Visible custom section for:', card.data('type'));
            console.log('Input value:', $(this).find('.custom-amount-input').val());
        });
        
        // Check selected membership cards
        $('.membership-type-card.selected').each(function() {
            console.log('Selected card:', $(this).data('type'), 'amount:', $(this).data('amount'));
        });
        
        // Test form data collection
        console.log('All form data:', membershipApp.getAllFormData());
        
        console.log('=================================');
        return membership;
    };
    
    window.debugAge = (birthDate) => {
        try {
            const testBirthDate = birthDate || $('#birth_date').val();
            const age = membershipApp.calculateAge(testBirthDate);
            console.log('Age calculation:', { birthDate: testBirthDate, age });
            
            if (age > 100) {
                console.log('Should show >100 warning');
            } else if (age < 12) {
                console.log('Should show <12 warning');
            } else {
                console.log('No age warning needed');
            }
            
            // Test the validation display
            if (testBirthDate) {
                $('#birth_date').val(testBirthDate).trigger('change');
            }
            
            return age;
        } catch (error) {
            console.error('Error in debugAge:', error);
            return 0;
        }
    };
    
// Debug commands available:
// - debugApp() - Show full application state  
// - debugMembershipSelection() - Check membership selection
// - debugAge(birthDate) - Test age validation

// ConfirmationStep class for step 6
class ConfirmationStep extends BaseStep {
    constructor() {
        super('confirmation');
    }
    
    render(state) {
        // Update final summary when rendered
        if (typeof membershipApp !== 'undefined' && membershipApp.updateFinalApplicationSummary) {
            membershipApp.updateFinalApplicationSummary();
        }
    }
    
    async validate() {
        let valid = true;
        
        // Clear previous validation
        $('.invalid-feedback').remove();
        $('.is-invalid').removeClass('is-invalid');
        
        // Terms validation
        if (!$('#terms').is(':checked')) {
            $('#terms').addClass('is-invalid');
            $('#terms').closest('.form-check').after('<div class="invalid-feedback d-block">You must accept the terms and conditions</div>');
            valid = false;
        }
        
        // GDPR consent validation
        if (!$('#gdpr_consent').is(':checked')) {
            $('#gdpr_consent').addClass('is-invalid');
            $('#gdpr_consent').closest('.form-check').after('<div class="invalid-feedback d-block">You must consent to data processing</div>');
            valid = false;
        }
        
        // Accuracy confirmation validation
        if (!$('#confirm_accuracy').is(':checked')) {
            $('#confirm_accuracy').addClass('is-invalid');
            $('#confirm_accuracy').closest('.form-check').after('<div class="invalid-feedback d-block">You must confirm the accuracy of your information</div>');
            valid = false;
        }
        
        return valid;
    }
}

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
