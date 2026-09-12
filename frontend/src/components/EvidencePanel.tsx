import { formatMoney, formatNumber } from '../utils.ts';
import React from 'react';
import { VerificationEvidence } from '../types/index.ts';
import { Calculator, Copy, History, FileCheck, ShieldAlert, CheckCircle, XCircle, AlertTriangle } from 'lucide-react';

export const EvidencePanel: React.FC<{ evidence?: VerificationEvidence }> = ({ evidence }) => {
  if (!evidence) {
    return (
      <div className="card">
        <h3 className="card-title">Verification Evidence</h3>
        <p style={{ color: 'var(--text-muted)' }}>No verification evidence recorded yet. Invoice is pending processing.</p>
      </div>
    );
  }

  const { arithmetic, duplicate, vendor_history, policy, risk, reasoning } = evidence;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* 1. Arithmetic Check */}
      <div className="card">
        <h4 style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 700 }}>
            <Calculator size={18} color="var(--accent-cyan)" /> Arithmetic Integrity
          </span>
          {arithmetic?.is_valid ? (
            <span className="badge badge-approved"><CheckCircle size={12} /> Valid</span>
          ) : (
            <span className="badge badge-blocked"><XCircle size={12} /> Discrepancy Found</span>
          )}
        </h4>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem', fontSize: '0.875rem' }}>
          <div><span style={{ color: 'var(--text-muted)' }}>Declared Subtotal:</span> </div>
          <div><span style={{ color: 'var(--text-muted)' }}>Computed Subtotal:</span> </div>
          <div><span style={{ color: 'var(--text-muted)' }}>Declared Total:</span> </div>
          <div><span style={{ color: 'var(--text-muted)' }}>Computed Total:</span> </div>
        </div>
        {arithmetic?.discrepancy_details && arithmetic.discrepancy_details.length > 0 && (
          <div style={{ marginTop: '0.75rem', padding: '0.5rem', background: 'rgba(239, 68, 68, 0.1)', borderRadius: 'var(--radius-sm)', color: '#fca5a5', fontSize: '0.8125rem' }}>
            {arithmetic.discrepancy_details.join(', ')}
          </div>
        )}
      </div>

      {/* 2. Duplicate Detection */}
      <div className="card">
        <h4 style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 700 }}>
            <Copy size={18} color="var(--accent-blue)" /> Duplicate Detection
          </span>
          {duplicate?.is_duplicate ? (
            <span className="badge badge-blocked"><XCircle size={12} /> Duplicate Detected</span>
          ) : (
            <span className="badge badge-approved"><CheckCircle size={12} /> Unique Record</span>
          )}
        </h4>
        <div style={{ fontSize: '0.875rem' }}>
          <p style={{ color: 'var(--text-secondary)' }}>
            {duplicate?.details || (duplicate?.is_duplicate ? 'Matching invoice previously processed.' : 'No duplicate invoice number or exact payload match found in repository.')}
          </p>
          {duplicate?.existing_invoice_id && (
            <div style={{ marginTop: '0.5rem', color: '#fca5a5', fontWeight: 600 }}>
              Collided Invoice ID: <code>{duplicate.existing_invoice_id}</code>
            </div>
          )}
        </div>
      </div>

      {/* 3. Vendor History */}
      <div className="card">
        <h4 style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 700 }}>
            <History size={18} color="var(--accent-indigo)" /> Vendor History & Profile
          </span>
          {vendor_history?.is_new_vendor ? (
            <span className="badge badge-review">New Vendor</span>
          ) : (
            <span className="badge badge-approved">Established Vendor</span>
          )}
        </h4>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem', fontSize: '0.875rem' }}>
          <div><span style={{ color: 'var(--text-muted)' }}>Historical Invoices:</span> {vendor_history?.historical_invoice_count ?? 0}</div>
          <div><span style={{ color: 'var(--text-muted)' }}>Historical Avg:</span> </div>
          <div><span style={{ color: 'var(--text-muted)' }}>Deviation Factor:</span> {formatNumber(vendor_history?.amount_deviation_factor, 2, "1.00")}x</div>
        </div>
      </div>

      {/* 4. Policy Compliance */}
      <div className="card">
        <h4 style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 700 }}>
            <FileCheck size={18} color="#fbbf24" /> Corporate Policy Check
          </span>
          {policy?.is_compliant ? (
            <span className="badge badge-approved"><CheckCircle size={12} /> Compliant</span>
          ) : (
            <span className="badge badge-review"><AlertTriangle size={12} /> Policy Exception</span>
          )}
        </h4>
        {policy?.violations && policy.violations.length > 0 ? (
          <ul style={{ paddingLeft: '1.25rem', color: '#fbbf24', fontSize: '0.875rem' }}>
            {policy.violations.map((v, i) => <li key={i}>{v}</li>)}
          </ul>
        ) : (
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>All enterprise threshold and vendor approval rules satisfied.</p>
        )}
      </div>

      {/* 5. Risk Assessment */}
      <div className="card">
        <h4 style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 700 }}>
            <ShieldAlert size={18} color="#f87171" /> Multi-Factor Risk Assessment
          </span>
          <span style={{ fontWeight: 800, fontSize: '1.125rem' }}>{risk?.risk_score ?? 0} / 100</span>
        </h4>
        {risk?.risk_factors && risk.risk_factors.length > 0 && (
          <div style={{ marginTop: '0.5rem' }}>
            <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>Triggered Risk Factors:</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
              {risk.risk_factors.map((f, i) => (
                <span key={i} className="badge badge-review">{f}</span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Reasoning Output */}
      {reasoning && (
        <div className="card">
          <h4 style={{ fontWeight: 700, marginBottom: '0.5rem' }}>Strands Agent Synthesis & Rationale</h4>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
            {reasoning}
          </p>
        </div>
      )}
    </div>
  );
};
