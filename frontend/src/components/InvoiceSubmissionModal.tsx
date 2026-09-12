import React, { useState } from 'react';
import { InvoiceCreatePayload, LineItem } from '../types/index.ts';
import { api } from '../services/api.ts';
import { X, Plus, Trash2, AlertCircle } from 'lucide-react';

interface InvoiceSubmissionModalProps {
  onClose: () => void;
  onCreated: (invoiceId: string) => void;
}

export const InvoiceSubmissionModal: React.FC<InvoiceSubmissionModalProps> = ({ onClose, onCreated }) => {
  const randNum = Math.floor(1000 + Math.random() * 9000);
  const [invoiceId, setInvoiceId] = useState(`INV-MANUAL-${randNum}`);
  const [invoiceNumber, setInvoiceNumber] = useState(`INV-${randNum}`);
  const [vendorId, setVendorId] = useState('VEND-ACME');
  const [vendorName, setVendorName] = useState('Acme Industrial Supplies');
  const [invoiceDate, setInvoiceDate] = useState(new Date().toISOString().split('T')[0]);
  const [currency, setCurrency] = useState('USD');
  const [customerName, setCustomerName] = useState('Global Enterprise Inc');

  const [lineItems, setLineItems] = useState<LineItem[]>([
    { item_id: 'ITEM-1', description: 'Cloud Infrastructure Consulting', quantity: 10, unit_price: 150.0, amount: 1500.0 },
    { item_id: 'ITEM-2', description: 'Hardware Server Maintenance', quantity: 2, unit_price: 500.0, amount: 1000.0 },
  ]);

  const [tax, setTax] = useState(250.0);
  const [discount, setDiscount] = useState(0.0);

  const subtotal = lineItems.reduce((acc, item) => acc + item.amount, 0);
  const total = subtotal + tax - discount;

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleUpdateItem = (index: number, field: keyof LineItem, val: any) => {
    const updated = [...lineItems];
    const item = { ...updated[index], [field]: val };
    if (field === 'quantity' || field === 'unit_price') {
      const q = field === 'quantity' ? Number(val) : item.quantity;
      const p = field === 'unit_price' ? Number(val) : item.unit_price;
      item.amount = Number((q * p).toFixed(2));
    }
    updated[index] = item;
    setLineItems(updated);
  };

  const handleAddItem = () => {
    const nextNum = lineItems.length + 1;
    setLineItems([
      ...lineItems,
      { item_id: `ITEM-${nextNum}`, description: 'Additional Services', quantity: 1, unit_price: 100.0, amount: 100.0 },
    ]);
  };

  const handleRemoveItem = (index: number) => {
    if (lineItems.length <= 1) return;
    setLineItems(lineItems.filter((_, i) => i !== index));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setErrorMsg(null);

    const payload: InvoiceCreatePayload = {
      invoice_id: invoiceId.trim(),
      invoice_number: invoiceNumber.trim(),
      vendor_id: vendorId.trim(),
      vendor_name: vendorName.trim(),
      invoice_date: invoiceDate,
      currency,
      customer_name: customerName.trim(),
      subtotal: Number(subtotal.toFixed(2)),
      tax: Number(tax),
      discount: Number(discount),
      total: Number(total.toFixed(2)),
      line_items: lineItems,
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
      <div className="modal-content" style={{ maxWidth: '750px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
          <h3 style={{ fontSize: '1.25rem', fontWeight: 700 }}>Ingest Accounts Payable Invoice</h3>
          <button className="btn btn-secondary" style={{ padding: '0.25rem' }} onClick={onClose}><X size={18} /></button>
        </div>

        {errorMsg && (
          <div className="alert alert-danger" style={{ marginBottom: '1rem' }}>
            <AlertCircle size={16} /> {errorMsg}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <div className="form-group">
              <label className="form-label">Invoice ID *</label>
              <input id="input-invoice-id" className="form-input" value={invoiceId} onChange={e => setInvoiceId(e.target.value)} required />
            </div>
            <div className="form-group">
              <label className="form-label">Vendor Invoice Number *</label>
              <input id="input-invoice-number" className="form-input" value={invoiceNumber} onChange={e => setInvoiceNumber(e.target.value)} required />
            </div>
            <div className="form-group">
              <label className="form-label">Vendor ID *</label>
              <input id="input-vendor-id" className="form-input" value={vendorId} onChange={e => setVendorId(e.target.value)} required />
            </div>
            <div className="form-group">
              <label className="form-label">Vendor Legal Name *</label>
              <input id="input-vendor-name" className="form-input" value={vendorName} onChange={e => setVendorName(e.target.value)} required />
            </div>
            <div className="form-group">
              <label className="form-label">Invoice Date *</label>
              <input id="input-invoice-date" type="date" className="form-input" value={invoiceDate} onChange={e => setInvoiceDate(e.target.value)} required />
            </div>
            <div className="form-group">
              <label className="form-label">Currency</label>
              <select id="select-currency" className="form-select" value={currency} onChange={e => setCurrency(e.target.value)}>
                <option value="USD">USD ($)</option>
                <option value="EUR">EUR (€)</option>
                <option value="GBP">GBP (£)</option>
              </select>
            </div>
          </div>

          <div style={{ marginTop: '1rem', marginBottom: '0.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h4 style={{ fontSize: '0.9375rem', fontWeight: 700 }}>Line Items ({lineItems.length})</h4>
            <button id="add-line-item-btn" type="button" className="btn btn-secondary" style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem' }} onClick={handleAddItem}>
              <Plus size={14} /> Add Line Item
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '1rem' }}>
            {lineItems.map((item, idx) => (
              <div key={idx} style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr auto', gap: '0.5rem', alignItems: 'center' }}>
                <input
                  className="form-input"
                  style={{ fontSize: '0.8125rem' }}
                  placeholder="Description"
                  value={item.description}
                  onChange={e => handleUpdateItem(idx, 'description', e.target.value)}
                  required
                />
                <input
                  type="number"
                  className="form-input"
                  style={{ fontSize: '0.8125rem' }}
                  placeholder="Qty"
                  value={item.quantity}
                  onChange={e => handleUpdateItem(idx, 'quantity', e.target.value)}
                  min={1}
                  required
                />
                <input
                  type="number"
                  step="0.01"
                  className="form-input"
                  style={{ fontSize: '0.8125rem' }}
                  placeholder="Price"
                  value={item.unit_price}
                  onChange={e => handleUpdateItem(idx, 'unit_price', e.target.value)}
                  min={0}
                  required
                />
                <div style={{ fontSize: '0.875rem', fontWeight: 600, textAlign: 'right', paddingRight: '0.5rem' }}>
                  ${item.amount.toFixed(2)}
                </div>
                <button
                  type="button"
                  className="btn btn-danger"
                  style={{ padding: '0.4rem' }}
                  onClick={() => handleRemoveItem(idx)}
                  disabled={lineItems.length <= 1}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem', background: 'var(--bg-surface)', padding: '1rem', borderRadius: 'var(--radius-sm)', marginBottom: '1.5rem' }}>
            <div>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Subtotal</span>
              <div style={{ fontSize: '1.125rem', fontWeight: 700 }}>${subtotal.toFixed(2)}</div>
            </div>
            <div>
              <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Tax Amount</label>
              <input type="number" step="0.01" className="form-input" value={tax} onChange={e => setTax(Number(e.target.value))} />
            </div>
            <div>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Computed Total</span>
              <div style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--accent-cyan)' }}>${total.toFixed(2)}</div>
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={isSubmitting}>Cancel</button>
            <button id="submit-ingest-invoice-btn" type="submit" className="btn btn-primary" disabled={isSubmitting}>
              {isSubmitting ? 'Submitting...' : 'Ingest & Publish to SQS'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
