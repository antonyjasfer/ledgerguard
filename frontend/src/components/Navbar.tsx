import React, { useState } from 'react';
import { Shield, LayoutDashboard, FileText, PlusCircle, Key, Check } from 'lucide-react';
import { getApiKey, setApiKey } from '../services/api.ts';

interface NavbarProps {
  currentView: 'dashboard' | 'invoices' | 'detail';
  onNavigate: (view: 'dashboard' | 'invoices') => void;
  onOpenCreate: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ currentView, onNavigate, onOpenCreate }) => {
  const [apiKeyVal, setApiKeyVal] = useState(getApiKey());
  const [showKeyModal, setShowKeyModal] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  const handleSaveKey = () => {
    setApiKey(apiKeyVal.trim());
    setSavedSuccess(true);
    setTimeout(() => {
      setSavedSuccess(false);
      setShowKeyModal(false);
    }, 800);
  };

  return (
    <nav className="navbar">
      <div className="nav-brand" onClick={() => onNavigate('dashboard')} id="nav-brand-btn">
        <div className="nav-brand-logo">
          <Shield size={20} />
        </div>
        <span className="nav-brand-title">LedgerGuard</span>
      </div>

      <div className="nav-links">
        <button
          id="nav-dashboard-btn"
          className={`nav-btn ${currentView === 'dashboard' ? 'active' : ''}`}
          onClick={() => onNavigate('dashboard')}
        >
          <LayoutDashboard size={16} /> Dashboard
        </button>
        <button
          id="nav-invoices-btn"
          className={`nav-btn ${currentView === 'invoices' || currentView === 'detail' ? 'active' : ''}`}
          onClick={() => onNavigate('invoices')}
        >
          <FileText size={16} /> Invoices
        </button>
      </div>

      <div className="nav-actions">
        <button
          id="nav-key-config-btn"
          className="btn btn-secondary"
          style={{ padding: '0.4rem 0.8rem', fontSize: '0.75rem' }}
          onClick={() => setShowKeyModal(true)}
          title="Configure API Key"
        >
          <Key size={14} /> Key: {apiKeyVal ? '••••' + apiKeyVal.slice(-3) : 'None'}
        </button>

        <button
          id="nav-new-invoice-btn"
          className="btn btn-primary"
          onClick={onOpenCreate}
        >
          <PlusCircle size={16} /> Ingest Invoice
        </button>
      </div>

      {showKeyModal && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '400px' }}>
            <h3 style={{ marginBottom: '1rem', fontSize: '1.125rem' }}>Backend API Key</h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginBottom: '1rem' }}>
              Used in the <code>X-API-Key</code> header for authenticated requests. Default is <code>dev-key</code>.
            </p>
            <div className="form-group">
              <input
                id="api-key-input"
                className="form-input"
                type="text"
                value={apiKeyVal}
                onChange={(e) => setApiKeyVal(e.target.value)}
                placeholder="Enter API Key"
              />
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
              <button className="btn btn-secondary" onClick={() => setShowKeyModal(false)}>Cancel</button>
              <button id="save-api-key-btn" className="btn btn-primary" onClick={handleSaveKey}>
                {savedSuccess ? <><Check size={16} /> Saved</> : 'Save Key'}
              </button>
            </div>
          </div>
        </div>
      )}
    </nav>
  );
};
