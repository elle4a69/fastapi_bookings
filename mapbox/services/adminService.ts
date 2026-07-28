import { apiFetch } from './apiClient';
import { 
  DashboardStats, 
  BookingDetail, 
  ConfirmRequest, 
  RescheduleRequest,
  ServiceDetail,
  ProviderDetail,
  CategoryDetail,
  LocationDetail,
  AddOnDetail,
  CompanyHoursRule,
  ProviderAvailabilityRule,
  ClientDetail,
  NotificationSetting,
  BusinessProfile
} from '../types';

export const adminService = {
  // --- MODULE 4: DASHBOARD & BOOKINGS ---
  async getDashboardStats(): Promise<DashboardStats> {
    return apiFetch<DashboardStats>('/api/admin/dashboard/stats', { method: 'GET' });
  },
  async getBookings(): Promise<BookingDetail[]> {
    return apiFetch<BookingDetail[]>('/api/admin/bookings', { method: 'GET' });
  },
  async confirmBooking(bookingId: number, request: ConfirmRequest): Promise<BookingDetail> {
    return apiFetch<BookingDetail>(`/api/admin/bookings/${bookingId}/confirm`, { method: 'POST', body: JSON.stringify(request) });
  },
  async rescheduleBooking(bookingId: number, request: RescheduleRequest): Promise<BookingDetail> {
    return apiFetch<BookingDetail>(`/api/admin/bookings/${bookingId}/reschedule`, { method: 'POST', body: JSON.stringify(request) });
  },
  async cancelBooking(bookingId: number, request: ConfirmRequest): Promise<BookingDetail> {
    return apiFetch<BookingDetail>(`/api/admin/bookings/${bookingId}/cancel`, { method: 'POST', body: JSON.stringify(request) });
  },

  // --- MODULE 5, 8, 9: CATALOGUE MANAGEMENT ---
  async getServices(): Promise<ServiceDetail[]> {
    return apiFetch<ServiceDetail[]>('/api/admin/services', { method: 'GET' });
  },
  async getService(id: number): Promise<ServiceDetail> {
    return apiFetch<ServiceDetail>(`/api/admin/services/${id}`, { method: 'GET' });
  },
  async createService(data: Partial<ServiceDetail>): Promise<ServiceDetail> {
    return apiFetch<ServiceDetail>('/api/admin/services', { method: 'POST', body: JSON.stringify(data) });
  },
  async updateService(id: number, data: Partial<ServiceDetail>): Promise<ServiceDetail> {
    return apiFetch<ServiceDetail>(`/api/admin/services/${id}`, { method: 'PUT', body: JSON.stringify(data) });
  },
  async deleteService(id: number): Promise<void> {
    return apiFetch<void>(`/api/admin/services/${id}`, { method: 'DELETE' });
  },

  async getProviders(): Promise<ProviderDetail[]> {
    return apiFetch<ProviderDetail[]>('/api/admin/providers', { method: 'GET' });
  },
  async getProvider(id: number): Promise<ProviderDetail> {
    return apiFetch<ProviderDetail>(`/api/admin/providers/${id}`, { method: 'GET' });
  },
  async createProvider(data: Partial<ProviderDetail>): Promise<ProviderDetail> {
    return apiFetch<ProviderDetail>('/api/admin/providers', { method: 'POST', body: JSON.stringify(data) });
  },
  async updateProvider(id: number, data: Partial<ProviderDetail>): Promise<ProviderDetail> {
    return apiFetch<ProviderDetail>(`/api/admin/providers/${id}`, { method: 'PUT', body: JSON.stringify(data) });
  },
  async deleteProvider(id: number): Promise<void> {
    return apiFetch<void>(`/api/admin/providers/${id}`, { method: 'DELETE' });
  },

  async getCategories(): Promise<CategoryDetail[]> {
    return apiFetch<CategoryDetail[]>('/api/admin/categories', { method: 'GET' });
  },
  async createCategory(data: Partial<CategoryDetail>): Promise<CategoryDetail> {
    return apiFetch<CategoryDetail>('/api/admin/categories', { method: 'POST', body: JSON.stringify(data) });
  },
  async updateCategory(id: number, data: Partial<CategoryDetail>): Promise<CategoryDetail> {
    return apiFetch<CategoryDetail>(`/api/admin/categories/${id}`, { method: 'PUT', body: JSON.stringify(data) });
  },

  async getLocations(): Promise<LocationDetail[]> {
    return apiFetch<LocationDetail[]>('/api/admin/locations', { method: 'GET' });
  },
  async createLocation(data: Partial<LocationDetail>): Promise<LocationDetail> {
    return apiFetch<LocationDetail>('/api/admin/locations', { method: 'POST', body: JSON.stringify(data) });
  },
  async updateLocation(id: number, data: Partial<LocationDetail>): Promise<LocationDetail> {
    return apiFetch<LocationDetail>(`/api/admin/locations/${id}`, { method: 'PUT', body: JSON.stringify(data) });
  },

  async getAddOns(): Promise<AddOnDetail[]> {
    return apiFetch<AddOnDetail[]>('/api/admin/add-ons', { method: 'GET' });
  },
  async createAddOn(data: Partial<AddOnDetail>): Promise<AddOnDetail> {
    return apiFetch<AddOnDetail>('/api/admin/add-ons', { method: 'POST', body: JSON.stringify(data) });
  },
  async updateAddOn(id: number, data: Partial<AddOnDetail>): Promise<AddOnDetail> {
    return apiFetch<AddOnDetail>(`/api/admin/add-ons/${id}`, { method: 'PUT', body: JSON.stringify(data) });
  },

  // --- MODULE 6: SCHEDULING ---
  async getCompanyHours(date: string): Promise<CompanyHoursRule> {
    return apiFetch<CompanyHoursRule>(`/api/admin/settings/hours?date=${date}`, { method: 'GET' });
  },
  async updateCompanyHours(data: CompanyHoursRule): Promise<CompanyHoursRule> {
    return apiFetch<CompanyHoursRule>('/api/admin/settings/hours', { method: 'PUT', body: JSON.stringify(data) });
  },

  async getProviderAvailability(providerId: number, date: string): Promise<ProviderAvailabilityRule> {
    return apiFetch<ProviderAvailabilityRule>(`/api/admin/providers/${providerId}/availability?date=${date}`, { method: 'GET' });
  },
  async updateProviderAvailability(providerId: number, data: ProviderAvailabilityRule): Promise<ProviderAvailabilityRule> {
    return apiFetch<ProviderAvailabilityRule>(`/api/admin/providers/${providerId}/availability`, { method: 'PUT', body: JSON.stringify(data) });
  },

  // --- MODULE 7: CLIENTS, NOTIFICATIONS, PROFILE ---
  async getClients(): Promise<ClientDetail[]> {
    return apiFetch<ClientDetail[]>('/api/admin/clients', { method: 'GET' });
  },
  async updateClientApproval(clientId: number, required: boolean, reason: string): Promise<ClientDetail> {
    return apiFetch<ClientDetail>(`/api/admin/clients/${clientId}/management-approval`, { 
      method: 'PATCH', 
      body: JSON.stringify({ management_approval_required: required, reason }) 
    });
  },

  async getNotificationSettings(): Promise<NotificationSetting[]> {
    return apiFetch<NotificationSetting[]>('/api/admin/settings/notifications', { method: 'GET' });
  },
  async updateNotificationSettings(data: NotificationSetting[]): Promise<NotificationSetting[]> {
    return apiFetch<NotificationSetting[]>('/api/admin/settings/notifications', { method: 'PUT', body: JSON.stringify(data) });
  },

  async getBusinessProfile(): Promise<BusinessProfile> {
    return apiFetch<BusinessProfile>('/api/admin/settings/business', { method: 'GET' });
  },
  async updateBusinessProfile(data: BusinessProfile): Promise<BusinessProfile> {
    return apiFetch<BusinessProfile>('/api/admin/settings/business', { method: 'PUT', body: JSON.stringify(data) });
  }
};
