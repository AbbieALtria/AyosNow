# AYOSNOW PRD Volumes 2C to 2J Rewrite v1.0

## Volume 2C - Booking And Dispatch Engine

### Objective

Define the booking lifecycle from customer request through dispatch, provider execution, completion, cancellation, and dispute.

### Core Requirements

- Booking must be created from an active service item and active customer address.
- Booking must store an immutable snapshot of customer address and requested service details.
- Booking must maintain a status history table.
- Manual dispatcher assignment is the MVP dispatch model.
- Provider eligibility must check approval status, service skill, city/service area, suspension status, and availability.
- Reassignment must require a reason and preserve history.
- Customer cancellation rules must vary by status.
- Booking cannot be completed unless it has an accepted assignment.

### State Transitions

Allowed transitions:

- draft to submitted
- submitted to pending_dispatch
- pending_dispatch to assigned
- assigned to provider_accepted
- assigned to provider_declined
- provider_declined to pending_dispatch
- provider_accepted to in_progress
- in_progress to completed_by_provider
- completed_by_provider to confirmed_completed
- completed_by_provider to disputed
- any pre-start status to cancelled when cancellation policy allows

Blocked transitions:

- cancelled to active status
- confirmed_completed to in_progress
- disputed to confirmed_completed without complaint resolution

### Admin Dispatch Screen

Fields:

- Booking ID
- Service
- Customer
- Address summary
- City/barangay
- Requested schedule
- SLA age
- Payment status
- Booking status
- Eligible provider count
- Assigned provider

Actions:

- Assign provider
- Reassign provider
- Cancel booking
- Add dispatch note
- Open customer profile
- Open provider profile

### Acceptance Criteria

- Dispatcher sees pending bookings ordered by SLA age.
- Dispatcher can filter by city, service, date, and status.
- Assignment writes booking status history, assignment record, notification, and audit log.
- Provider decline returns booking to dispatch queue.

## Volume 2D - Payment And Wallet Architecture

### Objective

Define payment capture, payment gateway integration, provider wallet, commissions, refunds, adjustments, and payout controls.

### Core Requirements

- Payment checkout must create a payment record before redirecting to gateway.
- Payment webhooks must be signature verified.
- Payment webhook processing must be idempotent.
- Wallet ledger must be append-only.
- Provider balance must be derived from ledger entries.
- Payout cannot exceed available balance.
- Complaint status can hold payout release.
- Finance actions must be audited.

### Payment Statuses

- pending
- processing
- captured
- failed
- cancelled
- refunded
- partially_refunded

### Ledger Rules

- Every financial movement creates a ledger entry.
- Ledger entries are never deleted.
- Corrections use adjustment entries.
- Each ledger entry must include source type, source ID, amount, direction, currency, provider ID where applicable, and created actor.

### Payout Rules

- Provider can request payout only when balance is positive and provider is approved.
- Finance Officer can approve, reject, release, or mark payout failed.
- Payout rejection requires reason.
- Released payout must link to proof or gateway reference.

### Acceptance Criteria

- Duplicate webhook does not duplicate wallet entries.
- Refund creates negative adjustment where applicable.
- Admin can reconcile payment, wallet, and payout records.

## Volume 2E - Admin Dashboard

### Objective

Define the operational back office for dispatch, provider verification, finance, support, reporting, and system administration.

### Admin Modules

- Login and RBAC
- Dispatch queue
- Booking management
- Provider verification
- Customer support
- Complaints and QA
- Payment monitoring
- Wallet ledger
- Payout review
- Reports
- Audit log
- User and role management

### Role Permissions

- Dispatcher: dispatch queue, booking assignment, dispatch notes
- Support Agent: customer lookup, complaint handling, booking notes
- Finance Officer: payment review, payout approval, finance reports
- Operations Manager: provider approval, dispatch oversight, complaints escalation
- System Admin: roles, permissions, system configuration

### Acceptance Criteria

- Admin users see only permitted modules.
- All restricted actions write audit logs.
- Lists are paginated and filterable.
- Finance screens show reconciliation-friendly references.

## Volume 2F - Reporting And Analytics

### Objective

Define MVP operational and executive reporting.

### MVP Reports

