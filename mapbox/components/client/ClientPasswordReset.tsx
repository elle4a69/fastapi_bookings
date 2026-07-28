import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { apiFetch } from '../../services/apiClient';

export const ClientPasswordReset: React.FC = () => {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await apiFetch('/api/public/clients/password-reset/request', {
        method: 'POST',
        body: JSON.stringify({ email }),
      });
      setSubmitted(true);
    } catch (err: any) {
      setError(err.uiError?.message || err.message || 'Password reset request failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-md mx-auto my-12 bg-white p-8 rounded-xl shadow-md border border-slate-200">
      <h2 className="text-2xl font-bold text-slate-900 mb-2">Reset Password</h2>
      <p className="text-slate-600 text-sm mb-6">Enter your email address to receive password reset instructions.</p>

      {submitted ? (
        <div className="bg-emerald-50 border-l-4 border-emerald-500 p-4 text-emerald-800 text-sm rounded-r mb-6">
          If an account exists for {email}, a password reset link has been dispatched.
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="bg-red-50 border-l-4 border-red-500 p-3 text-red-700 text-sm rounded-r">
              {error}
            </div>
          )}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Email Address</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
              placeholder="client@example.com"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg shadow transition-colors disabled:opacity-50"
          >
            {loading ? 'Sending Request...' : 'Send Reset Link'}
          </button>
        </form>
      )}

      <div className="mt-6 border-t border-slate-100 pt-4 text-center text-sm">
        <Link to="/client/login" className="text-blue-600 hover:underline">Back to Sign In</Link>
      </div>
    </div>
  );
};
