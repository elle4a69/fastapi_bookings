import React from 'react';
import { Link } from 'react-router-dom';

export const Error403: React.FC = () => (
  <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6 text-center">
    <div className="max-w-md w-full bg-white p-8 rounded-xl shadow-md border border-slate-200">
      <h1 className="text-4xl font-extrabold text-red-600 mb-2">403</h1>
      <h2 className="text-xl font-bold text-slate-800 mb-2">Permission Denied</h2>
      <p className="text-slate-600 text-sm mb-6">You do not have authorization to view this resource.</p>
      <Link to="/" className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium">Go to Homepage</Link>
    </div>
  </div>
);

export const Error404: React.FC = () => (
  <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6 text-center">
    <div className="max-w-md w-full bg-white p-8 rounded-xl shadow-md border border-slate-200">
      <h1 className="text-4xl font-extrabold text-slate-400 mb-2">404</h1>
      <h2 className="text-xl font-bold text-slate-800 mb-2">Page Not Found</h2>
      <p className="text-slate-600 text-sm mb-6">The requested route or resource does not exist.</p>
      <Link to="/" className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium">Go to Homepage</Link>
    </div>
  </div>
);
