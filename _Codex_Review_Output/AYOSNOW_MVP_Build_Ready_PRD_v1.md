# AYOSNOW MVP Build-Ready PRD v1.0

## 1. Product Objective

AyosNow is a Philippines service marketplace that connects customers with verified service providers for home, maintenance, delivery, personal, and corporate services.

The MVP objective is to prove the end-to-end marketplace operating loop in Metro Manila with manual dispatch, controlled provider onboarding, cashless payment support, wallet accounting, complaints handling, and admin operational visibility.

## 2. MVP Scope

### Included

- Customer registration and login
- Provider registration and verification
- Customer address management
- Service category browsing
- Booking creation
- Manual dispatch by admin
- Provider job acceptance and job status updates
- Payment checkout and payment webhook handling
- Provider wallet ledger
- Provider payout request
- Complaint creation and resolution tracking
- Admin dashboard for dispatch, providers, complaints, payments, payouts, and reports
- Audit logging for sensitive and operational actions

### Excluded From MVP

- Fully automated AI dispatch
- Franchise management
- Corporate billing portals
- In-app chat beyond basic booking notes
- Advanced route optimization
- Dynamic surge pricing
- Multi-country support
- Full data warehouse

## 3. Primary Actors

- Guest Customer
- Registered Customer
- Guest Provider
- Registered Provider
- Dispatcher
- Support Agent
- Finance Officer
- Operations Manager
- System Admin
- Payment Gateway

## 4. Core Entities

- User
- Customer
- Customer Address
- Provider
- Provider Document
- Provider Skill
- Service Category
- Service Item
- Booking
- Booking Status History
- Assignment
- Payment
- Payment Gateway Transaction
- Wallet Ledger Entry
- Payout
- Complaint
- Complaint Evidence
- Notification
- Audit Log

## 5. MVP Workflow

### 5.1 Customer Registration

Requirement IDs: CUST-001 to CUST-006

Customer shall be able to register using mobile number, password, first name, last name, and optional email.

Business rules:

- Mobile number must be unique.
- OTP verification is required before booking.
- Password must be stored as a hash only.
- Customer profile changes must be audited when PII is changed.

Acceptance criteria:

- Duplicate mobile registration returns conflict.
- Invalid mobile format returns validation error.
- Successful registration creates customer, user identity, OTP challenge, and audit event.

### 5.2 Customer Address Management

Requirement IDs: ADDR-001 to ADDR-007

Customer shall be able to create, update, list, and deactivate service addresses.

Required fields:

- Label
- Region
- City
- Barangay when available
- Address line 1
- Optional landmark
- Optional latitude and longitude

Business rules:

- Customer must have at least one active address before booking.
- Address ownership must be enforced.
- Deactivated addresses remain available for historical bookings.

Acceptance criteria:

- Customer cannot access another customer's address.
- Booking form lists only active addresses.
- Historical booking still displays address snapshot even after address changes.

### 5.3 Provider Registration And Verification

Requirement IDs: PROV-001 to PROV-015

Provider shall be able to register as individual, team, or company.

Required fields:

- Provider type
- Mobile number
- City
- Primary service category
- Legal name or business name
- ID document
- Proof of address or business document

Verification statuses:

- pending
- under_review
- approved
- rejected
- suspended

Business rules:

- Provider cannot accept jobs until approved.
- Document review decisions require admin actor, timestamp, reason, and audit log.
- Suspended provider cannot receive new assignments.

Acceptance criteria:

- Provider registration creates pending provider profile.
- Admin approval changes provider status to approved.
- Rejection requires visible reason.

### 5.4 Service Catalog

Requirement IDs: SERV-001 to SERV-010

Customer shall be able to browse active service categories and service items.

Business rules:

- Inactive categories are hidden from customers.
- Service item must define pricing model before it can be booked.
- MVP pricing may be fixed price, estimated price, or quote-required.

Acceptance criteria:

- Customer sees only bookable services.
- Admin can deactivate category without deleting history.

### 5.5 Booking Creation

Requirement IDs: BOOK-001 to BOOK-020

Customer shall be able to create a booking request.

Required fields:

- Service item
- Service address
- Requested schedule
- Problem description
- Optional photos
- Payment method

Booking statuses:

- draft
- submitted
- pending_dispatch
- assigned
- provider_accepted
- provider_declined
- in_progress
- completed_by_provider
- confirmed_completed
- cancelled
- disputed

