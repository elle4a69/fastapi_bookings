import React, { useEffect, useState } from 'react';
import { adminService } from '../../services/adminService';
import { ProviderAvailabilityRule, ProviderDetail, UiError } from '../../types';
import { useAuth } from '../../store/AuthContext';
import { IntervalGrid } from './IntervalGrid';

export const ProviderAvailability: React.FC = () => {
  const { user } = useAuth();
  const isStaff = user?.role === 'staff';

  const [providers, setProviders] = useState<ProviderDetail[]>([]);
  const [selectedProviderId, setSelectedProviderId] = useState<number | null>(isStaff ? user?.provider_id || null : null);
  const [selectedDate, setSelectedDate] = useState<string>(new Date().toISOString().split('T')[0]);
  
  const [rule, setRule] = useState<ProviderAvailabilityRule | null>(null);
  
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<UiError | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  // Fetch providers list for admins
  useEffect(() => {
    if (!isStaff) {
      adminService.getProviders().then(data => {
        setProviders(data);
        if (data.length > 0 && !selectedProviderId) {
          setSelectedProviderId(data[0].id);
        }
      }).catch(err => {
        setError(err.uiError || { code: 'FETCH_FAILED', message: 'Could not load providers.' });
      });
    }
  }, [isStaff, selectedProviderId]);

  const fetchAvailability = async (providerId: number, date: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await adminService.getProviderAvailability(providerId, date);
      setRule(data);
    } catch (err: any) {
      setError(err.uiError || { code: 'FETCH_FAILED', message: 'Could not load availability.' });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (selectedProviderId) {
      fetchAvailability(selectedProviderId, selectedDate);
    }
  }, [selectedProviderId, selectedDate]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rule || !selectedProviderId) return;

    setIsSaving(true);
    setError(null);
    setSaveMessage(null);

    try {
      const saved = await adminService.updateProviderAvailability(selectedProviderId, rule);
      setRule(saved);
      setSaveMessage('Availability saved.');
      setTimeout(() => setSaveMessage(null), 4000);
    } catch (err: any) {
      setError(err.uiError || { code: 'SAVE_FAILED', message: 'We couldn\'t save this availability. Your selections are still here.' });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Provider Availability</h1>
          <p className="text-sm text-slate-600 mt-1">Configure recurring schedules and date-specific overrides.</p>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded-md">
          <p className="text-sm text-red-700">{error.message}</p>
        </div>
      )}
      {saveMessage && (
        <div className="bg-green-50 border-l-4 border-green-500 p-4 rounded-md">
          <p className="text-sm text-green-700">{saveMessage}</p>
        </div>
      )}

      <div className="bg-white shadow-sm rounded-xl border border-slate-200 overflow-hidden">
        <div className="p-6 border-b border-slate-200 bg-slate-50 grid grid-cols-1 sm:grid-cols-2 gap-4">
          
          {!isStaff && (
            <div>
              <label htmlFor="provider-select" className="block text-sm font-medium text-slate-700 mb-2">
                Select Provider
              </label>
              <select
                id="provider-select"
                value={selectedProviderId || ''}
                onChange={(e) => setSelectedProviderId(parseInt(e.target.value, 10))}
                className="block w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border bg-white"
              >
                {providers.map(p => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>
          )}

          <div>
            <label htmlFor="date-select" className="block text-sm font-medium text-slate-700 mb-2">
              Select Date to View/Edit
            </label>
            <input
              type="date"
              id="date-select"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              className="block w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
            />
          </div>
        </div>

        <div className="p-6 relative min-h-[200px]">
          {isLoading && (
            <div className="absolute inset-0 bg-white/80 z-10 flex items-center justify-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
            </div>
          )}

          {!selectedProviderId && !isLoading && (
            <div className="text-center text-slate-500 py-8">Please select a provider.</div>
          )}

          {rule && selectedProviderId && (
            <form onSubmit={handleSave} className="space-y-6">
              
              <div className="flex items-start bg-indigo-50 p-4 rounded-lg border border-indigo-100">
                <div className="flex items-center h-5">
                  <input
                    id="recurring"
                    type="checkbox"
                    disabled={isSaving}
                    checked={rule.recurring_weekday}
                    onChange={(e) => setRule({ ...rule, recurring_weekday: e.target.checked })}
                    className="focus:ring-indigo-500 h-4 w-4 text-indigo-600 border-slate-300 rounded disabled:opacity-50"
                  />
                </div>
                <div className="ml-3 text-sm">
                  <label htmlFor="recurring" className="font-medium text-indigo-900">
                    Apply to all {new Date(selectedDate).toLocaleDateString(undefined, { weekday: 'long' })}s
                  </label>
                  <p className="text-indigo-700 mt-1">
                    If unchecked, these hours will only apply to the specific date selected above (one-off override).
                  </p>
                </div>
              </div>

              <div>
                <h3 className="text-sm font-medium text-slate-700 mb-3">Working Intervals</h3>
                <IntervalGrid 
                  intervals={rule.intervals} 
                  onChange={(intervals) => setRule({ ...rule, intervals })}
                  disabled={isSaving}
                />
              </div>

              <div className="pt-6 border-t border-slate-200 grid grid-cols-1 sm:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-slate-700">Max Advance Booking Days</label>
                  <input
                    type="number"
                    min="0"
                    max="730"
                    required
                    disabled={isSaving}
                    value={rule.max_advance_booking_days}
                    onChange={(e) => setRule({ ...rule, max_advance_booking_days: parseInt(e.target.value, 10) })}
                    className="mt-1 block w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border disabled:bg-slate-50 disabled:text-slate-500"
                  />
                  <p className="mt-1 text-xs text-slate-500">How far in advance clients can book.</p>
                </div>

                <div className="flex items-center pt-6">
                  <input
                    id="ignore_company_hours"
                    type="checkbox"
                    disabled={isSaving || isStaff} // Staff cannot toggle this permission
                    checked={rule.ignore_company_hours}
                    onChange={(e) => setRule({ ...rule, ignore_company_hours: e.target.checked })}
                    className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-slate-300 rounded disabled:opacity-50"
                  />
                  <label htmlFor="ignore_company_hours" className="ml-2 block text-sm text-slate-900">
                    Ignore Company Hours
                  </label>
                </div>
              </div>

              <div className="pt-4 border-t border-slate-200 flex justify-end">
                <button
                  type="submit"
                  disabled={isSaving || isLoading}
                  className="inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
                >
                  {isSaving ? 'Saving...' : 'Save Availability'}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
