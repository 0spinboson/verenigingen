// verenigingen/verenigingen/doctype/chapter/modules/ChapterController.js

import { BoardManager } from './BoardManager.js';
import { MemberManager } from './MemberManager.js';
import { CommunicationManager } from './CommunicationManager.js';
import { ChapterStatistics } from './ChapterStatistics.js';
import { ChapterUI } from './ChapterUI.js';
import { ChapterState } from './ChapterState.js';
import { ChapterValidation } from '../utils/ChapterValidation.js';
import { ChapterConfig } from '../config/ChapterConfig.js';

export class ChapterController {
    constructor(frm) {
        this.frm = frm;
        this.state = new ChapterState();
        this.ui = new ChapterUI(frm, this.state);
        
        // Initialize managers
        this.boardManager = new BoardManager(frm, this.state, this.ui);
        this.memberManager = new MemberManager(frm, this.state, this.ui);
        this.communicationManager = new CommunicationManager(frm, this.state);
        this.statistics = new ChapterStatistics(frm, this.state);
        
        // Bind event handlers
        this.bindEvents();
        
        // Initialize state
        this.initializeState();
    }
    
    bindEvents() {
        // Subscribe to state changes
        this.state.subscribe((path, value) => {
            this.handleStateChange(path, value);
        });
    }
    
    initializeState() {
        if (this.frm.doc.name) {
            // Load initial data
            this.state.update('chapter', {
                name: this.frm.doc.name,
                region: this.frm.doc.region,
                boardMembers: this.frm.doc.board_members || [],
                members: this.frm.doc.members || []
            });
        }
    }
    
    refresh() {
        // Clear any existing UI elements
        this.ui.clearCustomButtons();
        
        // Add navigation buttons
        this.addNavigationButtons();
        
        // Add action buttons
        this.addActionButtons();
        
        // Add board management buttons
        if (this.frm.doc.name) {
            this.boardManager.addButtons();
            this.memberManager.addButtons();
            this.communicationManager.addButtons();
            this.statistics.addButtons();
        }
        
        // Update UI elements
        this.ui.updateMembersSummary();
        this.ui.updatePostalCodePreview();
        
        // Set up board members grid
        this.boardManager.setupGrid();
        
        // Check for board memberships for current user
        this.checkUserBoardMemberships();
    }
    
    addNavigationButtons() {
        const buttons = [
            {
                label: __('View Members'),
                action: () => this.memberManager.viewMembers(),
                group: __('View')
            },
            {
                label: __('Current SEPA Mandate'),
                action: () => this.navigateToCurrentMandate(),
                group: __('View'),
                condition: () => this.hasCurrentMandate()
            }
        ];
        
        buttons.forEach(btn => {
            if (!btn.condition || btn.condition()) {
                this.ui.addButton(btn.label, btn.action, btn.group);
            }
        });
    }
    
    addActionButtons() {
        const buttons = [
            {
                label: __('Manage Board Members'),
                action: () => this.boardManager.showManageDialog(),
                group: __('Board')
            },
            {
                label: __('Transition Board Role'),
                action: () => this.boardManager.showTransitionDialog(),
                group: __('Board')
            },
            {
                label: __('View Board History'),
                action: () => this.boardManager.showHistory(),
                group: __('Board')
            },
            {
                label: __('Sync with Volunteer System'),
                action: () => this.boardManager.syncWithVolunteerSystem(),
                group: __('Board')
            },
            {
                label: __('Bulk Remove Board Members'),
                action: () => this.boardManager.showBulkRemoveDialog(),
                group: __('Board')
            }
        ];
        
        buttons.forEach(btn => {
            this.ui.addButton(btn.label, btn.action, btn.group);
        });
    }
    
    async checkUserBoardMemberships() {
        try {
            const result = await frappe.call({
                method: 'verenigingen.verenigingen.doctype.member.member.get_board_memberships',
                args: {
                    member_name: this.frm.doc.name
                }
            });
            
            if (result.message && result.message.length) {
                this.ui.showBoardMemberships(result.message);
            }
        } catch (error) {
            console.error('Error checking board memberships:', error);
        }
    }
    
    hasCurrentMandate() {
        // Check if chapter has a current SEPA mandate
        return this.frm.doc.current_sepa_mandate ? true : false;
    }
    
    navigateToCurrentMandate() {
        if (this.frm.doc.current_sepa_mandate) {
            frappe.set_route('Form', 'SEPA Mandate', this.frm.doc.current_sepa_mandate);
        }
    }
    
    async beforeSave() {
        // Validate board members
        const validation = await this.boardManager.validateBoardMembers();
        if (!validation.isValid) {
            frappe.validated = false;
            frappe.msgprint({
                title: __('Validation Error'),
                indicator: 'red',
                message: validation.errors.join('<br>')
            });
            return false;
        }
        
        // Validate postal codes
        const postalValidation = ChapterValidation.validatePostalCodes(this.frm.doc.postal_codes);
        if (!postalValidation.isValid) {
            this.ui.showPostalCodeWarning(postalValidation.invalidPatterns);
        }
        
        return true;
    }
    
    afterSave() {
        // Refresh the form to show updated data
        this.frm.refresh();
        
        // Show success message
        frappe.show_alert({
            message: __('Chapter saved successfully'),
            indicator: 'green'
        }, 5);
    }
    
    handleStateChange(path, value) {
        // Handle state changes
        console.log('State changed:', path, value);
        
        // Update UI based on state changes
        if (path.startsWith('boardMembers')) {
            this.boardManager.handleBoardMembersChange();
        } else if (path.startsWith('ui.bulkActionsVisible')) {
            this.ui.toggleBulkActions(value);
        }
    }
    
    destroy() {
        // Cleanup all managers
        this.boardManager.destroy();
        this.memberManager.destroy();
        this.communicationManager.destroy();
        this.statistics.destroy();
        this.ui.destroy();
        this.state.destroy();
    }
}
