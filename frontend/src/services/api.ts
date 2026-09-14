import {
  AuditEvent,
  BatchDocumentsResponse,
  BatchListResponse,
  BatchResponse,
  DashboardStats,
  HumanReviewRequest,
  InvoiceCreatePayload,
  InvoiceListResponse,
  InvoiceRecord,
  PolicyConfigResponse,
  ProcessingState,
  VendorListResponse,
  VendorRecordResponse,
  ExtractionResult,
  DocumentCorrectionRequest,
  BatchProgressResponse,
  BatchResumeResponse,
} from '../types/index.ts';

const API_BASE_URL = (import.meta as any).env?.VITE_API_URL || '';
const DEFAULT_API_KEY = 'dev-key';

export function getApiKey(): string {
  return localStorage.getItem('ledgerguard_api_key') || DEFAULT_API_KEY;
}

export function setApiKey(key: string): void {
  localStorage.setItem('ledgerguard_api_key', key);
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const headers = new Headers(options.headers || {});
  headers.set('X-API-Key', getApiKey());
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const url = `${API_BASE_URL}${endpoint}`;
  const response = await fetch(url, { ...options, headers });

  const contentType = response.headers.get('content-type') || '';

  if (!response.ok) {
    let errorDetail = 'API request failed';
    // Read the response body exactly ONCE
    const textBody = await response.text().catch(() => '');
    if (contentType.includes('application/json') && textBody) {
      try {
        const errJson = JSON.parse(textBody);
        errorDetail = errJson.detail || errJson.message || textBody;
      } catch {
        errorDetail = textBody;
      }
    } else if (contentType.includes('text/html')) {
      errorDetail = `Backend routing error: Received HTML instead of JSON for '${endpoint}'. Verify backend is running and proxy config in vite.config.ts.`;
    } else if (textBody) {
      errorDetail = textBody;
    }
    throw new Error(`HTTP ${response.status}: ${errorDetail}`);
  }

  // Handle successful response where HTML is returned unexpectedly (e.g. SPA fallback)
  if (contentType.includes('text/html')) {
    throw new Error(
      `Received HTML instead of JSON for '${endpoint}'. Check that the backend server is running and the proxy in vite.config.ts includes this route.`
    );
  }

  // Read the body exactly ONCE
  const text = await response.text();
  if (!text) {
    return {} as T;
  }
  try {
    return JSON.parse(text) as T;
  } catch (err: any) {
    throw new Error(`Failed to parse JSON response from '${endpoint}': ${err.message}`);
  }
}

