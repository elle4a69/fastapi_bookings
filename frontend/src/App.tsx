import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom"

import { navigation } from "@/components/navigation"
import { AdminLayout } from "@/layouts/admin-layout"

import CategoriesPage from "@/pages/admin/catalog/categories"
import LocationsPage from "@/pages/admin/catalog/locations"
import ServicesPage from "@/pages/admin/catalog/services"
import ProvidersPage from "@/pages/admin/catalog/providers"
import SchedulingPage from "@/pages/admin/catalog/scheduling"
import ClientsPage from "@/pages/admin/clients"

import WorkdaysPage from "@/pages/admin/schedule/workdays"
import ExceptionsPage from "@/pages/admin/schedule/exceptions"
import BookingsPage from "@/pages/admin/bookings"
import CalendarPage from "@/pages/admin/calendar"
import BookingFormsPage from "@/pages/admin/booking-forms"
import BookingFormEditorPage from "@/pages/admin/booking-form-editor"

import AddOnsPage from "@/pages/admin/catalog/add-ons"
import ProductsPage from "@/pages/admin/catalog/products"
import PackagesPage from "@/pages/admin/catalog/packages"
import ResourcesPage from "@/pages/admin/resources"
import RelationshipsPage from "@/pages/admin/relationships"

import TaxRatesPage from "@/pages/admin/finance/tax-rates"
import ProcessorsPage from "@/pages/admin/finance/processors"
import { InvoicesPage } from "@/pages/admin/finance/invoices"
import { PaymentsPage } from "@/pages/admin/finance/payments"
import { PromotionsPage } from "@/pages/admin/finance/promotions"
import ReviewsPage from "@/pages/admin/reviews"
import AdditionalFieldsPage from "@/pages/admin/configuration/additional-fields"

import MessagesPage from "@/pages/admin/notifications/messages"
import TemplatesPage from "@/pages/admin/notifications/templates"
import RemindersPage from "@/pages/admin/notifications/reminders"
import BusinessSettings from "@/pages/admin/settings/business"
import WebhooksSettings from "@/pages/admin/settings/webhooks"
import PluginsSettings from "@/pages/admin/settings/plugins"
import GDPRPage from "@/pages/admin/compliance/gdpr"
import AuditLogsPage from "@/pages/admin/audit"
import SystemPage from "@/pages/admin/system"
import PublicBookingPage from "@/pages/public/booking-page"

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

function App() {
  return (
    <BrowserRouter>
      <Routes>
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
                route.path === '/admin/clients' ? <ClientsPage /> :
                route.path === '/admin/schedule/workdays' ? <WorkdaysPage /> :
                route.path === '/admin/schedule/exceptions' ? <ExceptionsPage /> :
                route.path === '/admin/bookings' ? <BookingsPage /> :
                route.path === '/admin/calendar' ? <CalendarPage /> :
                route.path === '/admin/booking-forms' ? <BookingFormsPage /> :
                route.path === '/admin/catalog/add-ons' ? <AddOnsPage /> :
                route.path === '/admin/catalog/products' ? <ProductsPage /> :
                route.path === '/admin/catalog/packages' ? <PackagesPage /> :
                route.path === '/admin/resources' ? <ResourcesPage /> :
                route.path === '/admin/relationships' ? <RelationshipsPage /> :
                route.path === '/admin/finance/tax-rates' ? <TaxRatesPage /> :
                route.path === '/admin/finance/processors' ? <ProcessorsPage /> :
                route.path === '/admin/finance/invoices' ? <InvoicesPage /> :
                route.path === '/admin/finance/payments' ? <PaymentsPage /> :
                route.path === '/admin/finance/promotions' ? <PromotionsPage /> :
                route.path === '/admin/reviews' ? <ReviewsPage /> :
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
          <Route path="/admin/booking-forms/:formId" element={<BookingFormEditorPage />} />
        </Route>
        <Route path="/book/:slug" element={<PublicBookingPage />} />
        <Route path="/book" element={<PublicBookingPage />} />
        <Route path="/booking" element={<PublicBookingPage />} />
        <Route path="/403" element={<ErrorPage code="403" title="Permission denied" />} />
        <Route path="/404" element={<ErrorPage code="404" title="Page not found" />} />
        <Route path="/" element={<Navigate to="/admin" replace />} />
        <Route path="*" element={<Navigate to="/404" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
