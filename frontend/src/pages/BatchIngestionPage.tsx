import React, { useState } from 'react';
import { UploadCloud, CheckCircle2, AlertTriangle, AlertCircle, FileText, ArrowRight } from 'lucide-react';
import { api } from '../services/api.ts';
import { BatchResponse } from '../types/index.ts';

interface BatchIngestionPageProps {
  onViewBatches: () => void;
  onSelectBatch: (batchId: string) => void;
}

export const BatchIngestionPage: React.FC<BatchIngestionPageProps> = ({
  onViewBatches,
  onSelectBatch,
}) => {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [batchResult, setBatchResult] = useState<BatchResponse | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const filesArray = Array.from(e.target.files);
      setSelectedFiles(filesArray);
      setError(null);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files) {
      const filesArray = Array.from(e.dataTransfer.files);
      setSelectedFiles(filesArray);
      setError(null);
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
  };

  const handleUpload = async () => {
    if (selectedFiles.length === 0) {
      setError('Please select at least one document to ingest.');
      return;
    }

    if (selectedFiles.length > 100) {
      setError('A single batch cannot exceed 100 files.');
      return;
    }

    const totalSize = selectedFiles.reduce((acc, f) => acc + f.size, 0);
    if (totalSize > 100 * 1024 * 1024) {
      setError('Total batch payload size exceeds 100 MB limit.');
      return;
    }

    setUploading(true);
    setError(null);

    try {
      const result = await api.uploadBatchFiles(selectedFiles, 'UI_UPLOAD');
      setBatchResult(result);
    } catch (err: any) {
      setError(err.message || 'Failed to ingest batch.');
    } finally {
      setUploading(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'QUEUED':
      case 'STORED':
        return <span className="badge badge-success">QUEUED</span>;
      case 'DUPLICATE':
        return <span className="badge badge-warning">DUPLICATE</span>;
      case 'REJECTED':
      case 'FAILED':
        return <span className="badge badge-error">{status}</span>;
      default:
        return <span className="badge badge-info">{status}</span>;
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>Bulk Invoice Ingestion</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginTop: '0.25rem' }}>
            Phase 7: Multi-file ingestion, SHA-256 deduplication, S3 archive, and SQS job queuing.
          </p>
        </div>
        <button
          onClick={onViewBatches}
          className="btn btn-secondary"
          style={{ fontSize: '0.875rem' }}
        >
          View All Batches
        </button>
      </div>

      {/* Notice Banner */}
      <div style={{ padding: '1rem', background: 'rgba(99, 102, 241, 0.1)', border: '1px solid rgba(99, 102, 241, 0.3)', borderRadius: '8px', display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
        <AlertCircle size={20} color="#818cf8" style={{ marginTop: '2px', flexShrink: 0 }} />
        <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
          <strong style={{ color: 'var(--text-primary)', display: 'block', marginBottom: '0.25rem' }}>
            Phase 7 Ingestion Lifecycle
          </strong>
          Source documents are validated, hashed, stored in Amazon S3, and placed into the{' '}
          <code style={{ color: '#a5b4fc', background: 'rgba(99, 102, 241, 0.2)', padding: '0.125rem 0.375rem', borderRadius: '4px' }}>AWAITING_EXTRACTION</code> lifecycle state.
          OCR, layout analysis, and field extraction are strictly reserved for Phase 8.
        </div>
      </div>

      {/* Upload Box */}
      {!batchResult && (
        <div className="card" style={{ padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            style={{
              border: '2px dashed var(--border-color)',
              borderRadius: '8px',
              padding: '2.5rem 1.5rem',
              textAlign: 'center',
              cursor: 'pointer',
              background: 'rgba(15, 23, 42, 0.4)',
            }}
          >
            <input
              type="file"
              id="bulk-file-input"
              multiple
              accept=".pdf,.png,.jpg,.jpeg"
              onChange={handleFileChange}
              style={{ display: 'none' }}
            />
            <label htmlFor="bulk-file-input" style={{ cursor: 'pointer', display: 'block' }}>
              <UploadCloud size={40} color="#94a3b8" style={{ margin: '0 auto 1rem auto' }} />
              <div style={{ fontSize: '0.9375rem', fontWeight: 500, color: 'var(--text-primary)' }}>
                Drag and drop invoice documents here, or <span style={{ color: '#818cf8', textDecoration: 'underline' }}>browse</span>
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
                Supported formats: PDF, PNG, JPG (Max 10 MB per file, 100 MB per batch, up to 100 files)
              </div>
            </label>
          </div>

          {selectedFiles.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.875rem' }}>
                <strong>Selected Files ({selectedFiles.length})</strong>
                <span style={{ color: 'var(--text-secondary)' }}>
                  Total: {(selectedFiles.reduce((acc, f) => acc + f.size, 0) / (1024 * 1024)).toFixed(2)} MB
                </span>
              </div>
              <div style={{ maxHeight: '180px', overflowY: 'auto', border: '1px solid var(--border-color)', borderRadius: '6px', background: 'rgba(15, 23, 42, 0.3)' }}>
                {selectedFiles.map((f, idx) => (
                  <div key={idx} style={{ padding: '0.5rem 0.75rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8125rem', borderBottom: '1px solid var(--border-color)' }}>
                    <span style={{ fontFamily: 'monospace', color: 'var(--text-primary)' }}>{f.name}</span>
                    <span style={{ color: 'var(--text-secondary)' }}>{(f.size / 1024).toFixed(1)} KB</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {error && (
            <div style={{ padding: '0.75rem', background: 'rgba(244, 63, 94, 0.1)', border: '1px solid rgba(244, 63, 94, 0.3)', borderRadius: '6px', color: '#fda4af', fontSize: '0.8125rem' }}>
              {error}
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
            <button
              onClick={() => setSelectedFiles([])}
              disabled={uploading || selectedFiles.length === 0}
              className="btn btn-secondary"
            >
              Clear
            </button>
            <button
              onClick={handleUpload}
              disabled={uploading || selectedFiles.length === 0}
              className="btn btn-primary"
            >
              {uploading ? 'Validating & Uploading...' : `Ingest Batch (${selectedFiles.length} Files)`}
            </button>
          </div>
        </div>
      )}

      {/* Ingestion Results */}
      {batchResult && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div className="card" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <span style={{ fontSize: '0.75rem', fontFamily: 'monospace', color: '#818cf8' }}>BATCH ID</span>
                <h2 style={{ fontSize: '1.25rem', fontWeight: 'bold', fontFamily: 'monospace', marginTop: '0.25rem' }}>
                  {batchResult.batch_id}
                </h2>
              </div>
              <div style={{ textAlign: 'right' }}>
                <span style={{ fontSize: '0.75rem', fontFamily: 'monospace', color: 'var(--text-secondary)' }}>STATUS</span>
                <div style={{ marginTop: '0.25rem' }}>
                  <span className={`badge ${
                    batchResult.status === 'COMPLETED' ? 'badge-success' : batchResult.status === 'COMPLETED_WITH_EXCEPTIONS' ? 'badge-warning' : 'badge-error'
                  }`}>
                    {batchResult.status}
                  </span>
                </div>
              </div>
            </div>

            {/* Metrics Breakdown */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))', gap: '0.75rem' }}>
              <div style={{ background: 'rgba(15, 23, 42, 0.6)', border: '1px solid var(--border-color)', padding: '0.75rem', borderRadius: '6px', textAlign: 'center' }}>
                <div style={{ fontSize: '1.25rem', fontWeight: 'bold' }}>{batchResult.document_count}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Submitted</div>
              </div>
              <div style={{ background: 'rgba(15, 23, 42, 0.6)', border: '1px solid var(--border-color)', padding: '0.75rem', borderRadius: '6px', textAlign: 'center' }}>
                <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#34d399' }}>{batchResult.accepted_count}</div>
                <div style={{ fontSize: '0.75rem', color: '#34d399' }}>Accepted</div>
              </div>
              <div style={{ background: 'rgba(15, 23, 42, 0.6)', border: '1px solid var(--border-color)', padding: '0.75rem', borderRadius: '6px', textAlign: 'center' }}>
                <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#fbbf24' }}>{batchResult.duplicate_count}</div>
                <div style={{ fontSize: '0.75rem', color: '#fbbf24' }}>Duplicates</div>
              </div>
              <div style={{ background: 'rgba(15, 23, 42, 0.6)', border: '1px solid var(--border-color)', padding: '0.75rem', borderRadius: '6px', textAlign: 'center' }}>
                <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#f87171' }}>{batchResult.rejected_count}</div>
                <div style={{ fontSize: '0.75rem', color: '#f87171' }}>Rejected</div>
              </div>
              <div style={{ background: 'rgba(15, 23, 42, 0.6)', border: '1px solid var(--border-color)', padding: '0.75rem', borderRadius: '6px', textAlign: 'center' }}>
                <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#818cf8' }}>{batchResult.queued_count}</div>
                <div style={{ fontSize: '0.75rem', color: '#818cf8' }}>Queued</div>
              </div>
            </div>

            {/* Actions */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '0.5rem' }}>
              <button
                onClick={() => {
                  setBatchResult(null);
                  setSelectedFiles([]);
                }}
                className="btn btn-secondary"
              >
                Upload Another Batch
              </button>
              <button
                onClick={() => onSelectBatch(batchResult.batch_id)}
                className="btn btn-primary"
              >
                View Batch Details & Documents <ArrowRight size={14} style={{ display: 'inline', marginLeft: '4px' }} />
              </button>
            </div>
          </div>

          {/* Document list */}
          {batchResult.documents && batchResult.documents.length > 0 && (
            <div className="card" style={{ padding: '0', overflow: 'hidden' }}>
              <div style={{ padding: '1rem', borderBottom: '1px solid var(--border-color)' }}>
                <h3 style={{ fontSize: '0.9375rem', fontWeight: 600 }}>Batch Documents</h3>
              </div>
              <table style={{ width: '100%', fontSize: '0.8125rem', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: 'rgba(15, 23, 42, 0.6)', borderBottom: '1px solid var(--border-color)', color: 'var(--text-secondary)', textAlign: 'left' }}>
                    <th style={{ padding: '0.75rem 1rem' }}>Filename</th>
                    <th style={{ padding: '0.75rem 1rem' }}>Document ID</th>
                    <th style={{ padding: '0.75rem 1rem' }}>Status</th>
                    <th style={{ padding: '0.75rem 1rem' }}>Size</th>
                    <th style={{ padding: '0.75rem 1rem' }}>SHA-256 Hash</th>
                    <th style={{ padding: '0.75rem 1rem' }}>Details</th>
                  </tr>
                </thead>
                <tbody>
                  {batchResult.documents.map((d) => (
                    <tr key={d.document_id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                      <td style={{ padding: '0.75rem 1rem', fontFamily: 'monospace', color: 'var(--text-primary)' }}>{d.original_filename}</td>
                      <td style={{ padding: '0.75rem 1rem', fontFamily: 'monospace', color: 'var(--text-secondary)' }}>{d.document_id}</td>
                      <td style={{ padding: '0.75rem 1rem' }}>{getStatusBadge(d.status)}</td>
                      <td style={{ padding: '0.75rem 1rem', color: 'var(--text-secondary)' }}>{(d.file_size / 1024).toFixed(1)} KB</td>
                      <td style={{ padding: '0.75rem 1rem', fontFamily: 'monospace', color: 'var(--text-secondary)' }} title={d.document_hash}>
                        {d.document_hash.substring(0, 12)}...
                      </td>
                      <td style={{ padding: '0.75rem 1rem' }}>
                        {d.duplicate_reason && (
                          <div style={{ color: '#fbbf24', fontSize: '0.75rem' }}>{d.duplicate_reason}</div>
                        )}
                        {d.error_message && (
                          <div style={{ color: '#f87171', fontSize: '0.75rem' }}>{d.error_message}</div>
                        )}
                        {d.s3_key && (
                          <div style={{ color: '#94a3b8', fontFamily: 'monospace', fontSize: '0.75rem' }}>{d.s3_key}</div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
