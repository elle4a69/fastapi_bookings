import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { apiFetch } from '../../services/apiClient';

export const ClientLogin: React.FC = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const res = await apiFetch<{ token: string; client_id: number }>('/api/public/clients/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });
      if (res.token) {
        localStorage.setItem('client_token', res.token);
        navigate('/client/profile');
      }
    } catch (err: any) {
      setError(err.uiError?.message || err.message || 'Login failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-md mx-auto my-12 bg-white p-8 rounded-xl shadow-md border border-slate-200">
      <h2 className="text-2xl font-bold text-slate-900 mb-2">Client Sign In</h2>
      <p className="text-slate-600 text-sm mb-6">Manage your bookings, details, and consent preferences.</p>

      {error && (
        <div className="mb-4 bg-red-50 border-l-4 border-red-500 p-3 text-red-700 text-sm rounded-r">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
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
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Password</label>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
            placeholder="••••••••"
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg shadow transition-colors disabled:opacity-50"
        >
          {loading ? 'Signing in...' : 'Sign In'}
        </button>
      </form>

      <div className="mt-6 border-t border-slate-100 pt-4 flex flex-col space-y-2 text-center text-sm">
        <Link to="/client/register" className="text-blue-600 hover:underline">Don't have an account? Register</Link>
        <Link to="/client/password-reset" className="text-slate-500 hover:underline">Forgot password?</Link>
      </div>
    </div>
  );
};
