/**
 * Membership Application - Refactored Architecture with Bug Fixes
 * Beta Ready Version with Age Validation and Custom Amount Support
 */

// ===================================
// 1. CORE APPLICATION CLASS
// ===================================

class MembershipApplication {
    constructor(config = {}) {
        this.config = {
            maxSteps: 5,
            autoSaveInterval: 30000,
            ...config
        };
        
        this.state = new ApplicationState();
        this.validator = new FormValidator();
        this.api = new MembershipAPI();
        this.ui = new UIManager();
        
        this.steps = [
            new PersonalInfoStep(),
            new AddressStep(), 
            new MembershipStep(),
            new VolunteerStep(),
            new PaymentStep()
        ];
        
        this.init();
    }
    
    async init() {
        try {
            console.log('Initializing membership application...');
            await this.loadInitialData();
            this.bindEvents();
            this.showStep(1);
            this.startAutoSave();
            console.log('Membership application initialized successfully');
        } catch (error) {
            console.error('Failed to initialize application:', error);
            this.ui.showError('Failed to initialize application', error);
        }
    }
    
    async loadInitialData() {
        console.log('Loading form data...');
        const data = await this.api.getFormData();
        this.state.setInitialData(data);
        console.log('Form data loaded:', data);
    }
    
    bindEvents() {
        $('#next-btn').off('click').on('click', () => this.nextStep());
        $('#prev-btn').off('click').on('click', () => this.prevStep());
        $('#membership-application-form').off('submit').on('submit', (e) => this.submit(e));
    }
    
    async nextStep() {
        const currentStep = this.getCurrentStep();
        console.log(`Validating step ${this.state.currentStep}`);
        
        if (await currentStep.validate()) {
            this.state.incrementStep();
            this.showStep(this.state.currentStep);
        } else {
            console.log(`Step ${this.state.currentStep} validation failed`);
        }
    }
    
    prevStep() {
        this.state.decrementStep();
        this.showStep(this.state.currentStep);
    }
    
    showStep(stepNumber) {
        console.log(`Showing step ${stepNumber}`);
        const step = this.steps[stepNumber - 1];
        
        this.ui.hideAllSteps();
        this.ui.showStep(stepNumber);
        this.ui.updateProgress(stepNumber, this.config.maxSteps);
        this.ui.updateNavigation(stepNumber, this.config.maxSteps);
        
        step.render(this.state);
        step.bindEvents();
    }
    
    getCurrentStep() {
        return this.steps[this.state.currentStep - 1];
    }
    
    async submit(event) {
        event.preventDefault();
        console.log('Form submission started');
        
        if (!await this.getCurrentStep().validate()) {
            console.log('Final validation failed');
            return;
        }
        
        try {
            this.ui.setSubmitting(true);
            const formData = this.collectAllData();
            console.log('Submitting application data:', formData);
            
            const result = await this.api.submitApplication(formData);
            console.log('Application submitted successfully:', result);
            
            this.ui.showSuccess(result);
            this.redirectToPayment(result.payment_url);
        } catch (error) {
            console.error('Application submission failed:', error);
            this.ui.showError('Submission failed', error);
        } finally {
            this.ui.setSubmitting(false);
        }
    }
    
    collectAllData() {
        let allData = {};
        
        // Collect data from all steps
        this.steps.forEach(step => {
            allData = { ...allData, ...step.getData() };
        });
        
        return allData;
    }
    
    redirectToPayment(url) {
        if (url) {
            setTimeout(() => window.location.href = url, 2000);
        }
    }
    
    startAutoSave() {
        setInterval(() => {
            const data = this.collectAllData();
            this.api.saveDraft(data).catch(error => {
                console.log('Auto-save failed:', error);
            });
        }, this.config.autoSaveInterval);
    }
    
    // Legacy compatibility methods
    get formData() {
        return this.state.data;
    }
    
    getPaymentMethod() {
        return this.state.get('payment')?.method || null;
    }
    
    setPaymentMethod(method) {
        this.state.set('payment', { method });
    }
    
    get membershipTypes() {
        return this.state.get('membershipTypes') || [];
    }
    
    get paymentMethods() {
        return this.state.get('paymentMethods') || [];
    }
}

// ===================================
// 2. STATE MANAGEMENT
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
// 3. STEP CLASSES
// ===================================

class BaseStep {
    constructor(name) {
        this.name = name;
        this.validator = new FormValidator();
    }
    
    render(state) {
        // Override in subclasses
    }
    
    bindEvents() {
        // Override in subclasses
    }
    
    async validate() {
        throw new Error('validate() must be implemented by subclass');
    }
    
    getData() {
        throw new Error('getData() must be implemented by subclass');
    }
}

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
        
        // FIXED: Proper birthday check (was broken with comma operator)
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
        return await this.call('verenigingen.api.membership_application.submit_application', { data });
    }
    
    async saveDraft(data) {
        return await this.call('verenigingen.api.membership_application.save_draft_application', { data });
    }
    
    async call(method, args = {}) {
        return new Promise((resolve, reject) => {
            frappe.call({
                method,
                args,
                callback: (r) => {
                    if (r.message) {
                        resolve(r.message);
                    } else {
                        reject(new Error('No response from server'));
                    }
                },
                error: reject
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
    
    // Additional CSS for proper styling
    const appCSS = `
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

    #age-warning {
        font-size: 0.875rem;
        border-radius: 0.375rem;
        padding: 0.75rem;
        margin-top: 0.5rem;
    }

    #age-warning.alert-info {
        background-color: #cce7ff;
        border: 1px solid #99d6ff;
        color: #004085;
    }

    #age-warning.alert-warning {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        color: #856404;
    }

    #age-warning i {
        margin-right: 0.5rem;
    }

    .membership-type-card {
        border: 2px solid #dee2e6;
        border-radius: 8px;
        padding: 1rem;
        cursor: pointer;
        transition: all 0.3s ease;
        margin-bottom: 1rem;
    }

    .membership-type-card:hover {
        border-color: #007bff;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }

    .membership-type-card.selected {
        border-color: #007bff;
        background-color: #e7f3ff;
    }

    .payment-method-option {
        border: 2px solid #dee2e6;
        border-radius: 8px;
        padding: 1rem;
        cursor: pointer;
        transition: all 0.3s ease;
        margin-bottom: 1rem;
    }

    .payment-method-option:hover {
        border-color: #007bff;
        box-shadow: 0 2px 8px rgba(0,123,255,0.15);
    }

    .payment-method-option.selected {
        border-color: #007bff;
        background-color: #f8f9ff;
    }

    .amount-pill {
        background: #e9ecef;
        border: 1px solid #dee2e6;
        border-radius: 20px;
        padding: 0.25rem 0.75rem;
        font-size: 0.875rem;
        cursor: pointer;
        transition: all 0.2s ease;
        margin-right: 0.5rem;
        margin-bottom: 0.5rem;
        display: inline-block;
    }

    .amount-pill:hover {
        background: #007bff;
        color: white;
        border-color: #007bff;
    }

    .amount-pill.selected {
        background: #007bff;
        color: white;
        border-color: #007bff;
    }
    </style>
    `;

    // Inject CSS if not already present
    if (!$('#membership-app-styles').length) {
        $('head').append(appCSS);
        $('head').append('<meta id="membership-app-styles" />');
    }
    
    console.log('Refactored membership application initialized successfully');
    console.log('Available debug commands:');
    console.log('- debugApp() - Show full application state');
    console.log('- debugMembershipSelection() - Check membership selection');
    console.log('- debugAge(birthDate) - Test age validation');
});
