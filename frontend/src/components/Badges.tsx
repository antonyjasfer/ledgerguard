import React from 'react';
import { ProcessingState, AgentDecision, RiskLevel } from '../types/index.ts';
import { CheckCircle, AlertTriangle, ShieldAlert, Clock, RefreshCw, XCircle } from 'lucide-react';

export const StatusBadge: React.FC<{ status: ProcessingState | string }> = ({ status }) => {
  switch (status) {
    case 'HUMAN_APPROVED':
      return (
        <span className="badge badge-approved" style={{ background: 'rgba(16, 185, 129, 0.25)', borderColor: '#10b981', color: '#34d399' }}>
          <CheckCircle size={12} /> Human Approved
        </span>
      );
    case 'HUMAN_REJECTED':
      return (
        <span className="badge badge-blocked">
          <XCircle size={12} /> Human Rejected
        </span>
      );
    case 'AUTO_APPROVED':
      return (
        <span className="badge badge-approved">
          <CheckCircle size={12} /> Auto-Approved
        </span>
      );
    case 'MANUAL_REVIEW':
      return (
        <span className="badge badge-review">
          <AlertTriangle size={12} /> Manual Review
        </span>
      );
    case 'BLOCKED':
      return (
        <span className="badge badge-blocked">
          <ShieldAlert size={12} /> Blocked
        </span>
      );
    case 'FAILED':
      return (
        <span className="badge badge-blocked">
          <XCircle size={12} /> Failed
        </span>
      );
    case 'AGENT_PROCESSING':
    case 'PROCESSING':
    case 'EXTRACTING':
    case 'QUEUED':
      return (
        <span className="badge badge-processing">
          <RefreshCw size={12} className="animate-spin" /> Processing
        </span>
      );
    case 'VALIDATED':
      return (
        <span className="badge badge-processing">
          <Clock size={12} /> Validated
        </span>
      );
    case 'RECEIVED':
    default:
      return (
        <span className="badge badge-neutral">
          <Clock size={12} /> Received
        </span>
      );
  }
};

export const DecisionBadge: React.FC<{
  decision?: AgentDecision | string | null;
  reviewDecision?: string | null;
}> = ({ decision, reviewDecision }) => {
  if (reviewDecision) {
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
        <span className="badge badge-review" style={{ fontSize: '0.72rem' }}>MANUAL_REVIEW</span>
        <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>&rarr;</span>
        {reviewDecision === 'APPROVE' ? (
          <span className="badge badge-approved" style={{ fontSize: '0.72rem' }}><CheckCircle size={10} /> APPROVED</span>
        ) : reviewDecision === 'REJECT' ? (
          <span className="badge badge-blocked" style={{ fontSize: '0.72rem' }}><XCircle size={10} /> REJECTED</span>
        ) : (
          <span className="badge badge-neutral" style={{ fontSize: '0.72rem' }}>{reviewDecision}</span>
        )}
      </span>
    );
  }

  if (!decision) return <span className="badge badge-neutral">Pending</span>;

  switch (decision) {
    case 'AUTO_APPROVE':
      return <span className="badge badge-approved"><CheckCircle size={12} /> AUTO_APPROVE</span>;
    case 'MANUAL_REVIEW':
    case 'ESCALATE':
      return <span className="badge badge-review"><AlertTriangle size={12} /> {decision}</span>;
    case 'BLOCK':
      return <span className="badge badge-blocked"><ShieldAlert size={12} /> BLOCK</span>;
    default:
      return <span className="badge badge-neutral">{decision}</span>;
  }
};

export const RiskBadge: React.FC<{ level?: RiskLevel | null; score?: number | null }> = ({ level, score }) => {
  if (!level) return <span className="badge badge-neutral">Score: {score ?? '--'}</span>;

  const scoreText = score !== null && score !== undefined ? ` (${score})` : '';

  switch (level) {
    case 'LOW':
      return <span className="badge badge-approved">LOW RISK{scoreText}</span>;
    case 'MEDIUM':
      return <span className="badge badge-review">MEDIUM RISK{scoreText}</span>;
    case 'HIGH':
    case 'CRITICAL':
      return <span className="badge badge-blocked">{level} RISK{scoreText}</span>;
    default:
      return <span className="badge badge-neutral">{level}{scoreText}</span>;
  }
};
