import React, { useState } from 'react';
import { adminService } from '../../services/adminService';
import { BookingDetail } from '../../types';
import { BookingDrawer } from './BookingDrawer';
import { usePolling } from '../../hooks/usePolling';

export const CalendarView: React.FC = () => {
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
    mutateData(prev => prev ? prev.map(b => b.id === updated.id ? updated : b) : null);
    setSelectedBooking(updated);
  };

  const openDrawer = (booking: BookingDetail) => {
    setSelectedBooking(booking);
    setIsDrawerOpen(true);
  };

  const groupedBookings = (bookings || []).reduce((acc, booking) => {
    const dateKey = new Date(booking.start_time).toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' });
    if (!acc[dateKey]) acc[dateKey] = [];
    acc[dateKey].push(booking);
    return acc;
  }, {} as Record<string, BookingDetail[]>);

  const statusColors: Record<string, string> = {
    pending: 'border-blue-500 bg-blue-50',
    confirmed: 'border-green-500 bg-green-50',
    cancelled: 'border-slate-400 bg-slate-50 opacity-60',
    rescheduled: 'border-purple-500 bg-purple-50',
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <h1 className="text-2xl font-bold text-slate-900">Calendar</h1>
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
          Refresh Calendar
        </button>
      </div>

      {error && (
        <div className="bg-amber-50 border-l-4 border-amber-500 p-4 rounded-md">
          <p className="text-sm text-amber-700">{error.message}</p>
        </div>
      )}

      <div className="bg-white shadow-sm rounded-xl border border-slate-200 p-6">
        {isLoading && !bookings ? (
          <div className="text-center text-slate-500 py-12">Loading calendar...</div>
        ) : Object.keys(groupedBookings).length === 0 ? (
          <div className="text-center text-slate-500 py-12">No upcoming bookings.</div>
        ) : (
          <div className="space-y-8">
            {Object.entries(groupedBookings).map(([date, dayBookings]) => (
              <div key={date}>
                <h2 className="text-lg font-semibold text-slate-800 mb-4 border-b border-slate-200 pb-2">{date}</h2>
                <div className="space-y-3">
                  {(dayBookings as any[]).sort((a: any, b: any) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime()).map(booking => {
                    const startTime = new Date(booking.start_time).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
                    const endTime = new Date(booking.end_time).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
                    
                    return (
                      <button
                        key={booking.id}
                        onClick={() => openDrawer(booking)}
                        className={`w-full text-left p-4 rounded-lg border-l-4 shadow-sm transition-transform hover:-translate-y-0.5 ${statusColors[booking.status] || 'border-slate-300 bg-white'}`}
                      >
                        <div className="flex justify-between items-start">
                          <div>
                            <p className="font-semibold text-slate-900">{startTime} - {endTime}</p>
                            <p className="text-sm text-slate-700 mt-1">{booking.client_name} • {booking.service_name}</p>
                          </div>
                          <span className="text-xs font-medium uppercase tracking-wider text-slate-500 bg-white px-2 py-1 rounded border border-slate-200">
                            {booking.status}
                          </span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
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
