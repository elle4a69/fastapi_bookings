import React from 'react';
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';
import { TenantProvider } from './store/TenantContext';
import { AuthProvider } from './store/AuthContext';
import { BookingFlowProvider } from './store/BookingFlowContext';
import { PublicLayout, AdminLayout } from './components/Layout';
import { AdminLogin } from './components/auth/AdminLogin';
import { AuthGuard } from './components/auth/AuthGuard';
import { RoleNotEnabled } from './components/auth/RoleNotEnabled';
import { BookingWizard } from './components/public/BookingWizard';
import MapSearch from './components/public/MapSearch';

// Client Portal Components
import { ClientLayout } from './components/client/ClientLayout';
import { ClientLogin } from './components/client/ClientLogin';
import { ClientRegister } from './components/client/ClientRegister';
import { ClientPasswordReset } from './components/client/ClientPasswordReset';
import { ClientProfile } from './components/client/ClientProfile';
import { ClientTerms } from './components/client/ClientTerms';

// Admin Core Components
import { Dashboard } from './components/admin/Dashboard';
import { CalendarView } from './components/admin/CalendarView';
import { BookingList } from './components/admin/BookingList';
import { ServiceManager } from './components/admin/ServiceManager';
import { ProviderManager } from './components/admin/ProviderManager';
import { LocationManager } from './components/admin/LocationManager';
import { CategoryManager } from './components/admin/CategoryManager';
import { AddOnManager } from './components/admin/AddOnManager';
import { ClientManager } from './components/admin/ClientManager';
import { BusinessProfile } from './components/admin/BusinessProfile';

// Admin v2 Modules & Builder
import { BookingFormList, BookingFormEditor } from './components/admin/BookingForms';
import { ProductManager, PackageManager, ResourceManager, RelationshipEditor } from './components/admin/CatalogExtensions';
import { InvoicesManager, PaymentsManager, PromotionsManager, TaxRatesManager, ProcessorsManager, AdditionalFieldsManager } from './components/admin/FinanceAndOperations';
import { NotificationsManager, NotificationTemplatesManager, ReminderRulesManager, ManagementReviewsManager, AuditLogManager, GdprConsentManager, WebhooksManager, PluginStatesManager, SystemDiagnosticsManager, WorkdaysManager, ScheduleExceptionsManager, BookingDetailView, ClientDetailView } from './components/admin/NotificationsAndCompliance';

// Errors
import { Error403, Error404 } from './components/errors/ErrorPages';

export default function App() {
  return (
    <AuthProvider>
      <TenantProvider>
        <HashRouter>
          <Routes>
            {/* Public Discovery Map Surface */}
            <Route path="/" element={<MapSearch />} />
            <Route path="/discover" element={<MapSearch />} />
            <Route path="/map" element={<Navigate to="/" replace />} />

            {/* Client Portal Surfaces */}
            <Route path="/client" element={<ClientLayout />}>
              <Route index element={<Navigate to="/client/profile" replace />} />
              <Route path="login" element={<ClientLogin />} />
              <Route path="register" element={<ClientRegister />} />
              <Route path="password-reset" element={<ClientPasswordReset />} />
              <Route path="profile" element={<ClientProfile />} />
              <Route path="terms" element={<ClientTerms />} />
            </Route>

            {/* Admin Authentication & RBAC Denial */}
            <Route path="/admin/login" element={<AdminLogin />} />
            <Route path="/admin/role-not-enabled" element={<RoleNotEnabled />} />

            {/* Protected Admin Workspace */}
            <Route path="/admin" element={<AuthGuard />}>
              <Route element={<AdminLayout />}>
                <Route index element={<Dashboard />} />
                <Route path="calendar" element={<CalendarView />} />
                
                {/* Bookings */}
                <Route path="bookings" element={<BookingList />} />
                <Route path="bookings/:bookingId" element={<BookingDetailView />} />

                {/* Form Builder */}
                <Route path="booking-forms" element={<BookingFormList />} />
                <Route path="booking-forms/new" element={<BookingFormEditor />} />
                <Route path="booking-forms/:formId" element={<BookingFormEditor />} />

                {/* Catalog Managers */}
                <Route path="catalog/services" element={<ServiceManager />} />
                <Route path="catalog/providers" element={<ProviderManager />} />
                <Route path="catalog/locations" element={<LocationManager />} />
                <Route path="catalog/categories" element={<CategoryManager />} />
                <Route path="catalog/add-ons" element={<AddOnManager />} />
                <Route path="catalog/products" element={<ProductManager />} />
                <Route path="catalog/packages" element={<PackageManager />} />

                {/* Legacy Catalog Redirect Shortcuts */}
                <Route path="services" element={<Navigate to="/admin/catalog/services" replace />} />
                <Route path="providers" element={<Navigate to="/admin/catalog/providers" replace />} />
                <Route path="locations" element={<Navigate to="/admin/catalog/locations" replace />} />
                <Route path="categories" element={<Navigate to="/admin/catalog/categories" replace />} />
                <Route path="add-ons" element={<Navigate to="/admin/catalog/add-ons" replace />} />

                {/* Resources & Relationships */}
                <Route path="resources" element={<ResourceManager />} />
                <Route path="relationships" element={<RelationshipEditor />} />

                {/* Schedule & Shifts */}
                <Route path="schedule/workdays" element={<WorkdaysManager />} />
                <Route path="schedule/exceptions" element={<ScheduleExceptionsManager />} />
                <Route path="hours" element={<Navigate to="/admin/schedule/workdays" replace />} />
                <Route path="availability" element={<Navigate to="/admin/schedule/exceptions" replace />} />

                {/* Clients */}
                <Route path="clients" element={<ClientManager />} />
                <Route path="clients/:clientId" element={<ClientDetailView />} />

                {/* Intake Configuration */}
                <Route path="configuration/additional-fields" element={<AdditionalFieldsManager />} />

                {/* Finance */}
                <Route path="finance/invoices" element={<InvoicesManager />} />
                <Route path="finance/payments" element={<PaymentsManager />} />
                <Route path="finance/promotions" element={<PromotionsManager />} />
                <Route path="finance/tax-rates" element={<TaxRatesManager />} />
                <Route path="finance/processors" element={<ProcessorsManager />} />

                {/* Notifications & Reminders */}
                <Route path="notifications/messages" element={<NotificationsManager />} />
                <Route path="notifications/templates" element={<NotificationTemplatesManager />} />
                <Route path="notifications/reminders" element={<ReminderRulesManager />} />
                <Route path="notifications" element={<Navigate to="/admin/notifications/messages" replace />} />

                {/* Audit, Compliance & Settings */}
                <Route path="reviews" element={<ManagementReviewsManager />} />
                <Route path="audit" element={<AuditLogManager />} />
                <Route path="compliance/gdpr" element={<GdprConsentManager />} />
                <Route path="settings/business" element={<BusinessProfile />} />
                <Route path="profile" element={<Navigate to="/admin/settings/business" replace />} />
                <Route path="settings/webhooks" element={<WebhooksManager />} />
                <Route path="settings/plugins" element={<PluginStatesManager />} />
                <Route path="system" element={<SystemDiagnosticsManager />} />
              </Route>
            </Route>

            {/* Error Pages */}
            <Route path="/403" element={<Error403 />} />
            <Route path="/404" element={<Error404 />} />
            <Route path="*" element={<Error404 />} />
          </Routes>
        </HashRouter>
      </TenantProvider>
    </AuthProvider>
  );
}
