import { apiFetch } from './apiClient';
import { 
  SearchAvailabilityRequest, 
  SearchAvailabilityResponse,
  ClientDetails,
  ClientIdentityResponse,
  CheckoutRequest,
  CheckoutResponse,
  BookingResponse,
  ManagementReviewRequestPayload,
  ManagementReviewResponse
} from '../types';

export const bookingService = {
  async searchAvailability(request: SearchAvailabilityRequest): Promise<SearchAvailabilityResponse> {
    return apiFetch<SearchAvailabilityResponse>('/api/public/search-availability', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  async identifyClient(details: ClientDetails): Promise<ClientIdentityResponse> {
    return apiFetch<ClientIdentityResponse>('/api/public/clients/identify', {
      method: 'POST',
      body: JSON.stringify(details),
    });
  },

  async submitCheckout(request: CheckoutRequest): Promise<CheckoutResponse> {
    return apiFetch<CheckoutResponse>('/api/public/bookings/checkout', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  async submitBooking(request: CheckoutRequest): Promise<BookingResponse> {
    return apiFetch<BookingResponse>('/api/public/bookings', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  async submitReviewRequest(request: ManagementReviewRequestPayload): Promise<ManagementReviewResponse> {
    return apiFetch<ManagementReviewResponse>('/api/public/management-review-requests', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }
};
