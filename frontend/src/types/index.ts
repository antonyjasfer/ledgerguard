export type ProcessingState =
  | 'RECEIVED'
  | 'VALIDATED'
  | 'AGENT_PROCESSING'
  | 'AUTO_APPROVED'
  | 'MANUAL_REVIEW'
  | 'BLOCKED'
  | 'FAILED';

export type AgentDecision =
  | 'AUTO_APPROVE'
  | 'MANUAL_REVIEW'
  | 'BLOCK'
  | 'ESCALATE';

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface LineItem {
  item_id: string;
  description: string;
  quantity: number;
  unit_price: number;
  amount: number;
}

export interface VerificationEvidence {
  arithmetic?: {
    is_valid?: boolean;
    computed_subtotal?: number;
    declared_subtotal?: number;
    computed_total?: number;
    declared_total?: number;
    discrepancy?: number;
    discrepancy_details?: string[];
  };
  duplicate?: {
    is_duplicate?: boolean;
    duplicate_type?: string;
    existing_invoice_id?: string;
    details?: string;
  };
  vendor_history?: {
    vendor_exists?: boolean;
    is_new_vendor?: boolean;
    historical_invoice_count?: number;
    average_amount?: number;
    amount_deviation_factor?: number;
    risk_indicator?: string;
  };
  policy?: {
    is_compliant?: boolean;
    violations?: string[];
    rules_evaluated?: string[];
    threshold_exceeded?: boolean;
  };
  risk?: {
    risk_score?: number;
    risk_level?: RiskLevel;
    risk_factors?: string[];
  };
  reasoning?: string;
  guard_override?: boolean;
  guard_original_decision?: AgentDecision;
  guard_rule_triggered?: string;
}

export interface InvoiceRecord {
  invoice_id: string;
  invoice_number: string;
  vendor_id: string;
  vendor_name: string;
  invoice_date: string;
  currency: string;
  subtotal?: number | null;
  tax?: number | null;
  discount?: number | null;
  total?: number | null;
  document_s3_key?: string | null;
  processing_status: ProcessingState;
  decision?: AgentDecision | null;
  risk_level?: RiskLevel | null;
  risk_score?: number | null;
  created_at: string;
  updated_at: string;
  agent_run_id?: string | null;
  verification_summary?: VerificationEvidence;
  customer_name?: string | null;
  line_items?: LineItem[];
  original_decision?: AgentDecision | null;
  review_decision?: string | null;
  reviewer?: string | null;
  review_timestamp?: string | null;
  review_comment?: string | null;
}

export interface InvoiceListItem {
  invoice_id: string;
  invoice_number: string;
  vendor_id: string;
  vendor_name: string;
  invoice_date: string;
  currency: string;
  total?: number | null;
  processing_status: ProcessingState;
  decision?: AgentDecision | null;
  risk_level?: RiskLevel | null;
  risk_score?: number | null;
  created_at: string;
  updated_at: string;
  document_s3_key?: string | null;
  original_decision?: AgentDecision | null;
  review_decision?: string | null;
}

export interface InvoiceListResponse {
  items: InvoiceListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface DashboardStats {
  total_invoices: number;
  pending_invoices: number;
  processed_invoices: number;
  auto_approved_count: number;
  manual_review_count: number;
  blocked_count: number;
  total_amount_usd: number;
  average_risk_score: number;
  auto_approval_rate_pct: number;
  by_status: Record<string, number>;
  by_decision: Record<string, number>;
  by_risk_level: Record<string, number>;
}

export interface AuditEvent {
  event_id: string;
  invoice_id: string;
  event_type: string;
  timestamp: string;
  details: Record<string, any>;
}

export interface HumanReviewRequest {
  action: 'APPROVE' | 'REJECT' | 'REQUEST_INFORMATION';
  reviewer: string;
  comment: string;
}

export interface InvoiceCreatePayload {
  invoice_id: string;
  invoice_number: string;
  vendor_id: string;
  vendor_name: string;
  invoice_date: string;
  currency?: string;
  subtotal: number;
  tax: number;
  discount?: number;
  total: number;
  customer_name?: string;
  line_items: LineItem[];
}
