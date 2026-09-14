import React, { useState, useEffect } from 'react';
import { ExtractionResult, ExtractionField } from '../types/index.ts';
import { api } from '../services/api.ts';
import {
  X,
  CheckCircle2,
  AlertTriangle,
  FileText,
  Sliders,
  Sparkles,
  RefreshCw,
  Edit3,
} from 'lucide-react';

interface ExtractionCorrectionModalProps {
  batchId: string;
  documentId: string;
  onClose: () => void;
  onSuccess: () => void;
}

export const ExtractionCorrectionModal: React.FC<ExtractionCorrectionModalProps> = ({
  batchId,
  documentId,
  onClose,
  onSuccess,
}) => {
  const [extraction, setExtraction] = useState<ExtractionResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [reviewer, setReviewer] = useState('AP Specialist');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Field edit state: { [field_name]: { value: string, note: string } }
  const [corrections, setCorrections] = useState<Record<string, { value: string; note: string }>>({});

  useEffect(() => {
    loadExtraction();
  }, [batchId, documentId]);

  const loadExtraction = async () => {
    try {
      setLoading(true);
      setErrorMsg(null);
      const res = await api.getDocumentExtraction(batchId, documentId);
      setExtraction(res);
      // Initialize corrections map
      const initial: Record<string, { value: string; note: string }> = {};
      if (res.invoice_fields) {
        Object.entries(res.invoice_fields).forEach(([k, v]: [string, ExtractionField]) => {
          initial[k] = { value: v.value != null ? String(v.value) : '', note: '' };
        });
      }
      if (res.financials) {
        Object.entries(res.financials).forEach(([k, v]: [string, ExtractionField]) => {
          initial[k] = { value: v.value != null ? String(v.value) : '', note: '' };
        });
      }
      setCorrections(initial);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to load document extraction record.');
    } finally {
      setLoading(false);
    }
  };

  const handleFieldChange = (field: string, val: string) => {
    setCorrections((prev) => ({
      ...prev,
      [field]: { ...prev[field], value: val },
    }));
  };

  const handleNoteChange = (field: string, note: string) => {
    setCorrections((prev) => ({
      ...prev,
      [field]: { ...prev[field], note },
    }));
  };

  const handleSubmitCorrections = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!extraction) return;

    setIsSubmitting(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      // Find modified fields
      const payloadCorrections: Record<string, { value: any; note?: string }> = {};
      let changedCount = 0;

      for (const [key, curr] of Object.entries(corrections)) {
        const originalField =
          extraction.invoice_fields?.[key] || extraction.financials?.[key];
        const originalVal = originalField?.value != null ? String(originalField.value) : '';

        if (curr.value !== originalVal || curr.note.trim()) {
          payloadCorrections[key] = {
            value: curr.value === '' ? null : curr.value,
            note: curr.note.trim() || 'Manual AP specialist correction',
          };
          changedCount++;
        }
      }

      if (changedCount === 0) {
        setErrorMsg('No fields have been modified.');
        setIsSubmitting(false);
        return;
      }

      await api.correctDocumentExtraction(batchId, documentId, {
        corrections: payloadCorrections,
        reviewer: reviewer.trim() || 'AP Specialist',
      });

      setSuccessMsg(`Successfully applied ${changedCount} correction(s).`);
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 1200);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to submit document corrections.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const renderConfidenceBadge = (confidence: number) => {
    const pct = Math.round(confidence * 100);
    let color = 'bg-emerald-100 text-emerald-800 border-emerald-300';
    if (confidence < 0.6) {
      color = 'bg-rose-100 text-rose-800 border-rose-300';
    } else if (confidence < 0.85) {
      color = 'bg-amber-100 text-amber-800 border-amber-300';
    }
    return (
      <span className={`px-2 py-0.5 text-xs font-semibold rounded-full border ${color}`}>
        {pct}%
      </span>
    );
  };

  const renderStatusBadge = (status: string) => {
    switch (status) {
      case 'EXTRACTED':
        return <span className="px-2 py-0.5 text-xs font-medium rounded bg-blue-100 text-blue-800">EXTRACTED</span>;
      case 'INFERRED':
        return <span className="px-2 py-0.5 text-xs font-medium rounded bg-purple-100 text-purple-800">INFERRED</span>;
      case 'CORRECTED':
        return <span className="px-2 py-0.5 text-xs font-medium rounded bg-teal-100 text-teal-800">CORRECTED</span>;
      case 'NOT_STATED':
        return <span className="px-2 py-0.5 text-xs font-medium rounded bg-gray-100 text-gray-700">NOT STATED</span>;
      case 'MISSING':
        return <span className="px-2 py-0.5 text-xs font-medium rounded bg-rose-100 text-rose-800">MISSING</span>;
      default:
        return <span className="px-2 py-0.5 text-xs font-medium rounded bg-gray-100 text-gray-600">{status}</span>;
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black bg-opacity-60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-2xl border border-gray-200 w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between bg-slate-50">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-50 border border-indigo-100 text-indigo-600 rounded-lg">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-gray-900">Document Extraction & AP Correction</h3>
              <p className="text-xs text-gray-500 font-mono">
                Doc: {documentId} • Batch: {batchId}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto flex-1 space-y-6">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-12 text-gray-500">
              <RefreshCw className="w-8 h-8 animate-spin text-indigo-600 mb-3" />
              <p className="text-sm">Loading extraction data...</p>
            </div>
          ) : errorMsg && !extraction ? (
            <div className="p-4 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 flex items-center gap-3">
              <AlertTriangle className="w-5 h-5 flex-shrink-0" />
              <p className="text-sm">{errorMsg}</p>
            </div>
          ) : extraction ? (
            <>
              {/* Confidence & Extractor Overview Banner */}
              <div className="p-4 bg-gradient-to-r from-slate-50 to-indigo-50/30 rounded-xl border border-indigo-100/60 flex flex-wrap items-center justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">Overall Extraction Confidence</span>
                    {renderConfidenceBadge(extraction.overall_confidence)}
                  </div>
                  <div className="flex items-center gap-2 text-xs text-gray-600">
                    <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
                    <span>Provider: <strong className="font-semibold text-gray-800">{extraction.extractor_provider}</strong> (v{extraction.extractor_version})</span>
                  </div>
                </div>

                <div className="flex items-center gap-4 text-xs">
                  <div className="text-right">
                    <div className="text-gray-500">Declared Total</div>
                    <div className="font-bold text-gray-900 text-sm">
                      ${Number(extraction.financials?.total?.value || 0).toFixed(2)}
                    </div>
                  </div>
                  <div className="text-right border-l pl-4 border-gray-200">
                    <div className="text-gray-500">Computed Line Sum</div>
                    <div className="font-bold text-gray-900 text-sm">
                      ${Number(extraction.computed_subtotal || 0).toFixed(2)}
                    </div>
                  </div>
                  {extraction.discrepancy && Number(extraction.discrepancy) !== 0 ? (
                    <div className="text-right border-l pl-4 border-gray-200">
                      <div className="text-rose-600 font-semibold">Discrepancy</div>
                      <div className="font-bold text-rose-700 text-sm">
                        ${Number(extraction.discrepancy).toFixed(2)}
                      </div>
                    </div>
                  ) : null}
                </div>
              </div>

              {/* Extraction Errors / Warnings */}
              {extraction.errors && extraction.errors.length > 0 && (
                <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-800 text-xs space-y-1">
                  <div className="font-semibold flex items-center gap-1.5">
                    <AlertTriangle className="w-4 h-4" /> Extraction Warnings & Errors:
                  </div>
                  <ul className="list-disc list-inside space-y-0.5">
                    {extraction.errors.map((err, i) => (
                      <li key={i}>{err}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Fields Table */}
              <div>
                <h4 className="text-sm font-bold text-gray-800 mb-3 flex items-center gap-2">
                  <Sliders className="w-4 h-4 text-indigo-600" /> Header & Financial Fields
                </h4>
                <div className="border border-gray-200 rounded-lg overflow-hidden shadow-sm">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead className="bg-gray-50 text-gray-600 font-semibold border-b border-gray-200">
                      <tr>
                        <th className="py-2.5 px-3">Field</th>
                        <th className="py-2.5 px-3">Status</th>
                        <th className="py-2.5 px-3">Confidence</th>
                        <th className="py-2.5 px-3">Extracted Value</th>
                        <th className="py-2.5 px-3">Corrected Value</th>
                        <th className="py-2.5 px-3">Review Note</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100 bg-white">
                      {/* Invoice Fields */}
                      {extraction.invoice_fields &&
                        Object.entries(extraction.invoice_fields).map(([k, f]: [string, ExtractionField]) => (
                          <tr key={k} className="hover:bg-slate-50/80 transition-colors">
                            <td className="py-2 px-3 font-medium text-gray-800 capitalize">
                              {k.replace(/_/g, ' ')}
                            </td>
                            <td className="py-2 px-3">{renderStatusBadge(f.status)}</td>
                            <td className="py-2 px-3">{renderConfidenceBadge(f.confidence)}</td>
                            <td className="py-2 px-3 font-mono text-gray-600 truncate max-w-[140px]" title={String(f.value ?? '')}>
                              {f.value != null ? String(f.value) : <span className="text-gray-400 italic">none</span>}
                            </td>
                            <td className="py-2 px-3">
                              <input
                                type="text"
                                value={corrections[k]?.value ?? ''}
                                onChange={(e) => handleFieldChange(k, e.target.value)}
                                className="w-full px-2 py-1 text-xs border border-gray-300 rounded focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 font-mono"
                                placeholder={f.value != null ? String(f.value) : 'Enter corrected value'}
                              />
                            </td>
                            <td className="py-2 px-3">
                              <input
                                type="text"
                                value={corrections[k]?.note ?? ''}
                                onChange={(e) => handleNoteChange(k, e.target.value)}
                                className="w-full px-2 py-1 text-xs border border-gray-200 rounded focus:ring-1 focus:ring-indigo-500 text-gray-600"
                                placeholder="Reason..."
                              />
                            </td>
                          </tr>
                        ))}

                      {/* Financial Fields */}
                      {extraction.financials &&
                        Object.entries(extraction.financials).map(([k, f]: [string, ExtractionField]) => (
                          <tr key={k} className="hover:bg-slate-50/80 transition-colors">
                            <td className="py-2 px-3 font-medium text-gray-800 capitalize">
                              {k.replace(/_/g, ' ')}
                            </td>
                            <td className="py-2 px-3">{renderStatusBadge(f.status)}</td>
                            <td className="py-2 px-3">{renderConfidenceBadge(f.confidence)}</td>
                            <td className="py-2 px-3 font-mono text-gray-600 truncate max-w-[140px]" title={String(f.value ?? '')}>
                              {f.value != null ? `$${Number(f.value).toFixed(2)}` : <span className="text-gray-400 italic">none</span>}
                            </td>
                            <td className="py-2 px-3">
                              <input
                                type="text"
                                value={corrections[k]?.value ?? ''}
                                onChange={(e) => handleFieldChange(k, e.target.value)}
                                className="w-full px-2 py-1 text-xs border border-gray-300 rounded focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 font-mono"
                                placeholder={f.value != null ? String(f.value) : '0.00'}
                              />
                            </td>
                            <td className="py-2 px-3">
                              <input
                                type="text"
                                value={corrections[k]?.note ?? ''}
                                onChange={(e) => handleNoteChange(k, e.target.value)}
                                className="w-full px-2 py-1 text-xs border border-gray-200 rounded focus:ring-1 focus:ring-indigo-500 text-gray-600"
                                placeholder="Reason..."
                              />
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Line Items Preview */}
              {extraction.line_items && extraction.line_items.length > 0 && (
                <div>
                  <h4 className="text-sm font-bold text-gray-800 mb-2 flex items-center gap-2">
                    <FileText className="w-4 h-4 text-indigo-600" /> Line Items ({extraction.line_items.length})
                  </h4>
                  <div className="border border-gray-200 rounded-lg overflow-hidden shadow-sm">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead className="bg-gray-50 text-gray-600 font-semibold border-b border-gray-200">
                        <tr>
                          <th className="py-2 px-3">#</th>
                          <th className="py-2 px-3">Description</th>
                          <th className="py-2 px-3 text-right">Qty</th>
                          <th className="py-2 px-3 text-right">Unit Price</th>
                          <th className="py-2 px-3 text-right">Amount</th>
                          <th className="py-2 px-3 text-center">Avg Conf</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100 bg-white">
                        {extraction.line_items.map((item, idx) => {
                          const avgConf =
                            (item.description.confidence +
                              item.quantity.confidence +
                              item.unit_price.confidence +
                              item.amount.confidence) /
                            4;
                          return (
                            <tr key={idx} className="hover:bg-slate-50/80">
                              <td className="py-2 px-3 text-gray-400 font-mono">{idx + 1}</td>
                              <td className="py-2 px-3 font-medium text-gray-800">{item.description.value}</td>
                              <td className="py-2 px-3 text-right font-mono text-gray-600">{item.quantity.value}</td>
                              <td className="py-2 px-3 text-right font-mono text-gray-600">
                                ${Number(item.unit_price.value || 0).toFixed(2)}
                              </td>
                              <td className="py-2 px-3 text-right font-mono font-semibold text-gray-900">
                                ${Number(item.amount.value || 0).toFixed(2)}
                              </td>
                              <td className="py-2 px-3 text-center">{renderConfidenceBadge(avgConf)}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Reviewer signature */}
              <div className="pt-2 border-t border-gray-100 flex items-center gap-4">
                <label className="text-xs font-semibold text-gray-700">Reviewer ID / Signature:</label>
                <input
                  type="text"
                  value={reviewer}
                  onChange={(e) => setReviewer(e.target.value)}
                  className="px-3 py-1.5 text-xs border border-gray-300 rounded-lg focus:ring-1 focus:ring-indigo-500 font-medium text-gray-800 w-64"
                  placeholder="e.g. AP Specialist - John Doe"
                />
              </div>

              {errorMsg && (
                <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-800 text-xs flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                  <span>{errorMsg}</span>
                </div>
              )}

              {successMsg && (
                <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-800 text-xs flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
                  <span>{successMsg}</span>
                </div>
              )}
            </>
          ) : null}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-100 bg-gray-50 flex items-center justify-between">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold text-gray-700 hover:text-gray-900 border border-gray-300 rounded-lg bg-white hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={isSubmitting || loading || !extraction}
            onClick={handleSubmitCorrections}
            className="px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 rounded-lg shadow-sm flex items-center gap-2 transition-colors"
          >
            {isSubmitting ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                <span>Applying Corrections...</span>
              </>
            ) : (
              <>
                <Edit3 className="w-3.5 h-3.5" />
                <span>Apply Corrections & Emit Audit</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
