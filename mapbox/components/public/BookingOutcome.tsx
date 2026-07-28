import React from 'react';
import { useBookingFlow } from '../../store/BookingFlowContext';

export const BookingOutcome: React.FC = () => {
  const { outcome, resetFlow } = useBookingFlow();

  if (!outcome) return null;

  const renderContent = () => {
    switch (outcome.type) {
      case 'confirmed':
        return (
          <>
            <div className="mx-auto flex items-center justify-center h-16 w-16 rounded-full bg-green-100 mb-6">
              <svg className="h-8 w-8 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h2 className="text-2xl font-bold text-slate-900 mb-2">Booking confirmed</h2>
            <p className="text-slate-600 mb-6">
              Your deposit has been received and your time is secured. We've sent a confirmation email with the details.
            </p>
            <div className="bg-slate-50 rounded-lg p-4 text-left border border-slate-200 mb-8">
              <p className="text-sm text-slate-500">Booking Reference</p>
              <p className="font-mono font-medium text-slate-900">#{outcome.data.booking.id}</p>
            </div>
          </>
        );
      case 'pending':
        return (
          <>
            <div className="mx-auto flex items-center justify-center h-16 w-16 rounded-full bg-blue-100 mb-6">
              <svg className="h-8 w-8 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h2 className="text-2xl font-bold text-slate-900 mb-2">Request received</h2>
            <p className="text-slate-600 mb-8">
              Your booking request has been received and is awaiting confirmation. We will notify you once it is approved.
            </p>
          </>
        );
      case 'review':
        return (
          <>
            <div className="mx-auto flex items-center justify-center h-16 w-16 rounded-full bg-amber-100 mb-6">
              <svg className="h-8 w-8 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <h2 className="text-2xl font-bold text-slate-900 mb-2">Review request sent</h2>
            <p className="text-slate-600 mb-8">
              Your request has been sent to the business for review. No payment has been taken and the requested time is not reserved.
            </p>
          </>
        );
    }
  };

  return (
    <div className="max-w-md mx-auto bg-white p-8 rounded-xl shadow-sm border border-slate-200 text-center">
      {renderContent()}
      <button
        onClick={resetFlow}
        className="w-full py-3 px-4 border border-slate-300 rounded-lg shadow-sm text-sm font-medium text-slate-700 bg-white hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition-colors"
      >
        Return to start
      </button>
    </div>
  );
};
