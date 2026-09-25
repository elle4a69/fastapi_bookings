# Admin Finance & Billing Operations

## Purpose & Scope
The `frontend/src/pages/admin/finance/` directory implements financial administration for **FastAPI Bookings**. It encompasses accounts receivable, payment transaction processing, jurisdictional tax calculations, discount campaigns, and payment gateway configuration.

Key features:
- **Invoicing & Accounts Receivable** (`invoices.tsx`): Invoice lifecycle tracking (`Draft`, `Sent`, `Paid`, `Void`, `Overdue`), line item generation, payment receipts, and PDF export/email dispatch.
- **Payment Logs & Reconciliation** (`payments.tsx`): Real-time transaction log, payment method distribution, and refund processing with audit logs.
- **Payment Processors** (`processors.tsx`): Configuration for Stripe, PayPal, Square, and offline / manual payment methods.
- **Tax Rates** (`tax-rates.tsx`): Multi-jurisdiction sales tax percentages and active/inactive status.
- **Promotions & Discounts** (`promotions.tsx`): Coupon codes, percentage or fixed discounts, service eligibility rules, and expiration limits.

---

## Architecture & Key Files

### Directory Layout
```
frontend/src/pages/admin/finance/
├── invoices.tsx      # Comprehensive billing invoices list, line item modal & PDF exporter
├── payments.tsx      # Transactions ledger, refund initiator & payment method filters
├── processors.tsx    # Stripe / PayPal / Offline payment processor credentials & webhooks
├── promotions.tsx    # Promotional discount codes, percentage / fixed rules & service scopes
└── tax-rates.tsx     # Tax rate percentage definitions & jurisdictional settings
```

### Core Architecture Components
- **ResponsiveDataTable Integration**: Both `invoices.tsx` and `payments.tsx` implement `<ResponsiveDataTable<T>>`. Staff on desktop enjoy multi-column sortable grids with custom column visibility via `<ColumnVisibilityPicker>`, while staff on mobile phones receive touch-optimized card summaries (`renderMobileCard`) with active status badges.
- **Mobile Page Shell**: Every finance view wraps its content in `<MobilePageShell>` with minimum `44px` interactive touch targets for filters, search bars, and action buttons.
- **Split Master-Detail Views**: `promotions.tsx` and `tax-rates.tsx` employ a responsive two-column master-detail layout on desktop that seamlessly transforms into a slide-over mobile drawer or full-screen editor via `<MobileBackButton>` on small viewports.

---

## Setup, Configuration & Dependencies

### External Gateway Dependencies
- **Stripe**: Publishable Key, Secret Key, and Webhook Signing Secret configured in `processors.tsx`.
- **PayPal / Square / Offline**: Client ID, Client Secret, and customer payment instructions.

### Backend Endpoints
- `GET /api/admin/invoices`: Returns paginated invoices with line items and payment histories.
- `GET /api/admin/invoices/{id}/pdf`: Downloads rendered invoice PDF.
- `POST /api/admin/invoices/{id}/send`: Triggers customer email with payment link.
- `GET /api/admin/payments`: Lists payment transactions with gateway references.
- `PUT /api/admin/payments/{id}`: Marks a transaction as refunded or updates dispute status.
- `GET /api/admin/payment-processors`: Retrieves enabled gateways and public keys.
- `PUT /api/admin/payment-processors/{provider}`: Updates processor secrets and operational mode.
- `GET /api/admin/tax-rates` & `POST /api/admin/tax-rates`: Manages tax tiers.
- `GET /api/admin/promotions` & `POST /api/admin/promotions`: Manages discount campaigns.

---

## Core Workflows & Contracts

### 1. Invoicing & Payment Settlement
```
[Client Booking Completed]
             │
             ▼
Invoice Generated (status: 'Draft' or 'Sent')
             │
             ▼
Client pays via Portal or Public Checkout (Stripe webhook received)
             │
             ▼
Payment Record Logged (/api/admin/payments)
             │
             ▼
Invoice balance decremented; transitions to status: 'Paid'
```

### 2. Manual Refund Processing
Staff locating an erroneous or disputed charge in `payments.tsx` can click **Refund**. A PUT request is dispatched to `/api/admin/payments/{id}` with `{ status: 'refunded' }`. The UI displays a notification via `sonner`, refetches the ledger, and updates the associated invoice balance.

---

## Data Safety, Multi-Tenancy & PII Isolation

- **Financial Safety (Rule 3 & 4)**: Financial mutations (marking refunds, changing processor credentials) require explicit staff confirmation. Payment processor secret keys (`secret_key`, `client_secret`) are masked upon retrieval and never logged or exposed to the public portal.
- **PCI-DSS Compliance**: No raw credit card numbers or CVVs ever touch or pass through the frontend client state. All card tokenization is performed client-side directly by the payment processor's SDK (e.g. Stripe Elements).
- **Tenant Ledger Partitioning**: Invoices, payments, and tax rules are strictly scoped to the authenticated tenant. Cross-tenant financial queries are forbidden at the API level.

---

## Known Issues, Edge Cases & Outstanding Work

- **Multi-Currency Display**: Invoices currently default to the tenant's primary currency (e.g. `USD` or `AUD`). Multi-currency conversion for cross-border clients is planned.
- **Automated Partial Refunds**: Currently, partial refunds must be entered as manual credit adjustments on the invoice. Direct automated partial-amount refund dispatch via the Stripe API is scheduled for the next iteration.

---

## Verification & Testing Commands

```bash
# Typecheck and build finance modules
cd frontend
npm run build

# Run Oxlint across finance pages
npx oxlint src/pages/admin/finance
```
