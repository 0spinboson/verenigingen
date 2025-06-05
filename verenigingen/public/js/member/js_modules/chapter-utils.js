// Chapter-related utility functions for Member doctype

function suggest_chapter_for_member(frm) {
    const d = new frappe.ui.Dialog({
        title: __('Suggest Chapter for Member'),
        size: 'large',
        fields: [
            {
                fieldtype: 'HTML',
                options: `<div class="mb-3">
                    <p>${__("Let's find the best chapter for this member based on their location.")}</p>
                </div>`
            },
            {
                fieldname: 'search_method',
                fieldtype: 'Select',
                label: __('Search Method'),
                options: 'By Address\nBy Postal Code\nManual Selection',
                default: 'By Address',
                onchange: function() {
                    toggle_search_fields(d);
                }
            },
            {
                fieldname: 'postal_code',
                fieldtype: 'Data',
                label: __('Postal Code'),
                depends_on: 'eval:doc.search_method=="By Postal Code"'
            },
            {
                fieldname: 'chapter',
                fieldtype: 'Link',
                label: __('Chapter'),
                options: 'Chapter',
                depends_on: 'eval:doc.search_method=="Manual Selection"'
            },
            {
                fieldname: 'search_results',
                fieldtype: 'HTML',
                label: __('Search Results')
            }
        ],
        primary_action_label: __('Search'),
        primary_action: function(values) {
            search_chapters_for_member(frm, values, d);
        }
    });
    
    d.show();
    toggle_search_fields(d);
}

function toggle_search_fields(dialog) {
    const method = dialog.get_value('search_method');
    dialog.fields_dict.postal_code.wrapper.toggle(method === 'By Postal Code');
    dialog.fields_dict.chapter.wrapper.toggle(method === 'Manual Selection');
}

function search_chapters_for_member(frm, values, dialog) {
    let search_args = {
        member: frm.doc.name
    };
    
    if (values.search_method === 'By Postal Code' && values.postal_code) {
        search_args.postal_code = values.postal_code;
    } else if (values.search_method === 'Manual Selection' && values.chapter) {
        assign_chapter_to_member(frm, values.chapter);
        dialog.hide();
        return;
    }
    
    frappe.call({
        method: 'verenigingen.verenigingen.doctype.chapter.chapter.suggest_chapters_for_member',
        args: search_args,
        callback: function(r) {
            if (r.message && r.message.length > 0) {
                display_chapter_suggestions(r.message, frm, dialog);
            } else {
                dialog.fields_dict.search_results.wrapper.html(
                    '<div class="alert alert-info">' + 
                    __('No matching chapters found. Try a different search method.') + 
                    '</div>'
                );
            }
        }
    });
}

function display_chapter_suggestions(chapters, frm, dialog) {
    let html = '<div class="chapter-suggestions mt-3">';
    html += '<h5>' + __('Suggested Chapters') + '</h5>';
    
    chapters.forEach((chapter, index) => {
        html += `<div class="card mb-2">
            <div class="card-body">
                <h6 class="card-title">${chapter.name}</h6>
                <p class="card-text">
                    <strong>${__('Location')}:</strong> ${chapter.city || ''}, ${chapter.state || ''}<br>
                    <strong>${__('Match Score')}:</strong> ${chapter.match_score || 'N/A'}%<br>
                    <strong>${__('Distance')}:</strong> ${chapter.distance || 'N/A'} km
                </p>
                <button class="btn btn-primary btn-sm assign-chapter" data-chapter="${chapter.name}">
                    ${__('Assign Chapter')}
                </button>
            </div>
        </div>`;
    });
    
    html += '</div>';
    
    dialog.fields_dict.search_results.wrapper.html(html);
    
    // Add click handlers for assign buttons
    dialog.fields_dict.search_results.wrapper.find('.assign-chapter').on('click', function() {
        const chapter_name = $(this).data('chapter');
        assign_chapter_to_member(frm, chapter_name);
        dialog.hide();
    });
}

function assign_chapter_to_member(frm, chapter_name) {
    frappe.call({
        method: 'verenigingen.verenigingen.doctype.member.member.assign_chapter',
        args: {
            member: frm.doc.name,
            chapter: chapter_name
        },
        callback: function(r) {
            if (r.message) {
                frm.set_value('primary_chapter', chapter_name);
                frm.save();
                frappe.show_alert({
                    message: __('Chapter assigned successfully'),
                    indicator: 'green'
                }, 5);
            }
        }
    });
}

function suggest_chapter_from_address(frm) {
    console.log('suggest_chapter_from_address called for address:', frm.doc.primary_address);
    
    if (!frm.doc.primary_address) {
        console.log('No primary address set');
        return;
    }
    
    frappe.call({
        method: 'verenigingen.verenigingen.doctype.chapter.chapter.suggest_chapters_for_member',
        args: {
            member: frm.doc.name
        },
        callback: function(r) {
            console.log('Chapter suggestion response:', r);
            if (r.message && r.message.length > 0) {
                const bestMatch = r.message[0];
                
                frappe.confirm(
                    __('Based on the member address, we suggest assigning them to {0}. Would you like to proceed?', [bestMatch.name]),
                    function() {
                        assign_chapter_to_member(frm, bestMatch.name);
                    }
                );
            } else {
                frappe.msgprint(__('No suitable chapters found for this member\'s location.'));
            }
        }
    });
}

// Export functions for use in member.js
window.ChapterUtils = {
    suggest_chapter_for_member,
    suggest_chapter_from_address,
    assign_chapter_to_member
};