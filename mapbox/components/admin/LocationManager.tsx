import React, { useEffect, useState } from 'react';
import { adminService } from '../../services/adminService';
import { LocationDetail, ProviderDetail, ServiceDetail, CategoryDetail, UiError } from '../../types';
import { useAuth } from '../../store/AuthContext';
import { useTenant } from '../../store/TenantContext';

export const LocationManager: React.FC = () => {
  const { user } = useAuth();
  const { uiConfig } = useTenant();
  const isStaff = user?.role === 'staff';

  const [locations, setLocations] = useState<LocationDetail[]>([]);
  const [providers, setProviders] = useState<ProviderDetail[]>([]);
  const [services, setServices] = useState<ServiceDetail[]>([]);
  const [categories, setCategories] = useState<CategoryDetail[]>([]);
  
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<UiError | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  const [formData, setFormData] = useState<Partial<LocationDetail>>({});

  const fetchData = async () => {
    setIsLoading(true);
    try {
      const [locData, provData, svcData, catData] = await Promise.all([
        adminService.getLocations(),
        adminService.getProviders(),
        adminService.getServices(),
        uiConfig?.categories_enabled ? adminService.getCategories() : Promise.resolve([])
      ]);
      setLocations(locData);
      setProviders(provData);
      setServices(svcData);
      setCategories(catData);
      setError(null);
    } catch (err: any) {
      setError(err.uiError || { code: 'FETCH_FAILED', message: 'Could not load locations.' });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [uiConfig]);

  const handleSelect = (location: LocationDetail) => {
    setSelectedId(location.id);
    setFormData(location);
    setIsEditing(false);
    setSaveMessage(null);
    setError(null);
  };

  const handleCreateNew = () => {
    setSelectedId(null);
    setFormData({
      name: '',
      address: '',
      timezone: '',
      active: true,
      provider_ids: [],
      service_ids: [],
      category_ids: []
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
      let saved: LocationDetail;
      if (selectedId) {
        saved = await adminService.updateLocation(selectedId, formData);
        setLocations(prev => prev.map(l => l.id === saved.id ? saved : l));
      } else {
        saved = await adminService.createLocation(formData);
        setLocations(prev => [...prev, saved]);
        setSelectedId(saved.id);
      }
      setFormData(saved);
      setIsEditing(false);
      setSaveMessage('Location saved.');
      setTimeout(() => setSaveMessage(null), 4000);
    } catch (err: any) {
      setError(err.uiError || { code: 'SAVE_FAILED', message: 'We couldn\'t save this location. Your changes are still here.' });
    } finally {
      setIsLoading(false);
    }
  };

  const toggleRelationship = (type: 'provider_ids' | 'service_ids' | 'category_ids', id: number) => {
    if (isStaff) return;
    setFormData(prev => {
      const current = prev[type] || [];
      const updated = current.includes(id) 
        ? current.filter(itemId => itemId !== id)
        : [...current, id];
      return { ...prev, [type]: updated };
    });
  };

  return (
    <div className="h-[calc(100vh-12rem)] flex flex-col md:flex-row gap-6">
      
      {/* Left Pane: List */}
      <div className={`md:w-1/3 flex flex-col bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden ${selectedId || isEditing ? 'hidden md:flex' : 'flex'}`}>
        <div className="p-4 border-b border-slate-200 flex justify-between items-center bg-slate-50">
          <h2 className="font-bold text-slate-800">Locations</h2>
          {!isStaff && (
            <button onClick={handleCreateNew} className="text-sm bg-indigo-600 text-white px-3 py-1.5 rounded hover:bg-indigo-700 transition-colors">
              + New
            </button>
          )}
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {isLoading && locations.length === 0 ? (
            <div className="p-4 text-center text-slate-500 text-sm">Loading...</div>
          ) : locations.length === 0 ? (
            <div className="p-4 text-center text-slate-500 text-sm">No locations yet. Add a location for your business.</div>
          ) : (
            locations.map(location => (
              <button
                key={location.id}
                onClick={() => handleSelect(location)}
                className={`w-full text-left px-4 py-3 rounded-lg text-sm transition-colors ${selectedId === location.id ? 'bg-indigo-50 text-indigo-900 font-medium' : 'hover:bg-slate-50 text-slate-700'}`}
              >
                <div className="flex justify-between items-center">
                  <span>{location.name}</span>
                  {!location.active && <span className="text-xs bg-slate-200 text-slate-600 px-1.5 py-0.5 rounded">Inactive</span>}
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
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <p>Select a location to view details or create a new one.</p>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto">
            <div className="p-4 border-b border-slate-200 bg-slate-50 flex items-center justify-between sticky top-0 z-10">
              <div className="flex items-center">
                <button onClick={() => { setSelectedId(null); setIsEditing(false); }} className="md:hidden mr-3 text-slate-500 hover:text-slate-700">
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
                </button>
                <h2 className="font-bold text-slate-800">{selectedId ? 'Edit Location' : 'New Location'}</h2>
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
                    <label className="block text-sm font-medium text-slate-700">Location Name</label>
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
                    <label className="block text-sm font-medium text-slate-700">Address</label>
                    <textarea
                      rows={2}
                      disabled={!isEditing || isLoading}
                      value={formData.address || ''}
                      onChange={e => setFormData({...formData, address: e.target.value})}
                      className="mt-1 block w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border disabled:bg-slate-50 disabled:text-slate-500"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-700">Timezone (IANA)</label>
                    <input
                      type="text"
                      disabled={!isEditing || isLoading}
                      value={formData.timezone || ''}
                      onChange={e => setFormData({...formData, timezone: e.target.value})}
                      className="mt-1 block w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border disabled:bg-slate-50 disabled:text-slate-500"
                    />
                  </div>

                  <div className="flex items-center pt-2">
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

                {/* Canonical Relationships Accordions */}
                <div className="pt-6 border-t border-slate-200 space-y-6">
                  
                  <div>
                    <h3 className="text-lg font-medium text-slate-900 mb-3">Assigned Providers</h3>
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
                                onChange={() => toggleRelationship('provider_ids', provider.id)}
                                className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-slate-300 rounded disabled:opacity-50"
                              />
                              <span className="ml-3 text-sm font-medium text-slate-900">{provider.name}</span>
                            </label>
                          );
                        })}
                      </div>
                    )}
                  </div>

                  <div>
                    <h3 className="text-lg font-medium text-slate-900 mb-3">Assigned Services</h3>
                    {services.length === 0 ? (
                      <p className="text-sm text-slate-500">No services available.</p>
                    ) : (
                      <div className="space-y-2">
                        {services.map(service => {
                          const isAttached = formData.service_ids?.includes(service.id);
                          return (
                            <label key={service.id} className={`flex items-center p-3 border rounded-lg ${isEditing ? 'cursor-pointer hover:bg-slate-50' : 'opacity-70'} ${isAttached ? 'border-indigo-200 bg-indigo-50/30' : 'border-slate-200'}`}>
                              <input
                                type="checkbox"
                                disabled={!isEditing || isLoading}
                                checked={isAttached}
                                onChange={() => toggleRelationship('service_ids', service.id)}
                                className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-slate-300 rounded disabled:opacity-50"
                              />
                              <span className="ml-3 text-sm font-medium text-slate-900">{service.name}</span>
                            </label>
                          );
                        })}
                      </div>
                    )}
                  </div>

                  {uiConfig?.categories_enabled && (
                    <div>
                      <h3 className="text-lg font-medium text-slate-900 mb-3">Assigned Categories</h3>
                      {categories.length === 0 ? (
                        <p className="text-sm text-slate-500">No categories available.</p>
                      ) : (
                        <div className="space-y-2">
                          {categories.map(category => {
                            const isAttached = formData.category_ids?.includes(category.id);
                            return (
                              <label key={category.id} className={`flex items-center p-3 border rounded-lg ${isEditing ? 'cursor-pointer hover:bg-slate-50' : 'opacity-70'} ${isAttached ? 'border-indigo-200 bg-indigo-50/30' : 'border-slate-200'}`}>
                                <input
                                  type="checkbox"
                                  disabled={!isEditing || isLoading}
                                  checked={isAttached}
                                  onChange={() => toggleRelationship('category_ids', category.id)}
                                  className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-slate-300 rounded disabled:opacity-50"
                                />
                                <span className="ml-3 text-sm font-medium text-slate-900">{category.name}</span>
                              </label>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  )}

                </div>

                {isEditing && (
                  <div className="pt-6 flex justify-end space-x-3">
                    <button
                      type="button"
                      onClick={() => {
                        if (selectedId) {
                          handleSelect(locations.find(l => l.id === selectedId)!);
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
                      {isLoading ? 'Saving...' : 'Save Location'}
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
