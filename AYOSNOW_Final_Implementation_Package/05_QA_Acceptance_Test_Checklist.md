# AYOSNOW MVP QA Acceptance Test Checklist

Version: 1.0  
Purpose: MVP launch readiness checklist for product, QA, and engineering.

## 1. Customer Registration And OTP

- [ ] Customer can register with valid mobile, password, first name, last name.
- [ ] Duplicate mobile registration returns conflict error.
- [ ] Invalid mobile format returns validation error.
- [ ] Weak password returns validation error.
- [ ] OTP send returns token and expiry.
- [ ] Correct OTP verifies account.
- [ ] Wrong OTP fails.
- [ ] Expired OTP fails.
- [ ] Repeated OTP failures are rate-limited.
- [ ] Verified customer can authenticate and receive access token.

## 2. Customer Address

- [ ] Customer can create address with required fields.
- [ ] Customer can list own addresses.
- [ ] Customer cannot view another customer's address.
- [ ] Customer can deactivate address.
- [ ] Deactivated address is not selectable for new booking.
- [ ] Existing booking still shows original address snapshot after address edit.

## 3. Provider Registration And Verification

- [ ] Provider can register as individual.
- [ ] Provider can register as team.
- [ ] Provider can register as company.
- [ ] Provider application starts as pending.
- [ ] Provider cannot receive assignment before approval.
- [ ] Admin can view provider application.
- [ ] Admin can approve provider with required documents.
- [ ] Admin cannot approve provider when required documents are missing.
- [ ] Admin rejection requires reason.
- [ ] Admin suspension blocks new assignments.
- [ ] Provider verification decision writes audit log.

## 4. Service Catalog

- [ ] Guest can list active service categories.
- [ ] Customer can list active service categories.
- [ ] Inactive category is hidden.
- [ ] Inactive service item is hidden.
- [ ] Service item displays pricing model.

## 5. Booking Creation

- [ ] Verified customer can create booking with active service and active address.
- [ ] Unverified customer cannot create booking.
- [ ] Booking creation stores service snapshot.
- [ ] Booking creation stores address snapshot.
- [ ] Booking enters pending dispatch.
- [ ] Booking status history is created.
- [ ] Missing required booking field returns validation error.
- [ ] Customer cannot book using another customer's address.

## 6. Booking Cancellation

- [ ] Customer can cancel booking before provider starts.
- [ ] Cancellation requires reason.
- [ ] Cancelled booking writes status history.
- [ ] Customer cannot cancel booking after in_progress.
- [ ] Dispatcher can cancel booking with reason.
- [ ] Cancelled booking cannot be assigned.

## 7. Dispatch

- [ ] Dispatcher can view pending dispatch queue.
- [ ] Dispatch queue can filter by status.
- [ ] Dispatch queue can filter by city.
- [ ] Dispatch queue can filter by schedule date.
- [ ] Dispatcher can assign approved provider with matching skill.
- [ ] Dispatcher cannot assign unapproved provider.
- [ ] Dispatcher cannot assign suspended provider.
- [ ] Assignment writes audit log.
- [ ] Assignment creates active assignment record.
- [ ] Booking status changes to assigned.
- [ ] Reassignment requires reason.
- [ ] Only one active assignment exists per booking.

## 8. Provider Job Flow

- [ ] Provider can view assigned jobs.
- [ ] Provider cannot view another provider's jobs.
- [ ] Assigned provider can accept job.
- [ ] Non-assigned provider cannot accept job.
- [ ] Accepted job changes booking status to provider_accepted.
- [ ] Provider can start accepted job.
- [ ] Started job changes booking status to in_progress.
- [ ] Provider can complete in-progress job.
- [ ] Completion requires completion notes.
- [ ] Completion supports evidence URLs.
- [ ] Completed job changes booking status to completed_by_provider.

## 9. Payment Checkout

- [ ] Customer can create checkout for valid booking.
- [ ] Checkout requires idempotency key.
- [ ] Repeated request with same idempotency key does not create duplicate payment.
- [ ] Payment starts as pending.
- [ ] Checkout response includes checkout URL.
- [ ] Customer cannot create payment for another customer's booking.

## 10. Payment Webhook

- [ ] Webhook without valid signature is rejected.
- [ ] Valid captured webhook updates payment to captured.
- [ ] Captured webhook creates gateway event record.
- [ ] Duplicate webhook event is accepted safely without duplicate ledger entries.
- [ ] Failed payment webhook updates payment to failed.
- [ ] Unknown payment reference is handled without server crash.

