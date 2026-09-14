import React, { useEffect, useState } from 'react';
import {
  ArrowLeft,
  RefreshCw,
  AlertCircle,
  Plus,
  FileText,
  CheckCircle2,
  Play,
  Sliders,
  Sparkles,
  RotateCcw,
  Zap,
  Clock,
  ShieldCheck,
  AlertTriangle,
  XCircle,
  Copy,
} from 'lucide-react';
import { api } from '../services/api.ts';
import { BatchProgressResponse, BatchResponse, DocumentIngestionResponse } from '../types/index.ts';
import { ExtractionCorrectionModal } from '../components/ExtractionCorrectionModal.tsx';

interface BatchDetailPageProps {
  batchId: string;
  onBack: () => void;
  onNewBatch: () => void;
}

export const BatchDetailPage: React.FC<BatchDetailPageProps> = ({
  batchId,
  onBack,
  onNewBatch,
}) => {
  const [batch, setBatch] = useState<BatchResponse | null>(null);
  const [progress, setProgress] = useState<BatchProgressResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isExtractingAll, setIsExtractingAll] = useState(false);
  const [isResuming, setIsResuming] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [selectedDocForCorrection, setSelectedDocForCorrection] = useState<{
    batchId: string;
    documentId: string;
  } | null>(null);

  const fetchBatch = async () => {
    if (!batchId) return;
    try {
      const data = await api.getBatch(batchId);
      setBatch(data);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch batch details.');
    } finally {
      setLoading(false);
    }
  };

  const fetchProgress = async () => {
    if (!batchId) return;
    try {
      const p = await api.getBatchProgress(batchId);
      setProgress(p);
    } catch {
      // O(1) progress polling fallback
    }
  };

  useEffect(() => {
    setLoading(true);
    fetchBatch();
    fetchProgress();
  }, [batchId]);

  // Live polling every 2.5 seconds while batch is actively working
  useEffect(() => {
    let timer: any;
    const poll = async () => {
      await fetchProgress();
      if (
        batch?.status === 'PROCESSING' ||
        batch?.status === 'QUEUING' ||
        batch?.status === 'UPLOADING' ||
        (progress && progress.status === 'PROCESSING')
      ) {
        timer = setTimeout(poll, 2500);
      }
    };
    if (batch?.status === 'PROCESSING' || (progress && progress.status === 'PROCESSING')) {
      timer = setTimeout(poll, 2500);
    }
    return () => clearTimeout(timer);
  }, [batch?.status, progress?.status]);

  const handleExtractAll = async () => {
    if (!batchId) return;
    setIsExtractingAll(true);
    try {
      await api.extractAllDocuments(batchId);
      await fetchBatch();
      await fetchProgress();
    } catch (err: any) {
      alert(`Extract All failed: ${err.message || err}`);
    } finally {
      setIsExtractingAll(false);
    }
  };

  const handleResumeBatch = async () => {
    if (!batchId) return;
    setIsResuming(true);
    try {
      const res = await api.resumeBatch(batchId);
      alert(`Resumed ${res.resumed_count} eligible documents in batch ${batchId}.`);
      await fetchBatch();
      await fetchProgress();
    } catch (err: any) {
      alert(`Resume batch failed: ${err.message || err}`);
    } finally {
      setIsResuming(false);
    }
  };

  const handleExtractSingle = async (documentId: string) => {
    try {
      await api.extractDocument(batchId, documentId);
      await fetchBatch();
      await fetchProgress();
    } catch (err: any) {
      alert(`Extraction queue failed: ${err.message || err}`);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'QUEUED':
      case 'STORED':
        return <span className="badge badge-success">QUEUED</span>;
      case 'AWAITING_EXTRACTION':
        return <span className="badge badge-info">AWAITING EXTRACTION</span>;
      case 'EXTRACTING':
        return <span className="badge badge-warning">EXTRACTING</span>;
      case 'EXTRACTION_COMPLETED':
      case 'EXTRACTION_VALIDATED':
      case 'AUTO_APPROVED':
        return <span className="badge badge-success">{status.replace(/_/g, ' ')}</span>;
      case 'INSUFFICIENT_CONFIDENCE':
      case 'MANUAL_REVIEW':
        return <span className="badge badge-warning">{status.replace(/_/g, ' ')}</span>;
      case 'DUPLICATE':
        return <span className="badge badge-warning">DUPLICATE</span>;
      case 'BLOCKED':
      case 'REJECTED':
      case 'FAILED':
      case 'EXTRACTION_FAILED':
        return <span className="badge badge-error">{status.replace(/_/g, ' ')}</span>;
      default:
        return <span className="badge badge-info">{status}</span>;
    }
  };

  const renderConfidence = (conf?: number | null) => {
    if (conf == null) return null;
    const pct = Math.round(conf * 100);
    let color = '#34d399';
    if (conf < 0.6) color = '#f87171';
    else if (conf < 0.85) color = '#fbbf24';

    return (
      <span
        style={{
          fontSize: '0.75rem',
          fontWeight: 600,
          color,
          border: `1px solid ${color}40`,
          borderRadius: '9999px',
          padding: '0.125rem 0.375rem',
          marginLeft: '0.5rem',
        }}
      >
        {pct}%
      </span>
    );
  };

  if (loading) {
    return (
      <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
        Loading batch details...
      </div>
    );
  }

  if (error || !batch) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div
          style={{
            padding: '1rem',
            background: 'rgba(244, 63, 94, 0.1)',
            border: '1px solid rgba(244, 63, 94, 0.3)',
            borderRadius: '6px',
            color: '#fda4af',
            fontSize: '0.875rem',
          }}
        >
          {error || 'Batch not found.'}
        </div>
        <button onClick={onBack} className="btn btn-secondary" style={{ width: 'fit-content' }}>
          <ArrowLeft size={14} style={{ display: 'inline', marginRight: '4px' }} /> Back to Batches
        </button>
      </div>
    );
  }

  const awaitingCount =
    batch.documents?.filter((d) => d.status === 'AWAITING_EXTRACTION').length || 0;
  const failedCount =
    progress?.failed_count ??
    batch.documents?.filter((d) => d.status === 'FAILED' || d.status === 'EXTRACTION_FAILED').length ??
    0;

  // Filter documents
  const allDocs = batch.documents || [];
  const filteredDocs = allDocs.filter((doc) => {
    if (statusFilter === 'ALL') return true;
    if (statusFilter === 'AUTO_APPROVED') return doc.status === 'AUTO_APPROVED';
    if (statusFilter === 'MANUAL_REVIEW')
      return doc.status === 'MANUAL_REVIEW' || doc.status === 'INSUFFICIENT_CONFIDENCE' || doc.status === 'INSUFFICIENT_DATA';
    if (statusFilter === 'BLOCKED') return doc.status === 'BLOCKED';
    if (statusFilter === 'DUPLICATE') return doc.status === 'DUPLICATE';
    if (statusFilter === 'FAILED')
      return doc.status === 'FAILED' || doc.status === 'EXTRACTION_FAILED' || doc.status === 'REJECTED';
    return true;
  });

  const percentComplete = progress?.percent_complete ?? (
    batch.document_count > 0 ? Math.round((batch.completed_count / batch.document_count) * 100) : 100
  );
  const throughput = progress?.documents_per_minute ?? 0;
  const elapsed = progress?.elapsed_seconds ?? 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Top Bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderBottom: '1px solid var(--border-color)',
          paddingBottom: '1rem',
          flexWrap: 'wrap',
          gap: '1rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <button
            onClick={onBack}
            className="btn btn-secondary"
            style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem' }}
          >
            <ArrowLeft size={12} style={{ display: 'inline', marginRight: '4px' }} /> Back
          </button>
          <span style={{ color: 'var(--text-secondary)' }}>/</span>
          <span
            style={{
              fontFamily: 'monospace',
              fontWeight: 600,
              color: '#818cf8',
              fontSize: '0.875rem',
            }}
          >
            {batch.batch_id}
          </span>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          {/* Phase 9 Resume Batch Button */}
          {(awaitingCount > 0 || failedCount > 0 || batch.status === 'COMPLETED_WITH_EXCEPTIONS') && (
            <button
              onClick={handleResumeBatch}
              disabled={isResuming}
              className="btn btn-secondary"
              style={{
                fontSize: '0.8125rem',
                borderColor: '#fbbf24',
                color: '#fbbf24',
              }}
              title="Re-enqueue retry-eligible or incomplete documents without reprocessing completed items"
            >
              <RotateCcw
                size={14}
                className={isResuming ? 'animate-spin' : ''}
                style={{ display: 'inline', marginRight: '4px' }}
              />
              Resume Batch
            </button>
          )}

          {awaitingCount > 0 && (
            <button
              onClick={handleExtractAll}
              disabled={isExtractingAll}
              className="btn btn-primary"
              style={{ fontSize: '0.8125rem', background: '#4f46e5' }}
            >
              {isExtractingAll ? (
                <RefreshCw size={14} className="animate-spin" style={{ display: 'inline', marginRight: '4px' }} />
              ) : (
                <Play size={14} style={{ display: 'inline', marginRight: '4px' }} />
              )}
              Extract All ({awaitingCount})
            </button>
          )}

          <button onClick={() => { fetchBatch(); fetchProgress(); }} className="btn btn-secondary" style={{ fontSize: '0.8125rem' }}>
            <RefreshCw size={14} style={{ display: 'inline', marginRight: '4px' }} /> Refresh
          </button>

          <button onClick={onNewBatch} className="btn btn-primary" style={{ fontSize: '0.8125rem' }}>
            <Plus size={14} style={{ display: 'inline', marginRight: '4px' }} /> Ingest New Batch
          </button>
        </div>
      </div>

      {/* Phase 9 Operational Intelligence & Progress Bar */}
      <div
        className="card"
        style={{
          padding: '1.25rem',
          background: 'linear-gradient(180deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%)',
          border: '1px solid rgba(99, 102, 241, 0.3)',
          display: 'flex',
          flexDirection: 'column',
          gap: '1rem',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Zap size={18} color="#818cf8" />
            <span style={{ fontWeight: 600, fontSize: '0.9375rem', color: 'var(--text-primary)' }}>
              Live Autonomous Batch Engine (Phase 9 Bounded Concurrency)
            </span>
          </div>
          <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', fontSize: '0.8125rem' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#38bdf8' }}>
              <Zap size={14} /> <strong>{throughput}</strong> docs/min
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--text-secondary)' }}>
              <Clock size={14} /> <strong>{elapsed}s</strong> elapsed
            </span>
            {progress?.retry_count ? (
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#fbbf24' }}>
                <RotateCcw size={14} /> <strong>{progress.retry_count}</strong> retries
              </span>
            ) : null}
          </div>
        </div>

        {/* Progress Track */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
            <span>Progress: {progress?.completed_count ?? batch.completed_count} / {batch.document_count} Documents Verified</span>
            <span style={{ fontWeight: 600, color: '#818cf8' }}>{percentComplete}%</span>
          </div>
          <div
            style={{
              width: '100%',
              height: '10px',
              backgroundColor: 'rgba(51, 65, 85, 0.6)',
              borderRadius: '9999px',
              overflow: 'hidden',
              position: 'relative',
            }}
          >
            <div
              style={{
                width: `${percentComplete}%`,
                height: '100%',
                background: 'linear-gradient(90deg, #4f46e5 0%, #38bdf8 100%)',
                borderRadius: '9999px',
                transition: 'width 0.4s ease',
              }}
            />
          </div>
        </div>

        {/* Decision Breakdown Metrics */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
            gap: '0.75rem',
            paddingTop: '0.5rem',
          }}
        >
          <div style={{ background: 'rgba(15, 23, 42, 0.7)', border: '1px solid var(--border-color)', padding: '0.625rem', borderRadius: '6px' }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <ShieldCheck size={12} color="#34d399" /> AUTO-APPROVED
            </div>
            <div style={{ fontSize: '1.125rem', fontWeight: 'bold', color: '#34d399', marginTop: '2px' }}>
              {progress?.auto_approved_count ?? batch.auto_approved_count}
            </div>
          </div>
          <div style={{ background: 'rgba(15, 23, 42, 0.7)', border: '1px solid var(--border-color)', padding: '0.625rem', borderRadius: '6px' }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <AlertTriangle size={12} color="#fbbf24" /> MANUAL REVIEW
            </div>
            <div style={{ fontSize: '1.125rem', fontWeight: 'bold', color: '#fbbf24', marginTop: '2px' }}>
              {progress?.manual_review_count ?? batch.manual_review_count}
            </div>
          </div>
          <div style={{ background: 'rgba(15, 23, 42, 0.7)', border: '1px solid var(--border-color)', padding: '0.625rem', borderRadius: '6px' }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <XCircle size={12} color="#f87171" /> BLOCKED
            </div>
            <div style={{ fontSize: '1.125rem', fontWeight: 'bold', color: '#f87171', marginTop: '2px' }}>
              {progress?.blocked_count ?? batch.blocked_count}
            </div>
          </div>
          <div style={{ background: 'rgba(15, 23, 42, 0.7)', border: '1px solid var(--border-color)', padding: '0.625rem', borderRadius: '6px' }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Copy size={12} color="#94a3b8" /> DUPLICATES
            </div>
            <div style={{ fontSize: '1.125rem', fontWeight: 'bold', color: '#94a3b8', marginTop: '2px' }}>
              {progress?.duplicate_count ?? batch.duplicate_count}
            </div>
          </div>
          <div style={{ background: 'rgba(15, 23, 42, 0.7)', border: '1px solid var(--border-color)', padding: '0.625rem', borderRadius: '6px' }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <AlertCircle size={12} color="#fda4af" /> FAILED
            </div>
            <div style={{ fontSize: '1.125rem', fontWeight: 'bold', color: '#fda4af', marginTop: '2px' }}>
              {progress?.failed_count ?? batch.failed_count}
            </div>
          </div>
        </div>
      </div>

      {/* Overview Card */}
      <div className="card" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            flexWrap: 'wrap',
            gap: '1rem',
          }}
        >
          <div>
            <div style={{ fontSize: '0.75rem', fontFamily: 'monospace', color: 'var(--text-secondary)' }}>
              BATCH IDENTIFIER
            </div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 'bold', fontFamily: 'monospace', marginTop: '0.25rem' }}>
              {batch.batch_id}
            </h1>
            <div
              style={{
                fontSize: '0.8125rem',
                color: 'var(--text-secondary)',
                marginTop: '0.5rem',
                display: 'flex',
                gap: '1.25rem',
                flexWrap: 'wrap',
              }}
            >
              <span>Source: <strong style={{ color: 'var(--text-primary)' }}>{batch.source}</strong></span>
              <span>Created: <strong style={{ color: 'var(--text-primary)' }}>{new Date(batch.created_at).toLocaleString()}</strong></span>
              <span>Updated: <strong style={{ color: 'var(--text-primary)' }}>{new Date(batch.updated_at).toLocaleString()}</strong></span>
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <span style={{ fontSize: '0.75rem', fontFamily: 'monospace', color: 'var(--text-secondary)' }}>
              BATCH STATUS
            </span>
            <div style={{ marginTop: '0.25rem' }}>
              <span
                className={`badge ${
                  batch.status === 'COMPLETED'
                    ? 'badge-success'
                    : batch.status === 'COMPLETED_WITH_EXCEPTIONS'
                    ? 'badge-warning'
                    : batch.status === 'PROCESSING'
                    ? 'badge-info'
                    : 'badge-error'
                }`}
              >
                {batch.status}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Filter Tabs & Documents Table */}
      <div className="card" style={{ padding: '0', overflow: 'hidden' }}>
        <div
          style={{
            padding: '1rem 1.25rem',
            borderBottom: '1px solid var(--border-color)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '1rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <FileText size={16} color="var(--primary-color)" />
            <h2 style={{ fontSize: '1rem', fontWeight: 600 }}>
              Batch Documents ({filteredDocs.length} of {allDocs.length})
            </h2>
          </div>

          {/* Status Filter Tabs */}
          <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
            {[
              { id: 'ALL', label: 'All' },
              { id: 'AUTO_APPROVED', label: 'Auto-Approved' },
              { id: 'MANUAL_REVIEW', label: 'Manual Review' },
              { id: 'BLOCKED', label: 'Blocked' },
              { id: 'DUPLICATE', label: 'Duplicates' },
              { id: 'FAILED', label: 'Failed' },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setStatusFilter(tab.id)}
                style={{
                  fontSize: '0.75rem',
                  padding: '0.25rem 0.6rem',
                  borderRadius: '4px',
                  border: '1px solid',
                  borderColor: statusFilter === tab.id ? 'var(--primary-color)' : 'var(--border-color)',
                  backgroundColor: statusFilter === tab.id ? 'rgba(99, 102, 241, 0.15)' : 'transparent',
                  color: statusFilter === tab.id ? '#818cf8' : 'var(--text-secondary)',
                  cursor: 'pointer',
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8125rem' }}>
            <thead>
              <tr style={{ background: 'rgba(15, 23, 42, 0.5)', borderBottom: '1px solid var(--border-color)', textAlign: 'left' }}>
                <th style={{ padding: '0.75rem 1rem' }}>Document ID</th>
                <th style={{ padding: '0.75rem 1rem' }}>Filename</th>
                <th style={{ padding: '0.75rem 1rem' }}>Size</th>
                <th style={{ padding: '0.75rem 1rem' }}>Status</th>
                <th style={{ padding: '0.75rem 1rem' }}>Extraction Conf.</th>
                <th style={{ padding: '0.75rem 1rem' }}>Extracted Inv #</th>
                <th style={{ padding: '0.75rem 1rem' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredDocs.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                    No documents found matching the filter "{statusFilter}".
                  </td>
                </tr>
              ) : (
                filteredDocs.map((doc: DocumentIngestionResponse) => (
                  <tr key={doc.document_id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                    <td style={{ padding: '0.75rem 1rem', fontFamily: 'monospace', color: '#818cf8' }}>
                      {doc.document_id}
                    </td>
                    <td style={{ padding: '0.75rem 1rem', fontWeight: 500 }}>
                      {doc.original_filename}
                    </td>
                    <td style={{ padding: '0.75rem 1rem', color: 'var(--text-secondary)' }}>
                      {(doc.file_size / 1024).toFixed(1)} KB
                    </td>
                    <td style={{ padding: '0.75rem 1rem' }}>
                      {getStatusBadge(doc.status)}
                    </td>
                    <td style={{ padding: '0.75rem 1rem' }}>
                      {renderConfidence(doc.overall_confidence) || (
                        <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>--</span>
                      )}
                    </td>
                    <td style={{ padding: '0.75rem 1rem', fontFamily: 'monospace' }}>
                      {doc.extracted_invoice_id || (
                        <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>--</span>
                      )}
                    </td>
                    <td style={{ padding: '0.75rem 1rem' }}>
                      <div style={{ display: 'flex', gap: '0.5rem' }}>
                        {doc.status === 'AWAITING_EXTRACTION' && (
                          <button
                            onClick={() => handleExtractSingle(doc.document_id)}
                            className="btn btn-secondary"
                            style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}
                          >
                            <Play size={12} style={{ display: 'inline', marginRight: '2px' }} /> Extract
                          </button>
                        )}
                        {(doc.status === 'INSUFFICIENT_CONFIDENCE' ||
                          doc.status === 'INSUFFICIENT_DATA' ||
                          doc.status === 'EXTRACTION_COMPLETED' ||
                          doc.status === 'EXTRACTION_VALIDATED' ||
                          doc.status === 'MANUAL_REVIEW') && (
                          <button
                            onClick={() => setSelectedDocForCorrection({ batchId: doc.batch_id, documentId: doc.document_id })}
                            className="btn btn-secondary"
                            style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}
                          >
                            <Sliders size={12} style={{ display: 'inline', marginRight: '2px' }} /> Review / Edit
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Field Correction Modal */}
      {selectedDocForCorrection && (
        <ExtractionCorrectionModal
          batchId={selectedDocForCorrection.batchId}
          documentId={selectedDocForCorrection.documentId}
          onClose={() => setSelectedDocForCorrection(null)}
          onSuccess={() => {
            setSelectedDocForCorrection(null);
            fetchBatch();
            fetchProgress();
          }}
        />
      )}
    </div>
  );
};