- Daily booking volume
- Booking status summary
- Revenue summary
- Payment status summary
- Provider earnings
- Payout summary
- Complaint count and resolution time
- Dispatch SLA
- Cancellation rate
- Top services
- City/barangay demand

### Report Dimensions

- Date
- City
- Service category
- Provider
- Customer type
- Payment method
- Booking status
- Complaint status

### Acceptance Criteria

- Admin can filter reports by date range.
- Finance totals reconcile with payment and wallet records.
- Reports exclude deleted test data unless explicitly included by admin.

## Volume 2G - Database Design Requirements

### Objective

Define implementation expectations for the database schema.

### Core Requirements

- PostgreSQL is the system of record.
- Use UUID primary keys for public-facing entities.
- Use foreign keys for core relationships.
- Use indexes for all high-volume queries.
- Use soft delete only where historical integrity is needed.
- Use append-only tables for wallet and audit history.
- Use status history tables for booking and complaint lifecycle.
- Store files in object storage and metadata in PostgreSQL.

### Required Constraint Areas

- Booking to customer, address snapshot, service, and assignment
- Assignment to provider and booking
- Payment to booking and gateway transaction
- Wallet ledger to provider and source record
- Payout to provider and wallet entries
- Complaint to booking and actor
- Audit log to actor where possible

### Acceptance Criteria

- Schema can prevent orphaned core records.
- Common admin queries have indexes.
- Financial ledger cannot be mutated through normal application paths.

## Volume 2H - API Specification Requirements

### Objective

Define the machine-readable API contract expected by clients and backend.

### Core Requirements

- All APIs are under `/api/v1`.
- All responses use standard envelope: success, data, meta, error.
- All POST financial endpoints require idempotency key.
- All admin APIs require RBAC.
- All object APIs require ownership checks.
- All list APIs are paginated.
- All errors use standard error codes.

### Required OpenAPI Components

- ErrorEnvelope
- SuccessEnvelope
- PaginationMeta
- Customer
- Provider
- Booking
- Assignment
- Payment
- WalletLedgerEntry
- Payout
- Complaint
- AuditLog
- RegisterCustomerRequest
- CreateBookingRequest
- CheckoutRequest
- WebhookPayload

### Acceptance Criteria

- OpenAPI validates with a standard OpenAPI validator.
- Mobile teams can generate typed clients.
- QA can derive contract tests from OpenAPI.

## Volume 2I - Security And Compliance

### Objective

Define security, privacy, access, audit, and resilience requirements.

### Core Requirements

- HTTPS only.
- JWT access and refresh tokens.
- OTP for registration verification, password reset, and sensitive finance actions.
- RBAC for admin.
- Object ownership checks for customer and provider APIs.
- PII access must be limited and logged.
- Identity documents must be access-controlled.
- Payment secrets must not be stored in source code.
- Webhooks must verify signatures and replay windows.
- Backups must be encrypted.

### Audit Events

- Login failure threshold exceeded
- Provider approval/rejection/suspension
- Booking assignment/reassignment/cancellation
- Payment capture/refund
- Wallet adjustment
- Payout approval/release/rejection
- Complaint resolution
- Role or permission change

### Acceptance Criteria

- Unauthorized users cannot access another user's records.
- Admin sensitive actions are visible in audit log.
- Secrets are loaded through environment or secret manager.

## Volume 2J - AI Architecture

### Objective

Define future AI capabilities without blocking the MVP.

### MVP Position

AI is not required for MVP launch. MVP should collect clean operational data that later supports AI matching, fraud detection, support automation, and forecasting.

### Future AI Capabilities

- Provider matching score
- Fraud and abuse detection
- Complaint classification
- Support response suggestions
- Demand forecasting
- Provider churn risk
- Price recommendation
- Customer service recommendation

### Data Readiness Requirements

- Capture booking lifecycle events.
- Capture provider acceptance/decline behavior.
- Capture cancellation reasons.
- Capture complaint categories and outcomes.
- Capture payout and refund reasons.
- Keep clear entity IDs across events.

### Acceptance Criteria

- MVP can operate without AI services.
- Future AI features can be added through separate scoring services or read models.
- AI decisions that affect users must be explainable and auditable.
