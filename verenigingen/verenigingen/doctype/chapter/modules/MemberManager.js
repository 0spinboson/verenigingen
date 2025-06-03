// verenigingen/verenigingen/doctype/chapter/modules/MemberManager.js

import { ChapterAPI } from '../utils/ChapterAPI.js';

export class MemberManager {
    constructor(frm, state, ui) {
        this.frm = frm;
        this.state = state;
        this.ui = ui;
        this.api = new ChapterAPI();
    }
    
    addButtons() {
        // Add member management buttons
        this.ui.addButton(__('View Members'), () => this.viewMembers(), __('View'));
        
        // Only show member management buttons if chapter has been saved
        if (this.frm.doc.name && !this.frm.doc.__islocal) {
            this.ui.addButton(__('Add Members'), () => this.showAddMembersDialog(), __('Actions'));
            this.ui.addButton(__('Member Directory'), () => this.showMemberDirectory(), __('View'));
            this.ui.addButton(__('Export Member List'), () => this.exportMemberList(), __('Actions'));
        }
    }
    
    viewMembers() {
        if (!this.frm.doc.name) {
            this.ui.showError(__('Please save the chapter first'));
            return;
        }
        
        // Navigate to member list filtered by this chapter
        frappe.set_route('List', 'Member', {
            'primary_chapter': this.frm.doc.name
        });
    }
    
    async showAddMembersDialog() {
        try {
            // Get members not in this chapter
            const availableMembers = await this.getAvailableMembers();
            
            if (!availableMembers || availableMembers.length === 0) {
                this.ui.showError(__('No available members found to add to this chapter'));
                return;
            }
            
            const dialog = this.ui.showDialog({
                title: __('Add Members to Chapter'),
                size: 'large',
                fields: [
                    {
                        fieldname: 'info',
                        fieldtype: 'HTML',
                        options: `<div class="alert alert-info">
                            ${__('Select members to add to {0} chapter', [this.frm.doc.name])}
                        </div>`
                    },
                    {
                        fieldname: 'members',
                        fieldtype: 'MultiSelectPills',
                        label: __('Select Members'),
                        options: availableMembers.map(member => ({
                            label: `${member.full_name} (${member.email || 'No email'})`,
                            value: member.name
                        })),
                        reqd: 1
                    },
                    {
                        fieldname: 'set_as_primary',
                        fieldtype: 'Check',
                        label: __('Set as Primary Chapter'),
                        default: 0,
                        description: __('Update selected members to have this as their primary chapter')
                    }
                ],
                primary_action_label: __('Add Members'),
                primary_action: async (values) => {
                    await this.addMembersToChapter(values.members, values.set_as_primary);
                    dialog.hide();
                }
            });
        } catch (error) {
            this.ui.showError(__('Failed to load available members: {0}', [error.message]));
        }
    }
    
    async getAvailableMembers() {
        // Get all active members
        const allMembers = await this.api.getList('Member', {
            filters: { status: 'Active' },
            fields: ['name', 'full_name', 'email', 'primary_chapter'],
            limit: 500
        });
        
        // Get current chapter members
        const currentMemberIds = this.frm.doc.members?.map(m => m.member) || [];
        
        // Filter out members already in this chapter
        return allMembers.filter(member => !currentMemberIds.includes(member.name));
    }
    
