import React from 'react';
import { Outlet, Link, useNavigate } from 'react-router-dom';

export const ClientLayout: React.FC = () => {
  const navigate = useNavigate();
  const clientToken = localStorage.getItem('client_token');

  const handleLogout = () => {
    localStorage.removeItem('client_token');
    navigate('/client/login');
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      <header className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between shadow-sm">
        <div className="flex items-center space-x-4">
          <Link to="/client/profile" className="text-xl font-bold text-slate-800 tracking-tight flex items-center gap-2">
            <span className="w-8 h-8 rounded-lg bg-blue-600 text-white flex items-center justify-center text-sm font-semibold">C</span>
            Client Self-Service Portal
          </Link>
        </div>
        <nav className="flex items-center space-x-6">
          <Link to="/client/profile" className="text-sm font-medium text-slate-600 hover:text-blue-600 transition-colors">Profile</Link>
          <Link to="/client/terms" className="text-sm font-medium text-slate-600 hover:text-blue-600 transition-colors">Terms & Consent</Link>
          {clientToken ? (
            <button
              onClick={handleLogout}
              className="text-sm font-medium text-red-600 hover:text-red-700 bg-red-50 hover:bg-red-100 px-3 py-1.5 rounded-md transition-colors"
            >
              Sign Out
            </button>
          ) : (
            <Link to="/client/login" className="text-sm font-medium text-blue-600 hover:text-blue-700 bg-blue-50 px-3 py-1.5 rounded-md transition-colors">
              Sign In
            </Link>
          )}
        </nav>
      </header>

      <main className="flex-1 max-w-4xl w-full mx-auto p-6">
        <Outlet />
      </main>

      <footer className="bg-white border-t border-slate-200 py-4 px-6 text-center text-xs text-slate-500">
        FastAPI Bookings Client Portal v2 &bull; Secure Multi-tenant Identity
      </footer>
    </div>
  );
};
