import React, { useEffect, useState } from 'react';
import { PolicyConfigResponse } from '../types/index.ts';
import { api } from '../services/api.ts';
import { formatMoney } from '../utils.ts';
import {
  Shield,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Clock,
  Layers,
  FileText,
  DollarSign,
  Lock,
  RefreshCw,
} from 'lucide-react';

export const PolicyPage: React.FC = () => {
  const [policy, setPolicy] = useState<PolicyConfigResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchPolicy = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getPolicy();
      setPolicy(data);
    } catch (err: any) {
      setError(err.message || 'Failed to retrieve active corporate policy');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPolicy();
  }, []);

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '350px' }}>
        <RefreshCw className="spin-animation" size={28} color="var(--accent-blue)" />
        <span style={{ marginLeft: '0.75rem', color: 'var(--text-secondary)' }}>Loading corporate policy...</span>
      </div>
    );
  }

  if (error || !policy) {
    return (
      <div className="card" style={{ borderColor: 'var(--accent-red)', padding: '2rem', textAlign: 'center' }}>
        <AlertTriangle size={32} color="var(--accent-red)" style={{ marginBottom: '1rem' }} />
        <h3 style={{ color: 'var(--accent-red)', marginBottom: '0.5rem' }}>Failed to Load Policy</h3>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>{error}</p>
        <button className="btn btn-primary" onClick={fetchPolicy}>Retry</button>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: '1.75rem', fontWeight: 800, letterSpacing: '-0.02em', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <Shield size={26} color="var(--accent-blue)" /> Corporate Accounts Payable Policy
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            Deterministic rule thresholds and approval matrix applied by LedgerGuard autonomous agent
          </p>
        </div>
        <button className="btn btn-secondary" onClick={fetchPolicy} title="Refresh Policy">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {/* Company Profile Card */}
      <div className="card" style={{ background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.7), rgba(15, 23, 42, 0.9))' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1.25rem' }}>
          <div>
            <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>Company Legal Entity</div>
            <div style={{ fontSize: '1.125rem', fontWeight: 700, marginTop: '0.25rem' }}>{policy.company_name}</div>
            <div style={{ fontSize: '0.8125rem', color: 'var(--accent-blue)' }}>ID: {policy.company_id}</div>
          </div>
          <div>
            <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>Default Operational Currency</div>
            <div style={{ fontSize: '1.125rem', fontWeight: 700, marginTop: '0.25rem' }}>{policy.default_currency}</div>
            <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>Supported: {policy.supported_currencies.join(', ')}</div>
          </div>
          <div>
            <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>Auto-Approval Ceiling</div>
            <div style={{ fontSize: '1.125rem', fontWeight: 800, color: 'var(--accent-emerald)', marginTop: '0.25rem' }}>
              ${formatMoney(policy.auto_approval_limit)}
            </div>
            <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>Straight-Through Processing Limit</div>
          </div>
          <div>
            <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>High-Value Threshold</div>
            <div style={{ fontSize: '1.125rem', fontWeight: 800, color: 'var(--accent-amber)', marginTop: '0.25rem' }}>
              ${formatMoney(policy.high_value_threshold)}
            </div>
            <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>Finance Director Review Boundary</div>
          </div>
        </div>
      </div>

      {/* Rules Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.25rem' }}>
        {/* Verification Gates */}
        <div className="card">
          <h3 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Lock size={18} color="var(--accent-indigo)" /> Deterministic Enforcement Gates
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.875rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.5rem', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)' }}>
              <div>
                <span style={{ fontWeight: 600 }}>Confirmed Duplicate</span>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Duplicate invoice number from same vendor</div>
              </div>
              <span className="badge badge-blocked">BLOCK</span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.5rem', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)' }}>
              <div>
                <span style={{ fontWeight: 600 }}>Arithmetic Mismatch</span>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Calculation variance above tolerance (0.00)</div>
              </div>
              <span className="badge badge-blocked">BLOCK</span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.5rem', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)' }}>
              <div>
                <span style={{ fontWeight: 600 }}>New Vendor Detection</span>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Zero transaction history or unapproved onboarding</div>
              </div>
              <span className="badge badge-review">MANUAL_REVIEW</span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.5rem', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)' }}>
              <div>
                <span style={{ fontWeight: 600 }}>Missing Purchase Order</span>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Vendor requires PO but none provided</div>
              </div>
              <span className="badge badge-review">MANUAL_REVIEW</span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.5rem', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)' }}>
              <div>
                <span style={{ fontWeight: 600 }}>Unsupported Currency</span>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Currency outside approved company / vendor list</div>
              </div>
              <span className="badge badge-review">MANUAL_REVIEW</span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.5rem', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)' }}>
              <div>
                <span style={{ fontWeight: 600 }}>Excessive Discount (&gt;{policy.maximum_discount_percent}%)</span>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Exceeds allowable promotional discount limit</div>
              </div>
              <span className="badge badge-review">MANUAL_REVIEW</span>
            </div>
          </div>
        </div>

        {/* Required Fields & Audit Constraints */}
        <div className="card">
          <h3 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <FileText size={18} color="var(--accent-cyan)" /> Mandatory Invoice Fields & Tolerances
          </h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.8125rem', marginBottom: '0.75rem' }}>
            Invoices missing any of these required fields automatically trigger an AP compliance review:
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1.25rem' }}>
            {policy.required_fields.map((f, i) => (
              <span key={i} className="badge badge-neutral" style={{ fontFamily: 'var(--font-mono)' }}>
                {f}
              </span>
            ))}
          </div>

          <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '1rem', fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
            <div style={{ marginBottom: '0.5rem' }}>
              <strong>Lookback Window:</strong> Possible duplicates checked within {policy.possible_duplicate_days} days.
            </div>
            <div>
              <strong>Vendor Recency:</strong> Invoices within {policy.recent_invoice_days} days considered recent spend.
            </div>
          </div>
        </div>
      </div>

      {/* Approval Matrix Table */}
      <div className="card">
        <h3 style={{ fontSize: '1.125rem', fontWeight: 700, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Layers size={20} color="var(--accent-purple)" /> Corporate Approval Routing Matrix
        </h3>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginBottom: '1rem' }}>
          Deterministic authority levels evaluated before straight-through payment processing:
        </p>

        <div style={{ overflowX: 'auto' }}>
          <table className="table" style={{ width: '100%', fontSize: '0.875rem' }}>
            <thead>
              <tr>
                <th style={{ textAlign: 'left', padding: '0.75rem' }}>Routing Tier</th>
                <th style={{ textAlign: 'left', padding: '0.75rem' }}>Threshold / Condition</th>
                <th style={{ textAlign: 'left', padding: '0.75rem' }}>Mandated Business Action</th>
              </tr>
            </thead>
            <tbody>
              {policy.approval_matrix_tiers.map((t, idx) => (
                <tr key={idx} style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <td style={{ padding: '0.75rem' }}>
                    <span className={`badge ${
                      t.tier === 'AUTO_APPROVAL_ALLOWED'
                        ? 'badge-approved'
                        : t.tier === 'BLOCK'
                          ? 'badge-blocked'
                          : 'badge-review'
                    }`}>
                      {t.tier}
                    </span>
                  </td>
                  <td style={{ padding: '0.75rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {t.condition}
                  </td>
                  <td style={{ padding: '0.75rem', color: 'var(--text-secondary)' }}>
                    {t.action}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
