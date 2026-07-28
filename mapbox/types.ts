export interface UiError {
  code: string;
  message: string;
}

export interface Tenant {
  name: string;
  timezone: string;
}

export interface Service {
  id: number;
  name: string;
  duration_minutes: number;
  price_minor: number;
  deposit_amount_minor: number;
}

export interface Provider {
  id: number;
  name: string;
}

export interface Category {
  id: number;
  name: string;
}

export interface Location {
  id: number;
  name: string;
}

export interface AddOn {
  id: number;
  name: string;
  price_minor: number;
  duration_minutes: number;
}

export interface BootstrapData {
  tenant?: Tenant;
  company?: string;
  services: Service[];
  providers: Provider[];
  categories: Category[];
  locations: Location[];
  add_ons: AddOn[];
}

export interface UiConfig {
  categories_enabled: boolean;
  locations_enabled: boolean;
  add_ons_enabled: boolean;
  deposit_satisfies_approval: boolean;
}

export interface AuthUser {
  token: string;
  role: 'owner' | 'admin' | 'staff' | 'viewer';
  provider_id?: number;
  permission_keys: string[];
}

export interface ApiResponse<T> {
  ok: boolean;
  data?: T;
  error?: UiError;
  detail?: string;
}

export interface SearchAvailabilityRequest {
  service_id?: number;
  provider_id?: number;
  start_at?: string;
  category_id?: number;
  location_id?: number;
  add_on_ids?: number[];
  search_from?: string;
  search_to?: string;
}

export interface SearchAvailabilityResponse {
  total_duration_minutes: number;
  valid_services: number[];
  valid_providers: number[];
  valid_locations: number[];
  valid_categories: number[];
  valid_times: string[];
}

export interface ClientDetails {
  first_name: string;
  last_name: string;
  email: string;
  phone?: string;
}

export interface ClientIdentityResponse {
  id: number;
  management_approval_required: boolean;
}

export interface CheckoutRequest {
  client_id: number;
  service_id: number;
  provider_id: number;
  start_time: string;
  location_id?: number;
  add_on_ids?: number[];
  terms_accepted: boolean;
  payment_method_token?: string;
  idempotency_key: string;
}

export interface BookingResponse {
  id: number;
  status: 'pending' | 'confirmed' | 'cancelled' | 'completed' | 'no_show' | 'rescheduled';
  start_time: string;
  end_time: string;
}

export interface PaymentResponse {
  id: number;
  status: 'processing' | 'succeeded' | 'failed' | 'refunded';
  amount_minor: number;
  currency: string;
}

export interface CheckoutResponse {
  booking: BookingResponse;
  payment?: PaymentResponse;
}

export interface ManagementReviewRequestPayload {
  client_id: number;
  preferred_service_id: number;
  preferred_provider_id?: number;
  preferred_start_at: string;
  preferred_location_id?: number;
  note?: string;
}

export interface ManagementReviewResponse {
  id: number;
  status: string;
  slot_reserved: boolean;
  payment_taken: boolean;
}

export interface DashboardStats {
  pending_approvals: number;
  management_reviews: number;
  upcoming_today: number;
  exceptions: number;
}

export interface BookingDetail extends BookingResponse {
  client_name: string;
  service_name: string;
  provider_name: string;
  total_price_minor: number;
  provider_id: number;
}

export interface RescheduleRequest {
  new_start_time: string;
  idempotency_key: string;
}

export interface ConfirmRequest {
  idempotency_key: string;
}

export interface ServiceDetail extends Service {
  description?: string;
  active: boolean;
  provider_ids: number[];
  add_on_ids?: number[];
  category_ids?: number[];
  location_ids?: number[];
}

export interface ProviderDetail extends Provider {
  description?: string;
  email?: string;
  phone?: string;
  active: boolean;
  ignore_company_hours: boolean;
  max_advance_booking_days: number;
  service_ids: number[];
  location_ids?: number[];
}

export interface CategoryDetail extends Category {
  description?: string;
  active: boolean;
  service_ids: number[];
}

export interface LocationDetail extends Location {
  address?: string;
  timezone?: string;
  active: boolean;
  provider_ids: number[];
  service_ids: number[];
  category_ids?: number[];
}

export interface AddOnDetail extends AddOn {
  description?: string;
  active: boolean;
  service_ids: number[];
}

export interface TimeInterval {
  start_time: string;
  end_time: string;
}

export interface CompanyHoursRule {
  date: string;
  intervals: TimeInterval[];
  recurring_weekday: boolean;
}

export interface ProviderAvailabilityRule {
  provider_id: number;
  date: string;
  intervals: TimeInterval[];
  recurring_weekday: boolean;
  ignore_company_hours: boolean;
  max_advance_booking_days: number;
}

export interface ClientDetail {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  phone?: string;
  management_approval_required: boolean;
}

export interface NotificationSetting {
  id: number;
  event_type: string;
  recipient_type: 'client' | 'provider' | 'management';
  channel: string;
  enabled: boolean;
  template_body: string;
  remind_before_minutes?: number;
}

export interface BusinessProfile {
  name: string;
  email: string;
  phone?: string;
  timezone: string;
  country_code: string;
  website_url?: string;
  show_email_publicly: boolean;
  show_address_publicly: boolean;
}
