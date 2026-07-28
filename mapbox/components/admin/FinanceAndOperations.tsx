import React, { useState, useEffect } from 'react';
import { apiFetch } from '../../services/apiClient';

export const InvoicesManager: React.FC = () => {
  const [invoices, setInvoices] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<any[]>('/api/admin/invoices', { method: 'GET' })
      .then((res) => setInvoices(res || []))
      .catch(() => setInvoices([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Invoices & Financial Ledger</h1>
      {loading ? (
        <div className="p-8 text-center text-slate-500">Loading invoices...</div>
      ) : (
        <div className="bg-white rounded-xl border overflow-hidden">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 border-b text-xs font-semibold text-slate-700 uppercase">
              <tr>
                <th className="p-4">Invoice ID</th>
                <th className="p-4">Total</th>
                <th className="p-4">Paid</th>
                <th className="p-4">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {invoices.length === 0 ? (
                <tr><td colSpan={4} className="p-6 text-center text-slate-500">No invoices recorded.</td></tr>
              ) : (
                invoices.map((inv) => (
                  <tr key={inv.id}>
                    <td className="p-4 font-mono">#{inv.id}</td>
                    <td className="p-4 font-semibold">${Number(inv.total || 0).toFixed(2)}</td>
                    <td className="p-4">${Number(inv.amount_paid || 0).toFixed(2)}</td>
                    <td className="p-4"><span className="px-2 py-0.5 bg-slate-100 rounded text-xs">{inv.status}</span></td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export const PaymentsManager: React.FC = () => {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Payment Transactions</h1>
      <div className="bg-white p-8 rounded-xl border text-center text-slate-500">
        Review payment logs and process transaction refunds.
      </div>
    </div>
  );
};

export const PromotionsManager: React.FC = () => {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Promotions & Discount Codes</h1>
      <div className="bg-white p-8 rounded-xl border text-center text-slate-500">
        Configure promotional codes and percentage/fixed discount rules.
      </div>
    </div>
  );
};

export const TaxRatesManager: React.FC = () => {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Tax Rates</h1>
      <div className="bg-white p-8 rounded-xl border text-center text-slate-500">
        Manage regional GST / VAT / Sales Tax calculations.
      </div>
    </div>
  );
};

export const ProcessorsManager: React.FC = () => {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Payment Processors</h1>
      <div className="bg-white p-8 rounded-xl border text-center text-slate-500">
        Configure Stripe, PayPal, and local gateway integrations.
      </div>
    </div>
  );
};

export const AdditionalFieldsManager: React.FC = () => {
  const [fields, setFields] = useState<any[]>([]);

  useEffect(() => {
    apiFetch<any[]>('/api/admin/additional-fields', { method: 'GET' })
      .then((res) => setFields(res || []))
      .catch(() => setFields([]));
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Custom Intake Fields</h1>
      <div className="bg-white rounded-xl border p-6">
        <p className="text-slate-600 text-sm mb-4">Define custom fields collected during checkout intake.</p>
        <div className="space-y-2">
          {fields.map((f) => (
            <div key={f.id} className="p-3 border rounded flex justify-between items-center text-sm">
              <span className="font-semibold text-slate-800">{f.label} ({f.name})</span>
              <span className="text-xs text-slate-500">{f.field_type} {f.required ? '&bull; Required' : ''}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
