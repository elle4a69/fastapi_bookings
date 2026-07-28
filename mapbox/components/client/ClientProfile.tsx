import React, { useState, useEffect } from 'react';
import { apiFetch } from '../../services/apiClient';

interface ClientProfileData {
  id?: number;
  name: string;
  email: string;
  phone?: string;
  address_line1?: string;
  address_line2?: string;
  city?: string;
  state?: string;
  postcode?: string;
  country?: string;
  timezone?: string;
  accepts_marketing?: boolean;
}

export const ClientProfile: React.FC = () => {
  const [profile, setProfile] = useState<ClientProfileData>({
    name: '',
    email: '',
    phone: '',
    address_line1: '',
    city: '',
    state: '',
    postcode: '',
    country: '',
    accepts_marketing: false,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchProfile();
  }, []);

  const fetchProfile = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch<ClientProfileData>('/api/public/clients/me', { method: 'GET' });
      if (res) setProfile(res);
    } catch (err: any) {
      setError(err.uiError?.message || 'Failed to load client profile.');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setMessage(null);
    setError(null);

    try {
      const res = await apiFetch<ClientProfileData>('/api/public/clients/me', {
        method: 'PUT',
        body: JSON.stringify(profile),
      });
      if (res) setProfile(res);
      setMessage('Profile updated successfully.');
    } catch (err: any) {
      setError(err.uiError?.message || 'Failed to update profile.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center p-12 text-slate-500">
        Loading profile details...
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto bg-white p-8 rounded-xl shadow-sm border border-slate-200">
      <h1 className="text-2xl font-bold text-slate-900 mb-2">My Profile</h1>
      <p className="text-slate-600 text-sm mb-6">Manage your contact information, address, and marketing preferences.</p>

      {message && (
        <div className="mb-4 bg-emerald-50 border-l-4 border-emerald-500 p-3 text-emerald-800 text-sm rounded-r">
          {message}
        </div>
      )}

      {error && (
        <div className="mb-4 bg-red-50 border-l-4 border-red-500 p-3 text-red-700 text-sm rounded-r">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Full Name</label>
            <input
              type="text"
              required
              value={profile.name || ''}
              onChange={(e) => setProfile({ ...profile, name: e.target.value })}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Email Address</label>
            <input
              type="email"
              disabled
              value={profile.email || ''}
              className="w-full px-3 py-2 border border-slate-200 bg-slate-50 rounded-lg text-slate-500 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Phone Number</label>
            <input
              type="tel"
              value={profile.phone || ''}
              onChange={(e) => setProfile({ ...profile, phone: e.target.value })}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Timezone</label>
            <input
              type="text"
              value={profile.timezone || ''}
              onChange={(e) => setProfile({ ...profile, timezone: e.target.value })}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none text-sm"
              placeholder="e.g. UTC, Australia/Sydney"
            />
          </div>
        </div>

        <hr className="border-slate-100" />

        <div className="space-y-4">
          <h3 className="text-base font-semibold text-slate-800">Address Information</h3>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Street Address</label>
            <input
              type="text"
              value={profile.address_line1 || ''}
              onChange={(e) => setProfile({ ...profile, address_line1: e.target.value })}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none text-sm"
            />
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="col-span-2">
              <label className="block text-sm font-medium text-slate-700 mb-1">City</label>
              <input
                type="text"
                value={profile.city || ''}
                onChange={(e) => setProfile({ ...profile, city: e.target.value })}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">State</label>
              <input
                type="text"
                value={profile.state || ''}
                onChange={(e) => setProfile({ ...profile, state: e.target.value })}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Postcode</label>
              <input
                type="text"
                value={profile.postcode || ''}
                onChange={(e) => setProfile({ ...profile, postcode: e.target.value })}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none text-sm"
              />
            </div>
          </div>
        </div>

        <hr className="border-slate-100" />

        <div className="flex items-center space-x-3">
          <input
            type="checkbox"
            id="marketing"
            checked={profile.accepts_marketing || false}
            onChange={(e) => setProfile({ ...profile, accepts_marketing: e.target.checked })}
            className="h-4 w-4 text-blue-600 rounded border-slate-300 focus:ring-blue-500"
          />
          <label htmlFor="marketing" className="text-sm font-medium text-slate-700">
            Subscribe to promotional updates and news
          </label>
        </div>

        <div className="pt-2">
          <button
            type="submit"
            disabled={saving}
            className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg shadow transition-colors disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save Profile'}
          </button>
        </div>
      </form>
    </div>
  );
};
