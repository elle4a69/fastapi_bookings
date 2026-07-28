import React, { useState } from 'react';
import { adminService } from '../../services/adminService';
import { BookingDetail } from '../../types';
import { BookingDrawer } from './BookingDrawer';
import { usePolling } from '../../hooks/usePolling';

export const BookingList: React.FC = () => {
  const { 
    data: bookings, 
    isLoading, 
    isPolling, 
    error, 
    lastUpdated, 
    refetch,
    mutateData
  } = usePolling(adminService.getBookings, 30000);
  
  const [selectedBooking, setSelectedBooking] = useState<BookingDetail | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  const handleBookingUpdated = (updated: BookingDetail) => {
    // Optimistically update the local cache without waiting for the next poll
    mutateData(prev => prev ? prev.map(b => b.id === updated.id ? updated : b) : null);
    setSelectedBooking(updated);
  };

  const openDrawer = (booking: BookingDetail) => {
    setSelectedBooking(booking);
    setIsDrawerOpen(true);
  };

  const formatDateTime = (isoString: string) => {
    return new Date(isoString).toLocaleString(undefined, { 
      month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' 
    });
  };

  const statusColors: Record<string, string> = {
    pending: 'bg-blue-100 text-blue-800',
    confirmed: 'bg-green-100 text-green-800',
    cancelled: 'bg-slate-100 text-slate-800',
    rescheduled: 'bg-purple-100 text-purple-800',
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <h1 className="text-2xl font-bold text-slate-900">Bookings</h1>
          {isPolling && (
            <span className="flex items-center text-xs font-medium text-indigo-600 bg-indigo-50 px-2 py-1 rounded-full animate-pulse">
              <svg className="w-3 h-3 mr-1 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Syncing
            </span>
          )}
          {!isPolling && lastUpdated && (
            <span className="text-xs text-slate-500">
              Updated {lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          )}
        </div>
        <button 
          onClick={refetch} 
          disabled={isPolling || isLoading}
          className="text-sm text-indigo-600 hover:text-indigo-800 font-medium disabled:opacity-50"
        >
          Refresh List
        </button>
      </div>

      {error && (
        <div className="bg-amber-50 border-l-4 border-amber-500 p-4 rounded-md">
          <p className="text-sm text-amber-700">{error.message}</p>
        </div>
      )}

      <div className="bg-white shadow-sm rounded-xl border border-slate-200 overflow-hidden">
        {isLoading && !bookings ? (
          <div className="p-8 text-center text-slate-500">Loading bookings...</div>
        ) : !bookings || bookings.length === 0 ? (
          <div className="p-8 text-center text-slate-500">No bookings match these filters.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Client</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Service</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Time</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Status</th>
                  <th scope="col" className="relative px-6 py-3"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-slate-200">
                {bookings.map((booking) => (
                  <tr key={booking.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-slate-900">
                      {booking.client_name}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                      {booking.service_name} <br/>
                      <span className="text-xs text-slate-400">with {booking.provider_name}</span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                      {formatDateTime(booking.start_time)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full capitalize ${statusColors[booking.status] || 'bg-slate-100 text-slate-800'}`}>
                        {booking.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <button 
                        onClick={() => openDrawer(booking)}
                        className="text-indigo-600 hover:text-indigo-900"
                      >
                        Manage
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <BookingDrawer 
        booking={selectedBooking} 
        isOpen={isDrawerOpen} 
        onClose={() => setIsDrawerOpen(false)} 
        onBookingUpdated={handleBookingUpdated}
      />
    </div>
  );
};
