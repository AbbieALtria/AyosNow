# AYOSNOW Database Implementation Gap Report

## Summary

The enterprise database design document is broad and useful, but the SQL file is still a starter DDL.

Observed SQL state:

- Tables: 117
- Indexes detected: 0
- Triggers detected: 0
- Check constraints detected: 1
- Foreign-key/reference definitions detected: very low

## Critical Risks

### 1. Orphan Records

Without foreign keys, the database cannot prevent orphaned bookings, payments, assignments, complaints, wallet entries, or payout records.

Required relationships:

- booking to customer
- booking to service
- booking to address snapshot
- assignment to booking
- assignment to provider
- payment to booking
- wallet ledger to provider
- payout to provider
- complaint to booking
- audit log to actor where applicable

### 2. Slow Admin And Reporting Queries

Without indexes, admin lists and reports will degrade quickly.

Required index areas:

- booking status, city, schedule, created_at
- assignment provider_id and booking_id
- provider verification_status and city
- payment status and booking_id
- wallet ledger provider_id and created_at
- payout status and provider_id
- complaint status and booking_id
- audit log actor_id, entity_type, entity_id, created_at

### 3. Financial Ledger Mutation Risk

Wallet ledger must be append-only. If updates/deletes are allowed without guardrails, reconciliation becomes unreliable.

Required controls:

- No application update path for amount/direction/source fields
- Adjustment entries for corrections
- Audit event for every finance action
- Optional database trigger to block updates/deletes on ledger rows

### 4. Missing Lifecycle Constraints

Booking, payment, payout, provider verification, and complaint statuses should be constrained.

Required constraints:

- Booking status enum or check
- Payment status enum or check
- Payout status enum or check
- Complaint status enum or check
- Provider verification status enum or check

### 5. Migration Strategy Missing

The SQL file should not remain as one large manual starter file once implementation begins.

Recommended approach:

- Use Django migrations as source of truth.
- Keep generated SQL for review only.
- Add seed data migrations for roles, permissions, service categories, and launch locations.

## MVP Database Hardening Checklist

- Add foreign keys for all MVP core relationships.
- Add indexes for high-volume list screens and status filters.
- Add unique constraints for mobile, email where applicable, active role mappings, idempotency keys, gateway transaction IDs.
- Add check constraints for status fields and non-negative monetary values where applicable.
- Add created_at and updated_at consistently.
- Add created_by or actor fields for admin actions.
- Add soft delete fields only where needed.
- Add immutable ledger guard.
- Add audit log table indexes.
- Add migration tests.

## Done Definition

The database is implementation-ready when:

- The app can enforce core business rules through both application logic and database constraints.
- Finance records are reconciliable.
- Admin queries are indexed.
- Historical records remain intact.
- Migrations can build a clean database from zero.
