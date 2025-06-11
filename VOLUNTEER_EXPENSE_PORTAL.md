# Volunteer Expense Portal

The Volunteer Expense Portal provides a user-friendly interface for volunteers to submit and track their expense reimbursements.

## Features

### 🏠 Volunteer Dashboard (`/volunteer/dashboard`)
- Overview of volunteer profile and activities
- Expense summary statistics (12-month view)
- Recent activities and assignments
- Quick access to expense submission
- Organization memberships (chapters and teams)

### 💰 Expense Submission Portal (`/volunteer/expenses`)
- Intuitive expense submission form
- Real-time approval level indication based on amount
- File attachment support
- Organization-aware (chapter/team selection)
- Expense category classification
- Recent expense history view

## Access Control

### Authentication
- Requires user login (no guest access)
- Must have linked Volunteer record in the system
- Volunteer can be linked via Member record or direct email

### Organization Access
- Volunteers can only submit expenses for organizations they belong to
- Chapter access: Through active Chapter Member relationship
- Team access: Through active Team Member relationship
- Automatic organization detection when volunteer belongs to single org

## Expense Approval Workflow

### Amount-Based Approval Levels
- **€0 - €100**: Basic Level (any active board member)
- **€100 - €500**: Financial Level (board members with financial permissions)
- **€500+**: Admin Level (chapter chair or admin permissions)

### Approval Process
1. Volunteer submits expense through portal
2. System determines required approval level based on amount
3. Notification sent to appropriate approvers
4. Approvers can use Expense Approval Dashboard for review
5. Volunteer receives confirmation/rejection notification

## Technical Implementation

### Portal Pages
```
/volunteer/                 → Redirects to dashboard
/volunteer/dashboard        → Main volunteer dashboard
/volunteer/expenses         → Expense submission and tracking
```

### Key Components
- **Frontend**: Professional HTML/CSS with responsive design
- **Backend**: Python controllers with Frappe ORM
- **Permissions**: Integration with chapter board member roles
- **Notifications**: Enhanced email system with professional templates

### Database Integration
- **Volunteer Expense**: Main expense document
- **Expense Category**: Categorization system
- **Chapter/Team**: Organization relationships
- **Expense Permissions**: Permission validation system

## User Journey

### For New Volunteers
1. Login with member/volunteer account
2. Access portal via member dashboard link
3. Complete profile information if needed
4. Submit first expense with guided approval level info

### For Existing Volunteers
1. Quick access via `/volunteer/expenses`
2. View expense statistics and recent submissions
3. Submit new expenses with pre-filled organization data
4. Track approval status in real-time

## Administrator Features

### Dashboard Access
- **Expense Approval Dashboard**: `/app/expense-approval-dashboard`
- **Chapter Expense Report**: Query report with filtering
- **Bulk approval**: Process multiple expenses simultaneously

### Configuration
- **Expense Categories**: Manage available categories
- **Approval Thresholds**: Configured in permission system
- **Email Templates**: Professional notification templates

## API Endpoints

### Portal-Specific Endpoints
```python
@frappe.whitelist()
def submit_expense(expense_data)
    # Submit new expense from portal

@frappe.whitelist()
def get_organization_options(organization_type, volunteer_name)
    # Get available organizations for volunteer

@frappe.whitelist()
def get_expense_details(expense_name)
    # Get detailed expense information
```

### Integration Points
- Volunteer record validation
- Organization membership verification
- Permission level calculation
- Email notification triggers

## Best Practices

### For Volunteers
- Submit expenses promptly (within 30 days)
- Include detailed descriptions
- Attach receipts when possible
- Use appropriate expense categories
- Monitor approval status

### For Administrators
- Review expenses within 7 days
- Use bulk approval for efficiency
- Set up overdue reminder schedules
- Monitor expense trends via reports

## Security Features

- **Authentication**: Required login for all access
- **Authorization**: Organization-based access control
- **Data Validation**: Server-side validation of all inputs
- **Permission Checks**: Integrated with chapter board roles
- **Audit Trail**: Complete activity logging

## Mobile Responsive Design

The portal is fully responsive and optimized for:
- Desktop browsers (1200px+)
- Tablet devices (768px - 1199px)
- Mobile phones (<768px)
- Print-friendly layouts

## Future Enhancements

Potential improvements for future releases:
- Mobile app integration
- Receipt scanning with OCR
- Integration with accounting systems
- Advanced reporting and analytics
- Expense policy automation
- Multi-currency support enhancement