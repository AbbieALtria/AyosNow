# AYOSNOW Document Review Action Plan

Review date: 2026-06-17  
Source folder: E:\AyosNow  
Reviewer: Codex

## Executive Summary

The AyosNow document set has a strong strategic and architecture foundation, but it is not yet ready to hand directly to engineering as an implementation package.

The strongest source documents are:

- AyosNow_Business_Scope_and_Development_Plan.docx
- AyosNow_High_Level_IT_App_Design_Document.docx
- AYOSNOW_Enterprise_System_Design_Document_v1.0.docx
- AYOSNOW_Enterprise_API_Contracts_v1.0.docx
- AYOSNOW_Enterprise_Database_Design_Document_v1.0.docx

The weakest implementation artifacts are:

- AYOSNOW_PRD_Volume_2_Detailed_Functional_Specifications.docx
- AYOSNOW_PRD_2C_Booking_Dispatch_Engine.docx through AYOSNOW_PRD_2J_AI_Architecture.docx
- AYOSNOW_OpenAPI_Starter_v1.json
- ayosnow_enterprise_database_v1_schema.sql

## Critical Findings

### 1. PRD Volume 2 Is Placeholder Content

AYOSNOW_PRD_Volume_2_Detailed_Functional_Specifications.docx contains 1,200 generic requirements following the pattern:

`The system shall support [domain] capability #[number] including validation, workflow processing, audit logging, permissions, reporting, and exception handling.`

This is not usable as a product requirements document because it does not define specific behavior, data fields, user flows, state transitions, edge cases, or acceptance criteria.

Action:

- Replace it with a build-ready MVP PRD.
- Use specific requirement IDs grouped by domain.
- Make each requirement testable.
- Link requirements to screens, APIs, database entities, and acceptance criteria.

### 2. PRD Volumes 2C-2J Are Topic Templates

The 2C-2J PRD files identify the right domains but mostly contain headings rather than detailed specifications.

Action:

- Expand each volume into concrete workflows.
- Define actors, states, business rules, exception paths, validation rules, reporting requirements, and audit events.
- Keep AI architecture as post-MVP unless a specific MVP AI use case is required.

### 3. Database SQL Is a Starter, Not a Production Schema

The SQL file defines 117 tables but has almost no relational enforcement:

- 0 indexes detected
- 0 triggers detected
- 1 check constraint detected
- Very few foreign-key/reference definitions

Action:

- Add foreign keys for all core relationships.
- Add indexes for all lookup, listing, reporting, and status queries.
- Add lifecycle constraints for bookings, payments, wallet ledger, payouts, complaints, and provider verification.
- Add immutable financial ledger safeguards.
- Convert the SQL into migrations.

### 4. OpenAPI JSON Is Not Yet a Contract

AYOSNOW_OpenAPI_Starter_v1.json contains 21 paths and 0 schemas. Endpoints lack request body schemas and response schemas.

Action:

- Define reusable components for common models.
- Add request bodies for POST endpoints.
- Add response schemas for all endpoints.
- Add security schemes, error envelope schemas, pagination, idempotency headers, webhook signature headers, and examples.

### 5. Duplicate Documents Create Version Drift Risk

Some documents appear both loose and inside package folders/zips.

Action:

- Declare a single source of truth per document.
- Add a version register.
- Include generated package files only as release artifacts.

## Recommended Source Of Truth Structure

Use this structure for the next working set:

- 00_Document_Register.md
- 01_Business_Scope.md
- 02_MVP_PRD.md
- 03_PRD_2C_Booking_Dispatch.md
- 04_PRD_2D_Payments_Wallet.md
- 05_PRD_2E_Admin_Dashboard.md
- 06_PRD_2F_Reporting_Analytics.md
- 07_PRD_2G_Database_Requirements.md
- 08_PRD_2H_API_Requirements.md
- 09_PRD_2I_Security_Compliance.md
- 10_PRD_2J_AI_Roadmap.md
- 11_System_Design.md
- 12_API_OpenAPI.yaml
- 13_Database_Migrations/

## Immediate Implementation Priority

For MVP, build only the core operating loop:

1. Customer registers and manages addresses.
2. Provider registers, submits documents, and is approved.
3. Customer creates a booking.
4. Admin dispatcher assigns provider manually.
5. Provider accepts, starts, and completes job.
6. Customer confirms completion or raises complaint.
7. Payment is collected.
8. Provider wallet ledger records commission and payable balance.
9. Admin processes payout.
10. Admin views operational reports.

## Done Definition For Documentation

The documentation is ready for engineering when:

- Every MVP screen has field definitions and validation rules.
- Every MVP workflow has states and transitions.
- Every core endpoint has request and response schemas.
- Every financial operation has ledger and reconciliation rules.
- Every admin action has RBAC and audit requirements.
- Database constraints match the business rules.
- Requirements are testable by QA.
