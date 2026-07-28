import React from 'react';
import { Link } from 'react-router-dom';

export const RoleNotEnabled: React.FC = () => {
  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
      <div className="max-w-md w-full bg-white p-8 rounded-xl shadow-md border border-slate-200 text-center">
        <div className="w-16 h-16 bg-amber-100 text-amber-600 rounded-full flex items-center justify-center mx-auto mb-4 text-2xl font-bold">
          !
        </div>
        <h1 className="text-2xl font-bold text-slate-900 mb-2">Role Not Enabled</h1>
        <p className="text-slate-600 text-sm mb-6">
          This account role is not enabled for the administration workspace. Contact your system owner to request access.
        </p>
        <Link
          to="/admin/login"
          className="inline-block px-5 py-2.5 bg-slate-900 hover:bg-slate-800 text-white font-medium text-sm rounded-lg shadow transition-colors"
        >
          Return to Admin Login
        </Link>
      </div>
    </div>
  );
};
