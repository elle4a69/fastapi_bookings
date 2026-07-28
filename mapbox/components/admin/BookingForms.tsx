import React, { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { apiFetch } from '../../services/apiClient';

interface BookingForm {
  id: number;
  name: string;
  slug: string;
  description?: string;
  active: boolean;
  widget_type: string;
  created_at: string;
}

export const BookingFormList: React.FC = () => {
  const [forms, setForms] = useState<BookingForm[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchForms();
  }, []);

  const fetchForms = async () => {
    setLoading(true);
    try {
      const res = await apiFetch<BookingForm[]>('/api/admin/booking-forms', { method: 'GET' });
      if (res) setForms(res);
    } catch (err: any) {
      setError(err.uiError?.message || 'Failed to load booking forms');
    } fontFinally: {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Configurable Booking Forms</h1>
          <p className="text-sm text-slate-500">Design, customize, and deploy multi-step intake widgets.</p>
        </div>
        <Link
          to="/admin/booking-forms/new"
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg text-sm transition-colors shadow-sm"
        >
          + Create New Form
        </Link>
      </div>

      {error && <div className="p-4 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>}

      {loading ? (
        <div className="p-8 text-center text-slate-500">Loading booking forms...</div>
      ) : forms.length === 0 ? (
        <div className="p-8 bg-white rounded-xl border border-slate-200 text-center text-slate-500">
          No custom booking forms configured yet.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {forms.map((form) => (
            <div key={form.id} className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
              <div className="flex justify-between items-start mb-2">
                <h3 className="text-lg font-semibold text-slate-900">{form.name}</h3>
                <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${form.active ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-600'}`}>
                  {form.active ? 'Active' : 'Draft'}
                </span>
              </div>
              <p className="text-sm text-slate-500 mb-4">{form.description || 'Standard intake form'}</p>
              <div className="text-xs text-slate-400 mb-4">Slug: <code className="bg-slate-100 px-1 py-0.5 rounded text-slate-700">/book/{form.slug}</code></div>
              <div className="flex gap-2 border-t pt-3">
                <Link to={`/admin/booking-forms/${form.id}`} className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded text-xs font-medium">
                  Edit & Design
                </Link>
                <Link to={`/book/${form.slug}`} target="_blank" className="px-3 py-1.5 bg-blue-50 hover:bg-blue-100 text-blue-700 rounded text-xs font-medium">
                  Preview Widget
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export const BookingFormEditor: React.FC = () => {
  const { formId } = useParams();
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [slug, setSlug] = useState('');
  const [description, setDescription] = useState('');
  const [active, setActive] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (formId && formId !== 'new') {
      fetchForm();
    }
  }, [formId]);

  const fetchForm = async () => {
    try {
      const form = await apiFetch<BookingForm>(`/api/admin/booking-forms/${formId}`, { method: 'GET' });
      if (form) {
        setName(form.name);
        setSlug(form.slug);
        setDescription(form.description || '');
        setActive(form.active);
      }
    } catch (err: any) {
      setError(err.uiError?.message || 'Failed to load form');
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);

    const payload = {
      name,
      slug,
      description,
      active,
      widget_type: 'wizard',
      module_order: ['service', 'provider', 'time', 'details', 'checkout'],
      enabled_modules: { service: true, provider: true, time: true, details: true, checkout: true },
      predefined_values: {},
      provider_selection_mode: 'optional',
      clear_session_on_start: true,
      allow_switch_to_ada: false,
      appearance: {},
      settings: {}
    };

    try {
      if (formId && formId !== 'new') {
        await apiFetch(`/api/admin/booking-forms/${formId}`, { method: 'PUT', body: JSON.stringify(payload) });
      } else {
        await apiFetch('/api/admin/booking-forms', { method: 'POST', body: JSON.stringify(payload) });
      }
      navigate('/admin/booking-forms');
    } catch (err: any) {
      setError(err.uiError?.message || 'Failed to save form');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto bg-white p-8 rounded-xl shadow-sm border border-slate-200 space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">{formId === 'new' || !formId ? 'Create Booking Form' : 'Edit Booking Form'}</h1>

      {error && <div className="p-3 bg-red-50 text-red-700 rounded text-sm">{error}</div>}

      <form onSubmit={handleSave} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Form Title</label>
          <input
            type="text"
            required
            value={name}
            onChange={(e) => {
              setName(e.target.value);
              if (formId === 'new' || !formId) setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, '-'));
            }}
            className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
            placeholder="Main Intake Form"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">URL Slug</label>
          <input
            type="text"
            required
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
            placeholder="main-intake-form"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Description</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
            rows={3}
          />
        </div>
        <div className="flex items-center space-x-2">
          <input
            type="checkbox"
            id="active"
            checked={active}
            onChange={(e) => setActive(e.target.checked)}
            className="h-4 w-4 text-blue-600 rounded"
          />
          <label htmlFor="active" className="text-sm font-medium text-slate-700">Form Active</label>
        </div>

        <div className="pt-4 flex justify-end space-x-3">
          <button
            type="button"
            onClick={() => navigate('/admin/booking-forms')}
            className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm font-medium rounded-lg"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving}
            className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg shadow"
          >
            {saving ? 'Saving...' : 'Save Form'}
          </button>
        </div>
      </form>
    </div>
  );
};
