import React from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import { useTenant } from '../store/TenantContext';
import { useAuth } from '../store/AuthContext';

export const PublicLayout: React.FC = () => {
  const { bootstrap, isLoading, error, retryBootstrap } = useTenant();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="animate-pulse flex flex-col items-center">
          <div className="h-12 w-12 bg-slate-200 rounded-full mb-4"></div>
          <div className="h-4 w-32 bg-slate-200 rounded"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
        <div className="max-w-md w-full bg-white p-6 rounded-lg shadow-sm border border-red-100 text-center">
          <svg className="mx-auto h-12 w-12 text-red-400 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <h3 className="text-lg font-medium text-slate-900 mb-2">Booking page not found</h3>
          <p className="text-slate-600 mb-6">{error.message}</p>
          <button 
            onClick={retryBootstrap}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-900">
      <header className="bg-white shadow-sm border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <h1 className="text-xl font-bold text-slate-800 truncate">
            {bootstrap?.tenant?.name || bootstrap?.company || 'Booking System'}
          </h1>
          <div className="flex items-center space-x-4">
            <Link to="/client/login" className="text-sm text-slate-600 hover:text-blue-600 font-medium">
              Client Portal
            </Link>
            <Link to="/admin/login" className="text-sm text-indigo-600 hover:text-indigo-800 font-medium">
              Staff Login
            </Link>
          </div>
        </div>
      </header>
      <main className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>
    </div>
  );
};

export const AdminLayout: React.FC = () => {
  const { bootstrap } = useTenant();
  const { user, logout } = useAuth();
  const location = useLocation();

  const navItems = [
    { name: 'Dashboard', path: '/admin' },
    { name: 'Calendar', path: '/admin/calendar' },
    { name: 'Bookings', path: '/admin/bookings' },
    { name: 'Form Builder', path: '/admin/booking-forms' },
    { name: 'Services', path: '/admin/catalog/services' },
    { name: 'Providers', path: '/admin/catalog/providers' },
    { name: 'Locations', path: '/admin/catalog/locations' },
    { name: 'Categories', path: '/admin/catalog/categories' },
    { name: 'Add-ons', path: '/admin/catalog/add-ons' },
    { name: 'Products', path: '/admin/catalog/products' },
    { name: 'Packages', path: '/admin/catalog/packages' },
    { name: 'Resources', path: '/admin/resources' },
    { name: 'Matrix', path: '/admin/relationships' },
    { name: 'Workdays', path: '/admin/schedule/workdays' },
    { name: 'Exceptions', path: '/admin/schedule/exceptions' },
    { name: 'Clients', path: '/admin/clients' },
    { name: 'Custom Fields', path: '/admin/configuration/additional-fields' },
    { name: 'Finance', path: '/admin/finance/invoices' },
    { name: 'Notifications', path: '/admin/notifications/messages' },
    { name: 'Audit', path: '/admin/audit' },
    { name: 'Business', path: '/admin/settings/business' },
    { name: 'System', path: '/admin/system' },
  ];

  return (
    <div className="min-h-screen bg-slate-100 font-sans text-slate-900 flex flex-col">
      <header className="bg-indigo-700 text-white shadow-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center">
            <span className="text-xl font-bold tracking-tight">{bootstrap?.tenant?.name || bootstrap?.company || 'Booking System'} Admin Workspace</span>
            <span className="ml-4 px-2.5 py-0.5 rounded-full bg-indigo-800 text-xs font-medium uppercase tracking-wide">
              {user?.role || 'owner'}
            </span>
          </div>
          <button 
            onClick={logout}
            className="text-sm text-indigo-100 hover:text-white font-medium transition-colors"
          >
            Sign out
          </button>
        </div>
        {/* Admin Navigation Bar */}
        <div className="bg-indigo-800 overflow-x-auto">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <nav className="flex space-x-6" aria-label="Admin Navigation">
              {navItems.map((item) => {
                const isActive = location.pathname === item.path || (item.path !== '/admin' && location.pathname.startsWith(item.path));
                return (
                  <Link
                    key={item.name}
                    to={item.path}
                    className={`
                      whitespace-nowrap py-3 px-1 border-b-2 font-medium text-xs sm:text-sm transition-colors
                      ${isActive 
                        ? 'border-white text-white font-semibold' 
                        : 'border-transparent text-indigo-200 hover:text-white hover:border-indigo-300'}
                    `}
                  >
                    {item.name}
                  </Link>
                );
              })}
            </nav>
          </div>
        </div>
      </header>
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>
    </div>
  );
};
