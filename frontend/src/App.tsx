import React, { useState } from 'react';
import { Navbar } from './components/Navbar.tsx';
import { DashboardPage } from './pages/DashboardPage.tsx';
import { InvoicesPage } from './pages/InvoicesPage.tsx';
import { InvoiceDetailPage } from './pages/InvoiceDetailPage.tsx';
import { InvoiceSubmissionModal } from './components/InvoiceSubmissionModal.tsx';

export const App: React.FC = () => {
  const [currentView, setCurrentView] = useState<'dashboard' | 'invoices' | 'detail'>('dashboard');
  const [selectedInvoiceId, setSelectedInvoiceId] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);

  const handleSelectInvoice = (id: string) => {
    setSelectedInvoiceId(id);
    setCurrentView('detail');
  };

  const handleNavigate = (view: 'dashboard' | 'invoices') => {
    setCurrentView(view);
    setSelectedInvoiceId(null);
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
          />
        )}

        {currentView === 'invoices' && (
          <InvoicesPage onSelectInvoice={handleSelectInvoice} />
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
