import React, { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react';
import { 
  SearchAvailabilityRequest, 
  SearchAvailabilityResponse, 
  UiError,
  ClientDetails,
  ClientIdentityResponse,
  CheckoutResponse,
  BookingResponse,
  ManagementReviewResponse
} from '../types';
import { bookingService } from '../services/bookingService';

export type WizardStep = 'discovery' | 'client' | 'checkout' | 'outcome';

interface BookingSelections {
  serviceId?: number;
  providerId?: number;
  time?: string;
  addOnIds: number[];
}

type FinalOutcome = 
  | { type: 'confirmed'; data: CheckoutResponse }
  | { type: 'pending'; data: BookingResponse }
  | { type: 'review'; data: ManagementReviewResponse };

interface BookingFlowState {
  step: WizardStep;
  selections: BookingSelections;
  validOptions: SearchAvailabilityResponse | null;
  clientDetails: ClientDetails | null;
  clientIdentity: ClientIdentityResponse | null;
  outcome: FinalOutcome | null;
  isLoading: boolean;
  error: UiError | null;
  infoMessage: string | null;
  isComplete: boolean;
  
  setStep: (step: WizardStep) => void;
  setService: (id: number) => void;
  setProvider: (id: number) => void;
  setTime: (time: string) => void;
  toggleAddOn: (id: number) => void;
  clearSelection: (type: keyof BookingSelections) => void;
  clearInfoMessage: () => void;
  setError: (error: UiError | null) => void;
  
  identifyClient: (details: ClientDetails) => Promise<void>;
  setOutcome: (outcome: FinalOutcome) => void;
  resetFlow: () => void;
}

const BookingFlowContext = createContext<BookingFlowState | undefined>(undefined);

export const BookingFlowProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [step, setStep] = useState<WizardStep>('discovery');
  const [selections, setSelections] = useState<BookingSelections>({ addOnIds: [] });
  const [validOptions, setValidOptions] = useState<SearchAvailabilityResponse | null>(null);
  const [clientDetails, setClientDetails] = useState<ClientDetails | null>(null);
  const [clientIdentity, setClientIdentity] = useState<ClientIdentityResponse | null>(null);
  const [outcome, setOutcome] = useState<FinalOutcome | null>(null);
  
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<UiError | null>(null);
  const [infoMessage, setInfoMessage] = useState<string | null>(null);

  const fetchAvailability = useCallback(async (currentSelections: BookingSelections) => {
    // Only fetch if we are in discovery step to avoid unnecessary calls during checkout
    if (step !== 'discovery') return;

    setIsLoading(true);
    setError(null);
    try {
      const request: SearchAvailabilityRequest = {
        service_id: currentSelections.serviceId,
        provider_id: currentSelections.providerId,
        start_at: currentSelections.time,
        add_on_ids: currentSelections.addOnIds.length > 0 ? currentSelections.addOnIds : undefined,
      };
      
      const response = await bookingService.searchAvailability(request);
      setValidOptions(response);

      let changed = false;
      const newSelections = { ...currentSelections };

      if (newSelections.serviceId && !(response?.valid_services ?? []).includes(newSelections.serviceId)) {
        newSelections.serviceId = undefined;
        changed = true;
      }
      if (newSelections.providerId && !(response?.valid_providers ?? []).includes(newSelections.providerId)) {
        newSelections.providerId = undefined;
        changed = true;
      }
      if (newSelections.time && !(response?.valid_times ?? []).includes(newSelections.time)) {
        newSelections.time = undefined;
        changed = true;
      }

      if (changed) {
        setSelections(newSelections);
        setInfoMessage('Your options changed. Choose a new available option.');
      }

    } catch (err: any) {
      if (err.uiError?.code === 'AVAILABILITY_CHANGED') {
        setSelections({ addOnIds: [] });
        setInfoMessage(err.uiError.message);
      } else {
        setError(err.uiError || { code: 'SEARCH_FAILED', message: 'We couldn\'t refresh availability. Please try again.' });
      }
    } finally {
      setIsLoading(false);
    }
  }, [step]);

  useEffect(() => {
    fetchAvailability(selections);
  }, [selections, fetchAvailability]);

  const identifyClient = async (details: ClientDetails) => {
    setIsLoading(true);
    setError(null);
    try {
      const identity = await bookingService.identifyClient(details);
      setClientDetails(details);
      setClientIdentity(identity);
      setStep('checkout');
    } catch (err: any) {
      setError(err.uiError || { code: 'IDENTIFY_FAILED', message: 'We couldn\'t confirm your client details. Please try again.' });
    } finally {
      setIsLoading(false);
    }
  };

  const resetFlow = () => {
    setSelections({ addOnIds: [] });
    setClientDetails(null);
    setClientIdentity(null);
    setOutcome(null);
    setError(null);
    setInfoMessage(null);
    setStep('discovery');
  };

  const setService = (id: number) => setSelections(prev => ({ ...prev, serviceId: id }));
  const setProvider = (id: number) => setSelections(prev => ({ ...prev, providerId: id }));
  const setTime = (time: string) => setSelections(prev => ({ ...prev, time }));
  
  const toggleAddOn = (id: number) => setSelections(prev => {
    const exists = prev.addOnIds.includes(id);
    return {
      ...prev,
      addOnIds: exists ? prev.addOnIds.filter(a => a !== id) : [...prev.addOnIds, id]
    };
  });

  const clearSelection = (type: keyof BookingSelections) => {
    setSelections(prev => ({ ...prev, [type]: type === 'addOnIds' ? [] : undefined }));
  };

  const clearInfoMessage = () => setInfoMessage(null);

  const isComplete = !!(selections.serviceId && selections.providerId && selections.time);

  return (
    <BookingFlowContext.Provider value={{
      step,
      selections,
      validOptions,
      clientDetails,
      clientIdentity,
      outcome,
      isLoading,
      error,
      infoMessage,
      isComplete,
      setStep,
      setService,
      setProvider,
      setTime,
      toggleAddOn,
      clearSelection,
      clearInfoMessage,
      setError,
      identifyClient,
      setOutcome,
      resetFlow
    }}>
      {children}
    </BookingFlowContext.Provider>
  );
};

export const useBookingFlow = () => {
  const context = useContext(BookingFlowContext);
  if (context === undefined) {
    throw new Error('useBookingFlow must be used within a BookingFlowProvider');
  }
  return context;
};
