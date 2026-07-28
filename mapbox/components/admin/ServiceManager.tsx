import React, { useEffect, useState } from 'react';
import { adminService } from '../../services/adminService';
import { ServiceDetail, ProviderDetail, UiError } from '../../types';
import { useAuth } from '../../store/AuthContext';

export const ServiceManager: React.FC = () => {
  const { user } = useAuth();
  const isStaff = user?.role === 'staff';

  const [services, setServices] = useState<ServiceDetail[]>([]);
  const [providers, setProviders] = useState<ProviderDetail[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<UiError | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  // Form State
  const [formData, setFormData] = useState<Partial<ServiceDetail>>({});

  const fetchData = async () => {
    setIsLoading(true);
    try {
      const [svcData, provData] = await Promise.all([
        adminService.getServices(),
        adminService.getProviders()
      ]);
      setServices(svcData);
      setProviders(provData);
      setError(null);
    } catch (err: any) {
      setError(err.uiError || { code: 'FETCH_FAILED', message: 'Could not load services.' });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleSelect = (service: ServiceDetail) => {
    setSelectedId(service.id);
    setFormData(service);
    setIsEditing(false);
    setSaveMessage(null);
    setError(null);
  };

  const handleCreateNew = () => {
    setSelectedId(null);
    setFormData({
      name: '',
      description: '',
      duration_minutes: 60,
      price_minor: 0,
      deposit_amount_minor: 0,
      active: true,
      provider_ids: []
    });
    setIsEditing(true);
    setSaveMessage(null);
    setError(null);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isStaff) return;
    
    setIsLoading(true);
    setError(null);
    setSaveMessage(null);

    try {
      let saved: ServiceDetail;
      if (selectedId) {
        saved = await adminService.updateService(selectedId, formData);
        setServices(prev => prev.map(s => s.id === saved.id ? saved : s));
      } else {
        saved = await adminService.createService(formData);
        setServices(prev => [...prev, saved]);
        setSelectedId(saved.id);
      }
      setFormData(saved);
      setIsEditing(false);
      setSaveMessage('Service saved.');
      
      // Clear success message after 4 seconds per MCD
      setTimeout(() => setSaveMessage(null), 4000);
    } catch (err: any) {
      setError(err.uiError || { code: 'SAVE_FAILED', message: 'We couldn\'t save this service. Your changes are still here.' });
    } finally {
      setIsLoading(false);
    }
  };

  const toggleProvider = (providerId: number) => {
    if (isStaff) return;
    setFormData(prev => {
      const current = prev.provider_ids || [];
      const updated = current.includes(providerId) 
        ? current.filter(id => id !== providerId)
        : [...current, providerId];
      return { ...prev, provider_ids: updated };
    });
  };

  const formatPriceInput = (minor: number | undefined) => minor ? (minor / 100).toString() : '0';
  const parsePriceInput = (val: string) => Math.round(parseFloat(val || '0') * 100);

  return (
    <div className="h-[calc(100vh-12rem)] flex flex-col md:flex-row gap-6">
      
      {/* Left Pane: List */}
      <div className={`md:w-1/3 flex flex-col bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden ${selectedId || isEditing ? 'hidden md:flex' : 'flex'}`}>
        <div className="p-4 border-b border-slate-200 flex justify-between items-center bg-slate-50">
          <h2 className="font-bold text-slate-800">Services</h2>
          {!isStaff && (
            <button onClick={handleCreateNew} className="text-sm bg-indigo-600 text-white px-3 py-1.5 rounded hover:bg-indigo-700 transition-colors">
              + New
            </button>
          )}
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {isLoading && services.length === 0 ? (
            <div className="p-4 text-center text-slate-500 text-sm">Loading...</div>
          ) : services.length === 0 ? (
            <div className="p-4 text-center text-slate-500 text-sm">No services yet. Add the first service clients can book.</div>
          ) : (
            services.map(service => (
              <button
                key={service.id}
                onClick={() => handleSelect(service)}
                className={`w-full text-left px-4 py-3 rounded-lg text-sm transition-colors ${selectedId === service.id ? 'bg-indigo-50 text-indigo-900 font-medium' : 'hover:bg-slate-50 text-slate-700'}`}
              >
                <div className="flex justify-between items-center">
                  <span>{service.name}</span>
                  {!service.active && <span className="text-xs bg-slate-200 text-slate-600 px-1.5 py-0.5 rounded">Inactive</span>}
                </div>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Right Pane: Detail/Form */}
      <div className={`md:w-2/3 flex flex-col bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden ${!selectedId && !isEditing ? 'hidden md:flex items-center justify-center' : 'flex'}`}>
        
        {!selectedId && !isEditing ? (
          <div className="text-slate-500 text-center p-8">
            <svg className="mx-auto h-12 w-12 text-slate-300 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            <p>Select a service to view details or create a new one.</p>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto">
            <div className="p-4 border-b border-slate-200 bg-slate-50 flex items-center justify-between sticky top-0 z-10">
              <div className="flex items-center">
                <button onClick={() => { setSelectedId(null); setIsEditing(false); }} className="md:hidden mr-3 text-slate-500 hover:text-slate-700">
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
                </button>
                <h2 className="font-bold text-slate-800">{selectedId ? 'Edit Service' : 'New Service'}</h2>
              </div>
              {!isEditing && !isStaff && (
                <button onClick={() => setIsEditing(true)} className="text-sm text-indigo-600 hover:text-indigo-800 font-medium">
                  Edit
                </button>
              )}
            </div>

            <div className="p-6">
              {error && (
                <div className="mb-6 bg-red-50 border-l-4 border-red-500 p-4 rounded-md">
                  <p className="text-sm text-red-700">{error.message}</p>
                </div>
              )}
              {saveMessage && (
                <div className="mb-6 bg-green-50 border-l-4 border-green-500 p-4 rounded-md">
                  <p className="text-sm text-green-700">{saveMessage}</p>
                </div>
              )}

              <form onSubmit={handleSave} className="space-y-6">
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700">Service Name</label>
                    <input
                      type="text"
                      required
                      disabled={!isEditing || isLoading}
                      value={formData.name || ''}
                      onChange={e => setFormData({...formData, name: e.target.value})}
                      className="mt-1 block w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border disabled:bg-slate-50 disabled:text-slate-500"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-slate-700">Description</label>
                    <textarea
                      rows={3}
                      disabled={!isEditing || isLoading}
                      value={formData.description || ''}
                      onChange={e => setFormData({...formData, description: e.target.value})}
                      className="mt-1 block w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border disabled:bg-slate-50 disabled:text-slate-500"
                    />
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-slate-700">Duration (mins)</label>
                      <input
                        type="number"
                        min="1"
                        required
                        disabled={!isEditing || isLoading}
                        value={formData.duration_minutes || ''}
                        onChange={e => setFormData({...formData, duration_minutes: parseInt(e.target.value, 10)})}
                        className="mt-1 block w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border disabled:bg-slate-50 disabled:text-slate-500"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-700">Price ($)</label>
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        required
                        disabled={!isEditing || isLoading}
                        value={formatPriceInput(formData.price_minor)}
                        onChange={e => setFormData({...formData, price_minor: parsePriceInput(e.target.value)})}
                        className="mt-1 block w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border disabled:bg-slate-50 disabled:text-slate-500"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-700">Deposit ($)</label>
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        required
                        disabled={!isEditing || isLoading}
                        value={formatPriceInput(formData.deposit_amount_minor)}
                        onChange={e => setFormData({...formData, deposit_amount_minor: parsePriceInput(e.target.value)})}
                        className="mt-1 block w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border disabled:bg-slate-50 disabled:text-slate-500"
                      />
                    </div>
                  </div>

                  <div className="flex items-center mt-4">
                    <input
                      id="active"
                      type="checkbox"
                      disabled={!isEditing || isLoading}
                      checked={formData.active || false}
                      onChange={e => setFormData({...formData, active: e.target.checked})}
                      className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-slate-300 rounded disabled:opacity-50"
                    />
                    <label htmlFor="active" className="ml-2 block text-sm text-slate-900">
                      Active (visible to public)
                    </label>
                  </div>
                </div>

                {/* Canonical Relationships Accordion */}
                <div className="pt-6 border-t border-slate-200">
                  <h3 className="text-lg font-medium text-slate-900 mb-4">Assigned Providers</h3>
                  {providers.length === 0 ? (
                    <p className="text-sm text-slate-500">No providers available.</p>
                  ) : (
                    <div className="space-y-2">
                      {providers.map(provider => {
                        const isAttached = formData.provider_ids?.includes(provider.id);
                        return (
                          <label key={provider.id} className={`flex items-center p-3 border rounded-lg ${isEditing ? 'cursor-pointer hover:bg-slate-50' : 'opacity-70'} ${isAttached ? 'border-indigo-200 bg-indigo-50/30' : 'border-slate-200'}`}>
                            <input
                              type="checkbox"
                              disabled={!isEditing || isLoading}
                              checked={isAttached}
                              onChange={() => toggleProvider(provider.id)}
                              className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-slate-300 rounded disabled:opacity-50"
                            />
                            <span className="ml-3 text-sm font-medium text-slate-900">{provider.name}</span>
                          </label>
                        );
                      })}
                    </div>
                  )}
                </div>

                {isEditing && (
                  <div className="pt-6 flex justify-end space-x-3">
                    <button
                      type="button"
                      onClick={() => {
                        if (selectedId) {
                          handleSelect(services.find(s => s.id === selectedId)!);
                        } else {
                          setSelectedId(null);
                          setIsEditing(false);
                        }
                      }}
                      disabled={isLoading}
                      className="px-4 py-2 border border-slate-300 shadow-sm text-sm font-medium rounded-md text-slate-700 bg-white hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={isLoading}
                      className="px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 flex items-center"
                    >
                      {isLoading ? 'Saving...' : 'Save Service'}
                    </button>
                  </div>
                )}
              </form>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
