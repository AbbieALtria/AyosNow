# AYOSNOW Final MVP Product Requirements Document

Version: 1.0  
Date: 2026-06-17  
Target market: Philippines, Metro Manila MVP  
Primary stack assumption: Flutter apps, Django REST Framework backend, PostgreSQL, Redis, Celery, Admin Web

## 1. Product Goal

AyosNow is a service marketplace where customers book trusted local services, verified providers perform the work, and AyosNow manages booking, dispatch, payment, wallet accounting, complaints, and operational control.

The MVP must prove the complete operating loop:

1. Customer registers and books a service.
2. Admin dispatcher assigns an approved provider.
3. Provider accepts and completes the job.
4. Customer pays through supported payment flow.
5. Provider earnings are recorded in wallet ledger.
6. Finance processes payout.
7. Complaints can pause or adjust payout.
8. Admin can monitor the operation.

## 2. MVP Scope

### In Scope

- Customer registration, OTP verification, login, and profile.
- Customer address management.
- Provider registration, document submission, verification, suspension.
- Service catalog browsing.
- Booking creation, cancellation, status tracking.
- Manual admin dispatch.
- Provider job acceptance, start, completion.
- Payment checkout and payment webhook processing.
- Provider wallet ledger and payout request.
- Complaint creation, evidence, resolution.
- Admin dashboard for dispatch, provider verification, bookings, complaints, payments, payouts, reports, audit.
- Role-based admin permissions.
- Audit logging for sensitive actions.

### Out Of Scope

- Automated AI dispatch.
- Franchise management.
- Corporate billing portal.
- Full chat system.
- Real-time GPS tracking.
- Dynamic surge pricing.
- Native data warehouse.
- Multi-country support.

## 3. User Roles

| Role | Description |
| --- | --- |
| Guest Customer | Can register, verify OTP, view public service catalog. |
| Customer | Can manage addresses, create bookings, pay, cancel, complain. |
| Guest Provider | Can apply as service provider. |
| Provider | Can manage profile, view assigned jobs, accept, decline, complete jobs, request payout. |
| Dispatcher | Can manage dispatch queue and assignment. |
| Support Agent | Can inspect bookings/customers and handle complaints. |
| Finance Officer | Can review payments, wallet ledger, payouts, refunds, adjustments. |
| Operations Manager | Can approve providers, oversee dispatch, resolve escalations. |
| System Admin | Can manage roles, permissions, and system settings. |
| Payment Gateway | Sends payment status webhook events. |

## 4. Core Business Rules

### Customer

- Mobile number must be unique.
- Customer must verify OTP before creating booking.
- Customer must have at least one active address before booking.
- Customer may cancel before provider starts work.
- Customer cancellation after provider acceptance may require a cancellation fee. MVP default: no automated cancellation fee unless configured by admin.

### Provider

- Provider cannot receive assignments until approved.
- Provider can be `pending`, `under_review`, `approved`, `rejected`, or `suspended`.
- Provider suspension blocks new assignments.
- Provider document decisions require reason and audit log.

### Booking

- Booking must store customer address snapshot.
- Booking must store service snapshot.
- Booking status changes must be recorded in history.
- Booking can have only one active assignment at a time.
- Reassignment requires reason.
- Completion by provider does not release payout until confirmation or complaint window expires.

### Payment And Wallet

- Payment operations must use idempotency keys.
- Gateway webhooks must be signature verified.
- Duplicate webhook events must not create duplicate ledger entries.
- Provider wallet is derived from append-only ledger entries.
- Payout cannot exceed available balance.
- Complaint can place related earnings on hold.

### Complaint

- Complaint must be linked to a booking.
- Complaint can be opened by customer, provider, or support.
- Complaint resolution must include decision, reason, actor, and financial impact.

## 5. Status Models

### Booking Status

- `draft`
- `submitted`
- `pending_dispatch`
- `assigned`
- `provider_accepted`
- `provider_declined`
- `in_progress`
- `completed_by_provider`
- `confirmed_completed`
- `cancelled`
- `disputed`

Allowed transitions:

- `draft` to `submitted`
- `submitted` to `pending_dispatch`
- `pending_dispatch` to `assigned`
- `assigned` to `provider_accepted`
- `assigned` to `provider_declined`
- `provider_declined` to `pending_dispatch`
- `provider_accepted` to `in_progress`
- `in_progress` to `completed_by_provider`
- `completed_by_provider` to `confirmed_completed`
- `completed_by_provider` to `disputed`
- pre-start statuses to `cancelled`

### Payment Status

- `pending`
- `processing`
- `captured`
- `failed`
- `cancelled`
- `refunded`
- `partially_refunded`

### Payout Status

- `requested`
- `under_review`
- `approved`
- `rejected`
- `released`
- `failed`

### Complaint Status

