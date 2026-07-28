import React, { useState, useEffect } from 'react';
import { apiFetch } from '../../services/apiClient';

export const ProductManager: React.FC = () => {
  const [products, setProducts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchProducts();
  }, []);

  const fetchProducts = async () => {
    setLoading(true);
    try {
      const res = await apiFetch<any[]>('/api/admin/products', { method: 'GET' });
      if (res) setProducts(res);
    } catch (err: any) {
      setError(err.uiError?.message || 'Failed to load products');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Products Catalog</h1>
          <p className="text-sm text-slate-500">Manage retail products sold alongside services.</p>
        </div>
      </div>

      {error && <div className="p-4 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>}

      {loading ? (
        <div className="p-8 text-center text-slate-500">Loading products...</div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 border-b text-slate-700 uppercase text-xs font-semibold">
              <tr>
                <th className="p-4">SKU</th>
                <th className="p-4">Name</th>
                <th className="p-4">Price</th>
                <th className="p-4">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {products.length === 0 ? (
                <tr>
                  <td colSpan={4} className="p-6 text-center text-slate-500">No products configured.</td>
                </tr>
              ) : (
                products.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50">
                    <td className="p-4 font-mono text-slate-600">{p.sku || 'N/A'}</td>
                    <td className="p-4 font-medium text-slate-900">{p.name}</td>
                    <td className="p-4">${Number(p.price || 0).toFixed(2)}</td>
                    <td className="p-4">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${p.active ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-600'}`}>
                        {p.active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
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

export const PackageManager: React.FC = () => {
  const [packages, setPackages] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<any[]>('/api/admin/packages', { method: 'GET' })
      .then((res) => setPackages(res || []))
      .catch(() => setPackages([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Bundles & Packages</h1>
        <p className="text-sm text-slate-500">Configure multi-step service packages and series.</p>
      </div>

      {loading ? (
        <div className="p-8 text-center text-slate-500">Loading packages...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {packages.length === 0 ? (
            <div className="col-span-2 p-8 bg-white rounded-xl border text-center text-slate-500">No packages configured.</div>
          ) : (
            packages.map((pkg) => (
              <div key={pkg.id} className="bg-white p-5 rounded-xl border shadow-sm">
                <h3 className="font-bold text-slate-900">{pkg.name}</h3>
                <p className="text-sm text-slate-500 my-2">{pkg.description || 'Service package'}</p>
                <div className="text-sm font-semibold text-blue-600">${Number(pkg.price || 0).toFixed(2)}</div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
};

export const ResourceManager: React.FC = () => {
  const [resources, setResources] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<any[]>('/api/admin/resources', { method: 'GET' })
      .then((res) => setResources(res || []))
      .catch(() => setResources([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Equipment & Resources</h1>
        <p className="text-sm text-slate-500">Manage rooms, machinery, and physical equipment requirements.</p>
      </div>

      {loading ? (
        <div className="p-8 text-center text-slate-500">Loading resources...</div>
      ) : (
        <div className="bg-white rounded-xl border overflow-hidden">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 border-b text-xs font-semibold text-slate-700 uppercase">
              <tr>
                <th className="p-4">Name</th>
                <th className="p-4">Type</th>
                <th className="p-4">Capacity</th>
                <th className="p-4">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {resources.length === 0 ? (
                <tr><td colSpan={4} className="p-6 text-center text-slate-500">No equipment or resources listed.</td></tr>
              ) : (
                resources.map((r) => (
                  <tr key={r.id}>
                    <td className="p-4 font-medium text-slate-900">{r.name}</td>
                    <td className="p-4 text-slate-600">{r.type}</td>
                    <td className="p-4 text-slate-600">{r.capacity}</td>
                    <td className="p-4">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${r.active ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-600'}`}>
                        {r.active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
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

export const RelationshipEditor: React.FC = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Cross-Entity Relationship Matrix</h1>
        <p className="text-sm text-slate-500">Link services, providers, locations, and categories across tenant boundaries.</p>
      </div>

      <div className="bg-white p-8 rounded-xl border text-center text-slate-600 space-y-3">
        <p className="font-semibold text-slate-800">Interactive Relationship Graph & Matrix</p>
        <p className="text-sm max-w-xl mx-auto text-slate-500">
          Connect services to eligible providers and locations to maintain valid booking graph constraint rules.
        </p>
      </div>
    </div>
  );
};
