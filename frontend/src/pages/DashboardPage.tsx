import { formatMoney } from '../utils.ts';
import React, { useEffect, useState } from 'react';
import { DashboardStats, InvoiceListItem } from '../types/index.ts';
import { api } from '../services/api.ts';
import { StatusBadge, DecisionBadge, RiskBadge } from '../components/Badges.tsx';
import { ArchitectureDiagram } from '../components/ArchitectureDiagram.tsx';
import {
  FileText,
  Clock,
  CheckCircle,
  AlertTriangle,
  ShieldAlert,
  DollarSign,
  TrendingUp,
  Percent,
  RefreshCw,
  ArrowRight,
} from 'lucide-react';

interface DashboardPageProps {
  onSelectInvoice: (invoiceId: string) => void;
  onViewAllInvoices: () => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({ onSelectInvoice, onViewAllInvoices }) => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [recentInvoices, setRecentInvoices] = useState<InvoiceListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDashboardData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [statsData, listData] = await Promise.all([
        api.getDashboardStats(),
        api.listInvoices({ limit: 6, offset: 0 }),
      ]);
      setStats(statsData);
      setRecentInvoices(listData.items);
    } catch (err: any) {
      setError(err.message || 'Failed to load dashboard metrics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <div>
          <h2 style={{ fontSize: '1.75rem', fontWeight: 800, letterSpacing: '-0.02em' }}>Accounts Payable Overview</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            Live verification metrics and autonomous agent operational status
          </p>
        </div>
        <button
          id="refresh-dashboard-btn"
          className="btn btn-secondary"
          onClick={fetchDashboardData}
          disabled={loading}
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      {error && (
        <div className="alert alert-danger">
          <AlertTriangle size={18} /> {error}
        </div>
      )}

      {/* Metrics Grid */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-label">Total Ingested</div>
          <div className="stat-value" style={{ color: 'var(--text-primary)' }}>
            {stats ? stats.total_invoices : '--'}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            {stats ? `${stats.pending_invoices} pending processing` : ''}
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Auto-Approved</div>
          <div className="stat-value" style={{ color: '#34d399' }}>
            {stats ? stats.auto_approved_count : '--'}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            {stats ? `${stats.auto_approval_rate_pct}% approval rate` : ''}
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Manual Review</div>
          <div className="stat-value" style={{ color: '#fbbf24' }}>
            {stats ? stats.manual_review_count : '--'}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            Awaiting human auditor review
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Blocked Invoices</div>
          <div className="stat-value" style={{ color: '#f87171' }}>
            {stats ? stats.blocked_count : '--'}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            Protected by Decision Guard
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Verified Spend</div>
          <div className="stat-value" style={{ color: 'var(--accent-cyan)' }}>
            ${stats ? stats.total_amount_usd.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '--'}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            Processed volume
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Avg Risk Score</div>
          <div className="stat-value" style={{ color: stats && stats.average_risk_score > 50 ? '#f87171' : 'var(--text-primary)' }}>
            {stats ? `${stats.average_risk_score} / 100` : '--'}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            Multi-factor composite
          </div>
        </div>
      </div>

      {/* AWS Architecture Diagram */}
      <ArchitectureDiagram />

      {/* Recent Activity Table */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h3 className="card-title" style={{ margin: 0 }}>
            <Clock size={18} color="var(--accent-cyan)" /> Recent Invoice Activity
          </h3>
          <button id="view-all-invoices-btn" className="btn btn-secondary" style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem' }} onClick={onViewAllInvoices}>
            View All <ArrowRight size={12} />
          </button>
        </div>

        {recentInvoices.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', padding: '2rem', textAlign: 'center' }}>
            No invoices ingested yet. Click <strong>Ingest Invoice</strong> above to start.
          </div>
        ) : (
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Invoice ID</th>
                  <th>Vendor</th>
                  <th>Date</th>
                  <th>Total</th>
                  <th>Status</th>
                  <th>Decision</th>
                  <th>Risk</th>
                </tr>
              </thead>
              <tbody>
                {recentInvoices.map((inv) => (
                  <tr key={inv.invoice_id} onClick={() => onSelectInvoice(inv.invoice_id)}>
                    <td style={{ fontWeight: 700, color: 'var(--accent-cyan)' }}>
                      <code>{inv.invoice_id}</code>
                    </td>
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
      </div>
    </div>
  );
};
