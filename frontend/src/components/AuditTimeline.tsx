import React, { useEffect, useState } from 'react';
import { AuditEvent } from '../types/index.ts';
import { api } from '../services/api.ts';
import { Clock, Shield, CheckCircle, FileText, AlertTriangle } from 'lucide-react';

export const AuditTimeline: React.FC<{ invoiceId: string }> = ({ invoiceId }) => {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    api.getAuditTrail(invoiceId)
      .then((res: any) => {
        if (mounted) {
          const eventList = Array.isArray(res) ? res : (res.events || []);
          setEvents(eventList);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (mounted) {
          setError(err.message);
          setLoading(false);
        }
      });
    return () => { mounted = false; };
  }, [invoiceId]);

  if (loading) {
    return <div style={{ color: 'var(--text-muted)', padding: '1rem' }}>Loading immutable audit timeline...</div>;
  }

  if (error) {
    return <div className="alert alert-danger">{error}</div>;
  }

  if (events.length === 0) {
    return <div style={{ color: 'var(--text-muted)', padding: '1rem' }}>No audit events recorded for this invoice yet.</div>;
  }

  return (
    <div style={{ position: 'relative', paddingLeft: '1.5rem' }}>
      {/* Vertical Timeline Track */}
      <div style={{
        position: 'absolute',
        top: '8px',
        bottom: '8px',
        left: '7px',
        width: '2px',
        background: 'var(--border-color)',
      }} />

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        {events.map((ev, i) => (
          <div key={ev.event_id || i} style={{ position: 'relative' }}>
            {/* Dot */}
            <div style={{
              position: 'absolute',
              left: '-1.5rem',
              top: '4px',
              width: '16px',
              height: '16px',
              borderRadius: '50%',
              background: 'var(--bg-secondary)',
              border: '2px solid var(--accent-cyan)',
            }} />

            <div className="card" style={{ padding: '1rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                <span style={{ fontWeight: 700, fontSize: '0.875rem', color: 'var(--accent-cyan)' }}>
                  {ev.event_type}
                </span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                  <Clock size={12} /> {new Date(ev.timestamp).toLocaleString()}
                </span>
              </div>

              {ev.details && Object.keys(ev.details).length > 0 && (
                <pre style={{
                  background: 'var(--bg-primary)',
                  padding: '0.5rem 0.75rem',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '0.75rem',
                  overflowX: 'auto',
                  color: 'var(--text-secondary)',
                }}>
                  {JSON.stringify(ev.details, null, 2)}
                </pre>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
