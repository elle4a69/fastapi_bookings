# Authentication Flow

This document explains how authentication works in the FastAPI Bookings
application.

## Token types

Two types of tokens are issued by the API:

1. **Admin tokens**: Issued by `POST /api/admin/auth`. These encode the
   user ID and role and are used for all administrative endpoints under
   `/api/admin`. Only users with roles `owner` or `admin` can access
   privileged operations.
2. **Public tokens**: Issued by `POST /api/public/auth/token`. These
   encode the company name and are used by the public booking widget.
   Public tokens grant access to endpoints under `/api/public` and
   `/api/public/bookings`.

## Headers

All requests that require authentication must include the `X-Token`
header with the bearer token returned by the login endpoints.

```
X-Token: <access_token>
```

The `X-Company-Login` header from SimplyBook has been replaced with
token contents in the local implementation. The company is encoded in
the token itself.