    async addMembersToChapter(memberIds, setAsPrimary) {
        if (!memberIds || memberIds.length === 0) {
            this.ui.showError(__('Please select at least one member'));
            return;
        }
        
        try {
            this.state.setLoading('addMembers', true);
            this.ui.showProgress(__('Adding Members'), 0, memberIds.length);
            
            let successCount = 0;
            const errors = [];
            
            for (let i = 0; i < memberIds.length; i++) {
                try {
                    const memberId = memberIds[i];
                    const member = await this.api.getDoc('Member', memberId);
                    
                    // Add to chapter members table
                    const exists = this.frm.doc.members?.some(m => m.member === memberId);
                    
                    if (!exists) {
                        const newMember = this.frm.add_child('members');
                        frappe.model.set_value(newMember.doctype, newMember.name, {
                            member: memberId,
                            member_name: member.full_name,
                            enabled: 1
                        });
                        
                        successCount++;
                    }
                    
                    // Update primary chapter if requested
                    if (setAsPrimary && member.primary_chapter !== this.frm.doc.name) {
                        await this.api.setValue('Member', memberId, 'primary_chapter', this.frm.doc.name);
                    }
                    
                    this.ui.showProgress(__('Adding Members'), i + 1, memberIds.length);
                } catch (error) {
                    errors.push({
                        member: memberIds[i],
                        error: error.message
                    });
                }
            }
            
            this.frm.refresh_field('members');
            
            // Show results
            let message = __('Added {0} members to chapter', [successCount]);
            if (errors.length > 0) {
                message += `. ${__('Failed to add {0} members', [errors.length])}`;
            }
            
            this.ui.showAlert(message, errors.length > 0 ? 'orange' : 'green');
            
            // Update member count
            this.ui.updateMembersSummary();
            
        } catch (error) {
            this.ui.showError(__('Failed to add members: {0}', [error.message]));
        } finally {
            this.state.setLoading('addMembers', false);
        }
    }
    
    async showMemberDirectory() {
        try {
            this.state.setLoading('memberDirectory', true);
            
            // Get all chapter members with details
            const members = await this.getChapterMembersDetails();
            
            if (!members || members.length === 0) {
                this.ui.showError(__('No members found in this chapter'));
                return;
            }
            
            const html = this.generateMemberDirectoryHTML(members);
            
            const dialog = this.ui.showDialog({
                title: __('Member Directory - {0}', [this.frm.doc.name]),
                size: 'extra-large',
                fields: [
                    {
                        fieldtype: 'HTML',
                        options: html
                    }
                ],
                primary_action_label: __('Close'),
                primary_action: function() {
                    this.hide();
                }
            });
            
            // Add search functionality
            this.addDirectorySearch(dialog);
            
        } catch (error) {
            this.ui.showError(__('Failed to load member directory: {0}', [error.message]));
        } finally {
            this.state.setLoading('memberDirectory', false);
        }
    }
    
    async getChapterMembersDetails() {
        const memberIds = this.frm.doc.members?.filter(m => m.enabled).map(m => m.member) || [];
        
        if (memberIds.length === 0) return [];
        
        // Get detailed member information
        const members = await this.api.getList('Member', {
            filters: [['name', 'in', memberIds]],
            fields: ['name', 'full_name', 'email', 'mobile_no', 'status', 'member_since', 'image'],
            limit: 500
        });
        
        // Add chapter-specific information
        return members.map(member => {
            const chapterMember = this.frm.doc.members.find(m => m.member === member.name);
            return {
                ...member,
                introduction: chapterMember?.introduction,
                website_url: chapterMember?.website_url,
                joined_chapter: chapterMember?.creation
            };
        });
    }
    
