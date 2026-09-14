import { formatMoney } from '../utils.ts';
import React, { useEffect, useState } from 'react';
import { DashboardStats, InvoiceListItem, BatchResponse } from '../types/index.ts';
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
  Shield,
  Users,
  BookOpen,
  Calculator,
  Filter,
  Layers,
  Calendar,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Info,
} from 'lucide-react';

interface DashboardPageProps {
  onSelectInvoice: (invoiceId: string) => void;
  onViewAllInvoices: () => void;
  onNavigatePolicy?: () => void;
  onNavigateVendors?: () => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({
  onSelectInvoice,
  onViewAllInvoices,
  onNavigatePolicy,
  onNavigateVendors,
}) => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [recentInvoices, setRecentInvoices] = useState<InvoiceListItem[]>([]);
  const [batches, setBatches] = useState<BatchResponse[]>([]);
  const [selectedBatch, setSelectedBatch] = useState<string>('');
  const [selectedDateRange, setSelectedDateRange] = useState<string>('all_time');
  const [decisionFilter, setDecisionFilter] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDashboardData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [statsData, listData, batchesData] = await Promise.all([
        api.getDashboardStats({
          batch_id: selectedBatch || undefined,
          date_range: selectedDateRange !== 'all_time' ? selectedDateRange : undefined,
        }),
        api.listInvoices({ limit: 50, offset: 0 }),
        api.listBatches().catch(() => ({ items: [], limit: 50, offset: 0, total: 0 })),
      ]);
      setStats(statsData);
      setRecentInvoices(listData.items);
      setBatches(batchesData.items || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load dashboard metrics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, [selectedBatch, selectedDateRange]);

  // Filter invoices if decision filter is clicked
  const filteredInvoices = recentInvoices.filter((inv) => {
    if (!decisionFilter) return true;
    if (decisionFilter === 'AUTO_APPROVE') {
      return (inv.final_state === 'AUTO_APPROVED' || (inv.decision === 'AUTO_APPROVE' && !inv.review_decision));
    }
    if (decisionFilter === 'HUMAN_APPROVED') {
      return inv.final_state === 'HUMAN_APPROVED' || inv.review_decision === 'APPROVE' || inv.processing_status === 'HUMAN_APPROVED';
    }
    if (decisionFilter === 'MANUAL_REVIEW') {
      return inv.final_state === 'MANUAL_REVIEW' || (inv.processing_status === 'MANUAL_REVIEW' && !inv.review_decision && inv.decision !== 'AUTO_APPROVE');
    }
    if (decisionFilter === 'BLOCK') {
      return inv.final_state === 'BLOCKED' || inv.decision === 'BLOCK' || inv.processing_status === 'BLOCKED';
    }
    if (decisionFilter === 'DUPLICATE') {
      return (
        inv.processing_status === 'BLOCKED' &&
        (inv.invoice_id.includes('DUP') || JSON.stringify(inv).toUpperCase().includes('DUPLICATE'))
      );
    }
    return true;
  });

