export type ProcessingState =
  | 'RECEIVED'
  | 'VALIDATED'
  | 'AGENT_PROCESSING'
  | 'PROCESSING'
  | 'AUTO_APPROVED'
  | 'MANUAL_REVIEW'
  | 'HUMAN_APPROVED'
  | 'HUMAN_REJECTED'
  | 'BLOCKED'
  | 'FAILED'
  | 'DOCUMENT_INGESTED'
  | 'AWAITING_EXTRACTION'
  | 'EXTRACTING'
  | 'EXTRACTION_COMPLETED'
  | 'EXTRACTION_VALIDATED'
  | 'INSUFFICIENT_CONFIDENCE';

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
    discount?: number;
    shipping?: number;
    tax?: number;
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
    matched_invoice_ids?: string[];
    match_reasons?: string[];
  };
  vendor_history?: {
    vendor_exists?: boolean;
    is_new_vendor?: boolean;
    historical_invoice_count?: number;
    average_amount?: number;
    amount_deviation_factor?: number;
    risk_indicator?: string;
  };
  vendor_context?: {
    vendor_exists?: boolean;
    vendor_id?: string;
    vendor_name?: string;
    status?: string;
    onboarding_status?: string;
    bank_verification_status?: string;
    po_required?: boolean;
    po_provided?: boolean;
    missing_po?: boolean;
    currency_supported?: boolean;
    is_new_vendor?: boolean;
    historical_invoice_count?: number;
    historical_average?: number;
    historical_largest?: number;
    normal_range_min?: number;
    normal_range_max?: number;
    current_amount?: number;
    deviation_factor?: number;
    is_above_normal_range?: boolean;
    details?: string[];
  };
  approval_routing?: {
    tier?: string;
    reason?: string;
    threshold_applied?: number;
  };
  policy?: {
    is_compliant?: boolean;
    passed?: boolean;
    violations?: string[];
    rules_evaluated?: string[];
    threshold_exceeded?: boolean;
    should_block?: boolean;
    requires_review?: boolean;
  };
  risk?: {
    risk_score?: number;
    risk_level?: RiskLevel;
    risk_factors?: string[];
    recommended_action?: string;
  };
  summary?: string;
  reasoning?: string;
  human_review_reason?: string;
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
  shipping?: number | null;
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
  metadata?: Record<string, any>;
  extractor_provider?: string;
  customer_name?: string | null;
  purchase_order_number?: string | null;
  line_items?: LineItem[];
  original_decision?: AgentDecision | null;
  automated_decision?: AgentDecision | null;
  review_decision?: string | null;
  human_review_decision?: string | null;
  reviewer?: string | null;
  human_review_reviewer?: string | null;
  review_timestamp?: string | null;
  human_review_timestamp?: string | null;
  review_comment?: string | null;
  human_review_comment?: string | null;
  final_state?: string | null;
}

