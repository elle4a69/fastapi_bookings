import React, { useEffect, useState } from 'react';
import { adminService } from '../../services/adminService';
import { ClientDetail, UiError } from '../../types';
import { useAuth } from '../../store/AuthContext';

export const ClientManager: React.FC = () => {
  const { user } = useAuth();
  const isStaff = user?.role === 'staff';

  const [clients, setClients] = useState<ClientDetail[]>([]);
  const [selectedClient, setSelectedClient] = useState<ClientDetail | null>(null);
  
  const [isLoading, setIsLoading] = useState(true);
  const [isMutating, setIsMutating] = useState(false);
  const [error, setError] = useState<UiError | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  const fetchClients = async () => {
    setIsLoading(true);
    try {
      const data = await adminService.getClients();
      setClients(data);
      setError(null);
    } catch (err: any) {
      setError(err.uiError || { code: 'FETCH_FAILED', message: 'Could not load clients.' });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchClients();
  }, []);

  const handleSelect = (client: ClientDetail) => {
    setSelectedClient(client);
    setSaveMessage(null);
    setError(null);
  };

  const toggleRestriction = async () => {
    if (!selectedClient || isStaff) return;
    
    setIsMutating(true);
    setError(null);
    setSaveMessage(null);

    const newStatus = !selectedClient.management_approval_required;
    const reason = newStatus ? "Manually restricted by management." : "Restriction cleared by management.";

    try {
      const updated = await adminService.updateClientApproval(selectedClient.id, newStatus, reason);
      setClients(prev => prev.map(c => c.id === updated.id ? updated : c));
      setSelectedClient(updated);
      setSaveMessage('Client updated.');
      setTimeout(() => setSaveMessage(null), 4000);
    } catch (err: any) {
      setError(err.uiError || { code: 'UPDATE_FAILED', message: 'We couldn\'t update this client. Please try again.' });
    } finally {
      setIsMutating(false);
    }
  };

  return (
    <div className="h-[calc(100vh-12rem)] flex flex-col md:flex-row gap-6">
      
      {/* Left Pane: List */}
      <div className={`md:w-1/3 flex flex-col bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden ${selectedClient ? 'hidden md:flex' : 'flex'}`}>
        <div className="p-4 border-b border-slate-200 flex justify-between items-center bg-slate-50">
          <h2 className="font-bold text-slate-800">Clients</h2>
          <button onClick={fetchClients} className="text-sm text-indigo-600 hover:text-indigo-800 font-medium">
            Refresh
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {isLoading && clients.length === 0 ? (
            <div className="p-4 text-center text-slate-500 text-sm">Loading...</div>
          ) : clients.length === 0 ? (
            <div className="p-4 text-center text-slate-500 text-sm">No clients yet. Client profiles are created when clients book.</div>
          ) : (
            clients.map(client => (
              <button
                key={client.id}
                onClick={() => handleSelect(client)}
                className={`w-full text-left px-4 py-3 rounded-lg text-sm transition-colors ${selectedClient?.id === client.id ? 'bg-indigo-50 text-indigo-900 font-medium' : 'hover:bg-slate-50 text-slate-700'}`}
              >
                <div className="flex justify-between items-center">
                  <span className="font-medium">{client.first_name} {client.last_name}</span>
                  {client.management_approval_required && (
                    <span className="text-xs bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded font-semibold">Restricted</span>
                  )}
                </div>
                <p className="text-xs text-slate-500 mt-1 truncate">{client.email}</p>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Right Pane: Detail */}
      <div className={`md:w-2/3 flex flex-col bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden ${!selectedClient ? 'hidden md:flex items-center justify-center' : 'flex'}`}>
        
        {!selectedClient ? (
          <div className="text-slate-500 text-center p-8">
            <svg className="mx-auto h-12 w-12 text-slate-300 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
            <p>Select a client to view details.</p>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto">
            <div className="p-4 border-b border-slate-200 bg-slate-50 flex items-center sticky top-0 z-10">
              <button onClick={() => setSelectedClient(null)} className="md:hidden mr-3 text-slate-500 hover:text-slate-700">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
              </button>
              <h2 className="font-bold text-slate-800">Client Profile</h2>
            </div>

            <div className="p-6 space-y-8">
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

              {/* Identity Section */}
              <section>
                <h3 className="text-lg font-medium text-slate-900 mb-4">Identity & Contact</h3>
                <div className="bg-slate-50 p-4 rounded-lg border border-slate-200 grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-slate-500">Name</p>
                    <p className="font-medium text-slate-900">{selectedClient.first_name} {selectedClient.last_name}</p>
                  </div>
                  <div>
                    <p className="text-sm text-slate-500">Email</p>
                    <p className="font-medium text-slate-900">{selectedClient.email}</p>
                  </div>
                  <div>
                    <p className="text-sm text-slate-500">Phone</p>
                    <p className="font-medium text-slate-900">{selectedClient.phone || 'Not provided'}</p>
                  </div>
                </div>
              </section>

              {/* Restriction Section */}
              <section>
                <h3 className="text-lg font-medium text-slate-900 mb-4">Management Restriction</h3>
                <div className={`p-4 rounded-lg border ${selectedClient.management_approval_required ? 'bg-amber-50 border-amber-200' : 'bg-white border-slate-200'}`}>
                  <div className="flex items-start justify-between">
                    <div>
                      <p className={`font-medium ${selectedClient.management_approval_required ? 'text-amber-900' : 'text-slate-900'}`}>
                        {selectedClient.management_approval_required ? 'Approval Required' : 'Normal Booking Access'}
                      </p>
                      <p className={`text-sm mt-1 ${selectedClient.management_approval_required ? 'text-amber-700' : 'text-slate-500'}`}>
                        {selectedClient.management_approval_required 
                          ? 'This client cannot book online without management review. They can submit non-reserving requests.' 
                          : 'This client can book online according to normal business rules.'}
                      </p>
                    </div>
                    {!isStaff && (
                      <button
                        onClick={toggleRestriction}
                        disabled={isMutating}
                        className={`ml-4 px-4 py-2 text-sm font-medium rounded-md shadow-sm border transition-colors disabled:opacity-50 whitespace-nowrap
                          ${selectedClient.management_approval_required 
                            ? 'bg-white border-slate-300 text-slate-700 hover:bg-slate-50' 
                            : 'bg-amber-100 border-amber-200 text-amber-800 hover:bg-amber-200'}`}
                      >
                        {isMutating ? 'Updating...' : selectedClient.management_approval_required ? 'Clear Restriction' : 'Restrict Client'}
                      </button>
                    )}
                  </div>
                  {isStaff && (
                    <p className="text-xs text-slate-500 mt-4 italic">
                      Only Management or the Business Owner can change this restriction.
                    </p>
                  )}
                </div>
              </section>

            </div>
          </div>
        )}
      </div>
    </div>
  );
};
