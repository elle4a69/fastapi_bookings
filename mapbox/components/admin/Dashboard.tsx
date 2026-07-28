import React from 'react';
import { Link } from 'react-router-dom';
import { adminService } from '../../services/adminService';
import { useAuth } from '../../store/AuthContext';
import { usePolling } from '../../hooks/usePolling';

export const Dashboard: React.FC = () => {
  const { user } = useAuth();
  const isStaff = user?.role === 'staff';

  // Poll every 30 seconds (30000ms) per MCD requirements
  const { 
    data: stats, 
    isLoading, 
    isPolling, 
    error, 
    lastUpdated, 
    refetch 
  } = usePolling(adminService.getDashboardStats, 30000);

  if (isLoading && !stats) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map(i => (
          <div key={i} className="bg-white p-6 rounded-xl shadow-sm border border-slate-200 animate-pulse">
            <div className="h-4 bg-slate-200 rounded w-1/2 mb-4"></div>
            <div className="h-8 bg-slate-200 rounded w-1/4"></div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <h1 className="text-2xl font-bold text-slate-900">Overview</h1>
          {/* Subtle inline indicator for background refresh */}
          {isPolling && (
            <span className="flex items-center text-xs font-medium text-indigo-600 bg-indigo-50 px-2 py-1 rounded-full animate-pulse">
              <svg className="w-3 h-3 mr-1 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Syncing
            </span>
          )}
          {!isPolling && lastUpdated && (
            <span className="text-xs text-slate-500">
              Updated {lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          )}
        </div>
        <button 
          onClick={refetch} 
          disabled={isPolling || isLoading}
          className="text-sm text-indigo-600 hover:text-indigo-800 font-medium disabled:opacity-50"
        >
          Refresh
        </button>
      </div>

      {error && (
        <div className="bg-amber-50 border-l-4 border-amber-500 p-4 rounded-md">
          <p className="text-sm text-amber-700">{error.message}</p>
        </div>
      )}

      {stats && stats.pending_approvals === 0 && stats.upcoming_today === 0 && stats.management_reviews === 0 && (
        <div className="bg-white p-8 rounded-xl shadow-sm border border-slate-200 text-center">
          <p className="text-slate-600">Nothing needs attention right now.</p>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <DashboardCard 
          title="Pending Approvals" 
          count={stats?.pending_approvals || 0} 
          linkTo="/admin/bookings?status=pending"
          color="blue"
        />
        <DashboardCard 
          title="Upcoming Today" 
          count={stats?.upcoming_today || 0} 
          linkTo="/admin/calendar"
          color="green"
        />
        {!isStaff && (
          <DashboardCard 
            title="Management Reviews" 
            count={stats?.management_reviews || 0} 
            linkTo="/admin/bookings?status=review"
            color="amber"
          />
        )}
        <DashboardCard 
          title="Exceptions" 
          count={stats?.exceptions || 0} 
          linkTo="/admin/bookings?status=exception"
          color="red"
        />
      </div>
    </div>
  );
};

const DashboardCard = ({ title, count, linkTo, color }: { title: string, count: number, linkTo: string, color: 'blue' | 'green' | 'amber' | 'red' }) => {
  const colorClasses = {
    blue: 'bg-blue-50 text-blue-700 border-blue-100 hover:border-blue-300',
    green: 'bg-green-50 text-green-700 border-green-100 hover:border-green-300',
    amber: 'bg-amber-50 text-amber-700 border-amber-100 hover:border-amber-300',
    red: 'bg-red-50 text-red-700 border-red-100 hover:border-red-300',
  };

  return (
    <Link to={linkTo} className={`block p-6 rounded-xl shadow-sm border transition-colors ${colorClasses[color]}`}>
      <h3 className="text-sm font-medium uppercase tracking-wider opacity-80">{title}</h3>
      <p className="mt-2 text-3xl font-bold">{count}</p>
    </Link>
  );
};