Business rules:

- Booking must capture address snapshot.
- Customer may cancel before provider starts job, subject to cancellation policy.
- Every booking status change must create status history.
- Dispatcher can assign only approved providers.

Acceptance criteria:

- Valid booking enters pending_dispatch.
- Invalid service/address returns validation error.
- Booking detail shows current status and history.

### 5.6 Manual Dispatch

Requirement IDs: DISP-001 to DISP-018

Dispatcher shall be able to view pending bookings and assign approved providers.

Dispatch queue fields:

- Booking ID
- Service
- City
- Barangay
- Requested schedule
- Customer name
- SLA age
- Payment status
- Current status

Business rules:

- Assignment must enforce provider status, service skill, city coverage, and availability.
- Reassignment requires reason.
- Provider decline returns booking to dispatch queue.

Acceptance criteria:

- Dispatcher can assign a provider from eligible providers.
- Assignment creates provider notification and audit log.
- Reassignment history remains visible.

### 5.7 Provider Job Flow

Requirement IDs: JOB-001 to JOB-020

Provider shall be able to view assigned jobs, accept or decline, start work, and submit completion.

Business rules:

- Provider can accept only assigned jobs.
- Provider must submit completion notes and optional evidence.
- Job completion does not release payout until customer confirmation or complaint window closes.

Acceptance criteria:

- Accepted job changes booking status to provider_accepted.
- Started job changes booking status to in_progress.
- Completed job changes booking status to completed_by_provider.

### 5.8 Payment And Wallet

Requirement IDs: PAY-001 to PAY-025

Customer shall be able to pay through supported payment gateway checkout.

Business rules:

- Payment operations must use idempotency keys.
- Gateway webhooks must be signature verified.
- Wallet ledger must be append-only.
- Provider payable amount is calculated from gross amount minus commission, penalties, refunds, and adjustments.

Ledger entry types:

- payment_captured
- commission
- provider_earning
- refund
- adjustment
- payout_requested
- payout_released
- payout_failed

Acceptance criteria:

- Successful webhook marks payment captured.
- Duplicate webhook does not double-credit wallet.
- Wallet balance equals sum of ledger entries.

### 5.9 Complaints And QA

Requirement IDs: COMP-001 to COMP-018

Customer, provider, or support agent shall be able to create a complaint linked to a booking.

Complaint statuses:

- open
- under_review
- awaiting_customer
- awaiting_provider
- resolved
- rejected
- escalated

Business rules:

- Complaint can pause payout release.
- Resolution must capture decision, actor, reason, and financial impact.
- Evidence files must be access-controlled.

Acceptance criteria:

- Complaint linked to booking appears in admin queue.
- Resolution updates booking/payment/wallet where applicable.
- Complaint audit trail is preserved.

### 5.10 Admin Dashboard

Requirement IDs: ADMIN-001 to ADMIN-030

Admin dashboard shall support:

- Dispatch queue
- Provider verification queue
- Booking search
- Payment monitoring
- Wallet ledger search
- Payout review
- Complaint queue
- User and role management
- Audit log viewer
- Executive KPI view

Business rules:

- Admin capabilities are controlled by RBAC.
- Finance actions require Finance Officer or higher.
- Provider suspension requires reason.
- Audit logs cannot be edited from the admin dashboard.

Acceptance criteria:

- Unauthorized admin users cannot access restricted screens.
- Every create/update/approve/reject/suspend/refund/payout action writes audit log.

## 6. Non-Functional Requirements

Security:

- HTTPS only
- JWT access token and refresh token
- OTP for sensitive actions
- Password hashing
- RBAC and object ownership checks
- Audit logging
- Virus scanning for uploaded files where supported

Availability:

- MVP target: 99.5 percent monthly availability
- Payment webhook endpoint must be resilient to retries

Performance:

- Customer and provider mobile APIs should respond within 500 ms p95 for common reads under MVP load.
- Admin lists must be paginated.

Compliance:

- PII must be minimized and access-controlled.
- Retention rules must be documented for identity documents, booking history, payment records, and audit logs.

## 7. MVP Release Criteria

MVP is releasable when:

- Customer can create a paid booking.
- Dispatcher can assign provider.
- Provider can complete job.
- Payment capture creates wallet ledger.
- Admin can process payout.
- Complaint can hold or adjust payout.
- Reports show bookings, revenue, provider earnings, complaints, and payout totals.
- All sensitive actions are audited.
