import React, { useEffect, useState } from 'react';
import { adminService } from '../../services/adminService';
import { CompanyHoursRule, UiError } from '../../types';
import { useAuth } from '../../store/AuthContext';
import { IntervalGrid } from './IntervalGrid';

export const BusinessHours: React.FC = () => {
  const { user } = useAuth();
  const isStaff = user?.role === 'staff';

  const [selectedDate, setSelectedDate] = useState<string>(new Date().toISOString().split('T')[0]);
  const [rule, setRule] = useState<CompanyHoursRule | null>(null);
  
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<UiError | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  const fetchHours = async (date: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await adminService.getCompanyHours(date);
      setRule(data);
    } catch (err: any) {
      setError(err.uiError || { code: 'FETCH_FAILED', message: 'Could not load business hours.' });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchHours(selectedDate);
  }, [selectedDate]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isStaff || !rule) return;

    setIsSaving(true);
    setError(null);
    setSaveMessage(null);

    try {
      const saved = await adminService.updateCompanyHours(rule);
      setRule(saved);
      setSaveMessage('Business hours saved.');
      setTimeout(() => setSaveMessage(null), 4000);
    } catch (err: any) {
      setError(err.uiError || { code: 'SAVE_FAILED', message: 'We couldn\'t save these business hours. Your selections are still here.' });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Company Business Hours</h1>
          <p className="text-sm text-slate-600 mt-1">Define normal operating boundaries and date-specific overrides.</p>
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
        <div className="p-6 border-b border-slate-200 bg-slate-50">
          <label htmlFor="date-select" className="block text-sm font-medium text-slate-700 mb-2">
            Select Date to View/Edit
          </label>
          <input
            type="date"
            id="date-select"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            className="block w-full sm:w-64 rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
          />
        </div>

        <div className="p-6 relative min-h-[200px]">
          {isLoading && (
            <div className="absolute inset-0 bg-white/80 z-10 flex items-center justify-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
            </div>
          )}

          {rule && (
            <form onSubmit={handleSave} className="space-y-6">
              
              <div className="flex items-start bg-indigo-50 p-4 rounded-lg border border-indigo-100">
                <div className="flex items-center h-5">
                  <input
                    id="recurring"
                    type="checkbox"
                    disabled={isStaff || isSaving}
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
                <h3 className="text-sm font-medium text-slate-700 mb-3">Operating Intervals</h3>
                <IntervalGrid 
                  intervals={rule.intervals} 
                  onChange={(intervals) => setRule({ ...rule, intervals })}
                  disabled={isStaff || isSaving}
                />
              </div>

              {!isStaff && (
                <div className="pt-4 border-t border-slate-200 flex justify-end">
                  <button
                    type="submit"
                    disabled={isSaving || isLoading}
                    className="inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
                  >
                    {isSaving ? 'Saving...' : 'Save Business Hours'}
                  </button>
                </div>
              )}
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
