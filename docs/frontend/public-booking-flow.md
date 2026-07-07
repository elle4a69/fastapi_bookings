# Public Booking Flow

This document outlines the steps a customer must follow to book a service
using the public booking interface.

1. **Obtain a token:** The front end calls `POST /api/public/auth/token` with
   the company name and API key. The response contains a bearer token
   which must be sent in the `X-Token` header for subsequent requests.
2. **Bootstrap:** Use `GET /api/public/bootstrap` to retrieve the list of
   available services, providers, locations, categories, booking rules and
   the default timezone.
3. **Select service and provider:** Present the user with the services
   and providers. The front end may allow filtering providers by
   selected service.
4. **Check availability:** For the chosen service and provider, call
   `GET /api/public/availability` with `service_id`, `provider_id` and
   a date to obtain available time slots.
5. **Create booking:** Once the user selects a time slot and enters
   their contact information, send a request to `POST /api/public/bookings`
   with the booking details. The booking is created with status
   `pending`.
6. **Confirmation:** Display the booking details returned by the API to
   the customer and provide any follow‑up instructions.