export interface InvoiceListItem {
  invoice_id: string;
  invoice_number: string;
  vendor_id: string;
  vendor_name: string;
  invoice_date: string;
  currency: string;
  shipping?: number | null;
  total?: number | null;
  processing_status: ProcessingState;
  decision?: AgentDecision | null;
  risk_level?: RiskLevel | null;
  risk_score?: number | null;
  created_at: string;
  updated_at: string;
  document_s3_key?: string | null;
  original_decision?: AgentDecision | null;
  automated_decision?: AgentDecision | null;
  review_decision?: string | null;
  human_review_decision?: string | null;
  reviewer?: string | null;
  human_review_reviewer?: string | null;
  review_timestamp?: string | null;
  human_review_timestamp?: string | null;
  review_comment?: string | null;
  human_review_comment?: string | null;
  final_state?: string | null;
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
  human_approved_count?: number;
  human_rejected_count?: number;
  manual_review_count: number;
  blocked_count: number;
  total_amount_usd: number;
  average_risk_score: number;
  auto_approval_rate_pct: number;
  by_status: Record<string, number>;
  by_decision: Record<string, number>;
  by_risk_level: Record<string, number>;
  active_policy_summary?: {
    company_name: string;
    company_id: string;
    auto_approval_limit: number;
    high_value_threshold: number;
    default_currency: string;
  };
  enterprise_metrics?: {
    total_vendors: number;
    active_vendors: number;
    new_vendors_detected: number;
    duplicate_invoices_blocked: number;
  };
  // Phase 8: AP Financial Summary Dashboard Metrics
  total_verified_spend_usd?: string | number;
  total_invoice_value?: string | number;
  total_subtotal?: string | number;
  total_discount?: string | number;
  total_shipping?: string | number;
  total_tax?: string | number;
  estimated_payable_amount?: string | number;
  estimated_payable_coverage_pct?: number;
  estimated_payable_invoices_count?: number;
  auto_approved_value?: string | number;
  human_approved_value?: string | number;
  human_rejected_value?: string | number;
  manual_review_value?: string | number;
  blocked_value?: string | number;
  duplicate_value?: string | number;
  extraction_success_count?: number;
  extraction_failed_count?: number;
  low_confidence_count?: number;
  insufficient_data_count?: number;
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
  subtotal: number | string;
  tax: number | string;
  discount?: number | string;
  shipping?: number | string;
  total: number | string;
  customer_name?: string;
  purchase_order_number?: string;
  line_items: Array<{
    item_id?: string;
    description: string;
    quantity: number | string;
    unit_price: number | string;
    amount?: number | string;
    tax_rate?: number | string;
    discount?: number | string;
  }>;
}

export interface PolicyConfigResponse {
  company_name: string;
  company_id: string;
  supported_currencies: string[];
  default_currency: string;
  auto_approval_limit: number;
  high_value_threshold: number;
  new_vendor_requires_review: boolean;
  duplicate_requires_block: boolean;
  possible_duplicate_requires_review: boolean;
  possible_duplicate_days: number;
  recent_invoice_days: number;
  missing_po_requires_review: boolean;
  tax_mismatch_requires_review: boolean;
  arithmetic_mismatch_requires_block: boolean;
  unsupported_currency_requires_review: boolean;
  maximum_discount_percent: number;
  large_discount_requires_review: boolean;
  required_fields: string[];
  approval_matrix_tiers: Array<{
    tier: string;
    condition: string;
    action: string;
  }>;
}

export interface VendorRecordResponse {
  vendor_id: string;
  legal_name: string;
  status: string;
  country: string;
  approved_currencies: string[];
  payment_terms: string;
  po_required: boolean;
  onboarding_status: string;
  bank_verification_status: string;
  created_at: string;
  historical_invoice_count: number;
  historical_total_spend: number;
  historical_average_invoice: number;
  historical_largest_invoice: number;
  normal_invoice_min: number;
  normal_invoice_max: number;
  aliases: string[];
}

export interface VendorListResponse {
  items: VendorRecordResponse[];
  total: number;
}

// =============================================================================
// Phase 7: Batch Ingestion Types
// =============================================================================

export type BatchStatus =
  | 'RECEIVED'
  | 'VALIDATING'
  | 'UPLOADING'
  | 'QUEUING'
  | 'PROCESSING'
  | 'COMPLETED'
  | 'COMPLETED_WITH_EXCEPTIONS'
  | 'FAILED';

export type DocumentStatus =
  | 'RECEIVED'
  | 'VALIDATING'
  | 'UPLOADING'
  | 'STORED'
  | 'QUEUED'
  | 'DUPLICATE'
  | 'REJECTED'
  | 'FAILED'
  | 'AWAITING_EXTRACTION'
  | 'EXTRACTING'
  | 'EXTRACTION_COMPLETED'
  | 'EXTRACTION_VALIDATED'
  | 'INSUFFICIENT_CONFIDENCE'
  | 'INSUFFICIENT_DATA'
  | 'EXTRACTION_FAILED'
  | 'PROCESSING'
  | 'AUTO_APPROVED'
  | 'MANUAL_REVIEW'
  | 'BLOCKED';

