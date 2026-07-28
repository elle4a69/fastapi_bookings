import React from 'react';
import { useTenant } from '../../store/TenantContext';
import { useBookingFlow } from '../../store/BookingFlowContext';
import { ServiceCard } from './ServiceCard';
import { ProviderCard } from './ProviderCard';
import { TimeSelector } from './TimeSelector';
import { AddOnSelector } from './AddOnSelector';

export const DiscoveryShell: React.FC = () => {
  const { bootstrap, uiConfig } = useTenant();
  const { 
    selections, 
    validOptions, 
    isLoading, 
    error, 
    infoMessage, 
    isComplete,
    setService, 
    setProvider, 
    setTime, 
    toggleAddOn,
    clearSelection,
    clearInfoMessage,
    setStep
  } = useBookingFlow();

  if (!bootstrap) return null;

  const handleContinue = () => {
    setStep('client');
  };

  return (
    <div className="space-y-8 pb-24">
      
      {/* Global Error / Info Banners */}
      {error && (
        <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded-r-md">
          <p className="text-sm text-red-700">{error.message}</p>
        </div>
      )}
      
      {infoMessage && (
        <div className="bg-blue-50 border-l-4 border-blue-500 p-4 rounded-r-md flex justify-between items-center">
          <p className="text-sm text-blue-700">{infoMessage}</p>
          <button onClick={clearInfoMessage} className="text-blue-500 hover:text-blue-700">
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}

      {/* Services Section */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-slate-800">Select a Service</h2>
          {selections.serviceId && (
            <button onClick={() => clearSelection('serviceId')} className="text-sm text-indigo-600 hover:text-indigo-800 font-medium">
              Clear
            </button>
          )}
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 relative">
          {isLoading && !validOptions && (
            <div className="absolute inset-0 bg-white/50 z-10 flex items-center justify-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
            </div>
          )}
          {(bootstrap.services || []).map(service => (
            <ServiceCard
              key={service.id}
              service={service}
              isSelected={selections.serviceId === service.id}
              isValid={validOptions?.valid_services ? validOptions.valid_services.includes(service.id) : true}
              onSelect={() => setService(service.id)}
            />
          ))}
        </div>
      </section>

      {/* Add-ons Section (Optional) */}
      {uiConfig?.add_ons_enabled && bootstrap?.add_ons && bootstrap.add_ons.length > 0 && (
        <section>
          <h2 className="text-xl font-bold text-slate-800 mb-4">Optional Extras</h2>
          <AddOnSelector 
            addOns={bootstrap.add_ons || []}
            selectedIds={selections.addOnIds}
            onToggle={toggleAddOn}
          />
        </section>
      )}

      {/* Providers Section */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-slate-800">Select a Provider</h2>
          {selections.providerId && (
            <button onClick={() => clearSelection('providerId')} className="text-sm text-indigo-600 hover:text-indigo-800 font-medium">
              Clear
            </button>
          )}
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 relative">
          {(bootstrap.providers || []).map(provider => (
            <ProviderCard
              key={provider.id}
              provider={provider}
              isSelected={selections.providerId === provider.id}
              isValid={validOptions?.valid_providers ? validOptions.valid_providers.includes(provider.id) : true}
              onSelect={() => setProvider(provider.id)}
            />
          ))}
        </div>
      </section>

      {/* Time Section */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-slate-800">Select a Time</h2>
          {selections.time && (
            <button onClick={() => clearSelection('time')} className="text-sm text-indigo-600 hover:text-indigo-800 font-medium">
              Clear
            </button>
          )}
        </div>
        <div className="relative min-h-[100px]">
          {isLoading && (
            <div className="absolute inset-0 bg-white/60 z-10 flex items-center justify-center rounded-xl">
              <div className="flex items-center space-x-2 text-indigo-600">
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-indigo-600"></div>
                <span className="text-sm font-medium">Refreshing availability...</span>
              </div>
            </div>
          )}
          <TimeSelector 
            validTimes={validOptions?.valid_times || []}
            selectedTime={selections.time}
            onSelect={setTime}
          />
        </div>
      </section>

      {/* Sticky Footer Action */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-slate-200 p-4 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.05)] z-20">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div>
            {validOptions && (
              <p className="text-sm text-slate-600 font-medium">
                Total Duration: {validOptions.total_duration_minutes} mins
              </p>
            )}
          </div>
          <button
            onClick={handleContinue}
            disabled={!isComplete || isLoading}
            className="px-8 py-3 bg-indigo-600 text-white font-semibold rounded-lg shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            Continue to details
          </button>
        </div>
      </div>

    </div>
  );
};