    generateMemberDirectoryHTML(members) {
        let html = `
            <div class="member-directory">
                <div class="directory-controls mb-3">
                    <input type="text" class="form-control directory-search" 
                           placeholder="${__('Search members...')}" />
                </div>
                <div class="directory-stats mb-3">
                    <span class="badge badge-primary">${__('Total Members')}: ${members.length}</span>
                    <span class="badge badge-success">${__('Active')}: ${members.filter(m => m.status === 'Active').length}</span>
                </div>
                <div class="member-grid row">
        `;
        
        members.forEach(member => {
            const avatar = member.image 
                ? `<img src="${member.image}" alt="${member.full_name}" class="avatar">`
                : `<div class="avatar avatar-medium bg-primary">${this.getInitials(member.full_name)}</div>`;
            
            html += `
                <div class="col-md-6 col-lg-4 member-card-wrapper" data-member="${member.name}">
                    <div class="member-card card mb-3">
                        <div class="card-body">
                            <div class="d-flex align-items-center mb-2">
                                ${avatar}
                                <div class="ml-3">
                                    <h5 class="mb-0">
                                        <a href="/app/member/${member.name}" target="_blank">
                                            ${member.full_name}
                                        </a>
                                    </h5>
                                    <span class="badge badge-${member.status === 'Active' ? 'success' : 'secondary'}">
                                        ${member.status}
                                    </span>
                                </div>
                            </div>
                            <div class="member-details">
                                ${member.email ? `<p><i class="fa fa-envelope"></i> ${member.email}</p>` : ''}
                                ${member.mobile_no ? `<p><i class="fa fa-phone"></i> ${member.mobile_no}</p>` : ''}
                                ${member.member_since ? `<p><i class="fa fa-calendar"></i> ${__('Member since')} ${member.member_since}</p>` : ''}
                                ${member.introduction ? `<p class="text-muted">${member.introduction}</p>` : ''}
                                ${member.website_url ? `<p><i class="fa fa-globe"></i> <a href="${member.website_url}" target="_blank">${member.website_url}</a></p>` : ''}
                            </div>
                        </div>
                        <div class="card-footer">
                            <div class="btn-group btn-group-sm" role="group">
                                <button class="btn btn-default" onclick="frappe.set_route('Form', 'Member', '${member.name}')">
                                    <i class="fa fa-eye"></i> ${__('View')}
                                </button>
                                ${this.canManageMembers() ? `
                                    <button class="btn btn-default" onclick="window._chapterMemberManager.removeMemberFromChapter('${member.name}', '${member.full_name}')">
                                        <i class="fa fa-times"></i> ${__('Remove')}
                                    </button>
                                ` : ''}
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });
        
        html += `
                </div>
            </div>
            <style>
                .member-directory .avatar {
                    width: 50px;
                    height: 50px;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: white;
                    font-weight: bold;
                }
                .member-card {
                    height: 100%;
                    transition: box-shadow 0.3s;
                }
                .member-card:hover {
                    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                }
                .member-details p {
                    margin-bottom: 0.5rem;
                }
                .member-details i {
                    width: 20px;
                    color: #6c757d;
                }
            </style>
        `;
        
        // Store reference for onclick handlers
        window._chapterMemberManager = this;
        
        return html;
    }
    
    getInitials(name) {
        return name
            .split(' ')
            .map(part => part[0])
            .join('')
            .toUpperCase()
            .substring(0, 2);
    }
    
    addDirectorySearch(dialog) {
        const $search = dialog.$wrapper.find('.directory-search');
        
        $search.on('input', function() {
            const searchTerm = $(this).val().toLowerCase();
            
            dialog.$wrapper.find('.member-card-wrapper').each(function() {
                const $card = $(this);
                const text = $card.text().toLowerCase();
                
                if (text.includes(searchTerm)) {
                    $card.show();
                } else {
                    $card.hide();
                }
            });
            
            // Update count
            const visibleCount = dialog.$wrapper.find('.member-card-wrapper:visible').length;
            dialog.$wrapper.find('.directory-stats').append(
                ` <span class="badge badge-info">${__('Showing')}: ${visibleCount}</span>`
            );
        });
    }
    
    async removeMemberFromChapter(memberId, memberName) {
        this.ui.confirmAction(
            __('Are you sure you want to remove {0} from this chapter?', [memberName]),
            async () => {
                try {
                    // Find and remove from members table
                    const memberIndex = this.frm.doc.members.findIndex(m => m.member === memberId);
                    
                    if (memberIndex > -1) {
                        this.frm.doc.members.splice(memberIndex, 1);
                        
                        // Save the document
                        await this.frm.save();
                        
                        this.ui.showAlert(__('Member removed from chapter'), 'green');
                        
                        // Refresh member count
                        this.ui.updateMembersSummary();
                    }
                } catch (error) {
                    this.ui.showError(__('Failed to remove member: {0}', [error.message]));
                }
            }
        );
    }
    
    async exportMemberList() {
        try {
            this.state.setLoading('exportMembers', true);
            
            const members = await this.getChapterMembersDetails();
            
            if (!members || members.length === 0) {
                this.ui.showError(__('No members to export'));
                return;
            }
            
            // Create CSV content
            const headers = ['Name', 'Email', 'Mobile', 'Status', 'Member Since', 'Introduction', 'Website'];
            const rows = members.map(member => [
                member.full_name,
                member.email || '',
                member.mobile_no || '',
                member.status,
                member.member_since || '',
                member.introduction || '',
                member.website_url || ''
            ]);
            
            const csv = this.generateCSV(headers, rows);
            
            // Download CSV
            const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
            const link = document.createElement('a');
            const url = URL.createObjectURL(blob);
            
            link.setAttribute('href', url);
            link.setAttribute('download', `${this.frm.doc.name}_members_${frappe.datetime.nowdate()}.csv`);
            link.style.visibility = 'hidden';
            
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            this.ui.showAlert(__('Member list exported successfully'), 'green');
            
        } catch (error) {
            this.ui.showError(__('Failed to export member list: {0}', [error.message]));
        } finally {
            this.state.setLoading('exportMembers', false);
        }
    }
    
    generateCSV(headers, rows) {
        const csvRows = [];
        
        // Add headers
        csvRows.push(headers.map(h => `"${h}"`).join(','));
        
        // Add data rows
        rows.forEach(row => {
            const values = row.map(value => {
                // Escape quotes and wrap in quotes
                const escaped = String(value).replace(/"/g, '""');
                return `"${escaped}"`;
            });
            csvRows.push(values.join(','));
        });
        
        return csvRows.join('\n');
    }
    
    canManageMembers() {
        // Check if user has permission to manage members
        return frappe.user_roles.includes('Association Manager') || 
               frappe.user_roles.includes('System Manager');
    }
    
    // Handle member-related state changes
    handleMemberUpdate(memberId) {
        // Refresh member list if needed
        const memberIndex = this.frm.doc.members?.findIndex(m => m.member === memberId);
        
        if (memberIndex > -1) {
            this.frm.refresh_field('members');
            this.ui.updateMembersSummary();
        }
    }
    
    // Get member count for the chapter
    async getMemberCount() {
        try {
            const count = await this.api.getCount('Member', {
                primary_chapter: this.frm.doc.name
            });
            
            this.state.update('chapter.memberCount', count);
            return count;
        } catch (error) {
            console.error('Error getting member count:', error);
            return 0;
        }
    }
    
    // Check if a member is in this chapter
    isMemberInChapter(memberId) {
        return this.frm.doc.members?.some(m => m.member === memberId && m.enabled) || false;
    }
    
    // Get chapter member details
    getChapterMember(memberId) {
        return this.frm.doc.members?.find(m => m.member === memberId);
    }
    
    // Update member status in chapter
    async updateMemberStatus(memberId, enabled, leaveReason = null) {
        const member = this.getChapterMember(memberId);
        
        if (member) {
            frappe.model.set_value(member.doctype, member.name, {
                enabled: enabled,
                leave_reason: leaveReason
            });
            
            this.frm.refresh_field('members');
            
            await this.frm.save();
            
            this.ui.showAlert(
                enabled ? __('Member enabled') : __('Member disabled'),
                'green'
            );
        }
    }
    
    destroy() {
        // Clean up window reference
        delete window._chapterMemberManager;
        
        // Clear references
        this.frm = null;
        this.state = null;
        this.ui = null;
        this.api = null;
    }
}