  return (
    <div>
      {/* Top Header & Refresh */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.75rem', fontWeight: 800, letterSpacing: '-0.02em', margin: 0 }}>Accounts Payable Overview</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', margin: '0.25rem 0 0 0' }}>
            Live verification metrics, autonomous PDF understanding, and corporate policy enforcement
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <button
            id="refresh-dashboard-btn"
            className="btn btn-secondary"
            onClick={fetchDashboardData}
            disabled={loading}
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="alert alert-danger" style={{ marginBottom: '1.5rem' }}>
          <AlertTriangle size={18} /> {error}
        </div>
      )}

      {/* Enterprise Policy & Vendor Context Banner */}
      <div
        className="card"
        style={{
          marginBottom: '1.5rem',
          background: 'linear-gradient(135deg, rgba(30, 58, 138, 0.25), rgba(15, 23, 42, 0.6))',
          borderColor: 'rgba(59, 130, 246, 0.3)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <div style={{ padding: '0.75rem', background: 'rgba(59, 130, 246, 0.15)', borderRadius: 'var(--radius-md)' }}>
              <Shield size={24} color="var(--accent-blue)" />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ fontWeight: 800, fontSize: '1rem', color: 'var(--text-primary)' }}>
                  LedgerGuard Demo Corporation
                </span>
                <span className="badge badge-approved" style={{ fontSize: '0.7rem' }}>Active Policy</span>
              </div>
              <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                Auto-Approval Ceiling: <strong>$5,000.00</strong> &bull; High-Value Review: <strong>$25,000.00</strong> &bull; Supported Currencies: <strong>USD, EUR, GBP</strong>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '0.75rem' }}>
            {onNavigatePolicy && (
              <button className="btn btn-secondary" style={{ fontSize: '0.8125rem', padding: '0.4rem 0.75rem' }} onClick={onNavigatePolicy}>
                <BookOpen size={14} /> Company Policy
              </button>
            )}
            {onNavigateVendors && (
              <button className="btn btn-secondary" style={{ fontSize: '0.8125rem', padding: '0.4rem 0.75rem' }} onClick={onNavigateVendors}>
                <Users size={14} /> Vendor Master
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Filter Controls Bar */}
      <div
        className="card"
        style={{
          marginBottom: '1.5rem',
          padding: '0.875rem 1.25rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '1rem',
          background: 'rgba(15, 23, 42, 0.5)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.875rem', fontWeight: 600 }}>
            <Filter size={16} color="var(--accent-cyan)" /> Aggregation Filters:
          </div>

          {/* Batch Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <Layers size={14} color="var(--text-muted)" />
            <select
              id="dashboard-batch-filter"
              value={selectedBatch}
              onChange={(e) => setSelectedBatch(e.target.value)}
              style={{
                background: 'var(--bg-secondary)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-sm)',
                padding: '0.35rem 0.65rem',
                fontSize: '0.8125rem',
              }}
            >
              <option value="">All Invoices (All Batches)</option>
              {batches.map((b) => (
                <option key={b.batch_id} value={b.batch_id}>
                  Batch {b.batch_id} ({b.document_count} docs)
                </option>
              ))}
            </select>
          </div>

          {/* Date Range Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <Calendar size={14} color="var(--text-muted)" />
            <select
              id="dashboard-date-filter"
              value={selectedDateRange}
              onChange={(e) => setSelectedDateRange(e.target.value)}
              style={{
                background: 'var(--bg-secondary)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-sm)',
                padding: '0.35rem 0.65rem',
                fontSize: '0.8125rem',
              }}
            >
              <option value="all_time">All Time</option>
              <option value="today">Today</option>
              <option value="7_days">Last 7 Days</option>
              <option value="30_days">Last 30 Days</option>
            </select>
          </div>
        </div>

        {/* Active Decision Filter Badge */}
        {decisionFilter && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>Filtered by verdict:</span>
            <span className="badge badge-warning" style={{ fontSize: '0.75rem', fontWeight: 700 }}>
              {decisionFilter}
            </span>
            <button
              className="btn btn-secondary"
              style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}
              onClick={() => setDecisionFilter(null)}
            >
              Clear Filter
            </button>
          </div>
        )}
      </div>

      {/* ========================================================================= */}
      {/* PHASE 8: AP FINANCIAL SUMMARY SECTION */}
      {/* ========================================================================= */}
      <div className="card" style={{ marginBottom: '1.5rem', border: '1px solid rgba(14, 165, 233, 0.3)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.5rem' }}>
          <div>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 800, margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Calculator size={20} color="var(--accent-cyan)" /> AP Financial Summary
            </h3>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', margin: '0.2rem 0 0 0' }}>
              Strict Decimal monetary aggregation from verified invoice records &bull; Zero floating-point accumulation
            </p>
          </div>
          <span className="badge badge-info" style={{ fontSize: '0.75rem' }}>
            Phase 8 Live Financial Reconciliation
          </span>
        </div>

        {/* Primary Financial Metrics Grid */}
        <div className="stats-grid" style={{ marginBottom: '1.5rem' }}>
          <div className="stat-card" style={{ borderColor: 'rgba(56, 189, 248, 0.2)' }}>
            <div className="stat-label">Total Invoiced Value</div>
            <div className="stat-value" style={{ color: 'var(--text-primary)', fontSize: '1.4rem' }}>
              ${stats ? formatMoney(stats.total_invoice_value) : '--'}
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
              Sum of declared invoice totals
            </div>
          </div>

          <div className="stat-card" style={{ borderColor: 'rgba(56, 189, 248, 0.2)' }}>
            <div className="stat-label">Total Subtotal</div>
            <div className="stat-value" style={{ color: 'var(--accent-cyan)', fontSize: '1.4rem' }}>
              ${stats ? formatMoney(stats.total_subtotal) : '--'}
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
              Base line-item subtotal
            </div>
          </div>

          <div className="stat-card" style={{ borderColor: 'rgba(56, 189, 248, 0.2)' }}>
            <div className="stat-label">Total Discounts</div>
            <div className="stat-value" style={{ color: '#a78bfa', fontSize: '1.4rem' }}>
              ${stats ? formatMoney(stats.total_discount) : '--'}
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
              Explicit stated discounts
            </div>
          </div>

          <div className="stat-card" style={{ borderColor: 'rgba(56, 189, 248, 0.2)' }}>
            <div className="stat-label">Total Shipping</div>
            <div className="stat-value" style={{ color: '#38bdf8', fontSize: '1.4rem' }}>
              ${stats ? formatMoney(stats.total_shipping) : '--'}
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
              Freight & logistics
            </div>
          </div>

          <div className="stat-card" style={{ borderColor: 'rgba(56, 189, 248, 0.2)' }}>
            <div className="stat-label">Total Tax</div>
            <div className="stat-value" style={{ color: '#f59e0b', fontSize: '1.4rem' }}>
              ${stats ? formatMoney(stats.total_tax) : '--'}
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
              Explicit stated taxes
            </div>
          </div>

          <div className="stat-card" style={{ background: 'rgba(16, 185, 129, 0.08)', borderColor: 'rgba(16, 185, 129, 0.3)' }}>
            <div className="stat-label">Calculated / Estimated Payable</div>
            <div className="stat-value" style={{ color: '#34d399', fontSize: '1.4rem' }}>
              ${stats ? formatMoney(stats.estimated_payable_amount) : '--'}
            </div>
            <div style={{ fontSize: '0.75rem', color: '#10b981', marginTop: '0.25rem', fontWeight: 600 }}>
              Coverage: {stats?.estimated_payable_invoices_count || 0} / {stats?.total_invoices || 0} Invoices ({stats?.estimated_payable_coverage_pct || 0}%)
            </div>
          </div>
        </div>

        {/* Financial Reconciliation Formula Card */}
        <div
          style={{
            padding: '1rem 1.25rem',
            background: 'rgba(15, 23, 42, 0.6)',
            borderRadius: 'var(--radius-md)',
            border: '1px dashed rgba(14, 165, 233, 0.3)',
            marginBottom: '1.5rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
            <Calculator size={16} color="var(--accent-cyan)" />
            <span style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              Deterministic Financial Reconciliation Formula
            </span>
          </div>
          <div
            style={{
              fontFamily: 'monospace',
              fontSize: '0.9375rem',
              color: 'var(--accent-cyan)',
              background: 'rgba(0, 0, 0, 0.3)',
              padding: '0.6rem 1rem',
              borderRadius: 'var(--radius-sm)',
              display: 'flex',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: '0.5rem',
            }}
          >
            <span>Subtotal (${stats ? formatMoney(stats.total_subtotal) : '0.00'})</span>
            <span style={{ color: 'var(--text-muted)' }}>&minus;</span>
            <span style={{ color: '#a78bfa' }}>Discounts (${stats ? formatMoney(stats.total_discount) : '0.00'})</span>
            <span style={{ color: 'var(--text-muted)' }}>+</span>
            <span style={{ color: '#38bdf8' }}>Shipping (${stats ? formatMoney(stats.total_shipping) : '0.00'})</span>
            <span style={{ color: 'var(--text-muted)' }}>+</span>
            <span style={{ color: '#f59e0b' }}>Tax (${stats ? formatMoney(stats.total_tax) : '0.00'})</span>
            <span style={{ color: 'var(--text-muted)' }}>=</span>
            <span style={{ color: '#34d399', fontWeight: 800 }}>Estimated Payable (${stats ? formatMoney(stats.estimated_payable_amount) : '0.00'})</span>
          </div>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: '0.5rem 0 0 0' }}>
            * Note: Estimated Payable represents calculated AP liability from source documents with complete components. Incomplete documents (e.g. tax NOT_STATED) are excluded from payable calculation coverage without fabrication. Does not constitute executed disbursement.
          </p>
        </div>

        {/* Decision Value Breakdown & Data Quality Cards */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
          {/* Decision Value Breakdown (Clickable Drill-down) */}
          <div
            style={{
              padding: '1rem',
              background: 'rgba(30, 41, 59, 0.5)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-color)',
            }}
          >
            <div style={{ fontSize: '0.875rem', fontWeight: 700, marginBottom: '0.75rem', color: 'var(--text-primary)' }}>
              Decision Value Breakdown (Click to filter)
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <div
                onClick={() => setDecisionFilter(decisionFilter === 'AUTO_APPROVE' ? null : 'AUTO_APPROVE')}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '0.5rem 0.75rem',
                  borderRadius: 'var(--radius-sm)',
                  background: decisionFilter === 'AUTO_APPROVE' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(15, 23, 42, 0.4)',
                  cursor: 'pointer',
                  border: '1px solid rgba(16, 185, 129, 0.3)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <CheckCircle2 size={16} color="#34d399" />
                  <span style={{ fontSize: '0.8125rem', fontWeight: 600 }}>Auto-Approved Value</span>
                </div>
                <span style={{ fontWeight: 800, color: '#34d399' }}>
                  ${stats ? formatMoney(stats.auto_approved_value) : '0.00'}
                </span>
              </div>

              <div
                onClick={() => setDecisionFilter(decisionFilter === 'HUMAN_APPROVED' ? null : 'HUMAN_APPROVED')}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '0.5rem 0.75rem',
                  borderRadius: 'var(--radius-sm)',
                  background: decisionFilter === 'HUMAN_APPROVED' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(15, 23, 42, 0.4)',
                  cursor: 'pointer',
                  border: '1px solid rgba(16, 185, 129, 0.4)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <CheckCircle size={16} color="#10b981" />
                  <span style={{ fontSize: '0.8125rem', fontWeight: 600 }}>Human-Approved Value</span>
                </div>
                <span style={{ fontWeight: 800, color: '#10b981' }}>
                  ${stats ? formatMoney(stats.human_approved_value ?? '0.00') : '0.00'}
                </span>
              </div>

              <div
                onClick={() => setDecisionFilter(decisionFilter === 'MANUAL_REVIEW' ? null : 'MANUAL_REVIEW')}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '0.5rem 0.75rem',
                  borderRadius: 'var(--radius-sm)',
                  background: decisionFilter === 'MANUAL_REVIEW' ? 'rgba(245, 158, 11, 0.2)' : 'rgba(15, 23, 42, 0.4)',
                  cursor: 'pointer',
                  border: '1px solid rgba(245, 158, 11, 0.3)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <AlertTriangle size={16} color="#fbbf24" />
                  <span style={{ fontSize: '0.8125rem', fontWeight: 600 }}>Manual-Review Value</span>
                </div>
                <span style={{ fontWeight: 800, color: '#fbbf24' }}>
                  ${stats ? formatMoney(stats.manual_review_value) : '0.00'}
                </span>
              </div>

              <div
                onClick={() => setDecisionFilter(decisionFilter === 'BLOCK' ? null : 'BLOCK')}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '0.5rem 0.75rem',
                  borderRadius: 'var(--radius-sm)',
                  background: decisionFilter === 'BLOCK' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(15, 23, 42, 0.4)',
                  cursor: 'pointer',
                  border: '1px solid rgba(239, 68, 68, 0.3)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <ShieldAlert size={16} color="#f87171" />
                  <span style={{ fontSize: '0.8125rem', fontWeight: 600 }}>Blocked Value</span>
                </div>
                <span style={{ fontWeight: 800, color: '#f87171' }}>
                  ${stats ? formatMoney(stats.blocked_value) : '0.00'}
                </span>
              </div>

              <div
                onClick={() => setDecisionFilter(decisionFilter === 'DUPLICATE' ? null : 'DUPLICATE')}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '0.5rem 0.75rem',
                  borderRadius: 'var(--radius-sm)',
                  background: decisionFilter === 'DUPLICATE' ? 'rgba(167, 139, 250, 0.2)' : 'rgba(15, 23, 42, 0.4)',
                  cursor: 'pointer',
                  border: '1px solid rgba(167, 139, 250, 0.3)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Layers size={16} color="#a78bfa" />
                  <span style={{ fontSize: '0.8125rem', fontWeight: 600 }}>Flagged Duplicates Value</span>
                </div>
                <span style={{ fontWeight: 800, color: '#a78bfa' }}>
                  ${stats ? formatMoney(stats.duplicate_value) : '0.00'}
                </span>
              </div>
            </div>
          </div>

          {/* Extraction Quality & Ingestion Health */}
          <div
            style={{
              padding: '1rem',
              background: 'rgba(30, 41, 59, 0.5)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-color)',
            }}
          >
            <div style={{ fontSize: '0.875rem', fontWeight: 700, marginBottom: '0.75rem', color: 'var(--text-primary)' }}>
              Document Extraction Health & Quality
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>Total Invoices Ingested:</span>
                <span style={{ fontWeight: 700 }}>{stats?.total_invoices || 0}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>Extraction Succeeded:</span>
                <span style={{ fontWeight: 700, color: '#34d399' }}>{stats?.extraction_success_count || (stats?.total_invoices || 0)}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>Low Confidence (&lt; 0.85):</span>
                <span style={{ fontWeight: 700, color: '#fbbf24' }}>{stats?.low_confidence_count || 0}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>Extraction Failed:</span>
                <span style={{ fontWeight: 700, color: '#f87171' }}>{stats?.extraction_failed_count || 0}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>Payable Calculation Coverage:</span>
                <span style={{ fontWeight: 700, color: '#38bdf8' }}>{stats?.estimated_payable_coverage_pct || 0}%</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Operations Overview Grid */}
      <div className="stats-grid" style={{ marginBottom: '1.5rem' }}>
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
          <div className="stat-label">Human-Approved</div>
          <div className="stat-value" style={{ color: '#10b981' }}>
            {stats ? stats.human_approved_count ?? 0 : '--'}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            Auditor verified approvals
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
            ${stats ? formatMoney(stats.total_verified_spend_usd) : '--'}
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
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <h3 className="card-title" style={{ margin: 0 }}>
              <Clock size={18} color="var(--accent-cyan)" /> Recent Invoice Activity
            </h3>
            {decisionFilter && (
              <span className="badge badge-warning" style={{ fontSize: '0.75rem' }}>
                Showing: {decisionFilter}
              </span>
            )}
          </div>
          <button id="view-all-invoices-btn" className="btn btn-secondary" style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem' }} onClick={onViewAllInvoices}>
            View All <ArrowRight size={12} />
          </button>
        </div>

        {filteredInvoices.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', padding: '2rem', textAlign: 'center' }}>
            {decisionFilter ? `No invoices matching verdict filter "${decisionFilter}".` : 'No invoices ingested yet.'}
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
                {filteredInvoices.slice(0, 10).map((inv) => (
                  <tr key={inv.invoice_id} onClick={() => onSelectInvoice(inv.invoice_id)} style={{ cursor: 'pointer' }}>
                    <td style={{ fontWeight: 700, color: 'var(--accent-cyan)' }}>
                      <code>{inv.invoice_id}</code>
                    </td>
                    <td>{inv.vendor_name}</td>
                    <td>{inv.invoice_date}</td>
                    <td style={{ fontWeight: 600 }}>
                      {inv.total !== null && inv.total !== undefined ? `$${formatMoney(inv.total)}` : '--'}
                    </td>
                    <td><StatusBadge status={(inv.final_state || inv.processing_status) as any} /></td>
                    <td>
                      <DecisionBadge
                        decision={inv.automated_decision || inv.original_decision || inv.decision}
                        reviewDecision={inv.human_review_decision || inv.review_decision}
                      />
                    </td>
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
