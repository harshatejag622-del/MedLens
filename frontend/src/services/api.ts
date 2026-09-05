import { Patient, PatientOverview, DocumentItem, ConflictItem, ReviewItem, OperationalStats, AuditLogEntry } from '../types';

const API_ROOT = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
const API_BASE = `${API_ROOT}/api`;

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(errorBody.detail || `Request failed with status ${res.status}`);
  }
  return res.json();
}

export interface PatientSearchParams {
  search?: string;
  sex?: string;
  age_min?: number;
  age_max?: number;
  status?: string;
  include_archived?: boolean;
}

export const api = {
  async getHealth(): Promise<{ status: string; version: string; service: string }> {
    const res = await fetch(`${API_ROOT}/health`);
    return handleResponse(res);
  },

  async getStats(): Promise<OperationalStats> {
    const res = await fetch(`${API_BASE}/stats`);
    return handleResponse(res);
  },

  async getPatients(params?: PatientSearchParams | string): Promise<Patient[]> {
    let url = `${API_BASE}/patients`;
    if (typeof params === 'string') {
      url += `?search=${encodeURIComponent(params)}`;
    } else if (params) {
      const searchParams = new URLSearchParams();
      if (params.search) searchParams.append('search', params.search);
      if (params.sex) searchParams.append('sex', params.sex);
      if (params.age_min !== undefined) searchParams.append('age_min', params.age_min.toString());
      if (params.age_max !== undefined) searchParams.append('age_max', params.age_max.toString());
      if (params.status) searchParams.append('status', params.status);
      if (params.include_archived) searchParams.append('include_archived', 'true');
      const queryStr = searchParams.toString();
      if (queryStr) url += `?${queryStr}`;
    }
    const res = await fetch(url);
    return handleResponse(res);
  },

  async getPatient(id: string): Promise<Patient> {
    const res = await fetch(`${API_BASE}/patients/${id}`);
    return handleResponse(res);
  },

  async getPatientOverview(id: string): Promise<PatientOverview> {
    const res = await fetch(`${API_BASE}/patients/${id}`);
    return handleResponse(res);
  },

  async createPatient(payload: any): Promise<Patient> {
    const res = await fetch(`${API_BASE}/patients`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    return handleResponse(res);
  },

  async updatePatient(id: string, payload: any): Promise<Patient> {
    const res = await fetch(`${API_BASE}/patients/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    return handleResponse(res);
  },

  async deletePatient(id: string): Promise<{ success: boolean; message: string }> {
    const res = await fetch(`${API_BASE}/patients/${id}`, {
      method: 'DELETE'
    });
    return handleResponse(res);
  },

  async archivePatient(id: string): Promise<Patient> {
    const res = await fetch(`${API_BASE}/patients/${id}/archive`, {
      method: 'POST'
    });
    return handleResponse(res);
  },

  async unarchivePatient(id: string): Promise<Patient> {
    const res = await fetch(`${API_BASE}/patients/${id}/unarchive`, {
      method: 'POST'
    });
    return handleResponse(res);
  },

  async getDocuments(patientId?: string): Promise<DocumentItem[]> {
    const url = patientId ? `${API_BASE}/documents?patient_id=${patientId}` : `${API_BASE}/documents`;
    const res = await fetch(url);
    return handleResponse(res);
  },

  async uploadDocument(
    formData: FormData,
    onProgress?: (percent: number) => void
  ): Promise<{ document: DocumentItem; job: any; message: string }> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${API_BASE}/documents/upload`);

      if (onProgress && xhr.upload) {
        xhr.upload.onprogress = (event) => {
          if (event.lengthComputable) {
            const percent = Math.round((event.loaded / event.total) * 100);
            onProgress(percent);
          }
        };
      }

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const parsed = JSON.parse(xhr.responseText);
            resolve(parsed);
          } catch (e) {
            reject(new Error("Failed to parse server response"));
          }
        } else {
          try {
            const err = JSON.parse(xhr.responseText);
            reject(new Error(err.detail || `Upload failed with status ${xhr.status}`));
          } catch {
            reject(new Error(`Upload failed with status ${xhr.status}`));
          }
        }
      };

      xhr.onerror = () => {
        reject(new Error("Network error during document upload"));
      };

      xhr.send(formData);
    });
  },

  async retryDocument(documentId: string): Promise<any> {
    const res = await fetch(`${API_BASE}/documents/${documentId}/retry`, {
      method: 'POST'
    });
    return handleResponse(res);
  },

  async deleteDocument(documentId: string): Promise<{ success: boolean; message: string }> {
    const res = await fetch(`${API_BASE}/documents/${documentId}`, {
      method: 'DELETE'
    });
    return handleResponse(res);
  },


  async getConflicts(patientId?: string): Promise<ConflictItem[]> {
    const url = patientId ? `${API_BASE}/conflicts?patient_id=${patientId}` : `${API_BASE}/conflicts`;
    const res = await fetch(url);
    return handleResponse(res);
  },

  async resolveConflict(id: string, notes: string, newStatus: string = 'RESOLVED'): Promise<ConflictItem> {
    const res = await fetch(`${API_BASE}/conflicts/${id}/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ resolution_notes: notes, resolved_by: 'clinician_user', new_status: newStatus })
    });
    return handleResponse(res);
  },

  async detectConflicts(patientId: string): Promise<ConflictItem[]> {
    const res = await fetch(`${API_BASE}/conflicts/detect/${patientId}`, {
      method: 'POST'
    });
    return handleResponse(res);
  },

  async getReviewQueue(patientId?: string): Promise<ReviewItem[]> {
    const url = patientId ? `${API_BASE}/review?patient_id=${patientId}` : `${API_BASE}/review`;
    const res = await fetch(url);
    return handleResponse(res);
  },

  async getReviewItemDetails(id: string): Promise<any> {
    const res = await fetch(`${API_BASE}/review/${id}`);
    return handleResponse(res);
  },

  async takeReviewAction(id: string, action: string, correctedValue?: string, reason?: string): Promise<ReviewItem> {
    const res = await fetch(`${API_BASE}/review/${id}/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action,
        corrected_value: correctedValue,
        change_reason: reason,
        reviewer_id: 'clinician_user'
      })
    });
    return handleResponse(res);
  },

  async getAuditLogs(): Promise<AuditLogEntry[]> {
    const res = await fetch(`${API_BASE}/audit?limit=50`);
    return handleResponse(res);
  },

  async processDocument(documentId: string): Promise<{ document_id: string; processing_status: string; message: string }> {
    const res = await fetch(`${API_BASE}/documents/${documentId}/process`, {
      method: 'POST',
    });
    return handleResponse(res);
  },

  async getDocumentStatus(documentId: string): Promise<{ processing_status: string; current_step?: string }> {
    const res = await fetch(`${API_BASE}/documents/${documentId}/status`);
    return handleResponse(res);
  },

  async getTimeline(
    patientId: string,
    params?: {
      sort_order?: string;
      event_type?: string[];
      date_from?: string;
      date_to?: string;
      verification_status?: string;
      search_query?: string;
    }
  ): Promise<any> {
    let url = `${API_BASE}/timeline/${patientId}?`;
    if (params?.sort_order) url += `sort_order=${params.sort_order}&`;
    if (params?.date_from) url += `date_from=${params.date_from}&`;
    if (params?.date_to) url += `date_to=${params.date_to}&`;
    if (params?.verification_status) url += `verification_status=${encodeURIComponent(params.verification_status)}&`;
    if (params?.search_query) url += `search_query=${encodeURIComponent(params.search_query)}&`;
    if (params?.event_type && params.event_type.length > 0) {
      params.event_type.forEach(et => {
        url += `event_type=${encodeURIComponent(et)}&`;
      });
    }
    const res = await fetch(url);
    return handleResponse(res);
  },

  async getLabTrends(patientId: string): Promise<any> {
    const res = await fetch(`${API_BASE}/timeline/${patientId}/trends`);
    return handleResponse(res);
  },

  async getMedicationHistory(patientId: string): Promise<any> {
    const res = await fetch(`${API_BASE}/timeline/${patientId}/medications`);
    return handleResponse(res);
  },

  async getDiagnosisHistory(patientId: string): Promise<any> {
    const res = await fetch(`${API_BASE}/timeline/${patientId}/diagnoses`);
    return handleResponse(res);
  },

  async generateClinicalSummary(patientId: string): Promise<any> {
    const res = await fetch(`${API_BASE}/timeline/${patientId}/summary`, {
      method: 'POST'
    });
    return handleResponse(res);
  },

  async globalSearch(query: string): Promise<any> {
    const res = await fetch(`${API_BASE}/stats/search?q=${encodeURIComponent(query)}`);
    return handleResponse(res);
  },
};

