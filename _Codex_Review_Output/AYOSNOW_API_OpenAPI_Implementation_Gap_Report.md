# AYOSNOW API And OpenAPI Implementation Gap Report

## Summary

The Word API contract provides a useful starting point, but the OpenAPI JSON is not yet a build contract.

Observed OpenAPI state:

- OpenAPI version: 3.0.3
- Paths: 21
- Schemas: 0
- Request body schemas: missing
- Response schemas: missing

## Required Fixes

### 1. Add Security Schemes

Add:

- JWT bearer authentication
- Optional API key or signature scheme for payment gateway webhook
- Idempotency-Key header for financial POST endpoints

### 2. Add Standard Envelopes

Define:

- SuccessEnvelope
- ErrorEnvelope
- PaginationMeta
- FieldError

### 3. Add Domain Schemas

Minimum MVP schemas:

- Customer
- CustomerAddress
- Provider
- ProviderDocument
- ServiceCategory
- ServiceItem
- Booking
- BookingStatusHistory
- Assignment
- Payment
- WalletLedgerEntry
- Payout
- Complaint
- ReportSummary

### 4. Add Request Schemas

Minimum MVP request schemas:

- RegisterCustomerRequest
- RegisterProviderRequest
- SendOtpRequest
- VerifyOtpRequest
- CreateAddressRequest
- CreateBookingRequest
- CancelBookingRequest
- AssignProviderRequest
- AcceptJobRequest
- CompleteJobRequest
- CheckoutRequest
- PaymentWebhookRequest
- RequestPayoutRequest
- CreateComplaintRequest

### 5. Add Error Responses

Every endpoint should define:

- 400 VALIDATION_ERROR
- 401 UNAUTHORIZED
- 403 FORBIDDEN
- 404 NOT_FOUND where applicable
- 409 CONFLICT where applicable
- 422 BUSINESS_RULE_FAILED where applicable
- 429 RATE_LIMITED
- 500 SERVER_ERROR

### 6. Align Paths With Versioning

The Word contract uses `/api/v1/...`, while the JSON paths currently appear as `/auth/...`, `/bookings/...`, etc.

Decision required:

- Either include `/api/v1` in the server URL, or
- include `/api/v1` in every path.

Do not mix both approaches.

## Endpoint Priority

Implement these first:

1. POST /api/v1/auth/customer/register
2. POST /api/v1/auth/provider/register
3. POST /api/v1/auth/otp/send
4. POST /api/v1/auth/otp/verify
5. GET /api/v1/services/categories
6. POST /api/v1/customers/addresses
7. POST /api/v1/bookings
8. GET /api/v1/admin/dispatch/queue
9. POST /api/v1/admin/dispatch/assign
10. GET /api/v1/providers/jobs
11. POST /api/v1/providers/jobs/{assignment_id}/accept
12. POST /api/v1/providers/jobs/{job_id}/complete
13. POST /api/v1/payments/checkout
14. POST /api/v1/payments/webhook
15. GET /api/v1/providers/wallet
16. POST /api/v1/providers/payouts
17. POST /api/v1/complaints

## Done Definition

The API contract is ready when:

- OpenAPI validates successfully.
- Every endpoint has request and response schemas.
- Every schema has required fields.
- Error envelope is standardized.
- Auth requirements are visible per endpoint.
- Idempotency and webhook signature headers are documented.
- Examples exist for major workflows.
