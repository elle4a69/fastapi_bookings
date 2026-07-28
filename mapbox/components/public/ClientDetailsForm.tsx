import React, { useState } from 'react';
import { useBookingFlow } from '../../store/BookingFlowContext';

export const ClientDetailsForm: React.FC = () => {
  const { clientDetails, identifyClient, isLoading, setStep } = useBookingFlow();
  
  const [firstName, setFirstName] = useState(clientDetails?.first_name || '');
  const [lastName, setLastName] = useState(clientDetails?.last_name || '');
  const [email, setEmail] = useState(clientDetails?.email || '');
  const [phone, setPhone] = useState(clientDetails?.phone || '');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await identifyClient({
      first_name: firstName,
      last_name: lastName,
      email,
      phone: phone || undefined
    });
  };

  return (
    <div className="max-w-xl mx-auto bg-white p-6 sm:p-8 rounded-xl shadow-sm border border-slate-200">
      <div className="mb-6">
        <button 
          onClick={() => setStep('discovery')}
          className="text-sm text-indigo-600 hover:text-indigo-800 font-medium flex items-center mb-4"
        >
          <svg className="w-4 h-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Back to booking options
        </button>
        <h2 className="text-2xl font-bold text-slate-900">Your Details</h2>
        <p className="text-slate-600 mt-1">Enter your contact information to continue.</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          <div>
            <label htmlFor="firstName" className="block text-sm font-medium text-slate-700">First Name</label>
            <input
              type="text"
              id="firstName"
              required
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              className="mt-1 block w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
              disabled={isLoading}
            />
          </div>
          <div>
            <label htmlFor="lastName" className="block text-sm font-medium text-slate-700">Last Name</label>
            <input
              type="text"
              id="lastName"
              required
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              className="mt-1 block w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
              disabled={isLoading}
            />
          </div>
        </div>

        <div>
          <label htmlFor="email" className="block text-sm font-medium text-slate-700">Email Address</label>
          <input
            type="email"
            id="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 block w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
            disabled={isLoading}
          />
          <p className="mt-1 text-xs text-slate-500">Use "restricted@example.com" to test the management review flow.</p>
        </div>

        <div>
          <label htmlFor="phone" className="block text-sm font-medium text-slate-700">Phone Number (Optional)</label>
          <input
            type="tel"
            id="phone"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            className="mt-1 block w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
            disabled={isLoading}
          />
        </div>

        <div className="pt-4">
          <button
            type="submit"
            disabled={isLoading || !firstName || !lastName || !email}
            className="w-full flex justify-center py-3 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 transition-colors"
          >
            {isLoading ? 'Confirming details...' : 'Continue to review'}
          </button>
        </div>
      </form>
    </div>
  );
};
