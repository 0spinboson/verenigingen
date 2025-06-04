// verenigingen/verenigingen/doctype/chapter/chapter.js
// Main entry point for Chapter form functionality

import { ChapterController } from './modules/ChapterController.js';

// Store controller instance globally for debugging (optional)
window._chapterDebug = window._chapterDebug || {};

frappe.ui.form.on('Chapter', {
    onload: function(frm) {
        // Initialize the controller
        if (!frm._chapter_controller) {
            frm._chapter_controller = new ChapterController(frm);
            
            // Store for debugging (optional)
            window._chapterDebug[frm.doc.name] = frm._chapter_controller;
        }
    },
    
    refresh: function(frm) {
        if (frm._chapter_controller) {
            frm._chapter_controller.refresh();
        }
    },
    
    validate: function(frm) {
        // Validate before save
        if (frm._chapter_controller) {
            const isValid = frm._chapter_controller.validate();
            if (!isValid) {
                frappe.validated = false;
            }
            return isValid;
        }
        return true;
    },
    
    before_save: function(frm) {
        if (frm._chapter_controller) {
            return frm._chapter_controller.beforeSave();
        }
    },
    
    after_save: function(frm) {
        if (frm._chapter_controller) {
            frm._chapter_controller.afterSave();
        }
    },
    
    on_submit: function(frm) {
        if (frm._chapter_controller) {
            frm._chapter_controller.onSubmit();
        }
    },
    
    // Field-specific handlers
    postal_codes: function(frm) {
        if (frm._chapter_controller) {
            frm._chapter_controller.onPostalCodesChange();
        }
    },
    
    chapter_head: function(frm) {
        if (frm._chapter_controller) {
            frm._chapter_controller.onChapterHeadChange();
        }
    },
    
    region: function(frm) {
        if (frm._chapter_controller) {
            frm._chapter_controller.onRegionChange();
        }
    },
    
    published: function(frm) {
        if (frm._chapter_controller) {
            frm._chapter_controller.onPublishedChange();
        }
    },
    
    on_destroy: function(frm) {
        // Cleanup when form is destroyed
        if (frm._chapter_controller) {
            frm._chapter_controller.destroy();
            delete frm._chapter_controller;
            
            // Remove from debug storage
            if (window._chapterDebug && window._chapterDebug[frm.doc.name]) {
                delete window._chapterDebug[frm.doc.name];
            }
        }
    }
});

// Child table events - Chapter Board Member
frappe.ui.form.on('Chapter Board Member', {
    board_members_add: function(frm, cdt, cdn) {
        if (frm._chapter_controller) {
            frm._chapter_controller.boardManager.onBoardMemberAdd(cdt, cdn);
        }
    },
    
    board_members_remove: function(frm, cdt, cdn) {
        if (frm._chapter_controller) {
            frm._chapter_controller.boardManager.onBoardMemberRemove(cdt, cdn);
        }
    },
    
    volunteer: function(frm, cdt, cdn) {
        if (frm._chapter_controller) {
            frm._chapter_controller.boardManager.onVolunteerChange(cdt, cdn);
        }
    },
    
    chapter_role: function(frm, cdt, cdn) {
        if (frm._chapter_controller) {
            frm._chapter_controller.boardManager.onRoleChange(cdt, cdn);
        }
    },
    
    from_date: function(frm, cdt, cdn) {
        if (frm._chapter_controller) {
            frm._chapter_controller.boardManager.onDateChange(cdt, cdn, 'from_date');
        }
    },
    
    to_date: function(frm, cdt, cdn) {
        if (frm._chapter_controller) {
            frm._chapter_controller.boardManager.onDateChange(cdt, cdn, 'to_date');
        }
    },
    
    is_active: function(frm, cdt, cdn) {
        if (frm._chapter_controller) {
            frm._chapter_controller.boardManager.onActiveChange(cdt, cdn);
        }
    }
});

// Child table events - Chapter Member
frappe.ui.form.on('Chapter Member', {
    members_add: function(frm, cdt, cdn) {
        if (frm._chapter_controller) {
            frm._chapter_controller.memberManager.onMemberAdd(cdt, cdn);
        }
    },
    
    members_remove: function(frm, cdt, cdn) {
        if (frm._chapter_controller) {
            frm._chapter_controller.memberManager.onMemberRemove(cdt, cdn);
        }
    },
    
    member: function(frm, cdt, cdn) {
        if (frm._chapter_controller) {
            frm._chapter_controller.memberManager.onMemberChange(cdt, cdn);
        }
    },
    
    enabled: function(frm, cdt, cdn) {
        if (frm._chapter_controller) {
            frm._chapter_controller.memberManager.onEnabledChange(cdt, cdn);
        }
    },
    
    introduction: function(frm, cdt, cdn) {
        if (frm._chapter_controller) {
            frm._chapter_controller.memberManager.onIntroductionChange(cdt, cdn);
        }
    },
    
    website_url: function(frm, cdt, cdn) {
        if (frm._chapter_controller) {
            frm._chapter_controller.memberManager.onWebsiteURLChange(cdt, cdn);
        }
    }
});

// Utility functions that might be called from other parts of the system
frappe.ui.form.on('Chapter', {
    // These can be called externally via frm.trigger()
    update_chapter_head: function(frm) {
        if (frm._chapter_controller) {
            frm._chapter_controller.updateChapterHead();
        }
    },
    
    sync_board_members: function(frm) {
        if (frm._chapter_controller) {
            frm._chapter_controller.boardManager.syncWithVolunteerSystem();
        }
    },
    
    refresh_statistics: function(frm) {
        if (frm._chapter_controller) {
            frm._chapter_controller.statistics.refresh();
        }
    },
    
    validate_postal_codes: function(frm) {
        if (frm._chapter_controller) {
            frm._chapter_controller.validatePostalCodes();
        }
    }
});

// Global utility for debugging
window.getChapterController = function(chapterName) {
    if (window._chapterDebug && window._chapterDebug[chapterName]) {
        return window._chapterDebug[chapterName];
    }
    
    // Try to find it from current form
    if (cur_frm && cur_frm.doc.doctype === 'Chapter' && cur_frm.doc.name === chapterName) {
        return cur_frm._chapter_controller;
    }
    
    return null;
};

// Add custom keyboard shortcuts
frappe.ui.keys.add_shortcut({
    shortcut: 'ctrl+shift+b',
    action: () => {
        const controller = cur_frm && cur_frm._chapter_controller;
        if (controller && cur_frm.doc.doctype === 'Chapter') {
            controller.boardManager.showManageDialog();
        }
    },
    description: __('Manage Board Members'),
    page: frappe.get_route()[0] === 'Form' && frappe.get_route()[1] === 'Chapter'
});

frappe.ui.keys.add_shortcut({
    shortcut: 'ctrl+shift+m',
    action: () => {
        const controller = cur_frm && cur_frm._chapter_controller;
        if (controller && cur_frm.doc.doctype === 'Chapter') {
            controller.memberManager.showMemberDirectory();
        }
    },
    description: __('Show Member Directory'),
    page: frappe.get_route()[0] === 'Form' && frappe.get_route()[1] === 'Chapter'
});

frappe.ui.keys.add_shortcut({
    shortcut: 'ctrl+shift+s',
    action: () => {
        const controller = cur_frm && cur_frm._chapter_controller;
        if (controller && cur_frm.doc.doctype === 'Chapter') {
            controller.statistics.showStatisticsDialog();
        }
    },
    description: __('Show Chapter Statistics'),
    page: frappe.get_route()[0] === 'Form' && frappe.get_route()[1] === 'Chapter'
});