- `open`
- `under_review`
- `awaiting_customer`
- `awaiting_provider`
- `resolved`
- `rejected`
- `escalated`

## 6. Functional Requirements

### CUST-001 Customer Registration

Customer can register with mobile, password, first name, last name, optional email.

Acceptance criteria:

- Duplicate mobile returns `409 CONFLICT`.
- Invalid mobile returns `400 VALIDATION_ERROR`.
- Successful registration creates user, customer profile, OTP challenge, audit log.

### CUST-002 OTP Verification

Customer and provider can verify OTP for registration and sensitive actions.

Acceptance criteria:

- Expired OTP fails.
- Wrong OTP fails and increments attempt counter.
- Valid OTP activates the requested purpose.

### ADDR-001 Address Management

Customer can create, update, list, and deactivate addresses.

Acceptance criteria:

- Customer cannot access another customer's address.
- Booking uses address snapshot.
- Deactivated address is not selectable for new booking.

### PROV-001 Provider Registration

Provider can apply as individual, team, or company.

Acceptance criteria:

- Registration creates pending provider profile.
- Required document metadata is stored.
- Provider cannot accept jobs before approval.

### PROV-002 Provider Verification

Operations Manager can approve, reject, suspend, or unsuspend providers.

Acceptance criteria:

- Decision requires reason.
- Decision writes audit log.
- Approved provider becomes assignable.

### SERV-001 Service Catalog

Customer can browse active service categories and service items.

Acceptance criteria:

- Inactive services are hidden.
- Service item shows pricing model and booking requirements.

### BOOK-001 Create Booking

Customer can create a booking for active service and address.

Acceptance criteria:

- Booking enters `pending_dispatch`.
- Booking stores address and service snapshot.
- Booking creates status history.

### BOOK-002 Cancel Booking

Customer, dispatcher, or support can cancel booking where policy allows.

Acceptance criteria:

- Cancellation reason is required.
- Cancellation writes status history and audit log.
- Booking cannot be cancelled after `in_progress` by customer.

### DISP-001 Dispatch Queue

Dispatcher can list bookings needing assignment.

Acceptance criteria:

- Queue supports filtering by status, city, service, schedule date.
- Queue is ordered by SLA age.

### DISP-002 Assign Provider

Dispatcher can assign eligible provider to booking.

Acceptance criteria:

- Provider must be approved and active.
- Assignment creates provider notification.
- Assignment writes booking status history and audit log.

### JOB-001 Provider Accepts Job

Provider can accept assigned job.

Acceptance criteria:

- Only assigned provider can accept.
- Booking status becomes `provider_accepted`.

### JOB-002 Provider Completes Job

Provider can submit completion notes and evidence.

Acceptance criteria:

- Booking status becomes `completed_by_provider`.
- Completion proof is stored as file metadata.

### PAY-001 Create Checkout

Customer can create payment checkout for booking.

Acceptance criteria:

- Checkout uses idempotency key.
- Payment record is created as `pending`.
- Gateway reference is stored.

### PAY-002 Payment Webhook

Payment gateway can notify payment result.

Acceptance criteria:

- Webhook signature is verified.
- Duplicate webhook does not duplicate ledger entries.
- Captured payment updates payment and wallet ledger.

### WAL-001 Provider Wallet

Provider can view wallet balance and recent ledger.

Acceptance criteria:

- Balance equals sum of ledger entries.
- Held balance is separated from available balance.

### PAYOUT-001 Request Payout

Provider can request payout from available balance.

Acceptance criteria:

- Requested amount cannot exceed available balance.
- Payout request creates wallet hold ledger entry.

### COMP-001 Create Complaint

Customer, provider, or support can create complaint for booking.

Acceptance criteria:

- Complaint is linked to booking.
- Complaint can hold provider payout for the booking.
- Complaint appears in admin complaint queue.

### ADMIN-001 Admin Operations

Admin dashboard supports role-based operational workflows.

Acceptance criteria:

- Unauthorized admin cannot access restricted module.
- Sensitive admin action writes audit log.

## 7. Non-Functional Requirements

- All APIs must use HTTPS.
- All APIs must return standard response envelope.
- Admin lists must be paginated.
- Mobile APIs should be optimized for unstable mobile connections.
- PII and identity documents must be access-controlled.
- Payment secrets must be stored outside source code.
- Backups must be encrypted.
- MVP target availability: 99.5 percent monthly.

## 8. MVP Release Criteria

The MVP is ready for launch when:

- Customer can register, verify OTP, add address, create booking, pay, and complain.
- Provider can register, be approved, accept job, complete job, view wallet, request payout.
- Admin can dispatch, verify providers, resolve complaints, process payouts, and view reports.
- Payment webhook and wallet ledger are idempotent.
- Core admin actions are audited.
- QA acceptance checklist passes.
