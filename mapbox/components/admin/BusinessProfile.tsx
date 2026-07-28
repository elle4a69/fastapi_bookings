import React, { useEffect, useState } from 'react';
import { adminService } from '../../services/adminService';
import { BusinessProfile as BusinessProfileType, UiError } from '../../types';
import { useAuth } from '../../store/AuthContext';

export const BusinessProfile: React.FC = () => {
  const { user } = useAuth();
  const isStaff = user?.role === 'staff';

  const [profile, setProfile] = useState<BusinessProfileType | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<UiError | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  const fetchProfile = async () => {
    setIsLoading(true);
    try {
      const data = await adminService.getBusinessProfile();
      setProfile(data);
      setError(null);
    } catch (err: any) {
      setError(err.uiError || { code: 'FETCH_FAILED', message: 'Could not load business profile.' });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchProfile();
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isStaff || !profile) return;

    setIsSaving(true);
    setError(null);
    setSaveMessage(null);

    try {
      const saved = await adminService.updateBusinessProfile(profile);
      setProfile(saved);
      setSaveMessage('Business details saved.');
      setTimeout(() => setSaveMessage(null), 4000);
    } catch (err: any) {
      setError(err.uiError || { code: 'SAVE_FAILED', message: 'We couldn\'t save the business details. Your changes are still on this page.' });
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return <div className="p-8 text-center text-slate-500">Loading profile...</div>;
  }

  if (!profile) return null;

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Business Profile</h1>
          <p className="text-sm text-slate-600 mt-1">Manage your public identity and contact details.</p>
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
        <form onSubmit={handleSave} className="p-6 space-y-8">
          
          <section>
            <h3 className="text-lg font-medium text-slate-900 mb-4">Basic Information</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div className="sm:col-span-2">
                <label className="block text-sm font-medium text-slate-700">Business Name</label>
                <input
                  type="text"
                  required
                  disabled={isStaff || isSaving}
                  value={profile.name}
                  onChange={(e) => setProfile({ ...profile, name: e.target.value })}
                  className="mt-1 block w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border disabled:bg-slate-50 disabled:text-slate-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700">Email Address</label>
                <input
                  type="email"
                  required
                  disabled={isStaff || isSaving}
                  value={profile.email}
                  onChange={(e) => setProfile({ ...profile, email: e.target.value })}
                  className="mt-1 block w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border disabled:bg-slate-50 disabled:text-slate-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700">Phone Number</label>
                <input
                  type="tel"
                  disabled={isStaff || isSaving}
                  value={profile.phone || ''}
                  onChange={(e) => setProfile({ ...profile, phone: e.target.value })}
                  className="mt-1 block w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border disabled:bg-slate-50 disabled:text-slate-500"
                />
              </div>
              <div className="sm:col-span-2">
                <label className="block text-sm font-medium text-slate-700">Website URL</label>
                <input
                  type="url"
                  disabled={isStaff || isSaving}
                  value={profile.website_url || ''}
                  onChange={(e) => setProfile({ ...profile, website_url: e.target.value })}
                  placeholder="https://"
                  className="mt-1 block w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border disabled:bg-slate-50 disabled:text-slate-500"
                />
              </div>
            </div>
          </section>

          <section className="pt-6 border-t border-slate-200">
            <h3 className="text-lg font-medium text-slate-900 mb-4">Localization</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-slate-700">Timezone (IANA)</label>
                <input
                  type="text"
                  required
                  disabled={isStaff || isSaving}
                  value={profile.timezone}
                  onChange={(e) => setProfile({ ...profile, timezone: e.target.value })}
                  className="mt-1 block w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border disabled:bg-slate-50 disabled:text-slate-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700">Country Code (ISO)</label>
                <input
                  type="text"
                  required
                  maxLength={2}
                  disabled={isStaff || isSaving}
                  value={profile.country_code}
                  onChange={(e) => setProfile({ ...profile, country_code: e.target.value.toUpperCase() })}
                  className="mt-1 block w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border disabled:bg-slate-50 disabled:text-slate-500"
                />
              </div>
            </div>
          </section>

          <section className="pt-6 border-t border-slate-200">
            <h3 className="text-lg font-medium text-slate-900 mb-4">Public Visibility</h3>
            <div className="space-y-4">
              <div className="flex items-center">
                <input
                  id="show_email"
                  type="checkbox"
                  disabled={isStaff || isSaving}
                  checked={profile.show_email_publicly}
                  onChange={(e) => setProfile({ ...profile, show_email_publicly: e.target.checked })}
                  className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-slate-300 rounded disabled:opacity-50"
                />
                <label htmlFor="show_email" className="ml-2 block text-sm text-slate-900">
                  Show email address publicly on booking pages
                </label>
              </div>
              <div className="flex items-center">
                <input
                  id="show_address"
                  type="checkbox"
                  disabled={isStaff || isSaving}
                  checked={profile.show_address_publicly}
                  onChange={(e) => setProfile({ ...profile, show_address_publicly: e.target.checked })}
                  className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-slate-300 rounded disabled:opacity-50"
                />
                <label htmlFor="show_address" className="ml-2 block text-sm text-slate-900">
                  Show physical address publicly on booking pages
                </label>
              </div>
            </div>
          </section>

          {!isStaff && (
            <div className="pt-6 border-t border-slate-200 flex justify-end">
              <button
                type="submit"
                disabled={isSaving}
                className="inline-flex justify-center py-2 px-6 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
              >
                {isSaving ? 'Saving...' : 'Save Business Details'}
              </button>
            </div>
          )}
        </form>
      </div>
    </div>
  );
};
