export interface Condition {
  id: string;
  condition_name: string;
  status: string;
  diagnosed_date?: string;
  notes?: string;
  provenance: string;
}

export interface Allergy {
  id: string;
  allergen: string;
  reaction?: string;
  severity: string;
  provenance: string;
}

export interface Medication {
  id: string;
  medication_name: string;
  dosage?: string;
  frequency?: string;
  route?: string;
  provenance: string;
}

export interface Symptom {
  id: string;
  symptom: string;
  duration?: string;
  severity: string;
  provenance: string;
}

export interface Patient {
  id: string;
  mrn: string;
  first_name: string;
  last_name: string;
  date_of_birth: string;
  age: number;
  sex: string;
  contact_phone?: string;
  contact_email?: string;
  relevant_history?: string;
  notes?: string;
  is_archived?: boolean;
  is_synthetic_demo: boolean;
  conditions: Condition[];
  allergies: Allergy[];
  medications: Medication[];
  symptoms: Symptom[];
  created_at: string;
}

export interface DocumentOverviewItem {
  id: string;
  filename: string;
  file_type: string;
  file_size_bytes: number;
  facility_name?: string;
  upload_date: string;
  processing_status: string;
  sha256_checksum: string;
}

export interface LabResultOverviewItem {
  id: string;
  test_name: string;
  category: string;
  numerical_value?: number;
  text_value?: string;
  unit?: string;
  flag: string;
  reference_low?: number;
  reference_high?: number;
  reference_text?: string;
  collection_date?: string;
  provenance?: string;
  is_verified?: boolean;
  original_ai_value?: string;
  confidence?: number;
}

export interface ConflictOverviewItem {
  id: string;
  conflict_type: string;
  severity: 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO' | string;
  description: string;
  status: 'OPEN' | 'REVIEWED' | 'RESOLVED' | 'DISMISSED' | 'UNRESOLVED' | string;
  source_one?: string;
  source_two?: string;
  conflicting_values?: string;
  created_at: string;
}

export interface SummaryOverviewItem {
  id: string;
  summary_type: string;
  content: string;
  provenance: string;
  generated_at: string;
}

export interface TimelineEventOverviewItem {
  id: string;
  date: string;
  title: string;
  event_type: string;
  description: string;
  badge_type: string;
  source_provenance: string;
}

export interface PatientOverview extends Patient {
  documents: DocumentOverviewItem[];
  lab_results: LabResultOverviewItem[];
  conflicts: ConflictOverviewItem[];
  summaries: SummaryOverviewItem[];
  timeline: TimelineEventOverviewItem[];
}

export interface DocumentItem {
  id: string;
  patient_id: string;
  original_filename: string;
  file_type: string;
  file_size_bytes: number;
  sha256_checksum: string;
  report_date?: string;
  document_type: string;
  facility?: string;
  processing_status: 'QUEUED' | 'PROCESSING' | 'COMPLETED' | 'FAILED' | 'REVIEW_REQUIRED';
  processing_error?: string;
  raw_text?: string;
  created_at: string;
}

export interface ConflictItem {
  id: string;
  patient_id: string;
  conflict_type: string;
  severity: 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO' | string;
  title: string;
  description: string;
  source_a?: string;
  source_b?: string;
  conflicting_values?: string;
  status: 'OPEN' | 'REVIEWED' | 'RESOLVED' | 'DISMISSED' | 'UNRESOLVED' | string;
  resolution_notes?: string;
  resolved_by?: string;
  resolved_at?: string;
  created_at: string;
}

export interface ReviewItem {
  id: string;
  document_id?: string;
  patient_id: string;
  target_type: string;
  target_id: string;
  field_name: string;
  current_value?: string;
  original_value?: string;
  corrected_value?: string;
  confidence?: number;
  source_text?: string;
  reason: string;
  priority: 'HIGH' | 'MEDIUM' | 'LOW' | string;
  status: 'PENDING' | 'ACCEPTED' | 'EDITED' | 'REJECTED' | 'DEFERRED' | string;
  reviewer_note?: string;
  reviewed_by?: string;
  reviewed_at?: string;
  created_at: string;
}

export interface GlobalSearchResultItem {
  category: 'PATIENT' | 'DOCUMENT' | 'DIAGNOSIS' | 'MEDICATION' | 'LABORATORY' | 'CONFLICT';
  title: string;
  subtitle: string;
  patient_id?: string;
  document_id?: string;
  link_tab: string;
}

export interface GlobalSearchResponse {
  query: string;
  total_matches: number;
  results: GlobalSearchResultItem[];
}

export interface OperationalStats {
  total_patients: number;
  patients_requiring_review?: number;
  patients_with_high_conflicts?: number;

  reports_processed: number;
  total_documents?: number;
  processing_documents?: number;
  queued_documents?: number;
  failed_documents?: number;

  pending_reviews: number;
  high_priority_reviews?: number;
  verified_reviews?: number;
  corrected_reviews?: number;
  rejected_reviews?: number;
  deferred_reviews?: number;

  total_conflicts?: number;
  high_conflicts?: number;
  medium_conflicts?: number;
  low_conflicts?: number;
  open_conflicts?: number;
  resolved_conflicts?: number;
  dismissed_conflicts?: number;
  unresolved_conflicts: number;

  total_clinical_items?: number;
  ai_extracted_items?: number;
  human_verified_items?: number;
  human_corrected_items?: number;
  human_rejected_items?: number;

  system_status: string;
  demo_mode: boolean;
  recent_activity: Array<{
    id: string;
    action: string;
    entity_type: string;
    entity_id: string;
    timestamp: string;
    user_id: string;
  }>;
}

export interface AuditLogEntry {
  id: string;
  timestamp: string;
  action: string;
  entity_type: string;
  entity_id: string;
  user_id: string;
  ip_address: string;
  details?: string;
}