export const api = {
  // Dashboard
  getDashboardStats: (params?: { batch_id?: string; date_range?: string }): Promise<DashboardStats> => {
    const query = new URLSearchParams();
    if (params?.batch_id) query.append('batch_id', params.batch_id);
    if (params?.date_range) query.append('date_range', params.date_range);
    const qs = query.toString();
    return request<DashboardStats>(`/dashboard/stats${qs ? `?${qs}` : ''}`);
  },

  // Invoices List
  listInvoices: (params: {
    limit?: number;
    offset?: number;
    status?: ProcessingState | string;
    search?: string;
    vendor_id?: string;
  } = {}): Promise<InvoiceListResponse> => {
    const searchParams = new URLSearchParams();
    if (params.limit) searchParams.set('limit', params.limit.toString());
    if (params.offset !== undefined) searchParams.set('offset', params.offset.toString());
    if (params.status) searchParams.set('status', params.status);
    if (params.search) searchParams.set('search', params.search);
    if (params.vendor_id) searchParams.set('vendor_id', params.vendor_id);
    const qs = searchParams.toString();
    return request<InvoiceListResponse>(`/invoices${qs ? `?${qs}` : ''}`);
  },

  // Invoice Detail
  getInvoice: (invoiceId: string): Promise<InvoiceRecord> => {
    return request<InvoiceRecord>(`/invoices/${encodeURIComponent(invoiceId)}`);
  },

  // Invoice Ingestion
  createInvoice: (payload: InvoiceCreatePayload): Promise<{ invoice_id: string; job_id: string; status: string }> => {
    return request('/invoices', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  // Document Upload
  uploadDocument: (invoiceId: string, file: File): Promise<{ s3_key: string; filename: string }> => {
    const formData = new FormData();
    formData.append('file', file);
    return request(`/invoices/${encodeURIComponent(invoiceId)}/document`, {
      method: 'POST',
      body: formData,
    });
  },

  // Human Review
  submitReview: (invoiceId: string, payload: HumanReviewRequest): Promise<InvoiceRecord> => {
    return request(`/invoices/${encodeURIComponent(invoiceId)}/review`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  // Audit Trail
  getAuditTrail: (invoiceId: string): Promise<AuditEvent[] | { invoice_id: string; events: AuditEvent[] }> => {
    return request(`/invoices/${encodeURIComponent(invoiceId)}/audit`);
  },

  // Corporate Policy
  getPolicy: (): Promise<PolicyConfigResponse> => {
    return request<PolicyConfigResponse>('/policy');
  },

  // Vendor Master
  listVendors: (): Promise<VendorListResponse> => {
    return request<VendorListResponse>('/vendors');
  },

  getVendor: (vendorId: string): Promise<VendorRecordResponse> => {
    return request<VendorRecordResponse>(`/vendors/${encodeURIComponent(vendorId)}`);
  },

  // Batch Ingestion (Phase 7)
  createBatch: (payload: { source?: string; document_count?: number }): Promise<BatchResponse> => {
    return request<BatchResponse>('/batches', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  uploadBatchFiles: (
    files: File[],
    source: string = 'UI_UPLOAD',
    idempotencyKey?: string
  ): Promise<BatchResponse> => {
    const formData = new FormData();
    for (const file of files) {
      formData.append('files', file);
    }
    formData.append('source', source);
    if (idempotencyKey) {
      formData.append('idempotency_key', idempotencyKey);
    }
    return request<BatchResponse>('/batches/upload', {
      method: 'POST',
      body: formData,
    });
  },

  listBatches: (params: { limit?: number; offset?: number } = {}): Promise<BatchListResponse> => {
    const searchParams = new URLSearchParams();
    if (params.limit) searchParams.set('limit', params.limit.toString());
    if (params.offset !== undefined) searchParams.set('offset', params.offset.toString());
    const qs = searchParams.toString();
    return request<BatchListResponse>(`/batches${qs ? `?${qs}` : ''}`);
  },

  getBatch: (batchId: string): Promise<BatchResponse> => {
    return request<BatchResponse>(`/batches/${encodeURIComponent(batchId)}`);
  },

  listBatchDocuments: (
    batchId: string,
    params: { limit?: number; offset?: number; status?: string } = {}
  ): Promise<BatchDocumentsResponse> => {
    const query = new URLSearchParams();
    if (params.limit !== undefined) query.set('limit', String(params.limit));
    if (params.offset !== undefined) query.set('offset', String(params.offset));
    if (params.status) query.set('status', params.status);
    const qs = query.toString();
    return request<BatchDocumentsResponse>(`/batches/${encodeURIComponent(batchId)}/documents${qs ? `?${qs}` : ''}`);
  },

  getBatchProgress: (batchId: string): Promise<BatchProgressResponse> => {
    return request<BatchProgressResponse>(`/batches/${encodeURIComponent(batchId)}/progress`);
  },

  resumeBatch: (batchId: string): Promise<BatchResumeResponse> => {
    return request<BatchResumeResponse>(`/batches/${encodeURIComponent(batchId)}/resume`, {
      method: 'POST',
    });
  },


  // Document Extraction & OCR (Phase 8)
  extractDocument: (batchId: string, documentId: string): Promise<any> => {
    return request(`/batches/${encodeURIComponent(batchId)}/documents/${encodeURIComponent(documentId)}/extract`, {
      method: 'POST',
    });
  },

  getDocumentExtraction: (batchId: string, documentId: string): Promise<ExtractionResult> => {
    return request<ExtractionResult>(`/batches/${encodeURIComponent(batchId)}/documents/${encodeURIComponent(documentId)}/extraction`);
  },

  correctDocumentExtraction: (
    batchId: string,
    documentId: string,
    payload: DocumentCorrectionRequest
  ): Promise<any> => {
    return request(`/batches/${encodeURIComponent(batchId)}/documents/${encodeURIComponent(documentId)}/correct`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  extractAllDocuments: (batchId: string): Promise<{ queued_count: number; total_documents: number }> => {
    return request(`/batches/${encodeURIComponent(batchId)}/extract-all`, {
      method: 'POST',
    });
  },

  // Health probe
  checkHealth: (): Promise<{ status: string }> => {
    return request('/health');
  },
};
