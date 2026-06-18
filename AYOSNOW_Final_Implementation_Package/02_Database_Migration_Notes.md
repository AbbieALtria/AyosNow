# AYOSNOW Database Migration Notes

## Purpose

`02_database_migration_001_mvp_core.sql` is a hardened MVP database starter. It intentionally focuses on the tables needed to launch the first operating loop instead of carrying forward every future enterprise table.

## What This Migration Covers

- Users, roles, permissions, OTP
- Regions, cities, barangays
- Customers and addresses
- Providers, documents, skills
- Service categories and service items
- Bookings, status history, assignments
- Payments, gateway events
- Wallet ledger, payouts
- Complaints and evidence
- Audit logs
- Foreign keys, indexes, status checks, idempotency key, append-only wallet guard

## Recommended Django Implementation

Use Django migrations as source of truth:

1. Create Django apps by domain:
   - accounts
   - geo
   - customers
   - providers
   - services
   - bookings
   - finance
   - complaints
   - audit
2. Convert SQL tables into Django models.
3. Generate migrations with `python manage.py makemigrations`.
4. Compare generated SQL against this migration.
5. Add database-level constraints that Django cannot express cleanly.

## Seed Data Required

- Admin roles:
  - dispatcher
  - support_agent
  - finance_officer
  - operations_manager
  - system_admin
- Permissions per admin module.
- Initial Metro Manila region/city/barangay data.
- Initial service categories and service items.

## Production Hardening To Add Before Launch

- Encryption strategy for identity document metadata.
- Object storage signed URL policy.
- Backup and restore procedure.
- Payment gateway webhook replay window table or cache.
- Database migration rollback policy.
- Monitoring for failed payments, duplicate webhook attempts, and payout failures.
