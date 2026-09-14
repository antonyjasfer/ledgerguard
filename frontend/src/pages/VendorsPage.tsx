import React, { useEffect, useState } from 'react';
import { VendorRecordResponse } from '../types/index.ts';
import { api } from '../services/api.ts';
import { formatMoney } from '../utils.ts';
import {
  Users,
  Search,
  CheckCircle,
  AlertCircle,
  Clock,
  Building,
  RefreshCw,
  ShieldCheck,
  ShieldAlert,
} from 'lucide-react';

export const VendorsPage: React.FC = () => {
  const [vendors, setVendors] = useState<VendorRecordResponse[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchVendors = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listVendors();
      setVendors(data.items);
    } catch (err: any) {
      setError(err.message || 'Failed to retrieve vendor master records');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchVendors();
  }, []);

  const filteredVendors = vendors.filter((v) => {
    const q = searchTerm.toLowerCase();
    return (
      v.legal_name.toLowerCase().includes(q) ||
      v.vendor_id.toLowerCase().includes(q) ||
      v.country.toLowerCase().includes(q) ||
      v.aliases.some((a) => a.toLowerCase().includes(q))
    );
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: '1.75rem', fontWeight: 800, letterSpacing: '-0.02em', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <Users size={26} color="var(--accent-indigo)" /> Enterprise Vendor Master
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            Authoritative corporate vendor directory, banking verification status, and historical spending baselines
          </p>
        </div>
        <button className="btn btn-secondary" onClick={fetchVendors} title="Refresh Directory">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {/* Search Bar */}
      <div className="card" style={{ padding: '0.75rem 1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <Search size={18} color="var(--text-muted)" />
          <input
            id="vendor-search-input"
            type="text"
            className="form-input"
            style={{ border: 'none', background: 'transparent', padding: '0.25rem', fontSize: '0.875rem' }}
            placeholder="Search by vendor name, ID, alias, or country..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
          {searchTerm && (
            <button
              className="btn btn-secondary"
              style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
              onClick={() => setSearchTerm('')}
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '300px' }}>
          <RefreshCw className="spin-animation" size={28} color="var(--accent-blue)" />
          <span style={{ marginLeft: '0.75rem', color: 'var(--text-secondary)' }}>Loading vendor master directory...</span>
        </div>
      ) : error ? (
        <div className="card" style={{ borderColor: 'var(--accent-red)', textAlign: 'center', padding: '2rem' }}>
          <AlertCircle size={32} color="var(--accent-red)" style={{ marginBottom: '1rem' }} />
          <h3 style={{ color: 'var(--accent-red)', marginBottom: '0.5rem' }}>Error Loading Vendors</h3>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '1rem' }}>{error}</p>
          <button className="btn btn-primary" onClick={fetchVendors}>Retry</button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))', gap: '1.25rem' }}>
          {filteredVendors.map((vendor) => {
            const isVerified = vendor.bank_verification_status === 'VERIFIED';
            const isApproved = vendor.onboarding_status === 'APPROVED';
            const isActive = vendor.status === 'ACTIVE';

            return (
              <div
                key={vendor.vendor_id}
                className="card"
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.875rem',
                  borderTop: isActive ? '3px solid var(--accent-emerald)' : '3px solid var(--accent-amber)',
                }}
              >
                {/* Vendor Card Header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <h3 style={{ fontSize: '1.125rem', fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <Building size={16} color="var(--accent-blue)" />
                      {vendor.legal_name}
                    </h3>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: '0.125rem' }}>
                      ID: {vendor.vendor_id} • {vendor.country}
                    </div>
                  </div>
                  <span className={`badge ${isActive ? 'badge-approved' : 'badge-review'}`}>
                    {vendor.status}
                  </span>
                </div>

                {/* Status Badges */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', fontSize: '0.75rem' }}>
                  <span className={`badge ${isApproved ? 'badge-approved' : 'badge-review'}`} style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                    {isApproved ? <CheckCircle size={10} /> : <Clock size={10} />}
                    Onboarding: {vendor.onboarding_status}
                  </span>
                  <span className={`badge ${isVerified ? 'badge-approved' : 'badge-blocked'}`} style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                    {isVerified ? <ShieldCheck size={10} /> : <ShieldAlert size={10} />}
                    Bank: {vendor.bank_verification_status}
                  </span>
                  {vendor.po_required && (
                    <span className="badge badge-neutral" style={{ color: 'var(--accent-cyan)' }}>
                      PO Required
                    </span>
                  )}
                </div>

                {/* Financial Baseline Stats */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.5rem', background: 'var(--bg-secondary)', padding: '0.75rem', borderRadius: 'var(--radius-sm)', fontSize: '0.8125rem' }}>
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>Historical Invoices:</span>
                    <div style={{ fontWeight: 700, fontSize: '0.9375rem', marginTop: '0.125rem' }}>
                      {vendor.historical_invoice_count}
                    </div>
                  </div>
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>Historical Average:</span>
                    <div style={{ fontWeight: 700, fontSize: '0.9375rem', marginTop: '0.125rem' }}>
                      ${formatMoney(vendor.historical_average_invoice)}
                    </div>
                  </div>
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>Largest Recorded:</span>
                    <div style={{ fontWeight: 700, marginTop: '0.125rem' }}>
                      ${formatMoney(vendor.historical_largest_invoice)}
                    </div>
                  </div>
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>Normal Amount Range:</span>
                    <div style={{ fontWeight: 600, marginTop: '0.125rem' }}>
                      ${formatMoney(vendor.normal_invoice_min)} - ${formatMoney(vendor.normal_invoice_max)}
                    </div>
                  </div>
                </div>

                {/* Additional Metadata */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.75rem', color: 'var(--text-secondary)', borderTop: '1px solid var(--border-color)', paddingTop: '0.5rem' }}>
                  <span>Terms: <strong>{vendor.payment_terms}</strong></span>
                  <span>Currencies: <strong>{vendor.approved_currencies.join(', ')}</strong></span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
