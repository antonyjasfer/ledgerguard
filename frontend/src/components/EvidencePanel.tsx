import React from 'react';
import { formatMoney, formatNumber } from '../utils.ts';
import { InvoiceRecord } from '../types/index.ts';
import {
  Calculator,
  Copy,
  History,
  FileCheck,
  ShieldAlert,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Building,
  ShieldCheck,
  Layers,
} from 'lucide-react';

interface EvidencePanelProps {
  evidence?: any;
  invoice?: InvoiceRecord | null;
}

export const EvidencePanel: React.FC<EvidencePanelProps> = ({ evidence, invoice }) => {
  if (!evidence) {
    return (
      <div className="card">
        <h3 className="card-title">Verification Evidence</h3>
        <p style={{ color: 'var(--text-muted)' }}>No verification evidence recorded yet. Invoice is pending processing.</p>
      </div>
    );
  }

  // Support both VerificationDecision (evidence array) and direct dictionary formats
  const evidenceList: any[] = Array.isArray(evidence.evidence) ? evidence.evidence : [];

  const findTool = (nameSnippet: string) => {
    return evidenceList.find((e: any) =>
      e.source === nameSnippet ||
      (typeof e.source === 'string' && e.source.toLowerCase().includes(nameSnippet.toLowerCase()))
    );
  };

  // 1. Arithmetic Normalization
  const arithItem = findTool('arithmetic');
  const arithDetails = arithItem?.details || {};
  const arithRaw = evidence.arithmetic || {};

  const arithPassed = arithDetails.passed !== undefined
    ? Boolean(arithDetails.passed)
    : arithItem?.finding === 'PASS'
      ? true
      : arithRaw.passed !== undefined
        ? Boolean(arithRaw.passed)
        : arithRaw.is_valid !== undefined
          ? Boolean(arithRaw.is_valid)
          : true;

  const declaredSubtotal = arithDetails.actual_subtotal ?? arithDetails.declared_subtotal ?? arithRaw.actual_subtotal ?? arithRaw.declared_subtotal ?? invoice?.subtotal;
  const computedSubtotal = arithDetails.expected_subtotal ?? arithDetails.computed_subtotal ?? arithRaw.expected_subtotal ?? arithRaw.computed_subtotal ?? invoice?.subtotal;
  const declaredDiscount = arithDetails.actual_discount ?? arithDetails.discount ?? arithRaw.actual_discount ?? arithRaw.discount ?? invoice?.discount ?? '0.00';
  const declaredShipping = arithDetails.actual_shipping ?? arithDetails.shipping ?? arithRaw.actual_shipping ?? arithRaw.shipping ?? (invoice as any)?.shipping ?? '0.00';
  const declaredTax = arithDetails.actual_tax ?? arithDetails.tax ?? arithRaw.actual_tax ?? arithRaw.tax ?? invoice?.tax;
  const declaredTotal = arithDetails.actual_total ?? arithDetails.declared_total ?? arithRaw.actual_total ?? arithRaw.declared_total ?? invoice?.total;
  const computedTotal = arithDetails.expected_total ?? arithDetails.computed_total ?? arithRaw.expected_total ?? arithRaw.computed_total ?? invoice?.total;
  const difference = arithDetails.difference ?? arithDetails.discrepancy ?? arithRaw.difference ?? arithRaw.discrepancy ?? '0.00';
  const arithDetailsList: string[] = Array.isArray(arithDetails.details)
    ? arithDetails.details
    : Array.isArray(arithRaw.discrepancy_details)
      ? arithRaw.discrepancy_details
      : Array.isArray(arithRaw.details)
        ? arithRaw.details
        : [];

  // 2. Duplicate Detection Normalization
  const dupItem = findTool('duplicate');
  const dupDetails = dupItem?.details || {};
  const dupRaw = evidence.duplicate || {};

  const isDuplicate = dupItem?.finding === 'CONFIRMED_DUPLICATE' ||
    dupItem?.finding === 'POSSIBLE_DUPLICATE' ||
    Boolean(dupDetails.is_duplicate) ||
    Boolean(dupRaw.is_duplicate) ||
    dupRaw.status === 'CONFIRMED_DUPLICATE';

  const matchedIds: string[] = Array.isArray(dupDetails.matched_invoice_ids)
    ? dupDetails.matched_invoice_ids
    : dupDetails.existing_invoice_id
      ? [dupDetails.existing_invoice_id]
      : Array.isArray(dupRaw.matched_invoice_ids)
        ? dupRaw.matched_invoice_ids
        : dupRaw.existing_invoice_id
          ? [dupRaw.existing_invoice_id]
          : [];

  const matchReasons: string[] = Array.isArray(dupDetails.match_reasons)
    ? dupDetails.match_reasons
    : Array.isArray(dupRaw.match_reasons)
      ? dupRaw.match_reasons
      : [];

  const rawDupDetails = dupDetails.details || dupRaw.details;
  const dupText = Array.isArray(rawDupDetails)
    ? rawDupDetails.join(' ')
    : typeof rawDupDetails === 'string' && rawDupDetails.trim()
      ? rawDupDetails
      : (isDuplicate ? 'Matching duplicate invoice previously processed in repository.' : 'No duplicate invoice number or exact payload match found in repository.');

  // 3. Vendor Context & Master Normalization
  const vCtxItem = findTool('vendor_context') || findTool('get_vendor_context');
  const vCtxDetails = vCtxItem?.details || evidence.vendor_context || {};

  const vendorItem = findTool('get_vendor_history') || findTool('vendor_history') || findTool('vendor');
  const vendorDetails = vendorItem?.details || evidence.vendor_history || {};

  const vendorExists = vCtxDetails.vendor_exists !== undefined ? Boolean(vCtxDetails.vendor_exists) : true;
  const isNewVendor = vCtxDetails.is_new_vendor !== undefined
    ? Boolean(vCtxDetails.is_new_vendor)
    : vendorDetails.new_vendor !== undefined
      ? Boolean(vendorDetails.new_vendor)
      : false;

  const vendorStatus = vCtxDetails.status || 'ACTIVE';
  const onboardingStatus = vCtxDetails.onboarding_status || 'APPROVED';
  const bankVerificationStatus = vCtxDetails.bank_verification_status || 'VERIFIED';
  const historicalInvoiceCount = vCtxDetails.historical_invoice_count ?? vendorDetails.invoice_count ?? 0;
  const historicalAvg = vCtxDetails.historical_average ?? vendorDetails.average_amount ?? 0;
  const historicalLargest = vCtxDetails.historical_largest ?? vendorDetails.largest_amount;
  const normalMin = vCtxDetails.normal_range_min;
  const normalMax = vCtxDetails.normal_range_max;
  const deviationFactor = vCtxDetails.deviation_factor;
  const poRequired = Boolean(vCtxDetails.po_required);
  const missingPo = Boolean(vCtxDetails.missing_po);
  const currencySupported = vCtxDetails.currency_supported !== undefined ? Boolean(vCtxDetails.currency_supported) : true;

  // 4. Approval Matrix Routing Normalization
  const matrixItem = findTool('approval_matrix') || findTool('evaluate_approval_matrix');
  const matrixDetails = matrixItem?.details || evidence.approval_routing || {};
  const approvalTier = matrixDetails.tier || matrixItem?.finding;
  const approvalReason = matrixDetails.reason;

  // 5. Corporate Policy Normalization
  const policyItem = findTool('policy') || findTool('evaluate_invoice_policy');
  const policyDetails = policyItem?.details || {};
  const policyRaw = evidence.policy || {};

  const policyPassed = policyDetails.passed !== undefined
    ? Boolean(policyDetails.passed)
    : policyItem?.finding === 'PASS'
      ? true
      : policyRaw.passed !== undefined
        ? Boolean(policyRaw.passed)
        : policyRaw.is_compliant !== undefined
          ? Boolean(policyRaw.is_compliant)
          : true;

  const violations: string[] = Array.isArray(policyDetails.violations)
    ? policyDetails.violations
    : Array.isArray(policyRaw.violations)
      ? policyRaw.violations
      : [];

  const rulesEvaluated: string[] = Array.isArray(policyDetails.rules_evaluated)
    ? policyDetails.rules_evaluated
    : Array.isArray(policyRaw.rules_evaluated)
      ? policyRaw.rules_evaluated
      : [];

  // 6. Risk Normalization
  const riskItem = findTool('risk') || findTool('calculate_invoice_risk');
  const riskDetails = riskItem?.details || {};
  const riskRaw = evidence.risk || {};

  const riskScore = Number(
    riskDetails.risk_score ??
    evidence.risk_score ??
    riskRaw.risk_score ??
    invoice?.risk_score ??
    0
  );

  const riskLevel = String(
    riskDetails.risk_level ??
    evidence.risk_level ??
    riskRaw.risk_level ??
    riskItem?.finding ??
    invoice?.risk_level ??
    'LOW'
  );

  const riskFactors: string[] = Array.isArray(riskDetails.risk_factors)
    ? riskDetails.risk_factors
    : Array.isArray(riskRaw.risk_factors)
      ? riskRaw.risk_factors
      : [];

  const recommendedAction = riskDetails.recommended_action || evidence.recommended_action || invoice?.decision || 'AUTO_APPROVE';
  const reasoningText = evidence.summary || evidence.reasoning || evidence.human_review_reason || '';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* 1. Arithmetic Integrity */}
      <div className="card">
        <h4 style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 700 }}>
            <Calculator size={18} color="var(--accent-cyan)" /> Arithmetic Integrity
          </span>
          {arithPassed ? (
            <span className="badge badge-approved"><CheckCircle size={12} /> Valid</span>
          ) : (
            <span className="badge badge-blocked"><XCircle size={12} /> Discrepancy Found</span>
          )}
        </h4>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '0.75rem', fontSize: '0.875rem' }}>
          <div><span style={{ color: 'var(--text-muted)' }}>Declared Subtotal:</span> ${formatMoney(declaredSubtotal)}</div>
          <div><span style={{ color: 'var(--text-muted)' }}>Computed Subtotal:</span> ${formatMoney(computedSubtotal)}</div>
          <div><span style={{ color: 'var(--text-muted)' }}>Discount:</span> ${formatMoney(declaredDiscount, '0.00')}</div>
          <div><span style={{ color: 'var(--text-muted)' }}>Shipping:</span> ${formatMoney(declaredShipping, '0.00')}</div>
          <div><span style={{ color: 'var(--text-muted)' }}>Tax:</span> {declaredTax !== null && declaredTax !== undefined ? `$${formatMoney(declaredTax)}` : '<Not Stated>'}</div>
          <div><span style={{ color: 'var(--text-muted)' }}>Declared Total:</span> ${formatMoney(declaredTotal)}</div>
          <div><span style={{ color: 'var(--text-muted)' }}>Computed Total:</span> ${formatMoney(computedTotal)}</div>
          <div><span style={{ color: 'var(--text-muted)' }}>Discrepancy:</span> ${formatMoney(difference, '0.00')}</div>
        </div>
        {arithDetailsList.length > 0 && (
          <div style={{ marginTop: '0.75rem', padding: '0.5rem', background: arithPassed ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)', borderRadius: 'var(--radius-sm)', color: arithPassed ? '#34d399' : '#fca5a5', fontSize: '0.8125rem' }}>
            {arithDetailsList.join(', ')}
          </div>
        )}
      </div>

      {/* 2. Duplicate Detection */}
      <div className="card">
        <h4 style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 700 }}>
            <Copy size={18} color="var(--accent-blue)" /> Duplicate Detection
          </span>
          {isDuplicate ? (
            <span className="badge badge-blocked"><XCircle size={12} /> Duplicate Detected</span>
          ) : (
            <span className="badge badge-approved"><CheckCircle size={12} /> Unique Record</span>
          )}
        </h4>
        <div style={{ fontSize: '0.875rem' }}>
          <p style={{ color: 'var(--text-secondary)' }}>{dupText}</p>
          {matchedIds.length > 0 && (
            <div style={{ marginTop: '0.5rem', color: '#fca5a5', fontWeight: 600 }}>
              Collided Invoice ID{matchedIds.length > 1 ? 's' : ''}: <code>{matchedIds.join(', ')}</code>
            </div>
          )}
          {matchReasons.length > 0 && (
            <div style={{ marginTop: '0.25rem', fontSize: '0.8125rem', color: '#fca5a5' }}>
              Reasons: {matchReasons.join('; ')}
            </div>
          )}
        </div>
      </div>

      {/* 3. Enterprise Vendor Context & History */}
      <div className="card">
        <h4 style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 700 }}>
            <Building size={18} color="var(--accent-indigo)" /> Enterprise Vendor Master & Context
          </span>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            {isNewVendor ? (
              <span className="badge badge-review">New Vendor</span>
            ) : (
              <span className="badge badge-approved">Established Vendor</span>
            )}
            <span className={`badge ${bankVerificationStatus === 'VERIFIED' ? 'badge-approved' : 'badge-blocked'}`}>
              Bank: {bankVerificationStatus}
            </span>
          </div>
        </h4>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem', fontSize: '0.875rem' }}>
          <div><span style={{ color: 'var(--text-muted)' }}>Master Profile:</span> <strong>{vendorExists ? 'Registered' : 'Unregistered'}</strong></div>
          <div><span style={{ color: 'var(--text-muted)' }}>Vendor Status:</span> <strong>{vendorStatus}</strong></div>
          <div><span style={{ color: 'var(--text-muted)' }}>Onboarding:</span> <strong>{onboardingStatus}</strong></div>
          <div><span style={{ color: 'var(--text-muted)' }}>Historical Invoices:</span> <strong>{historicalInvoiceCount}</strong></div>
          <div><span style={{ color: 'var(--text-muted)' }}>Historical Average:</span> ${formatMoney(historicalAvg)}</div>
          <div><span style={{ color: 'var(--text-muted)' }}>Historical Largest:</span> {historicalLargest ? `$${formatMoney(historicalLargest)}` : '--'}</div>
          <div><span style={{ color: 'var(--text-muted)' }}>Normal Range:</span> {normalMin && normalMax ? `$${formatMoney(normalMin)} - $${formatMoney(normalMax)}` : '--'}</div>
          <div><span style={{ color: 'var(--text-muted)' }}>Deviation Factor:</span> <strong>{deviationFactor !== null && deviationFactor !== undefined ? `${deviationFactor}x` : 'N/A (No History)'}</strong></div>
          <div><span style={{ color: 'var(--text-muted)' }}>PO Requirement:</span> {poRequired ? (missingPo ? <span style={{ color: 'var(--accent-red)' }}>Missing Required PO</span> : <span style={{ color: 'var(--accent-emerald)' }}>PO Provided</span>) : 'Not Required'}</div>
          <div><span style={{ color: 'var(--text-muted)' }}>Currency Valid:</span> {currencySupported ? 'Yes' : <span style={{ color: 'var(--accent-red)' }}>Unsupported Currency</span>}</div>
        </div>
      </div>

      {/* 4. Policy Compliance & Approval Routing */}
      <div className="card">
        <h4 style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 700 }}>
            <FileCheck size={18} color="#fbbf24" /> Corporate Policy Evaluation
          </span>
          {policyPassed ? (
            <span className="badge badge-approved"><CheckCircle size={12} /> Compliant</span>
          ) : (
            <span className="badge badge-review"><AlertTriangle size={12} /> Policy Exception</span>
          )}
        </h4>

        {approvalTier && (
          <div style={{ marginBottom: '0.75rem', padding: '0.5rem 0.75rem', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>Approval Matrix Tier:</span>
            <span className={`badge ${approvalTier === 'AUTO_APPROVAL_ALLOWED' ? 'badge-approved' : approvalTier === 'BLOCK' ? 'badge-blocked' : 'badge-review'}`}>
              {approvalTier}
            </span>
          </div>
        )}

        {!policyPassed && violations.length > 0 ? (
          <div>
            <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginBottom: '0.375rem' }}>Triggered Policy Exceptions:</div>
            <ul style={{ paddingLeft: '1.25rem', color: '#fbbf24', fontSize: '0.875rem' }}>
              {violations.map((v, i) => <li key={i}><strong>{v}</strong></li>)}
            </ul>
          </div>
        ) : !policyPassed ? (
          <p style={{ color: '#fbbf24', fontSize: '0.875rem' }}>Corporate policy rules flagged this invoice for manual review.</p>
        ) : (
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>All enterprise threshold and vendor approval rules satisfied.</p>
        )}
      </div>

      {/* 5. Risk Assessment */}
      <div className="card">
        <h4 style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 700 }}>
            <ShieldAlert size={18} color="#f87171" /> Multi-Factor Deterministic Risk
          </span>
          <span style={{ fontWeight: 800, fontSize: '1.125rem' }}>{riskScore} / 100 ({riskLevel})</span>
        </h4>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem', fontSize: '0.875rem' }}>
          <span style={{ color: 'var(--text-muted)' }}>Recommended Action:</span>
          <span className={`badge ${recommendedAction === 'AUTO_APPROVE' ? 'badge-approved' : recommendedAction === 'BLOCK' ? 'badge-blocked' : 'badge-review'}`}>
            {recommendedAction}
          </span>
        </div>

        {riskFactors.length > 0 && (
          <div style={{ marginTop: '0.5rem' }}>
            <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>Active Risk Factors:</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
              {riskFactors.map((f, i) => (
                <span key={i} className="badge badge-review">{f}</span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 6. Agent Reasoning & Rationale */}
      {reasoningText && (
        <div className="card">
          <h4 style={{ fontWeight: 700, marginBottom: '0.5rem' }}>Strands Agent Synthesis & Rationale</h4>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
            {reasoningText}
          </p>
        </div>
      )}
    </div>
  );
};