export interface DocumentIngestionResponse {
  document_id: string;
  batch_id: string;
  original_filename: string;
  safe_filename: string;
  content_type: string;
  file_size: number;
  document_hash: string;
  s3_key?: string | null;
  status: DocumentStatus;
  created_at: string;
  updated_at: string;
  error_code?: string | null;
  error_message?: string | null;
  matched_document_id?: string | null;
  matched_batch_id?: string | null;
  duplicate_reason?: string | null;
  idempotency_key?: string | null;
  extraction_status?: string | null;
  overall_confidence?: number | null;
  extractor_provider?: string | null;
  extracted_invoice_id?: string | null;
  extraction_summary?: Record<string, any> | null;
}

export interface BatchResponse {
  batch_id: string;
  status: BatchStatus;
  source: string;
  created_at: string;
  updated_at: string;
  document_count: number;
  received_count: number;
  accepted_count: number;
  rejected_count: number;
  duplicate_count: number;
  failed_count: number;
  queued_count: number;
  processing_count: number;
  completed_count: number;
  auto_approved_count: number;
  manual_review_count: number;
  blocked_count: number;
  error_count: number;
  extracting_count?: number;
  extraction_completed_count?: number;
  insufficient_confidence_count?: number;
  extraction_failed_count?: number;
  documents?: DocumentIngestionResponse[];
}

export interface BatchListResponse {
  items: BatchResponse[];
  total: number;
  limit: number;
  offset: number;
}

export interface BatchDocumentsResponse {
  batch_id: string;
  items: DocumentIngestionResponse[];
  total: number;
}


// =============================================================================
// Phase 8: Extraction & OCR Understanding Types
// =============================================================================

export type FieldStatus =
  | 'EXTRACTED'
  | 'INFERRED'
  | 'DEFAULTED'
  | 'CORRECTED'
  | 'NOT_STATED'
  | 'MISSING';

export type ExtractionStatus =
  | 'SUCCESS'
  | 'INSUFFICIENT_CONFIDENCE'
  | 'INSUFFICIENT_DATA'
  | 'ARITHMETIC_MISMATCH'
  | 'FAILED';

export interface ExtractionField {
  field_name: string;
  value?: any;
  confidence: number;
  status: FieldStatus;
  raw_text?: string | null;
  location?: {
    page: number;
    bbox?: [number, number, number, number] | null;
  } | null;
  normalization_notes?: string | null;
}

export interface ExtractionLineItem {
  item_id?: string | null;
  description: ExtractionField;
  quantity: ExtractionField;
  unit_price: ExtractionField;
  amount: ExtractionField;
  line_index: number;
}

export interface ExtractionResult {
  document_id: string;
  batch_id: string;
  status: ExtractionStatus;
  overall_confidence: number;
  extractor_provider: string;
  extractor_version: string;
  invoice_fields: Record<string, ExtractionField>;
  financials: Record<string, ExtractionField>;
  line_items: ExtractionLineItem[];
  computed_subtotal?: number | null;
  computed_total?: number | null;
  discrepancy?: number | null;
  errors?: string[];
  warnings?: string[];
  reconstructed_invoice?: any;
  extracted_at?: string;
  human_corrected?: boolean;
}

export interface DocumentCorrectionRequest {
  corrections: Record<string, {
    value: any;
    note?: string;
  }>;
  reviewer?: string;
}


export interface BatchProgressResponse {
  batch_id: string;
  status: string;
  total_documents: number;
  extracted_count: number;
  queued_count: number;
  processing_count: number;
  completed_count: number;
  auto_approved_count: number;
  manual_review_count: number;
  blocked_count: number;
  duplicate_count: number;
  failed_count: number;
  percent_complete: number;
  documents_per_minute: number;
  elapsed_seconds: number;
  retry_count: number;
}

export interface BatchResumeResponse {
  batch_id: string;
  resumed_count: number;
  status: string;
  message: string;
}
