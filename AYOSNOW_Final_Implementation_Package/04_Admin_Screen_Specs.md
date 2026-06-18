# AYOSNOW Admin Screen Specifications

Version: 1.0  
Audience: Product, Engineering, QA, Operations

## 1. Admin Roles

| Role | Access |
| --- | --- |
| Dispatcher | Dispatch queue, booking assignment, dispatch notes |
| Support Agent | Customer lookup, booking lookup, complaint handling |
| Finance Officer | Payment monitoring, wallet ledger, payout review, finance reports |
| Operations Manager | Provider verification, dispatch oversight, complaint escalation, reports |
| System Admin | Admin users, roles, permissions, system settings, audit log |

## 2. Shared Admin UI Rules

- All list screens must support pagination.
- All list screens must support CSV export only for authorized roles.
- All sensitive actions require confirmation modal.
- All destructive or financial actions require reason.
- All admin actions must write audit log with actor, action, entity, timestamp, before/after where applicable.
- Admin screens must show server-side validation errors inline.

## 3. Login Screen

Purpose: Authenticate admin users.

Fields:

- Mobile or email
- Password
- OTP code when required

Actions:

- Login
- Request password reset

Validation:

- Required credential.
- Required password.
- Lock or rate-limit repeated failures.

Audit:

- Login success
- Login failure threshold exceeded

## 4. Dashboard Home

Purpose: Daily operational snapshot.

Widgets:

- Pending dispatch count
- Provider applications pending review
- Open complaints
- Payments captured today
- Payouts pending review
- Cancelled bookings today
- SLA breach count

Filters:

- Date range
- City
- Service category

Permissions:

- All admin roles can view dashboard.
- Finance totals visible only to Finance Officer, Operations Manager, System Admin.

## 5. Dispatch Queue

Purpose: Assign providers to pending bookings.

Columns:

- Booking ID
- Status
- SLA age
- Customer
- Service
- City
- Barangay
- Requested schedule
- Payment status
- Eligible provider count
- Assigned provider

Filters:

- Status
- City
- Service category
- Schedule date
- SLA breach

Actions:

- View booking
- Assign provider
- Reassign provider
- Add dispatch note
- Cancel booking

Assign Provider Modal:

- Provider search
- Provider verification status
- Provider skills
- Provider city
- Current active jobs
- Assignment reason

Validation:

- Provider must be approved.
- Provider must have matching service skill.
- Assignment reason required.

Audit:

- Provider assigned
- Provider reassigned
- Booking cancelled by admin

## 6. Booking Detail

Purpose: Inspect full booking lifecycle.

Sections:

- Customer summary
- Address snapshot
- Service snapshot
- Booking details
- Status history
- Assignment history
- Payment summary
- Complaint summary
- Internal notes

Actions:

- Add note
- Cancel booking
- Reassign provider
- Open complaint
- View audit trail

Permissions:

- Dispatcher can assign and add dispatch notes.
- Support can add support notes and open complaints.
- Finance can view payment details.

## 7. Provider Verification Queue

Purpose: Review provider applications and documents.

Columns:

- Provider ID
- Display name
- Provider type
- City
- Services
- Verification status
- Submitted date
- Document count

Filters:

- Status
- City
- Provider type
- Service category

Actions:

- View provider
- Approve
- Reject
- Suspend
- Unsuspend
- Request more information

Provider Detail Sections:

- Profile
- Documents
- Skills
- Service areas
- Booking history
- Wallet summary
- Complaint history
- Verification decision history

Validation:

- Approval requires at least required documents submitted.
- Rejection requires reason.
- Suspension requires reason.

Audit:

- Provider approved
- Provider rejected
- Provider suspended
- Provider unsuspended
- Document approved/rejected

## 8. Customer Search

Purpose: Support customer service workflows.

Search fields:

- Mobile
- Email
- Name
- Customer ID

Customer Detail Sections:

- Profile
- Addresses
- Booking history
- Payment history summary
- Complaints
- Notes

Actions:

- View booking
- Add support note
- Open complaint
- Suspend customer, Operations Manager or System Admin only

Audit:

- Customer suspension
- PII viewed, optional based on compliance setting

## 9. Complaints Queue

Purpose: Resolve disputes and service quality issues.

Columns:

- Complaint ID
- Booking ID
- Status
- Category
- Opened by
- Customer
- Provider
- Created date
- SLA age

Filters:

- Status
- Category
- City
- Date range
- Assigned support agent

Actions:

- View complaint
- Assign owner
- Request customer information
- Request provider information
- Resolve
- Reject
- Escalate

Resolution Modal:

- Decision
- Resolution notes
- Financial impact
- Refund amount
- Provider penalty amount
- Release or hold payout

Validation:

- Resolution requires reason.
- Financial impact must be non-negative.
- Refund and penalty actions require finance permission.

Audit:

- Complaint status changed
- Complaint resolved
- Financial adjustment applied

## 10. Payment Monitoring

Purpose: Track payment lifecycle and webhook events.

Columns:

- Payment ID
- Booking ID
- Customer
- Amount
- Currency
- Gateway
- Status
- Gateway reference
- Created date
- Updated date

Filters:

- Status
- Gateway
- Date range
- Booking ID

Actions:

- View payment
- View gateway events
- Retry internal processing, System Admin only
- Mark for manual review

Audit:

- Manual review flag
- Internal retry

## 11. Wallet Ledger

Purpose: Reconcile provider balances.

Columns:

- Ledger ID
- Provider
- Entry type
- Direction
- Amount
- Available or held
- Source type
- Source ID
- Created date

Filters:

- Provider
- Entry type
- Direction
- Date range
- Source type

Actions:

- View source record
- Create adjustment, Finance Officer only

Validation:

- Adjustment requires reason.
- Adjustment amount must be positive.

Audit:

- Wallet adjustment created

## 12. Payout Review

Purpose: Process provider payout requests.

Columns:

- Payout ID
- Provider
- Requested amount
- Available balance
- Status
- Requested date
- Reviewed by

Filters:

- Status
- Provider
- Date range

Actions:

- Approve
- Reject
- Mark released
- Mark failed
- Add finance note

Validation:

- Reject requires reason.
- Release requires payout reference.
- Released payout cannot be edited.

Audit:

- Payout approved
- Payout rejected
- Payout released
- Payout failed

## 13. Reports

Reports:

- Booking volume
- Revenue summary
- Provider earnings
- Payout summary
- Complaint summary
- Dispatch SLA
- Cancellation rate
- Top services

Filters:

- Date range
- City
- Service category
- Provider

Permissions:

- Finance reports require Finance Officer or higher.
- Operations reports require Operations Manager or higher.

## 14. Admin Users And Roles

Purpose: Manage back-office access.

Actions:

- Create admin user
- Deactivate admin user
- Assign role
- Remove role
- View permissions

Validation:

- System Admin role required.
- User cannot remove their own final System Admin role.

Audit:

- Admin user created
- Role assigned
- Role removed
- Admin user deactivated

## 15. Audit Log Viewer

Purpose: Investigate sensitive actions.

Columns:

- Timestamp
- Actor
- Action
- Entity type
- Entity ID
- IP address

Filters:

- Actor
- Action
- Entity type
- Entity ID
- Date range

Actions:

- View audit detail

Rules:

- Audit logs are read-only.
- Audit export requires System Admin.
