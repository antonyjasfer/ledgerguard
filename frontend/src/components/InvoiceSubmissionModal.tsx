import React, { useState } from 'react';
import { InvoiceCreatePayload, LineItem } from '../types/index.ts';
import { api } from '../services/api.ts';
import { X, Plus, Trash2, AlertCircle, RefreshCw, Zap } from 'lucide-react';

interface InvoiceSubmissionModalProps {
  onClose: () => void;
  onCreated: (invoiceId: string) => void;
}

export const InvoiceSubmissionModal: React.FC<InvoiceSubmissionModalProps> = ({ onClose, onCreated }) => {
  const randNum = Math.floor(1000 + Math.random() * 9000);
  const [invoiceId, setInvoiceId] = useState(`INV-MANUAL-${randNum}`);
  const [invoiceNumber, setInvoiceNumber] = useState(`INV-${randNum}`);
  const [vendorId, setVendorId] = useState('SUPERSTORE-001');
  const [vendorName, setVendorName] = useState('SuperStore');
  const [invoiceDate, setInvoiceDate] = useState(new Date().toISOString().split('T')[0]);
  const [currency, setCurrency] = useState('USD');
  const [customerName, setCustomerName] = useState('LedgerGuard Demo Corporation');
  const [poNumber, setPoNumber] = useState('PO-2026-9901');

  const [lineItems, setLineItems] = useState<LineItem[]>([
    { item_id: 'ITEM-1', description: 'Office Equipment', quantity: 1, unit_price: 850.0, amount: 850.0 },
  ]);

  const [discount, setDiscount] = useState(0.0);
  const [shipping, setShipping] = useState(0.0);
  const [tax, setTax] = useState(0.0);
  const [overrideTotal, setOverrideTotal] = useState<string | null>(null);

  // Decimal-safe rounding to 2 decimal places
  const round2 = (num: number) => Math.round((num + Number.EPSILON) * 100) / 100;
  const subtotal = round2(lineItems.reduce((acc, item) => acc + (Number(item.amount) || 0), 0));
  const calculatedTotal = round2(subtotal - discount + shipping + tax);
  const effectiveTotal = overrideTotal !== null ? Number(overrideTotal) : calculatedTotal;

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Scenario 1: Clean Established Vendor
  const loadScenario1Clean = () => {
    const num = Math.floor(1000 + Math.random() * 9000);
    setInvoiceId(`DEMO-SCENARIO-1-${num}`);
    setInvoiceNumber(`INV-S1-${num}`);
    setVendorId('SUPERSTORE-001');
    setVendorName('SuperStore');
    setCustomerName('LedgerGuard Demo Corporation');
    setInvoiceDate(new Date().toISOString().split('T')[0]);
    setCurrency('USD');
    setPoNumber(`PO-2026-${num}`);
    setLineItems([
      { item_id: 'ITEM-1', description: 'Office Furniture & Supplies', quantity: 1, unit_price: 850.0, amount: 850.0 },
    ]);
    setDiscount(0.0);
    setShipping(0.0);
    setTax(0.0);
    setOverrideTotal(null);
    setErrorMsg(null);
  };

  // Scenario 2: New Vendor
  const loadScenario2NewVendor = () => {
    const num = Math.floor(1000 + Math.random() * 9000);
    setInvoiceId(`DEMO-SCENARIO-2-${num}`);
    setInvoiceNumber(`INV-S2-${num}`);
    setVendorId('NEW-VENDOR-001');
    setVendorName('New Unverified Supplies LLC');
    setCustomerName('LedgerGuard Demo Corporation');
    setInvoiceDate(new Date().toISOString().split('T')[0]);
    setCurrency('USD');
    setPoNumber(`PO-2026-${num}`);
    setLineItems([
      { item_id: 'ITEM-1', description: 'Industrial Testing Reagents', quantity: 1, unit_price: 850.0, amount: 850.0 },
    ]);
    setDiscount(0.0);
    setShipping(0.0);
    setTax(0.0);
    setOverrideTotal(null);
    setErrorMsg(null);
  };

  // Scenario 3: High Value
  const loadScenario3HighValue = () => {
    const num = Math.floor(1000 + Math.random() * 9000);
    setInvoiceId(`DEMO-SCENARIO-3-${num}`);
    setInvoiceNumber(`INV-S3-${num}`);
    setVendorId('SUPERSTORE-001');
    setVendorName('SuperStore');
    setCustomerName('LedgerGuard Demo Corporation');
    setInvoiceDate(new Date().toISOString().split('T')[0]);
    setCurrency('USD');
    setPoNumber(`PO-2026-${num}`);
    setLineItems([
      { item_id: 'ITEM-1', description: 'Enterprise Server Fleet Acquisition', quantity: 40, unit_price: 1000.0, amount: 40000.0 },
    ]);
    setDiscount(0.0);
    setShipping(0.0);
    setTax(0.0);
    setOverrideTotal(null);
    setErrorMsg(null);
  };

  // Scenario 4: Confirmed Duplicate
  const loadScenario4Duplicate = () => {
    setInvoiceId(`DEMO-SCENARIO-4-DUP`);
    setInvoiceNumber('36259'); // Re-uses identical invoice number from SuperStore
    setVendorId('SUPERSTORE-001');
    setVendorName('SuperStore');
    setCustomerName('LedgerGuard Demo Corporation');
    setInvoiceDate('2012-03-06');
    setCurrency('USD');
    setPoNumber('PO-36259');
    setLineItems([
      { item_id: 'ITEM-1', description: 'Duplicate Invoiced Merchandise', quantity: 1, unit_price: 850.0, amount: 850.0 },
    ]);
    setDiscount(0.0);
    setShipping(0.0);
    setTax(0.0);
    setOverrideTotal(null);
    setErrorMsg(null);
  };

  // Scenario 5: Arithmetic Mismatch
  const loadScenario5ArithmeticMismatch = () => {
    const num = Math.floor(1000 + Math.random() * 9000);
    setInvoiceId(`DEMO-SCENARIO-5-${num}`);
    setInvoiceNumber(`INV-S5-${num}`);
    setVendorId('SUPERSTORE-001');
    setVendorName('SuperStore');
    setCustomerName('LedgerGuard Demo Corporation');
    setInvoiceDate(new Date().toISOString().split('T')[0]);
    setCurrency('USD');
    setPoNumber(`PO-2026-${num}`);
    setLineItems([
      { item_id: 'ITEM-1', description: 'Stationery Items', quantity: 5, unit_price: 100.0, amount: 500.0 },
    ]);
    setDiscount(0.0);
    setShipping(0.0);
    setTax(0.0);
    setOverrideTotal('999.00'); // Intentionally mismatched declared total (999.00 vs 500.00)
    setErrorMsg(null);
  };

  // Real SuperStore Invoice #36259
  const loadSuperStorePreset = () => {
    setInvoiceId('DEMO-SUPERSTORE-36259');
    setInvoiceNumber('36259');
    setVendorId('SUPERSTORE-001');
    setVendorName('SuperStore');
    setCustomerName('LedgerGuard Demo Corporation');
    setInvoiceDate('2012-03-06');
    setCurrency('USD');
    setPoNumber('PO-36259');
    setLineItems([
      { item_id: 'ITEM-1', description: 'Newell 330', quantity: 3, unit_price: 17.94, amount: 53.82 },
    ]);
    setDiscount(0.0);
    setShipping(4.29);
    setTax(0.0);
    setOverrideTotal(null);
    setErrorMsg(null);
  };

  const clearForm = () => {
    setInvoiceId('');
    setInvoiceNumber('');
    setVendorId('');
    setVendorName('');
    setCustomerName('');
    setPoNumber('');
    setInvoiceDate(new Date().toISOString().split('T')[0]);
    setCurrency('USD');
    setLineItems([
      { item_id: 'ITEM-1', description: '', quantity: 1, unit_price: 0, amount: 0 },
    ]);
    setDiscount(0.0);
    setShipping(0.0);
    setTax(0.0);
    setOverrideTotal(null);
    setErrorMsg(null);
  };

  const handleUpdateItem = (index: number, field: keyof LineItem, val: any) => {
    const updated = [...lineItems];
    const item = { ...updated[index], [field]: val };
    if (field === 'quantity' || field === 'unit_price') {
      const q = field === 'quantity' ? Number(val) : Number(item.quantity);
      const p = field === 'unit_price' ? Number(val) : Number(item.unit_price);
      item.amount = round2(q * p);
    }
    updated[index] = item;
    setLineItems(updated);
  };

  const handleAddItem = () => {
    const nextNum = lineItems.length + 1;
    setLineItems([
      ...lineItems,
      { item_id: `ITEM-${nextNum}`, description: '', quantity: 1, unit_price: 0.0, amount: 0.0 },
    ]);
  };

  const handleRemoveItem = (index: number) => {
    if (lineItems.length <= 1) {
      setLineItems([{ item_id: 'ITEM-1', description: '', quantity: 1, unit_price: 0.0, amount: 0.0 }]);
      return;
    }
    setLineItems(lineItems.filter((_, i) => i !== index));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setErrorMsg(null);

    const validLineItems = lineItems.filter(item => item.description.trim().length > 0);
    if (validLineItems.length === 0) {
      setErrorMsg('At least one line item with a description is required.');
      setIsSubmitting(false);
      return;
    }

    const payload: InvoiceCreatePayload = {
      invoice_id: invoiceId.trim(),
      invoice_number: invoiceNumber.trim(),
      vendor_id: vendorId.trim(),
      vendor_name: vendorName.trim(),
      invoice_date: invoiceDate,
      currency,
      customer_name: customerName.trim() || 'LedgerGuard Demo Corporation',
      purchase_order_number: poNumber.trim() || undefined,
      subtotal: subtotal.toFixed(2),
      discount: discount.toFixed(2),
      shipping: shipping.toFixed(2),
      tax: tax.toFixed(2),
      total: effectiveTotal.toFixed(2),
      line_items: validLineItems.map(item => ({
        description: item.description.trim(),
        quantity: Number(item.quantity) || 1,
        unit_price: Number(item.unit_price).toFixed(2),
      })),
    };

    try {
      const res = await api.createInvoice(payload);
      onCreated(res.invoice_id);
      onClose();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to ingest invoice.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content" style={{ maxWidth: '820px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <div>
            <h3 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0 }}>Ingest Accounts Payable Invoice</h3>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: '0.25rem 0 0 0' }}>
              Create and queue invoice for autonomous verification against corporate policies
            </p>
          </div>
          <button className="btn btn-secondary" style={{ padding: '0.25rem' }} onClick={onClose}><X size={18} /></button>
        </div>

        {/* Demo Scenarios Bar */}
        <div style={{ background: 'var(--bg-secondary)', padding: '0.75rem', borderRadius: 'var(--radius-sm)', marginBottom: '1.25rem' }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
            <Zap size={13} color="var(--accent-amber)" /> PHASE P DEMO SCENARIOS:
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <button
              type="button"
              id="scenario-1-btn"
              className="btn btn-secondary"
              style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem' }}
              onClick={loadScenario1Clean}
            >
              1. Clean Established ($850)
            </button>
            <button
              type="button"
              id="scenario-2-btn"
              className="btn btn-secondary"
              style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem' }}
              onClick={loadScenario2NewVendor}
            >
              2. New Vendor ($850)
            </button>
            <button
              type="button"
              id="scenario-3-btn"
              className="btn btn-secondary"
              style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem' }}
              onClick={loadScenario3HighValue}
            >
              3. High Value ($40k)
            </button>
            <button
              type="button"
              id="scenario-4-btn"
              className="btn btn-secondary"
              style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem' }}
              onClick={loadScenario4Duplicate}
            >
              4. Duplicate Block
            </button>
            <button
              type="button"
              id="scenario-5-btn"
              className="btn btn-secondary"
              style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem' }}
              onClick={loadScenario5ArithmeticMismatch}
            >
              5. Arithmetic Mismatch
            </button>
            <button
              type="button"
              id="load-superstore-preset-btn"
              className="btn btn-secondary"
              style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem', color: 'var(--accent-cyan)' }}
              onClick={loadSuperStorePreset}
            >
              SuperStore #36259
            </button>
            <button
              type="button"
              id="clear-form-btn"
              className="btn btn-secondary"
              style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem' }}
              onClick={clearForm}
            >
              Clear
            </button>
          </div>
        </div>

        {errorMsg && (
          <div className="alert alert-danger" style={{ marginBottom: '1rem' }}>
            <AlertCircle size={16} /> {errorMsg}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.75rem', marginBottom: '1rem' }}>
            <div className="form-group">
              <label className="form-label">Invoice ID *</label>
              <input
                id="invoice-id-input"
                className="form-input"
                type="text"
                value={invoiceId}
                onChange={(e) => setInvoiceId(e.target.value)}
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label">Invoice Number *</label>
              <input
                id="invoice-number-input"
                className="form-input"
                type="text"
                value={invoiceNumber}
                onChange={(e) => setInvoiceNumber(e.target.value)}
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label">Purchase Order (PO) #</label>
              <input
                id="po-number-input"
                className="form-input"
                type="text"
                placeholder="e.g. PO-2026-9901"
                value={poNumber}
                onChange={(e) => setPoNumber(e.target.value)}
              />
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.75rem', marginBottom: '1rem' }}>
            <div className="form-group">
              <label className="form-label">Vendor ID *</label>
              <input
                id="vendor-id-input"
                className="form-input"
                type="text"
                value={vendorId}
                onChange={(e) => setVendorId(e.target.value)}
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label">Vendor Legal Name *</label>
              <input
                id="vendor-name-input"
                className="form-input"
                type="text"
                value={vendorName}
                onChange={(e) => setVendorName(e.target.value)}
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label">Invoice Date *</label>
              <input
                id="invoice-date-input"
                className="form-input"
                type="date"
                value={invoiceDate}
                onChange={(e) => setInvoiceDate(e.target.value)}
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label">Currency *</label>
              <select
                id="currency-input"
                className="form-input"
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
              >
                <option value="USD">USD ($)</option>
                <option value="EUR">EUR (€)</option>
                <option value="GBP">GBP (£)</option>
                <option value="CAD">CAD (C$)</option>
                <option value="JPY">JPY (¥)</option>
              </select>
            </div>
          </div>

          {/* Line Items Table */}
          <div style={{ marginBottom: '1rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <span className="form-label" style={{ margin: 0 }}>Line Items</span>
              <button
                type="button"
                id="add-line-item-btn"
                className="btn btn-secondary"
                style={{ fontSize: '0.75rem', padding: '0.25rem 0.5rem' }}
                onClick={handleAddItem}
              >
                <Plus size={12} /> Add Item
              </button>
            </div>

            <div style={{ maxHeight: '180px', overflowY: 'auto', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8125rem' }}>
                <thead>
                  <tr style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-color)', textAlign: 'left' }}>
                    <th style={{ padding: '0.5rem' }}>Description</th>
                    <th style={{ padding: '0.5rem', width: '80px' }}>Qty</th>
                    <th style={{ padding: '0.5rem', width: '100px' }}>Unit Price</th>
                    <th style={{ padding: '0.5rem', width: '100px' }}>Amount</th>
                    <th style={{ padding: '0.5rem', width: '40px' }}></th>
                  </tr>
                </thead>
                <tbody>
                  {lineItems.map((item, idx) => (
                    <tr key={idx} style={{ borderBottom: '1px solid var(--border-color)' }}>
                      <td style={{ padding: '0.4rem' }}>
                        <input
                          className="form-input"
                          style={{ padding: '0.25rem 0.5rem' }}
                          type="text"
                          value={item.description}
                          onChange={(e) => handleUpdateItem(idx, 'description', e.target.value)}
                          placeholder="Item description"
                          required
                        />
                      </td>
                      <td style={{ padding: '0.4rem' }}>
                        <input
                          className="form-input"
                          style={{ padding: '0.25rem 0.5rem' }}
                          type="number"
                          step="1"
                          min="0"
                          value={item.quantity}
                          onChange={(e) => handleUpdateItem(idx, 'quantity', e.target.value)}
                        />
                      </td>
                      <td style={{ padding: '0.4rem' }}>
                        <input
                          className="form-input"
                          style={{ padding: '0.25rem 0.5rem' }}
                          type="number"
                          step="0.01"
                          min="0"
                          value={item.unit_price}
                          onChange={(e) => handleUpdateItem(idx, 'unit_price', e.target.value)}
                        />
                      </td>
                      <td style={{ padding: '0.4rem', fontWeight: 600 }}>
                        ${Number(item.amount || 0).toFixed(2)}
                      </td>
                      <td style={{ padding: '0.4rem', textAlign: 'center' }}>
                        <button
                          type="button"
                          className="btn btn-secondary"
                          style={{ padding: '0.2rem', color: 'var(--accent-red)' }}
                          onClick={() => handleRemoveItem(idx)}
                        >
                          <Trash2 size={12} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Financial Totals Breakdown */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.75rem', marginBottom: '1.25rem', background: 'var(--bg-secondary)', padding: '0.75rem', borderRadius: 'var(--radius-sm)' }}>
            <div className="form-group" style={{ margin: 0 }}>
              <label className="form-label" style={{ fontSize: '0.75rem' }}>Subtotal</label>
              <div style={{ fontWeight: 700, fontSize: '1rem', marginTop: '0.25rem' }}>${subtotal.toFixed(2)}</div>
            </div>
            <div className="form-group" style={{ margin: 0 }}>
              <label className="form-label" style={{ fontSize: '0.75rem' }}>Discount ($)</label>
              <input
                className="form-input"
                type="number"
                step="0.01"
                min="0"
                value={discount}
                onChange={(e) => setDiscount(Number(e.target.value))}
              />
            </div>
            <div className="form-group" style={{ margin: 0 }}>
              <label className="form-label" style={{ fontSize: '0.75rem' }}>Shipping ($)</label>
              <input
                className="form-input"
                type="number"
                step="0.01"
                min="0"
                value={shipping}
                onChange={(e) => setShipping(Number(e.target.value))}
              />
            </div>
            <div className="form-group" style={{ margin: 0 }}>
              <label className="form-label" style={{ fontSize: '0.75rem' }}>Tax ($)</label>
              <input
                className="form-input"
                type="number"
                step="0.01"
                min="0"
                value={tax}
                onChange={(e) => setTax(Number(e.target.value))}
              />
            </div>
          </div>

          {/* Total & Submit */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--border-color)', paddingTop: '1rem' }}>
            <div>
              <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>Declared Total:</div>
              <div style={{ fontSize: '1.375rem', fontWeight: 800, color: 'var(--accent-cyan)' }}>
                ${effectiveTotal.toFixed(2)} {currency}
                {overrideTotal !== null && (
                  <span style={{ fontSize: '0.75rem', color: 'var(--accent-amber)', marginLeft: '0.5rem', fontWeight: 600 }}>
                    (Mismatched declared total)
                  </span>
                )}
              </div>
            </div>

            <div style={{ display: 'flex', gap: '0.75rem' }}>
              <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
              <button
                type="submit"
                id="submit-invoice-btn"
                className="btn btn-primary"
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <><RefreshCw size={14} className="spin-animation" /> Ingesting...</>
                ) : (
                  'Ingest & Verify'
                )}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};
