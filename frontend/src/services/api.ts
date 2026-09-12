import {
  AuditEvent,
  DashboardStats,
  HumanReviewRequest,
  InvoiceCreatePayload,
  InvoiceListResponse,
  InvoiceRecord,
  ProcessingState,
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

  if (!response.ok) {
    let errorDetail = 'API request failed';
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errJson.message || JSON.stringify(errJson);
    } catch {
      errorDetail = await response.text();
    }
    throw new Error(`HTTP ${response.status}: ${errorDetail}`);
  }

  return response.json();
}

export const api = {
  // Dashboard
  getDashboardStats: (): Promise<DashboardStats> => {
    return request<DashboardStats>('/dashboard/stats');
  },

  // Invoices List
  listInvoices: (params: {
    limit?: number;
    offset?: number;
    status?: ProcessingState | '';
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
    return request(`/invoices/${encodeURIComponent(invoiceId)}/documents`, {
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

  // Health probe
  checkHealth: (): Promise<{ status: string }> => {
    return request('/health');
  },
};
