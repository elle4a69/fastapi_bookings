import React, { useEffect, useState } from 'react';
import { adminService } from '../../services/adminService';
import { NotificationSetting, UiError } from '../../types';
import { useAuth } from '../../store/AuthContext';

export const NotificationSettings: React.FC = () => {
  const { user } = useAuth();
  const isStaff = user?.role === 'staff';

  const [settings, setSettings] = useState<NotificationSetting[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<UiError | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  const fetchSettings = async () => {
    setIsLoading(true);
    try {
      const data = await adminService.getNotificationSettings();
      setSettings(data);
      setError(null);
    } catch (err: any) {
      setError(err.uiError || { code: 'FETCH_FAILED', message: 'Could not load notification settings.' });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchSettings();
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isStaff) return;

    setIsSaving(true);
    setError(null);
    setSaveMessage(null);

    try {
      const saved = await adminService.updateNotificationSettings(settings);
      setSettings(saved);
      setSaveMessage('Notification settings saved.');
      setTimeout(() => setSaveMessage(null), 4000);
    } catch (err: any) {
      setError(err.uiError || { code: 'SAVE_FAILED', message: 'We couldn\'t save these settings. Your changes are still here.' });
    } finally {
      setIsSaving(false);
    }
  };

  const handleChange = (id: number, field: keyof NotificationSetting, value: any) => {
    setSettings(prev => prev.map(s => s.id === id ? { ...s, [field]: value } : s));
  };

  if (isLoading) {
    return <div className="p-8 text-center text-slate-500">Loading settings...</div>;
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Notifications</h1>
          <p className="text-sm text-slate-600 mt-1">Configure automated messages sent to clients and staff.</p>
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

      <form onSubmit={handleSave} className="space-y-6">
        {settings.length === 0 ? (
          <div className="bg-white p-8 rounded-xl shadow-sm border border-slate-200 text-center text-slate-500">
            No notification channels are configured yet.
          </div>
        ) : (
          settings.map(setting => (
            <div key={setting.id} className="bg-white shadow-sm rounded-xl border border-slate-200 overflow-hidden">
              <div className="p-4 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
                <div>
                  <h3 className="font-bold text-slate-800 capitalize">{setting.event_type.replace('_', ' ')}</h3>
                  <p className="text-xs text-slate-500 mt-0.5 uppercase tracking-wider">
                    To: {setting.recipient_type} • Via: {setting.channel}
                  </p>
                </div>
                <div className="flex items-center">
                  <input
                    id={`enable-${setting.id}`}
                    type="checkbox"
                    disabled={isStaff || isSaving}
                    checked={setting.enabled}
                    onChange={(e) => handleChange(setting.id, 'enabled', e.target.checked)}
                    className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-slate-300 rounded disabled:opacity-50"
                  />
                  <label htmlFor={`enable-${setting.id}`} className="ml-2 text-sm font-medium text-slate-700">
                    Enabled
                  </label>
                </div>
              </div>
              
              <div className={`p-6 space-y-4 ${!setting.enabled ? 'opacity-50 pointer-events-none' : ''}`}>
                {setting.remind_before_minutes !== undefined && (
                  <div>
                    <label className="block text-sm font-medium text-slate-700">Send Reminder Before (Minutes)</label>
                    <input
                      type="number"
                      min="1"
                      max="10080"
                      disabled={isStaff || isSaving}
                      value={setting.remind_before_minutes}
                      onChange={(e) => handleChange(setting.id, 'remind_before_minutes', parseInt(e.target.value, 10))}
                      className="mt-1 block w-full sm:w-64 rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border disabled:bg-slate-50 disabled:text-slate-500"
                    />
                  </div>
                )}
                
                <div>
                  <label className="block text-sm font-medium text-slate-700 flex justify-between">
                    Message Template
                    <span className="text-xs text-slate-400 font-normal">Supports variables like {'{{start_time}}'}</span>
                  </label>
                  <textarea
                    rows={4}
                    disabled={isStaff || isSaving}
                    value={setting.template_body}
                    onChange={(e) => handleChange(setting.id, 'template_body', e.target.value)}
                    className="mt-1 block w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border font-mono text-sm disabled:bg-slate-50 disabled:text-slate-500"
                  />
                </div>
              </div>
            </div>
          ))
        )}

        {!isStaff && settings.length > 0 && (
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={isSaving || isLoading}
              className="inline-flex justify-center py-2 px-6 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
            >
              {isSaving ? 'Saving...' : 'Save notification settings'}
            </button>
          </div>
        )}
      </form>
    </div>
  );
};
