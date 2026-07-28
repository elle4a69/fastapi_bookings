import React, { useState } from 'react';
import { BookingDetail, UiError } from '../../types';
import { adminService } from '../../services/adminService';

interface BookingDrawerProps {
  booking: BookingDetail | null;
  isOpen: boolean;
  onClose: () => void;
  onBookingUpdated: (updatedBooking: BookingDetail) => void;
}

export const BookingDrawer: React.FC<BookingDrawerProps> = ({ booking, isOpen, onClose, onBookingUpdated }) => {
  const [isMutating, setIsMutating] = useState(false);
  const [error, setError] = useState<UiError | null>(null);

  if (!isOpen || !booking) return null;

  const formatDateTime = (isoString: string) => {
    return new Date(isoString).toLocaleString(undefined, { 
      weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' 
    });
  };

  const formatPrice = (minor: number) => `$${(minor / 100).toFixed(2)}`;

  const handleAction = async (action: 'confirm' | 'cancel') => {
    setIsMutating(true);
    setError(null);
    const idempotencyKey = crypto.randomUUID();

    try {
      let updated: BookingDetail;
      if (action === 'confirm') {
        updated = await adminService.confirmBooking(booking.id, { idempotency_key: idempotencyKey });
      } else {
        updated = await adminService.cancelBooking(booking.id, { idempotency_key: idempotencyKey });
      }
      onBookingUpdated(updated);
    } catch (err: any) {
      setError(err.uiError || { code: 'ACTION_FAILED', message: 'We couldn\'t update this booking. Please try again.' });
    } finally {
      setIsMutating(false);
    }
  };

  const statusColors: Record<string, string> = {
    pending: 'bg-blue-100 text-blue-800',
    confirmed: 'bg-green-100 text-green-800',
    cancelled: 'bg-slate-100 text-slate-800',
    rescheduled: 'bg-purple-100 text-purple-800',
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden" aria-labelledby="slide-over-title" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-slate-900 bg-opacity-25 transition-opacity" onClick={onClose}></div>
      <div className="fixed inset-y-0 right-0 pl-10 max-w-full flex">
        <div className="w-screen max-w-md transform transition-transform ease-in-out duration-300">
          <div className="h-full flex flex-col bg-white shadow-xl overflow-y-scroll">
            
            {/* Header */}
            <div className="px-4 py-6 bg-slate-50 border-b border-slate-200 sm:px-6 flex justify-between items-center">
              <div>
                <h2 className="text-lg font-medium text-slate-900" id="slide-over-title">
                  Booking #{booking.id}
                </h2>
                <span className={`mt-1 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium capitalize ${statusColors[booking.status] || 'bg-slate-100 text-slate-800'}`}>
                  {booking.status}
                </span>
              </div>
              <button
                type="button"
                className="bg-white rounded-md text-slate-400 hover:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                onClick={onClose}
              >
                <span className="sr-only">Close panel</span>
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Content */}
            <div className="p-6 flex-1 space-y-6">
              {error && (
                <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded-md">
                  <p className="text-sm text-red-700">{error.message}</p>
                </div>
              )}

              <div>
                <h3 className="text-sm font-medium text-slate-500">Client</h3>
                <p className="mt-1 text-base text-slate-900">{booking.client_name}</p>
              </div>

              <div>
                <h3 className="text-sm font-medium text-slate-500">Service Details</h3>
                <p className="mt-1 text-base text-slate-900">{booking.service_name}</p>
                <p className="text-sm text-slate-600">with {booking.provider_name}</p>
              </div>

              <div>
                <h3 className="text-sm font-medium text-slate-500">Schedule</h3>
                <p className="mt-1 text-base text-slate-900">{formatDateTime(booking.start_time)}</p>
                <p className="text-sm text-slate-600">to {formatDateTime(booking.end_time)}</p>
              </div>

              <div>
                <h3 className="text-sm font-medium text-slate-500">Financials</h3>
                <p className="mt-1 text-base text-slate-900">Total: {formatPrice(booking.total_price_minor)}</p>
              </div>
            </div>

            {/* Actions Footer */}
            <div className="px-4 py-4 border-t border-slate-200 bg-slate-50 sm:px-6 flex flex-col space-y-3">
              {booking.status === 'pending' && (
                <button
                  onClick={() => handleAction('confirm')}
                  disabled={isMutating}
                  className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-indigo-600 text-base font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
                >
                  {isMutating ? 'Processing...' : 'Confirm Booking'}
                </button>
              )}
              
              {(booking.status === 'pending' || booking.status === 'confirmed' || booking.status === 'rescheduled') && (
                <button
                  onClick={() => handleAction('cancel')}
                  disabled={isMutating}
                  className="w-full inline-flex justify-center rounded-md border border-slate-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-red-700 hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50"
                >
                  Cancel Booking
                </button>
              )}
              
              {/* Note: Staff never sees a "Delete" button per MCD rules. Cancel is a lifecycle state. */}
            </div>

          </div>
        </div>
      </div>
    </div>
  );
};
