import React, { useState } from 'react';
import { Navbar } from './components/Navbar.tsx';
import { DashboardPage } from './pages/DashboardPage.tsx';
import { InvoicesPage } from './pages/InvoicesPage.tsx';
import { InvoiceDetailPage } from './pages/InvoiceDetailPage.tsx';
import { PolicyPage } from './pages/PolicyPage.tsx';
import { VendorsPage } from './pages/VendorsPage.tsx';
import { BatchIngestionPage } from './pages/BatchIngestionPage.tsx';
import { BatchesPage } from './pages/BatchesPage.tsx';
import { BatchDetailPage } from './pages/BatchDetailPage.tsx';
import { InvoiceSubmissionModal } from './components/InvoiceSubmissionModal.tsx';

type ViewMode =
  | 'dashboard'
  | 'invoices'
  | 'detail'
  | 'policy'
  | 'vendors'
  | 'batches'
  | 'batch_ingest'
  | 'batch_detail';

export const App: React.FC = () => {
  const urlParams = new URLSearchParams(window.location.search);
  const paramInvoiceId = urlParams.get('invoice_id');
  const paramBatchId = urlParams.get('batch_id');
  const paramView = (urlParams.get('view') as ViewMode) || (paramInvoiceId ? 'detail' : paramBatchId ? 'batch_detail' : 'dashboard');

  const [currentView, setCurrentView] = useState<ViewMode>(paramView);
  const [selectedInvoiceId, setSelectedInvoiceId] = useState<string | null>(paramInvoiceId);
  const [selectedBatchId, setSelectedBatchId] = useState<string | null>(paramBatchId);
  const [showCreateModal, setShowCreateModal] = useState(false);

  const handleSelectInvoice = (id: string) => {
    setSelectedInvoiceId(id);
    setCurrentView('detail');
  };

  const handleSelectBatch = (id: string) => {
    setSelectedBatchId(id);
    setCurrentView('batch_detail');
  };

  const handleNavigate = (view: 'dashboard' | 'invoices' | 'policy' | 'vendors' | 'batches' | 'batch_ingest') => {
    setCurrentView(view);
    setSelectedInvoiceId(null);
    setSelectedBatchId(null);
  };

  return (
    <div className="app-container">
      <Navbar
        currentView={currentView}
        onNavigate={handleNavigate}
        onOpenCreate={() => setShowCreateModal(true)}
      />

      <main className="main-content">
        {currentView === 'dashboard' && (
          <DashboardPage
            onSelectInvoice={handleSelectInvoice}
            onViewAllInvoices={() => setCurrentView('invoices')}
            onNavigatePolicy={() => setCurrentView('policy')}
            onNavigateVendors={() => setCurrentView('vendors')}
          />
        )}

        {currentView === 'invoices' && (
          <InvoicesPage onSelectInvoice={handleSelectInvoice} />
        )}

        {currentView === 'batch_ingest' && (
          <BatchIngestionPage
            onViewBatches={() => setCurrentView('batches')}
            onSelectBatch={handleSelectBatch}
          />
        )}

        {currentView === 'batches' && (
          <BatchesPage
            onSelectBatch={handleSelectBatch}
            onNewBatch={() => setCurrentView('batch_ingest')}
          />
        )}

        {currentView === 'batch_detail' && selectedBatchId && (
          <BatchDetailPage
            batchId={selectedBatchId}
            onBack={() => setCurrentView('batches')}
            onNewBatch={() => setCurrentView('batch_ingest')}
          />
        )}

        {currentView === 'policy' && (
          <PolicyPage />
        )}

        {currentView === 'vendors' && (
          <VendorsPage />
        )}

        {currentView === 'detail' && selectedInvoiceId && (
          <InvoiceDetailPage
            invoiceId={selectedInvoiceId}
            onBack={() => setCurrentView('invoices')}
          />
        )}
      </main>

      {showCreateModal && (
        <InvoiceSubmissionModal
          onClose={() => setShowCreateModal(false)}
          onCreated={(newId) => {
            handleSelectInvoice(newId);
          }}
        />
      )}
    </div>
  );
};

export default App;

