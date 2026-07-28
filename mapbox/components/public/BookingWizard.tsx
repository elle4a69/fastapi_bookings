import React from 'react';
import { useBookingFlow } from '../../store/BookingFlowContext';
import { DiscoveryShell } from './DiscoveryShell';
import { ClientDetailsForm } from './ClientDetailsForm';
import { CheckoutReview } from './CheckoutReview';
import { BookingOutcome } from './BookingOutcome';

export const BookingWizard: React.FC = () => {
  const { step, error } = useBookingFlow();

  return (
    <div className="w-full">
      {/* Global Error Banner for Checkout/Identify steps */}
      {error && step !== 'discovery' && (
        <div className="max-w-2xl mx-auto mb-6 bg-red-50 border-l-4 border-red-500 p-4 rounded-r-md">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <p className="text-sm text-red-700">{error.message}</p>
            </div>
          </div>
        </div>
      )}

      {step === 'discovery' && <DiscoveryShell />}
      {step === 'client' && <ClientDetailsForm />}
      {step === 'checkout' && <CheckoutReview />}
      {step === 'outcome' && <BookingOutcome />}
    </div>
  );
};
