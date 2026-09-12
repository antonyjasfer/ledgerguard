import React from 'react';
import { ArrowRight, Server, Database, Cpu, ShieldCheck, HardDrive, CheckCircle2 } from 'lucide-react';

export const ArchitectureDiagram: React.FC = () => {
  return (
    <div className="card" style={{ marginBottom: '2rem' }}>
      <h3 className="card-title">
        <Cpu size={20} color="var(--accent-cyan)" /> Autonomous Pipeline Architecture
      </h3>
      <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginBottom: '1.5rem' }}>
        Deterministic financial tools verify facts. Strands Agent reasons over evidence. Decision Guard enforces protective policy.
      </p>

      <div style={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '1rem',
        padding: '1.25rem',
        background: 'var(--bg-primary)',
        borderRadius: 'var(--radius-md)',
        border: '1px solid var(--border-color)',
      }}>
        {/* Step 1 */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', minWidth: '120px' }}>
          <div style={{ width: '44px', height: '44px', borderRadius: '50%', background: 'rgba(56, 189, 248, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--accent-cyan)', marginBottom: '0.5rem' }}>
            <Server size={22} />
          </div>
          <span style={{ fontSize: '0.8125rem', fontWeight: 700 }}>FastAPI Ingestion</span>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Idempotent API</span>
        </div>

        <ArrowRight size={20} color="var(--text-muted)" />

        {/* Step 2 */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', minWidth: '120px' }}>
          <div style={{ width: '44px', height: '44px', borderRadius: '50%', background: 'rgba(59, 130, 246, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--accent-blue)', marginBottom: '0.5rem' }}>
            <HardDrive size={22} />
          </div>
          <span style={{ fontSize: '0.8125rem', fontWeight: 700 }}>AWS Storage & Queue</span>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>S3 + SQS + DynamoDB</span>
        </div>

        <ArrowRight size={20} color="var(--text-muted)" />

        {/* Step 3 */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', minWidth: '120px' }}>
          <div style={{ width: '44px', height: '44px', borderRadius: '50%', background: 'rgba(99, 102, 241, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--accent-indigo)', marginBottom: '0.5rem' }}>
            <Cpu size={22} />
          </div>
          <span style={{ fontSize: '0.8125rem', fontWeight: 700 }}>Strands Agent</span>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Bedrock Mantle / Gemma 3</span>
        </div>

        <ArrowRight size={20} color="var(--text-muted)" />

        {/* Step 4 */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', minWidth: '120px' }}>
          <div style={{ width: '44px', height: '44px', borderRadius: '50%', background: 'rgba(245, 158, 11, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fbbf24', marginBottom: '0.5rem' }}>
            <Database size={22} />
          </div>
          <span style={{ fontSize: '0.8125rem', fontWeight: 700 }}>5 Deterministic Tools</span>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Math, Dup, Risk, Policy</span>
        </div>

        <ArrowRight size={20} color="var(--text-muted)" />

        {/* Step 5 */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', minWidth: '120px' }}>
          <div style={{ width: '44px', height: '44px', borderRadius: '50%', background: 'rgba(16, 185, 129, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#34d399', marginBottom: '0.5rem' }}>
            <ShieldCheck size={22} />
          </div>
          <span style={{ fontSize: '0.8125rem', fontWeight: 700 }}>Decision Guard</span>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Non-Bypassable Safety</span>
        </div>
      </div>
    </div>
  );
};
