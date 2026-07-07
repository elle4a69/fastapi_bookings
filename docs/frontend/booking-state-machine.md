# Booking State Machine

Bookings progress through a finite set of states. The allowed
transitions are defined in `app/core/state_machine.py`. This document
summarizes the states and transitions.

## States

| State       | Description                                                     |
|-------------|-----------------------------------------------------------------|
| pending     | A booking has been created but not yet confirmed.              |
| confirmed   | The booking has been accepted by staff or automatically.       |
| cancelled   | The booking has been cancelled and will not take place.        |
| completed   | The booking took place successfully.                           |
| no_show     | The client did not attend the appointment.                     |
| rescheduled | The booking has been rescheduled to a new time.                |

## Allowed transitions

| From       | To                            | Notes                             |
|------------|------------------------------|------------------------------------|
| pending    | confirmed, cancelled, rescheduled | Client can be accepted, declined or moved. |
| confirmed  | cancelled, completed, no_show, rescheduled | Staff can conclude or modify the booking. |
| rescheduled| confirmed, cancelled          | After rescheduling, booking must be confirmed or cancelled. |
| cancelled  | —                            | Cancelled bookings are final.      |
| completed  | —                            | Completed bookings are final.      |
| no_show    | —                            | No‑show bookings are final.        |

Attempts to perform an invalid transition will result in a 400 error.