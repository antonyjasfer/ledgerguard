import { formatMoney } from '../utils.ts';
import React, { useEffect, useState } from 'react';
import { InvoiceListItem, ProcessingState } from '../types/index.ts';
import { api } from '../services/api.ts';
import { StatusBadge, DecisionBadge, RiskBadge } from '../components/Badges.tsx';
import { Search, Filter, RefreshCw, ChevronLeft, ChevronRight } from 'lucide-react';

interface InvoicesPageProps {
  onSelectInvoice: (invoiceId: string) => void;
}

export const InvoicesPage: React.FC<InvoicesPageProps> = ({ onSelectInvoice }) => {
  const [invoices, setInvoices] = useState<InvoiceListItem[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<ProcessingState | ''>('');
  const [page, setPage] = useState(0);
  const pageSize = 10;

  const fetchInvoices = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.listInvoices({
        limit: pageSize,
        offset: page * pageSize,
        status: statusFilter,
        search: searchTerm.trim() || undefined,
      });
      setInvoices(res.items);
      setTotalCount(res.total);
    } catch (err: any) {
      setError(err.message || 'Failed to retrieve invoices');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInvoices();
  }, [page, statusFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(0);
    fetchInvoices();
  };

  const totalPages = Math.ceil(totalCount / pageSize);

  const filterPills: Array<{ label: string; val: ProcessingState | '' }> = [
    { label: 'All', val: '' },
    { label: 'Auto-Approved', val: 'AUTO_APPROVED' },
    { label: 'Manual Review', val: 'MANUAL_REVIEW' },
    { label: 'Blocked', val: 'BLOCKED' },
    { label: 'Processing', val: 'AGENT_PROCESSING' },
    { label: 'Received', val: 'RECEIVED' },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <div>
          <h2 style={{ fontSize: '1.75rem', fontWeight: 800 }}>Invoice Directory</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            Filter, inspect evidence, and trace audit trails for all Accounts Payable records
          </p>
        </div>
        <button id="refresh-invoices-btn" className="btn btn-secondary" onClick={fetchInvoices} disabled={loading}>
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', justifyContent: 'space-between', alignItems: 'center' }}>
          <form onSubmit={handleSearchSubmit} style={{ display: 'flex', gap: '0.5rem', flex: 1, minWidth: '280px' }}>
            <div style={{ position: 'relative', flex: 1 }}>
              <Search size={16} style={{ position: 'absolute', left: '10px', top: '12px', color: 'var(--text-muted)' }} />
              <input
                id="search-invoices-input"
                className="form-input"
                style={{ paddingLeft: '32px' }}
                placeholder="Search by Invoice ID, Number, or Vendor Name..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            <button id="search-invoices-btn" type="submit" className="btn btn-secondary">Search</button>
          </form>

          <div style={{ display: 'flex', gap: '0.375rem', flexWrap: 'wrap' }}>
            {filterPills.map((pill) => (
              <button
                key={pill.label}
                id={`filter-pill-${pill.val || 'all'}`}
                className={`btn ${statusFilter === pill.val ? 'btn-primary' : 'btn-secondary'}`}
                style={{ padding: '0.35rem 0.75rem', fontSize: '0.75rem' }}
                onClick={() => {
                  setStatusFilter(pill.val);
                  setPage(0);
                }}
              >
                {pill.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && (
        <div className="alert alert-danger">{error}</div>
      )}

      {/* Table */}
      <div className="card" style={{ padding: 0 }}>
        {loading && invoices.length === 0 ? (
          <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
            Loading invoices from DynamoDB repository...
          </div>
        ) : invoices.length === 0 ? (
          <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
            No invoices matching query criteria found.
          </div>
        ) : (
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Invoice ID</th>
                  <th>Vendor Number</th>
                  <th>Vendor Entity</th>
                  <th>Invoice Date</th>
                  <th>Total</th>
                  <th>Status</th>
                  <th>Decision</th>
                  <th>Risk Tier</th>
                </tr>
              </thead>
              <tbody>
                {invoices.map((inv) => (
                  <tr key={inv.invoice_id} id={`invoice-row-${inv.invoice_id}`} onClick={() => onSelectInvoice(inv.invoice_id)}>
                    <td style={{ fontWeight: 700, color: 'var(--accent-cyan)' }}>
                      <code>{inv.invoice_id}</code>
                    </td>
                    <td>{inv.invoice_number}</td>
                    <td>{inv.vendor_name}</td>
                    <td>{inv.invoice_date}</td>
                    <td style={{ fontWeight: 600 }}></td>
                    <td><StatusBadge status={inv.processing_status} /></td>
                    <td><DecisionBadge decision={inv.decision} /></td>
                    <td><RiskBadge level={inv.risk_level} score={inv.risk_score} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Controls */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem', borderTop: '1px solid var(--border-color)' }}>
          <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
            Showing {invoices.length > 0 ? page * pageSize + 1 : 0}–{Math.min((page + 1) * pageSize, totalCount)} of {totalCount} invoices
          </span>

          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              id="pagination-prev-btn"
              className="btn btn-secondary"
              style={{ padding: '0.35rem 0.6rem' }}
              disabled={page === 0}
              onClick={() => setPage(p => Math.max(0, p - 1))}
            >
              <ChevronLeft size={16} /> Prev
            </button>
            <span style={{ display: 'flex', alignItems: 'center', fontSize: '0.8125rem', padding: '0 0.5rem' }}>
              Page {totalPages > 0 ? page + 1 : 0} of {totalPages}
            </span>
            <button
              id="pagination-next-btn"
              className="btn btn-secondary"
              style={{ padding: '0.35rem 0.6rem' }}
              disabled={page >= totalPages - 1}
              onClick={() => setPage(p => p + 1)}
            >
              Next <ChevronRight size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
