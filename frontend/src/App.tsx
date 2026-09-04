import { Suspense, lazy } from "react"
import { BrowserRouter, Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom"

import { navigation } from "@/components/navigation"
import { AdminLayout } from "@/layouts/admin-layout"
import { getAdminAccessToken } from "@/lib/api"

// Lazy loaded page components
const CategoriesPage = lazy(() => import("@/pages/admin/catalog/categories"))
const LocationsPage = lazy(() => import("@/pages/admin/catalog/locations"))
const ServicesPage = lazy(() => import("@/pages/admin/catalog/services"))
const ProvidersPage = lazy(() => import("@/pages/admin/catalog/providers"))
const SchedulingPage = lazy(() => import("@/pages/admin/catalog/scheduling"))
const ClientsPage = lazy(() => import("@/pages/admin/clients"))

const WorkdaysPage = lazy(() => import("@/pages/admin/schedule/workdays"))
const ExceptionsPage = lazy(() => import("@/pages/admin/schedule/exceptions"))
const BookingsPage = lazy(() => import("@/pages/admin/bookings"))
const CalendarPage = lazy(() => import("@/pages/admin/calendar"))
const BookingFormsPage = lazy(() => import("@/pages/admin/booking-forms"))
const BookingFormEditorPage = lazy(() => import("@/pages/admin/booking-form-editor"))

const AddOnsPage = lazy(() => import("@/pages/admin/catalog/add-ons"))
const ProductsPage = lazy(() => import("@/pages/admin/catalog/products"))
const PackagesPage = lazy(() => import("@/pages/admin/catalog/packages"))
const ResourcesPage = lazy(() => import("@/pages/admin/resources"))
const RelationshipsPage = lazy(() => import("@/pages/admin/relationships"))
const RelationshipsMatrixPage = lazy(() => import("@/pages/admin/relationships-matrix"))
const RelationshipsTreePage = lazy(() => import("@/pages/admin/relationships-tree"))

const TaxRatesPage = lazy(() => import("@/pages/admin/finance/tax-rates"))
const ProcessorsPage = lazy(() => import("@/pages/admin/finance/processors"))
const InvoicesPage = lazy(() => import("@/pages/admin/finance/invoices").then(m => ({ default: m.InvoicesPage })))
const PaymentsPage = lazy(() => import("@/pages/admin/finance/payments").then(m => ({ default: m.PaymentsPage })))
const PromotionsPage = lazy(() => import("@/pages/admin/finance/promotions").then(m => ({ default: m.PromotionsPage })))
const ReviewsPage = lazy(() => import("@/pages/admin/reviews"))
const AdditionalFieldsPage = lazy(() => import("@/pages/admin/configuration/additional-fields"))
const MediaPage = lazy(() => import("@/pages/admin/media"))
const SmsAssistantPage = lazy(() => import("@/pages/admin/sms-assistant"))

const MessagesPage = lazy(() => import("@/pages/admin/notifications/messages"))
const TemplatesPage = lazy(() => import("@/pages/admin/notifications/templates"))
const RemindersPage = lazy(() => import("@/pages/admin/notifications/reminders"))
const BusinessSettings = lazy(() => import("@/pages/admin/settings/business"))
const WebhooksSettings = lazy(() => import("@/pages/admin/settings/webhooks"))
const PluginsSettings = lazy(() => import("@/pages/admin/settings/plugins"))
const GDPRPage = lazy(() => import("@/pages/admin/compliance/gdpr"))
const AuditLogsPage = lazy(() => import("@/pages/admin/audit"))
const SystemPage = lazy(() => import("@/pages/admin/system"))
const PublicBookingPage = lazy(() => import("@/pages/public/booking-page"))
const PublicUploadPage = lazy(() => import("@/pages/public/upload-page"))
const LoginPage = lazy(() => import("@/pages/login"))

const adminRoutes = navigation.flatMap((section) =>
  section.items.flatMap((item) => {
    if (item.url) {
      return [{ path: item.url, title: item.title }]
    }

    return (item.children ?? []).map((child) => ({
      path: child.url,
      title: child.title,
    }))
  }),
)

function RoutePlaceholder({ title }: { title: string }) {
  const { pathname } = useLocation()

  return (
    <section className="mx-auto flex w-full max-w-7xl flex-col gap-4">
      <div className="flex flex-col gap-1">
        <p className="text-sm font-medium text-primary">Admin workspace</p>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1>
        <p className="text-sm text-muted-foreground">The application shell is ready for this module.</p>
      </div>
      <div className="rounded-xl border bg-card p-5 shadow-sm">
        <p className="text-sm text-muted-foreground">
          Current route: <code className="rounded bg-muted px-1.5 py-0.5 text-foreground">{pathname}</code>
        </p>
      </div>
    </section>
  )
}

function ErrorPage({ code, title }: { code: string; title: string }) {
  return (
    <main className="grid min-h-svh place-items-center p-6">
      <section className="flex max-w-md flex-col gap-3 text-center">
        <p className="text-sm font-semibold text-primary">{code}</p>
        <h1 className="text-3xl font-semibold tracking-tight">{title}</h1>
        <a className="text-sm font-medium text-primary underline-offset-4 hover:underline" href="/admin">
          Return to the admin workspace
        </a>
      </section>
    </main>
  )
}

function PageLoader() {
  return (
    <div className="flex h-48 w-full items-center justify-center text-sm text-muted-foreground">
      <div className="flex items-center gap-2">
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        <span>Loading page...</span>
      </div>
    </div>
  )
}

function RequireAdminSession() {
  const location = useLocation()

  if (!getAdminAccessToken()) {
    return <Navigate to="/login" replace state={{ from: { pathname: location.pathname } }} />
  }

  return <Outlet />
}

function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<RequireAdminSession />}>
            <Route element={<AdminLayout />}>
              {adminRoutes.map((route) => (
                <Route
                  key={route.path}
                  path={route.path}
                  element={
                    route.path === '/admin/catalog/categories' ? <CategoriesPage /> :
                    route.path === '/admin/catalog/locations' ? <LocationsPage /> :
                    route.path === '/admin/catalog/services' ? <ServicesPage /> :
                    route.path === '/admin/catalog/providers' ? <ProvidersPage /> :
                    route.path === '/admin/catalog/scheduling' ? <SchedulingPage /> :
                    route.path === '/admin/schedule/exceptions' ? <ExceptionsPage /> :
                    route.path === '/admin/clients' ? <ClientsPage /> :
                    route.path === '/admin/schedule/workdays' ? <WorkdaysPage /> :
                    route.path === '/admin/bookings' ? <BookingsPage /> :
                    route.path === '/admin/calendar' ? <CalendarPage /> :
                    route.path === '/admin/booking-forms' ? <BookingFormsPage /> :
                    route.path === '/admin/catalog/add-ons' ? <AddOnsPage /> :
                    route.path === '/admin/catalog/products' ? <ProductsPage /> :
                    route.path === '/admin/catalog/packages' ? <PackagesPage /> :
                    route.path === '/admin/resources' ? <ResourcesPage /> :
                    route.path === '/admin/relationships' ? <RelationshipsPage /> :
                    route.path === '/admin/relationships-matrix' ? <RelationshipsMatrixPage /> :
                    route.path === '/admin/relationships-tree' ? <RelationshipsTreePage /> :
                    route.path === '/admin/finance/tax-rates' ? <TaxRatesPage /> :
                    route.path === '/admin/finance/processors' ? <ProcessorsPage /> :
                    route.path === '/admin/finance/invoices' ? <InvoicesPage /> :
                    route.path === '/admin/finance/payments' ? <PaymentsPage /> :
                    route.path === '/admin/finance/promotions' ? <PromotionsPage /> :
                    route.path === '/admin/reviews' ? <ReviewsPage /> :
                    route.path === '/admin/media' ? <MediaPage /> :
                    route.path === '/admin/sms-assistant' ? <SmsAssistantPage /> :
                    route.path === '/admin/configuration/additional-fields' ? <AdditionalFieldsPage /> :
                    route.path === '/admin/notifications/messages' ? <MessagesPage /> :
                    route.path === '/admin/notifications/templates' ? <TemplatesPage /> :
                    route.path === '/admin/notifications/reminders' ? <RemindersPage /> :
                    route.path === '/admin/settings/business' ? <BusinessSettings /> :
                    route.path === '/admin/settings/webhooks' ? <WebhooksSettings /> :
                    route.path === '/admin/settings/plugins' ? <PluginsSettings /> :
                    route.path === '/admin/compliance/gdpr' ? <GDPRPage /> :
                    route.path === '/admin/audit' ? <AuditLogsPage /> :
                    route.path === '/admin/system' ? <SystemPage /> :
                    <RoutePlaceholder title={route.title} />
                  }
                />
              ))}
              <Route path="/admin/relationships-matrix" element={<RelationshipsMatrixPage />} />
              <Route path="/admin/relationships-tree" element={<RelationshipsTreePage />} />
              <Route path="/admin/booking-forms/:formId" element={<BookingFormEditorPage />} />
            </Route>
          </Route>
          <Route path="/book/*" element={<PublicBookingPage />} />
          <Route path="/book" element={<PublicBookingPage />} />
          <Route path="/booking" element={<PublicBookingPage />} />
          <Route path="/public/upload" element={<PublicUploadPage />} />
          <Route path="/book/upload" element={<PublicUploadPage />} />
          <Route path="/403" element={<ErrorPage code="403" title="Permission denied" />} />
          <Route path="/404" element={<ErrorPage code="404" title="Page not found" />} />
          <Route path="/" element={<Navigate to="/admin" replace />} />
          <Route path="*" element={<Navigate to="/404" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}

export default App
