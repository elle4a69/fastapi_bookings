# Error Handling

All API responses use a consistent envelope structure. Successful
responses include an `ok: true` field and one of `data` or `meta`
payloads. Errors use `ok: false` and an `error` object containing
machine‑readable codes and human‑friendly messages.

Example error response:

```json
{
  "ok": false,
  "error": {
    "code": "BOOKING_SLOT_UNAVAILABLE",
    "message": "That time slot is no longer available.",
    "field": "start_time",
    "details": null
  }
}
```

Applications should use the `code` property to determine how to
respond, and display the `message` to the user. The optional
`field` property indicates which form input, if any, caused the error.