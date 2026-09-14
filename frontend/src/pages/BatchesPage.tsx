import React, { useEffect, useState } from 'react';
import { Layers, Plus, RefreshCw, ArrowRight } from 'lucide-react';
import { api } from '../services/api.ts';
import { BatchResponse } from '../types/index.ts';

interface BatchesPageProps {
  onSelectBatch: (batchId: string) => void;
  onNewBatch: () => void;
}

export const BatchesPage: React.FC<BatchesPageProps> = ({ onSelectBatch, onNewBatch }) => {
  const [batches, setBatches] = useState<BatchResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchBatches = async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await api.listBatches({ limit: 50 });
      setBatches(resp.items);
    } catch (err: any) {
      setError(err.message || 'Failed to load batches.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBatches();
  }, []);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return <span className="badge badge-success">COMPLETED</span>;
      case 'COMPLETED_WITH_EXCEPTIONS':
        return <span className="badge badge-warning">EXCEPTIONS</span>;
      case 'VALIDATING':
      case 'UPLOADING':
      case 'QUEUING':
        return <span className="badge badge-info">{status}</span>;
      case 'FAILED':
        return <span className="badge badge-error">FAILED</span>;
      default:
        return <span className="badge badge-secondary">{status}</span>;
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>Batch Ingestion History</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginTop: '0.25rem' }}>
            Overview of all multi-document batches ingested into LedgerGuard.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button
            onClick={fetchBatches}
            disabled={loading}
            className="btn btn-secondary"
            style={{ fontSize: '0.8125rem' }}
          >
            <RefreshCw size={14} style={{ display: 'inline', marginRight: '4px' }} /> Refresh
          </button>
          <button
            onClick={onNewBatch}
            className="btn btn-primary"
            style={{ fontSize: '0.8125rem' }}
          >
            <Plus size={14} style={{ display: 'inline', marginRight: '4px' }} /> Ingest New Batch
          </button>
        </div>
      </div>

      {error && (
        <div style={{ padding: '0.75rem', background: 'rgba(244, 63, 94, 0.1)', border: '1px solid rgba(244, 63, 94, 0.3)', borderRadius: '6px', color: '#fda4af', fontSize: '0.8125rem' }}>
          {error}
        </div>
      )}

      {/* Batches Table */}
      <div className="card" style={{ padding: '0', overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            Loading batches...
          </div>
        ) : batches.length === 0 ? (
          <div style={{ padding: '3rem 1.5rem', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            <Layers size={36} color="#64748b" style={{ margin: '0 auto 1rem auto' }} />
            <p>No batches found.</p>
            <button
              onClick={onNewBatch}
              className="btn btn-primary"
              style={{ marginTop: '1rem', fontSize: '0.8125rem' }}
            >
              Ingest Your First Batch
            </button>
          </div>
        ) : (
          <table style={{ width: '100%', fontSize: '0.8125rem', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: 'rgba(15, 23, 42, 0.6)', borderBottom: '1px solid var(--border-color)', color: 'var(--text-secondary)', textAlign: 'left' }}>
                <th style={{ padding: '0.75rem 1rem' }}>Batch ID</th>
                <th style={{ padding: '0.75rem 1rem' }}>Status</th>
                <th style={{ padding: '0.75rem 1rem' }}>Source</th>
                <th style={{ padding: '0.75rem 1rem', textAlign: 'center' }}>Total Files</th>
                <th style={{ padding: '0.75rem 1rem', textAlign: 'center' }}>Accepted</th>
                <th style={{ padding: '0.75rem 1rem', textAlign: 'center' }}>Duplicates</th>
                <th style={{ padding: '0.75rem 1rem', textAlign: 'center' }}>Rejected</th>
                <th style={{ padding: '0.75rem 1rem' }}>Created At</th>
                <th style={{ padding: '0.75rem 1rem', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {batches.map((b) => (
                <tr
                  key={b.batch_id}
                  onClick={() => onSelectBatch(b.batch_id)}
                  style={{ borderBottom: '1px solid var(--border-color)', cursor: 'pointer' }}
                >
                  <td style={{ padding: '0.75rem 1rem', fontFamily: 'monospace', fontWeight: 600, color: '#818cf8' }}>
                    {b.batch_id}
                  </td>
                  <td style={{ padding: '0.75rem 1rem' }}>{getStatusBadge(b.status)}</td>
                  <td style={{ padding: '0.75rem 1rem', fontFamily: 'monospace', color: 'var(--text-secondary)' }}>{b.source}</td>
                  <td style={{ padding: '0.75rem 1rem', textAlign: 'center', color: 'var(--text-primary)' }}>{b.document_count}</td>
                  <td style={{ padding: '0.75rem 1rem', textAlign: 'center', color: '#34d399', fontWeight: 600 }}>{b.accepted_count}</td>
                  <td style={{ padding: '0.75rem 1rem', textAlign: 'center', color: '#fbbf24' }}>{b.duplicate_count}</td>
                  <td style={{ padding: '0.75rem 1rem', textAlign: 'center', color: '#f87171' }}>{b.rejected_count}</td>
                  <td style={{ padding: '0.75rem 1rem', color: 'var(--text-secondary)' }}>
                    {new Date(b.created_at).toLocaleString()}
                  </td>
                  <td style={{ padding: '0.75rem 1rem', textAlign: 'right' }}>
                    <span style={{ color: '#818cf8', display: 'inline-flex', alignItems: 'center', gap: '2px', fontWeight: 500 }}>
                      Details <ArrowRight size={12} />
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
