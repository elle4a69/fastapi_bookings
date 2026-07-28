import React, { useState, useEffect } from 'react';
import { apiFetch } from '../../services/apiClient';

interface GdprConsentItem {
  consent_type: string;
  is_approved: boolean;
}

export const ClientTerms: React.FC = () => {
  const [consents, setConsents] = useState<{ marketing: boolean; data_processing: boolean; third_party: boolean }>({
    marketing: false,
    data_processing: true,
    third_party: false,
  });
  const [termsText, setTermsText] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    fetchTerms();
  }, []);

  const fetchTerms = async () => {
    setLoading(true);
    try {
      const res = await apiFetch<{ terms: string }>('/api/public/clients/terms', { method: 'GET' });
      if (res?.terms) setTermsText(res.terms);
      else setTermsText('Standard Terms of Service and Privacy Policy for FastAPI Bookings Platform.');
    } catch {
      setTermsText('Standard Terms of Service and Privacy Policy for FastAPI Bookings Platform.');
    } finally {
      setLoading(false);
    }
  };

  const handleConsentToggle = async (type: 'marketing' | 'data_processing' | 'third_party', approved: boolean) => {
    setConsents((prev) => ({ ...prev, [type]: approved }));
    setSaving(true);
    setMessage(null);

    try {
      await apiFetch('/api/public/gdpr-consent', {
        method: 'POST',
        body: JSON.stringify({
          consent_type: type,
          is_approved: approved,
          ip_address: '127.0.0.1',
        }),
      });
      setMessage('Consent preferences updated.');
    } catch (err: any) {
      // Retain state
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="p-8 text-center text-slate-500">Loading terms and consent agreements...</div>;
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="bg-white p-8 rounded-xl shadow-sm border border-slate-200">
        <h1 className="text-2xl font-bold text-slate-900 mb-2">Terms & Privacy Policy</h1>
        <p className="text-slate-600 text-sm mb-6">Review legal terms and manage your GDPR data privacy consent.</p>

        {message && (
          <div className="mb-4 bg-emerald-50 border-l-4 border-emerald-500 p-3 text-emerald-800 text-sm rounded-r">
            {message}
          </div>
        )}

        <div className="bg-slate-50 border border-slate-200 p-4 rounded-lg text-sm text-slate-700 max-h-60 overflow-y-auto mb-6 leading-relaxed">
          {termsText}
        </div>

        <h2 className="text-lg font-semibold text-slate-900 mb-4">Privacy & Data Protection Preferences</h2>

        <div className="space-y-4">
          <div className="flex items-start justify-between p-4 border border-slate-200 rounded-lg hover:border-slate-300">
            <div>
              <h4 className="font-semibold text-slate-800 text-sm">Data Processing Consent</h4>
              <p className="text-xs text-slate-500 mt-0.5">Required to store appointment details and client communications.</p>
            </div>
            <input
              type="checkbox"
              disabled
              checked={consents.data_processing}
              className="h-5 w-5 text-blue-600 rounded border-slate-300"
            />
          </div>

          <div className="flex items-start justify-between p-4 border border-slate-200 rounded-lg hover:border-slate-300">
            <div>
              <h4 className="font-semibold text-slate-800 text-sm">Marketing & Promotional Outreach</h4>
              <p className="text-xs text-slate-500 mt-0.5">Allow receiving updates, discounts, and newsletters.</p>
            </div>
            <input
              type="checkbox"
              checked={consents.marketing}
              onChange={(e) => handleConsentToggle('marketing', e.target.checked)}
              className="h-5 w-5 text-blue-600 rounded border-slate-300 focus:ring-blue-500"
            />
          </div>

          <div className="flex items-start justify-between p-4 border border-slate-200 rounded-lg hover:border-slate-300">
            <div>
              <h4 className="font-semibold text-slate-800 text-sm">Third-Party Analytics</h4>
              <p className="text-xs text-slate-500 mt-0.5">Allow anonymized usage diagnostics to improve service performance.</p>
            </div>
            <input
              type="checkbox"
              checked={consents.third_party}
              onChange={(e) => handleConsentToggle('third_party', e.target.checked)}
              className="h-5 w-5 text-blue-600 rounded border-slate-300 focus:ring-blue-500"
            />
          </div>
        </div>
      </div>
    </div>
  );
};
