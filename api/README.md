# AyosNow API Notes

The API routes are mounted under `/api/v1/`.

Responses use the standard envelope:

```json
{
  "success": true,
  "data": {},
  "meta": null,
  "error": null
}
```

Errors use:

```json
{
  "success": false,
  "data": null,
  "meta": null,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input",
    "fields": {}
  }
}
```

The implementation is intentionally MVP-first. Authentication, OTP, payment provider integration, notification delivery, and file upload signing are stubbed or minimal until those providers are finalized.
