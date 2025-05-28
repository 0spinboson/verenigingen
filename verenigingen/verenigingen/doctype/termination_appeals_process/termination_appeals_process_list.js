frappe.listview_settings['Termination Appeals Process'] = {
    get_indicator: function(doc) {
        const status_colors = {
            'Draft': ['Draft', 'gray'],
            'Submitted': ['Submitted', 'blue'],
            'Under Review': ['Under Review', 'orange'],
            'Pending Decision': ['Pending Decision', 'yellow'],
            'Decided - Upheld': ['Upheld', 'green'],
            'Decided - Rejected': ['Rejected', 'red'],
            'Decided - Partially Upheld': ['Partially Upheld', 'orange'],
            'Withdrawn': ['Withdrawn', 'darkgray'],
            'Dismissed': ['Dismissed', 'darkgray']
        };
        
        return status_colors[doc.appeal_status] || ['Unknown', 'gray'];
    },
    
    onload: function(listview) {
        // Add custom buttons
        listview.page.add_menu_item(__('Overdue Appeals Report'), function() {
            frappe.set_route('query-report', 'Appeals Analysis Report', {
                'appeal_status': 'Under Review',
                'overdue_only': 1
            });
        });
        
        listview.page.add_menu_item(__('Success Rate Analysis'), function() {
            frappe.set_route('query-report', 'Appeals Analysis Report');
        });
    },
    
    formatters: {
        member_name: function(value, df, doc) {
            return `<a href="/app/member/${doc.member}">${value}</a>`;
        },
        
        review_deadline: function(value, df, doc) {
            if (!value) return '';
            
            const deadline = frappe.datetime.str_to_obj(value);
            const today = frappe.datetime.now_date();
            const diff = frappe.datetime.get_diff(deadline, today);
            
            if (doc.appeal_status === 'Under Review' || doc.appeal_status === 'Pending Decision') {
                if (diff < 0) {
                    return `<span class="text-danger">${frappe.datetime.str_to_user(value)} (${Math.abs(diff)} days overdue)</span>`;
                } else if (diff <= 7) {
                    return `<span class="text-warning">${frappe.datetime.str_to_user(value)} (${diff} days left)</span>`;
                }
            }
            
            return frappe.datetime.str_to_user(value);
        },
        
        appeal_type: function(value) {
            const type_badges = {
                'Procedural Appeal': 'badge-info',
                'Substantive Appeal': 'badge-primary',
                'New Evidence Appeal': 'badge-warning',
                'Full Review Appeal': 'badge-danger'
            };
            
            const badge_class = type_badges[value] || 'badge-default';
            return `<span class="badge ${badge_class}">${value}</span>`;
        }
    },
    
    button: {
        show: function(doc) {
            return doc.appeal_status === 'Submitted' || doc.appeal_status === 'Under Review';
        },
        get_label: function() {
            return __('Review');
        },
        get_description: function(doc) {
            return __('Review this appeal');
        },
        action: function(doc) {
            frappe.set_route('Form', 'Termination Appeals Process', doc.name);
        }
    }
};
