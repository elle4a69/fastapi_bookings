import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { apiFetch } from '../../services/apiClient';

export const NotificationsManager: React.FC = () => (
  <div className="space-y-6">
    <h1 className="text-2xl font-bold text-slate-900">Notifications & Device Tokens</h1>
    <div className="bg-white p-8 rounded-xl border text-center text-slate-500">
      Track sent SMS, Email, and Push notifications across client bookings.
    </div>
  </div>
);

export const NotificationTemplatesManager: React.FC = () => (
  <div className="space-y-6">
    <h1 className="text-2xl font-bold text-slate-900">Notification Templates</h1>
    <div className="bg-white p-8 rounded-xl border text-center text-slate-500">
      Manage localized templates for booking receipts, reminders, and confirmations.
    </div>
  </div>
);

export const ReminderRulesManager: React.FC = () => (
  <div className="space-y-6">
    <h1 className="text-2xl font-bold text-slate-900">Automated Reminder Rules</h1>
    <div className="bg-white p-8 rounded-xl border text-center text-slate-500">
      Set up automated 24h/1h SMS & Email reminder dispatch rules.
    </div>
  </div>
);

export const ManagementReviewsManager: React.FC = () => (
  <div className="space-y-6">
    <h1 className="text-2xl font-bold text-slate-900">Management Reviews</h1>
    <div className="bg-white p-8 rounded-xl border text-center text-slate-500">
      Review pending booking approvals requiring administrative sign-off.
    </div>
  </div>
);

export const AuditLogManager: React.FC = () => {
  const [logs, setLogs] = useState<any[]>([]);

  useEffect(() => {
    apiFetch<any>('/api/admin/audit-log', { method: 'GET' })
      .then((res) => setLogs(res?.items || res || []))
      .catch(() => setLogs([]));
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Audit Log & Security Ledger</h1>
      <div className="bg-white rounded-xl border overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 border-b text-xs font-semibold text-slate-700 uppercase">
            <tr>
              <th className="p-4">Timestamp</th>
              <th className="p-4">Action</th>
              <th className="p-4">Target Type</th>
              <th className="p-4">Target ID</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {logs.length === 0 ? (
              <tr><td colSpan={4} className="p-6 text-center text-slate-500">No audit log entries recorded.</td></tr>
            ) : (
              logs.map((l, i) => (
                <tr key={i}>
                  <td className="p-4 text-xs text-slate-500">{l.timestamp}</td>
                  <td className="p-4 font-semibold text-slate-800">{l.action}</td>
                  <td className="p-4 text-slate-600">{l.target_type || '-'}</td>
                  <td className="p-4 font-mono">{l.target_id || '-'}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export const GdprConsentManager: React.FC = () => (
  <div className="space-y-6">
    <h1 className="text-2xl font-bold text-slate-900">GDPR Compliance & Consents</h1>
    <div className="bg-white p-8 rounded-xl border text-center text-slate-500">
      Review active client GDPR opt-in records and legal consent timestamps.
    </div>
  </div>
);

export const WebhooksManager: React.FC = () => (
  <div className="space-y-6">
    <h1 className="text-2xl font-bold text-slate-900">Webhooks Integration</h1>
    <div className="bg-white p-8 rounded-xl border text-center text-slate-500">
      Register outgoing event webhooks for booking lifecycle changes.
    </div>
  </div>
);

export const PluginStatesManager: React.FC = () => (
  <div className="space-y-6">
    <h1 className="text-2xl font-bold text-slate-900">System Plugin States</h1>
    <div className="bg-white p-8 rounded-xl border text-center text-slate-500">
      Enable and configure modular system plugins.
    </div>
  </div>
);

export const SystemDiagnosticsManager: React.FC = () => (
  <div className="space-y-6">
    <h1 className="text-2xl font-bold text-slate-900">System Maintenance & Diagnostics</h1>
    <div className="bg-white p-8 rounded-xl border text-center text-slate-500">
      Run database integrity diagnostics, orphan cleanup, and client anonymization.
    </div>
  </div>
);

export const WorkdaysManager: React.FC = () => (
  <div className="space-y-6">
    <h1 className="text-2xl font-bold text-slate-900">Workdays & Shift Schedules</h1>
    <div className="bg-white p-8 rounded-xl border text-center text-slate-500">
      Configure standard weekday operational hours per provider and location.
    </div>
  </div>
);

export const ScheduleExceptionsManager: React.FC = () => (
  <div className="space-y-6">
    <h1 className="text-2xl font-bold text-slate-900">Special Days & Blocked Times</h1>
    <div className="bg-white p-8 rounded-xl border text-center text-slate-500">
      Manage holidays, blocked time blocks, and provider special availability overrides.
    </div>
  </div>
);

export const BookingDetailView: React.FC = () => {
  const { bookingId } = useParams();
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">Booking #{bookingId}</h1>
        <Link to="/admin/bookings" className="text-sm text-blue-600 hover:underline">&larr; Back to Bookings</Link>
      </div>
      <div className="bg-white p-8 rounded-xl border text-slate-600">
        Detailed lifecycle status transitions for booking #{bookingId}.
      </div>
    </div>
  );
};

export const ClientDetailView: React.FC = () => {
  const { clientId } = useParams();
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">Client Profile #{clientId}</h1>
        <Link to="/admin/clients" className="text-sm text-blue-600 hover:underline">&larr; Back to Clients</Link>
      </div>
      <div className="bg-white p-8 rounded-xl border text-slate-600">
        Client record, history, and compliance consent details for #{clientId}.
      </div>
    </div>
  );
};
