import React, { useState } from 'react';
import { useBookingFlow } from '../../store/BookingFlowContext';
import { useTenant } from '../../store/TenantContext';
import { bookingService } from '../../services/bookingService';

export const CheckoutReview: React.FC = () => {
  const { bootstrap } = useTenant();
  const { 
    selections, 
    clientIdentity, 
    setStep, 
    setOutcome, 
    setError, 
    isLoading 
  } = useBookingFlow();
  
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!bootstrap || !clientIdentity || !selections.serviceId || !selections.providerId || !selections.time) {
    return null;
  }

  const service = bootstrap.services?.find(s => s.id === selections.serviceId);
  const provider = bootstrap.providers?.find(p => p.id === selections.providerId);
  const addOns = bootstrap.add_ons?.filter(a => selections.addOnIds.includes(a.id)) || [];

  if (!service || !provider) return null;

  const isRestricted = clientIdentity.management_approval_required;
  const requiresDeposit = service.deposit_amount_minor > 0;
  
  const formatPrice = (minor: number) => `$${(minor / 100).toFixed(2)}`;
  const formatDateTime = (isoString: string) => {
    const d = new Date(isoString);
    return d.toLocaleString(undefined, { weekday: 'long', month: 'long', day: 'numeric', hour: 'numeric', minute: '2-digit' });
  };

  const handleCheckout = async () => {
    setIsSubmitting(true);
    setError(null);
    
    const idempotencyKey = crypto.randomUUID();

    try {
      if (isRestricted) {
        // Submit Management Review Request
        const response = await bookingService.submitReviewRequest({
          client_id: clientIdentity.id,
          preferred_service_id: service.id,
          preferred_provider_id: provider.id,
          preferred_start_at: selections.time!,
          note: "Submitted via public checkout flow."
        });
        setOutcome({ type: 'review', data: response });
        setStep('outcome');
      } else if (requiresDeposit) {
        // Submit Checkout with Payment
        const response = await bookingService.submitCheckout({
          client_id: clientIdentity.id,
          service_id: service.id,
          provider_id: provider.id,
          start_time: selections.time!,
          add_on_ids: selections.addOnIds,
          terms_accepted: termsAccepted,
          payment_method_token: 'mock_tok_success', // In real app, this comes from Stripe/Square element
          idempotency_key: idempotencyKey
        });
        setOutcome({ type: 'confirmed', data: response });
        setStep('outcome');
      } else {
        // Submit No-Deposit Booking
        const response = await bookingService.submitBooking({
          client_id: clientIdentity.id,
          service_id: service.id,
          provider_id: provider.id,
          start_time: selections.time!,
          add_on_ids: selections.addOnIds,
          terms_accepted: termsAccepted,
          idempotency_key: idempotencyKey
        });
        setOutcome({ type: 'pending', data: response });
        setStep('outcome');
      }
    } catch (err: any) {
      setError(err.uiError || { code: 'SUBMIT_FAILED', message: 'We couldn\'t submit this booking. Please try again.' });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <button 
        onClick={() => setStep('client')}
        className="text-sm text-indigo-600 hover:text-indigo-800 font-medium flex items-center"
        disabled={isSubmitting}
      >
        <svg className="w-4 h-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
        </svg>
        Back to details
      </button>

      {isRestricted && (
        <div className="bg-amber-50 border-l-4 border-amber-500 p-4 rounded-r-md">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-amber-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-amber-800">Review Required</h3>
              <p className="text-sm text-amber-700 mt-1">
                Your request needs to be reviewed before online booking can continue. Submitting this request will not take payment or reserve the time slot.
              </p>
            </div>
          </div>
        </div>
      )}

      <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
        <h2 className="text-xl font-bold text-slate-900 mb-4">Booking Summary</h2>
        
        <div className="space-y-4 divide-y divide-slate-100">
          <div className="pb-4">
            <p className="text-sm text-slate-500">Service</p>
            <p className="font-medium text-slate-900">{service.name}</p>
          </div>
          
          <div className="py-4">
            <p className="text-sm text-slate-500">Provider</p>
            <p className="font-medium text-slate-900">{provider.name}</p>
          </div>

          <div className="py-4">
            <p className="text-sm text-slate-500">Time</p>
            <p className="font-medium text-slate-900">{formatDateTime(selections.time!)}</p>
          </div>

          {addOns.length > 0 && (
            <div className="py-4">
              <p className="text-sm text-slate-500 mb-1">Extras</p>
              <ul className="space-y-1">
                {addOns.map(a => (
                  <li key={a.id} className="flex justify-between text-sm">
                    <span className="text-slate-700">{a.name}</span>
                    <span className="text-slate-900 font-medium">{formatPrice(a.price_minor)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {!isRestricted && (
            <div className="pt-4">
              <div className="flex justify-between items-center mb-2">
                <span className="text-slate-600">Total Price</span>
                <span className="font-semibold text-slate-900">
                  {formatPrice(service.price_minor + addOns.reduce((sum, a) => sum + a.price_minor, 0))}
                </span>
              </div>
              {requiresDeposit && (
                <div className="flex justify-between items-center bg-slate-50 p-3 rounded-lg border border-slate-200">
                  <span className="text-slate-800 font-medium">Deposit Required Now</span>
                  <span className="font-bold text-indigo-700">{formatPrice(service.deposit_amount_minor)}</span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {!isRestricted && (
        <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
          <label className="flex items-start">
            <div className="flex items-center h-5">
              <input
                type="checkbox"
                checked={termsAccepted}
                onChange={(e) => setTermsAccepted(e.target.checked)}
                className="focus:ring-indigo-500 h-4 w-4 text-indigo-600 border-slate-300 rounded"
                disabled={isSubmitting}
              />
            </div>
            <div className="ml-3 text-sm">
              <span className="font-medium text-slate-700">I accept the booking terms and conditions</span>
              <p className="text-slate-500 mt-1">By continuing, you agree to our cancellation and refund policies.</p>
            </div>
          </label>
        </div>
      )}

      <button
        onClick={handleCheckout}
        disabled={isSubmitting || (!isRestricted && !termsAccepted)}
        className="w-full flex justify-center py-4 px-4 border border-transparent rounded-xl shadow-sm text-base font-bold text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 transition-colors"
      >
        {isSubmitting 
          ? 'Processing...' 
          : isRestricted 
            ? 'Send review request' 
            : requiresDeposit 
              ? 'Pay deposit and confirm booking' 
              : 'Submit booking request'}
      </button>
    </div>
  );
};
