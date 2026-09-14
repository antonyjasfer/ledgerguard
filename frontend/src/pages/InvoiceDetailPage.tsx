import { formatMoney } from '../utils.ts';
import React, { useEffect, useState, useRef } from 'react';
import { InvoiceRecord } from '../types/index.ts';
import { api } from '../services/api.ts';
import { StatusBadge, DecisionBadge, RiskBadge } from '../components/Badges.tsx';
import { EvidencePanel } from '../components/EvidencePanel.tsx';
import { DecisionGuardVisualizer } from '../components/DecisionGuardVisualizer.tsx';
import { HumanReviewModal } from '../components/HumanReviewModal.tsx';
import { AuditTimeline } from '../components/AuditTimeline.tsx';
import { DocumentUpload } from '../components/DocumentUpload.tsx';
import {
  ArrowLeft,
  UserCheck,
  FileText,
  ShieldCheck,
  History,
  Paperclip,
  Clock,
  RefreshCw,
} from 'lucide-react';

interface InvoiceDetailPageProps {
  invoiceId: string;
  onBack: () => void;
}

const TERMINAL_STATUSES = ['AUTO_APPROVED', 'MANUAL_REVIEW', 'BLOCKED', 'FAILED'];

export const InvoiceDetailPage: React.FC<InvoiceDetailPageProps> = ({ invoiceId, onBack }) => {
  const [invoice, setInvoice] = useState<InvoiceRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'evidence' | 'guard' | 'audit' | 'document'>('evidence');
  const [showReviewModal, setShowReviewModal] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const pollTimerRef = useRef<number | null>(null);

  const fetchInvoice = async () => {
    try {
      const data = await api.getInvoice(invoiceId);
      setInvoice(data);
      setLoading(false);

      // Check if terminal
      if (TERMINAL_STATUSES.includes(data.processing_status)) {
        if (pollTimerRef.current) {
          window.clearInterval(pollTimerRef.current);
          pollTimerRef.current = null;
        }
        setIsPolling(false);
      } else {
        // Non-terminal state: start live polling
        if (!pollTimerRef.current) {
          setIsPolling(true);
          pollTimerRef.current = window.setInterval(fetchInvoice, 2500);
        }
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load invoice details');
      setLoading(false);
      if (pollTimerRef.current) {
        window.clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
      setIsPolling(false);
    }
  };

  useEffect(() => {
    fetchInvoice();
    return () => {
      if (pollTimerRef.current) {
        window.clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [invoiceId]);

  if (loading && !invoice) {
    return (
      <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
        Loading invoice verification record for <code>{invoiceId}</code>...
      </div>
    );
  }

  if (error || !invoice) {
    return (
      <div>
        <button className="btn btn-secondary" style={{ marginBottom: '1rem' }} onClick={onBack}>
          <ArrowLeft size={16} /> Back to Invoices
        </button>
        <div className="alert alert-danger">{error || 'Invoice not found'}</div>
      </div>
    );
  }

  const canReview = invoice.processing_status === 'MANUAL_REVIEW' || invoice.decision === 'MANUAL_REVIEW';

  return (
    <div>
      {/* Header & Back */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <button id="back-to-invoices-btn" className="btn btn-secondary" onClick={onBack}>
            <ArrowLeft size={16} /> Back
          </button>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <h2 style={{ fontSize: '1.5rem', fontWeight: 800 }}>Invoice {invoice.invoice_id}</h2>
              {isPolling && (
                <span className="badge badge-processing">
                  <RefreshCw size={12} className="animate-spin" /> Live Polling SQS / Worker
                </span>
              )}
            </div>
            <span style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
              Vendor: <strong>{invoice.vendor_name}</strong> (Number: <code>{invoice.invoice_number}</code>)
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem' }}>
          {canReview && (
            <button
              id="open-human-review-btn"
              className="btn btn-primary"
              onClick={() => setShowReviewModal(true)}
            >
              <UserCheck size={16} /> Perform Human Review
            </button>
          )}
        </div>
      </div>

      {/* Human Review Banner if completed */}
      {invoice.review_decision && (
        <div className="alert alert-info" style={{ marginBottom: '1.5rem' }}>
          <UserCheck size={18} />
          <div>
            <strong>Human Review Verdict: {invoice.review_decision}</strong> by <em>{invoice.reviewer || 'Reviewer'}</em> on {invoice.review_timestamp ? new Date(invoice.review_timestamp).toLocaleString() : ''}.
            {invoice.review_comment && <div style={{ marginTop: '0.25rem' }}>Comment: "{invoice.review_comment}"</div>}
          </div>
        </div>
      )}

      {/* Metadata & Status Card */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1.25rem' }}>
          <div>
            <div className="stat-label">Lifecycle Status</div>
            <StatusBadge status={invoice.processing_status} />
          </div>

          <div>
            <div className="stat-label">Verification Verdict</div>
            <DecisionBadge decision={invoice.decision} />
          </div>

          <div>
            <div className="stat-label">Risk Assessment</div>
            <RiskBadge level={invoice.risk_level} score={invoice.risk_score} />
          </div>

          <div>
            <div className="stat-label">Total Amount</div>
            <div style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--accent-cyan)' }}>
              ${formatMoney(invoice.total)} {invoice.currency}
            </div>
            {(invoice.subtotal !== null && invoice.subtotal !== undefined) && (
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.125rem' }}>
                Subtotal: ${formatMoney(invoice.subtotal)} | Tax: ${formatMoney(invoice.tax)}
              </div>
            )}
          </div>

          <div>
            <div className="stat-label">Invoice Date</div>
            <div style={{ fontSize: '0.875rem' }}>{invoice.invoice_date}</div>
          </div>

          <div>
            <div className="stat-label">Created Timestamp</div>
            <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
              {new Date(invoice.created_at).toLocaleString()}
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '0.5rem', borderBottom: '1px solid var(--border-color)', marginBottom: '1.5rem' }}>
        <button
          id="tab-evidence-btn"
          className={`nav-btn ${activeTab === 'evidence' ? 'active' : ''}`}
          style={{ borderBottomLeftRadius: 0, borderBottomRightRadius: 0 }}
          onClick={() => setActiveTab('evidence')}
        >
          <FileText size={16} /> Deterministic Evidence
        </button>
        <button
          id="tab-guard-btn"
          className={`nav-btn ${activeTab === 'guard' ? 'active' : ''}`}
          style={{ borderBottomLeftRadius: 0, borderBottomRightRadius: 0 }}
          onClick={() => setActiveTab('guard')}
        >
          <ShieldCheck size={16} /> Decision Guard
        </button>
        <button
          id="tab-audit-btn"
          className={`nav-btn ${activeTab === 'audit' ? 'active' : ''}`}
          style={{ borderBottomLeftRadius: 0, borderBottomRightRadius: 0 }}
          onClick={() => setActiveTab('audit')}
        >
          <History size={16} /> Audit Timeline
        </button>
        <button
          id="tab-document-btn"
          className={`nav-btn ${activeTab === 'document' ? 'active' : ''}`}
          style={{ borderBottomLeftRadius: 0, borderBottomRightRadius: 0 }}
          onClick={() => setActiveTab('document')}
        >
          <Paperclip size={16} /> S3 Attachment
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === 'evidence' && (
        <EvidencePanel evidence={invoice.verification_summary} invoice={invoice} />
      )}

      {activeTab === 'guard' && (
        <DecisionGuardVisualizer invoice={invoice} />
      )}

      {activeTab === 'audit' && (
        <AuditTimeline invoiceId={invoice.invoice_id} />
      )}

      {activeTab === 'document' && (
        <DocumentUpload
          invoiceId={invoice.invoice_id}
          currentKey={invoice.document_s3_key}
          onUploaded={(key) => {
            setInvoice((prev) => prev ? { ...prev, document_s3_key: key } : null);
          }}
        />
      )}

      {/* Human Review Modal */}
      {showReviewModal && (
        <HumanReviewModal
          invoice={invoice}
          onClose={() => setShowReviewModal(false)}
          onSuccess={(updated) => {
            setInvoice(updated);
          }}
        />
      )}
    </div>
  );
};
