import React from 'react';
import { InvoiceRecord } from '../types/index.ts';
import { DecisionBadge } from './Badges.tsx';
import { ShieldAlert, ArrowDown, ShieldCheck, AlertCircle } from 'lucide-react';

export const DecisionGuardVisualizer: React.FC<{ invoice: InvoiceRecord }> = ({ invoice }) => {
  const summary = invoice.verification_summary || {};
  const isOverride = summary.guard_override || (invoice.original_decision && invoice.decision && invoice.original_decision !== invoice.decision);
  const proposedDecision = summary.guard_original_decision || invoice.original_decision || invoice.decision;
  const finalVerdict = invoice.decision;

  return (
    <div className="card" style={{ marginBottom: '1.5rem', position: 'relative' }}>
      <h3 className="card-title">
        <ShieldCheck size={20} color="var(--accent-cyan)" /> Decision Guard Pipeline
      </h3>

      {isOverride && (
        <div className="alert alert-danger" style={{ marginBottom: '1.5rem' }}>
          <ShieldAlert size={20} />
          <div>
            <strong>Decision Guard Safety Override Active!</strong>
            <div style={{ marginTop: '0.25rem' }}>
              {summary.guard_rule_triggered || 'Safety boundary enforced: An automated approval or review proposal was blocked due to critical risk or duplicate conflict.'}
            </div>
          </div>
        </div>
      )}

      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '1rem',
        padding: '1.5rem',
        background: 'var(--bg-primary)',
        borderRadius: 'var(--radius-md)',
        border: '1px solid var(--border-color)',
      }}>
        {/* Step 1: Agent Proposal */}
        <div style={{
          width: '100%',
          maxWidth: '420px',
          padding: '1rem',
          background: 'var(--bg-surface)',
          borderRadius: 'var(--radius-sm)',
          border: '1px solid var(--border-color)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700 }}>
              1. Strands Agent Proposed Verdict
            </div>
            <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>Based on LLM reasoning & evidence</div>
          </div>
          <DecisionBadge decision={proposedDecision} />
        </div>

        <ArrowDown size={20} color="var(--text-muted)" />

        {/* Step 2: Decision Guard Safety Check */}
        <div style={{
          width: '100%',
          maxWidth: '420px',
          padding: '1rem',
          background: isOverride ? 'rgba(239, 68, 68, 0.1)' : 'rgba(56, 189, 248, 0.1)',
          borderRadius: 'var(--radius-sm)',
          border: isOverride ? '1px solid rgba(239, 68, 68, 0.3)' : '1px solid rgba(56, 189, 248, 0.3)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
          <div>
            <div style={{ fontSize: '0.75rem', color: isOverride ? '#f87171' : 'var(--accent-cyan)', textTransform: 'uppercase', fontWeight: 700 }}>
              2. Decision Guard Enforcement
            </div>
            <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
              {isOverride ? 'Safety Threshold Violated' : 'Deterministic Safety Verified'}
            </div>
          </div>
          {isOverride ? (
            <span className="badge badge-blocked"><ShieldAlert size={12} /> OVERRIDDEN</span>
          ) : (
            <span className="badge badge-approved"><ShieldCheck size={12} /> PASS</span>
          )}
        </div>

        <ArrowDown size={20} color="var(--text-muted)" />

        {/* Step 3: Final Verdict */}
        <div style={{
          width: '100%',
          maxWidth: '420px',
          padding: '1.25rem',
          background: 'var(--bg-secondary)',
          borderRadius: 'var(--radius-sm)',
          border: '1px solid var(--border-color)',
          boxShadow: 'var(--shadow-md)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700 }}>
              3. Final Protected Verdict
            </div>
            <div style={{ fontSize: '0.875rem', fontWeight: 600 }}>Authoritative DynamoDB State</div>
          </div>
          <DecisionBadge decision={finalVerdict} />
        </div>
      </div>
    </div>
  );
};
