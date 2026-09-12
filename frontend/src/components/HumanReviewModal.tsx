import React, { useState } from 'react';
import { HumanReviewRequest, InvoiceRecord } from '../types/index.ts';
import { api } from '../services/api.ts';
import { CheckCircle, XCircle, HelpCircle, AlertTriangle } from 'lucide-react';

interface HumanReviewModalProps {
  invoice: InvoiceRecord;
  onClose: () => void;
  onSuccess: (updated: InvoiceRecord) => void;
}

export const HumanReviewModal: React.FC<HumanReviewModalProps> = ({ invoice, onClose, onSuccess }) => {
  const [action, setAction] = useState<'APPROVE' | 'REJECT' | 'REQUEST_INFORMATION'>('APPROVE');
  const [reviewer, setReviewer] = useState('Enterprise Reviewer');
  const [comment, setComment] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!comment.trim()) {
      setErrorMsg('A review comment explaining your decision is required.');
      return;
    }

    setIsSubmitting(true);
    setErrorMsg(null);

    try {
      const payload: HumanReviewRequest = {
        action,
        reviewer: reviewer.trim() || 'Anonymous Reviewer',
        comment: comment.trim(),
      };
      await api.submitReview(invoice.invoice_id, payload);
      const refreshed = await api.getInvoice(invoice.invoice_id);
      onSuccess(refreshed);
      onClose();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to submit human review verdict.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content" style={{ maxWidth: '550px' }}>
        <h3 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.5rem' }}>
          Human Review Workflow
        </h3>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginBottom: '1.25rem' }}>
          Reviewing Invoice <code>{invoice.invoice_id}</code> ({invoice.vendor_name}). Automated decision: <strong>{invoice.decision || 'PENDING'}</strong>.
        </p>

        {errorMsg && (
          <div className="alert alert-danger" style={{ marginBottom: '1rem' }}>
            <AlertTriangle size={16} /> {errorMsg}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          {/* Action Choice */}
          <div className="form-group">
            <label className="form-label">Review Action</label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem' }}>
              <button
                type="button"
                id="review-action-approve"
                className={`btn ${action === 'APPROVE' ? 'btn-success' : 'btn-secondary'}`}
                style={{ padding: '0.6rem 0.5rem', fontSize: '0.8125rem' }}
                onClick={() => setAction('APPROVE')}
              >
                <CheckCircle size={14} /> Approve
              </button>
              <button
                type="button"
                id="review-action-reject"
                className={`btn ${action === 'REJECT' ? 'btn-danger' : 'btn-secondary'}`}
                style={{ padding: '0.6rem 0.5rem', fontSize: '0.8125rem' }}
                onClick={() => setAction('REJECT')}
              >
                <XCircle size={14} /> Reject
              </button>
              <button
                type="button"
                id="review-action-request-info"
                className={`btn ${action === 'REQUEST_INFORMATION' ? 'btn-primary' : 'btn-secondary'}`}
                style={{ padding: '0.6rem 0.5rem', fontSize: '0.8125rem' }}
                onClick={() => setAction('REQUEST_INFORMATION')}
              >
                <HelpCircle size={14} /> Request Info
              </button>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Reviewer Identity</label>
            <input
              id="reviewer-name-input"
              type="text"
              className="form-input"
              value={reviewer}
              onChange={(e) => setReviewer(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">Audit Comment / Justification *</label>
            <textarea
              id="reviewer-comment-input"
              className="form-textarea"
              rows={4}
              placeholder="State the audit rationale for approving, rejecting, or requesting further documentation..."
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              required
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1.5rem' }}>
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={isSubmitting}>
              Cancel
            </button>
            <button id="submit-review-btn" type="submit" className="btn btn-primary" disabled={isSubmitting}>
              {isSubmitting ? 'Recording Verdict...' : 'Submit Human Verdict'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