## 11. Wallet Ledger

- [ ] Captured payment creates provider earning ledger entry when booking/provider relationship is valid.
- [ ] Commission entry is recorded according to configured commission rule.
- [ ] Wallet balance equals sum of ledger entries.
- [ ] Held balance is separate from available balance.
- [ ] Wallet ledger rows cannot be edited.
- [ ] Wallet ledger rows cannot be deleted.
- [ ] Finance adjustment creates new ledger entry rather than mutating old entry.

## 12. Payout

- [ ] Provider can request payout from available balance.
- [ ] Provider cannot request payout above available balance.
- [ ] Suspended provider cannot request payout.
- [ ] Payout request creates payout record.
- [ ] Finance Officer can approve payout.
- [ ] Finance Officer can reject payout with reason.
- [ ] Released payout requires payout reference.
- [ ] Released payout cannot be edited.
- [ ] Payout status changes write audit log.

## 13. Complaints

- [ ] Customer can create complaint for own booking.
- [ ] Provider can create complaint for assigned booking.
- [ ] Support can create complaint for booking.
- [ ] Complaint appears in admin complaint queue.
- [ ] Complaint can place provider earning on hold.
- [ ] Complaint resolution requires reason.
- [ ] Complaint resolution can apply refund or penalty with finance permission.
- [ ] Resolved complaint writes audit log.
- [ ] Rejected complaint writes audit log.

## 14. Admin Permissions

- [ ] Dispatcher can access dispatch queue.
- [ ] Dispatcher cannot approve payout.
- [ ] Finance Officer can access payout review.
- [ ] Finance Officer cannot change admin roles.
- [ ] Operations Manager can approve providers.
- [ ] Support Agent can manage complaints but cannot release payout.
- [ ] System Admin can manage roles.
- [ ] Admin user cannot remove their own final System Admin role.
- [ ] Unauthorized admin route returns forbidden.

## 15. Admin Screen Functional Checks

- [ ] Dashboard shows pending dispatch count.
- [ ] Dashboard shows provider applications pending review.
- [ ] Dashboard shows open complaints.
- [ ] Booking detail shows customer, address snapshot, service snapshot, status history, assignment history.
- [ ] Provider detail shows documents, skills, status, wallet summary.
- [ ] Complaint detail shows booking, parties, evidence, status history.
- [ ] Payment detail shows gateway events.
- [ ] Audit log viewer filters by actor.
- [ ] Audit log viewer filters by entity ID.

## 16. Reporting

- [ ] Executive report filters by date range.
- [ ] Booking volume report matches booking records.
- [ ] Revenue report matches captured payments.
- [ ] Provider earnings report matches wallet ledger.
- [ ] Payout report matches payout records.
- [ ] Complaint report matches complaint records.
- [ ] Cancellation rate report excludes non-cancelled statuses.

## 17. API Contract

- [ ] OpenAPI file validates successfully.
- [ ] All authenticated endpoints reject missing token.
- [ ] All role-restricted endpoints reject insufficient role.
- [ ] Standard success envelope is used.
- [ ] Standard error envelope is used.
- [ ] Validation errors include field details.
- [ ] List endpoints are paginated.
- [ ] Financial POST endpoints require idempotency key.

## 18. Security And Compliance

- [ ] Passwords are stored hashed.
- [ ] JWT expiry is enforced.
- [ ] Refresh token flow is tested.
- [ ] PII endpoints require authentication.
- [ ] Object ownership is enforced for customer records.
- [ ] Object ownership is enforced for provider records.
- [ ] Payment secrets are not exposed in API responses.
- [ ] Uploaded document URLs are not public unless signed.
- [ ] Sensitive admin actions are audited.

## 19. Performance Smoke Checks

- [ ] Customer profile endpoint responds within target under normal load.
- [ ] Service catalog endpoint responds within target under normal load.
- [ ] Dispatch queue remains paginated with large booking count.
- [ ] Audit log viewer remains paginated with large audit count.
- [ ] Reports complete within acceptable time for MVP data volume.

## 20. Launch Exit Criteria

MVP can launch only when:

- [ ] All P0 tests pass.
- [ ] No unresolved payment, wallet, payout, or permission P1 defects remain.
- [ ] Payment webhook idempotency is verified.
- [ ] Wallet reconciliation is verified.
- [ ] Provider approval and suspension are verified.
- [ ] Admin audit logging is verified.
- [ ] Backup and restore procedure has been tested at least once.
