import React, { useState, useEffect } from 'react';
import { api } from '../services/api.ts';
import { UploadCloud, FileCheck, AlertCircle, Info } from 'lucide-react';

interface DocumentUploadProps {
  invoiceId: string;
  currentKey?: string | null;
  onUploaded: (key: string, filename?: string) => void;
}

export const DocumentUpload: React.FC<DocumentUploadProps> = ({ invoiceId, currentKey, onUploaded }) => {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successKey, setSuccessKey] = useState<string | null>(currentKey || null);

  useEffect(() => {
    if (currentKey) {
      setSuccessKey(currentKey);
    }
  }, [currentKey]);

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError(null);

    try {
      const res = await api.uploadDocument(invoiceId, file);
      setSuccessKey(res.s3_key);
      onUploaded(res.s3_key, res.filename);
      setFile(null);
    } catch (err: any) {
      setError(err.message || 'Failed to upload document to S3');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="card">
      <h4 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <UploadCloud size={18} color="var(--accent-cyan)" /> Amazon S3 Document Attachment
      </h4>

      {/* Mandatory Transparency Notice */}
      <div className="alert alert-info">
        <Info size={18} style={{ flexShrink: 0 }} />
        <div>
          <strong>Document Storage Policy:</strong> Documents are stored in Amazon S3 for audit and manual inspection. OCR and PDF text extraction are not implemented.
        </div>
      </div>

      {error && (
        <div className="alert alert-danger">
          <AlertCircle size={16} /> {error}
        </div>
      )}

      {successKey ? (
        <div style={{ padding: '0.75rem', background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.3)', borderRadius: 'var(--radius-sm)', marginBottom: '1rem', fontSize: '0.875rem' }}>
          <span style={{ color: '#34d399', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
            <FileCheck size={16} /> Document safely attached in S3
          </span>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginTop: '0.25rem' }}>
            S3 Key: <code>{successKey}</code>
          </div>
        </div>
      ) : (
        <div style={{ padding: '0.75rem', background: 'var(--bg-primary)', border: '1px dashed var(--border-color)', borderRadius: 'var(--radius-sm)', marginBottom: '1rem', fontSize: '0.875rem', color: 'var(--text-muted)' }}>
          No source document currently attached to this invoice record.
        </div>
      )}

      <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
        <input
          id="s3-document-file-input"
          type="file"
          accept=".pdf,.png,.jpg,.jpeg"
          onChange={(e) => {
            setError(null);
            setFile(e.target.files?.[0] || null);
          }}
          style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}
        />
        <button
          id="upload-s3-doc-btn"
          className="btn btn-primary"
          onClick={handleUpload}
          disabled={!file || uploading}
          style={{ whiteSpace: 'nowrap' }}
        >
          {uploading ? 'Uploading to S3...' : 'Upload to S3'}
        </button>
      </div>
    </div>
  );
};
