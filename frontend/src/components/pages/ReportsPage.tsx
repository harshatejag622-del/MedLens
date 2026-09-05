import React, { useState, useEffect, useRef } from 'react';
import {
  FileText,
  UploadCloud,
  CheckCircle,
  Clock,
  AlertCircle,
  AlertTriangle,
  Eye,
  Hash,
  Building2,
  Calendar,
  RotateCw,
  Trash2,
  Download,
  Search,
  Filter,
  FileCheck,
  X,
  Plus,
  Zap,
  Cpu,
  Loader2
} from 'lucide-react';
import { DocumentItem, Patient } from '../../types';
import { api } from '../../services/api';

interface ReportsPageProps {
  documents: DocumentItem[];
  patients?: Patient[];
  onRefresh?: () => Promise<void>;
}

export const ReportsPage: React.FC<ReportsPageProps> = ({
  documents,
  patients = [],
  onRefresh
}) => {
  const [selectedDoc, setSelectedDoc] = useState<DocumentItem | null>(documents[0] || null);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [searchFilter, setSearchFilter] = useState('');

  // Upload Form State
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [targetPatientId, setTargetPatientId] = useState<string>(patients[0]?.id || '');
  const [docType, setDocType] = useState('LABORATORY_REPORT');
  const [facilityName, setFacilityName] = useState('St. Jude Clinical Laboratories');
  const [sourceName, setSourceName] = useState('Outpatient Diagnostic Center');
  const [reportDate, setReportDate] = useState(new Date().toISOString().split('T')[0]);

  // Upload Progress & Errors
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccessMsg, setUploadSuccessMsg] = useState<string | null>(null);
  const [actionInProgress, setActionInProgress] = useState(false);

  // AI Processing state
  const [processingDocId, setProcessingDocId] = useState<string | null>(null);
  const [processingMsg, setProcessingMsg] = useState<string | null>(null);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // File selection & client-side pre-validation
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setUploadError(null);
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      const ext = file.name.split('.').pop()?.toLowerCase();
      const allowed = ['pdf', 'png', 'jpg', 'jpeg', 'tiff', 'webp', 'txt'];

      if (!ext || !allowed.includes(ext)) {
        setUploadError(`Unsupported file format '.${ext}'. Please upload PDF, PNG, JPG, JPEG, TIFF, WEBP, or TXT.`);
        return;
      }

      if (file.size > 25 * 1024 * 1024) {
        setUploadError(`File size (${(file.size / (1024 * 1024)).toFixed(1)}MB) exceeds the 25MB limit.`);
        return;
      }

      setSelectedFile(file);
    }
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setUploadError('Please select a file to upload.');
      return;
    }
    if (!targetPatientId) {
      setUploadError('Please select a patient to associate this report with.');
      return;
    }

    try {
      setUploading(true);
      setUploadProgress(10);
      setUploadError(null);
      setUploadSuccessMsg(null);

      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('patient_id', targetPatientId);
      formData.append('document_type', docType);
      formData.append('facility', facilityName);
      formData.append('source', sourceName);
      formData.append('report_date', reportDate);

      const res = await api.uploadDocument(formData, (pct) => {
        setUploadProgress(Math.max(pct, 15));
      });

      setUploadProgress(100);
      setUploadSuccessMsg(`Document '${res.document.original_filename}' uploaded successfully (State: QUEUED).`);

      if (onRefresh) {
        await onRefresh();
      }

      setTimeout(() => {
        setShowUploadModal(false);
        setSelectedFile(null);
        setUploadProgress(0);
        setUploadSuccessMsg(null);
      }, 1200);
    } catch (err: any) {
      setUploadError(err.message || 'Failed to upload document.');
    } finally {
      setUploading(false);
    }
  };

  const handleRetry = async (docId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      setActionInProgress(true);
      await api.retryDocument(docId);
      if (onRefresh) await onRefresh();
    } catch (err: any) {
      alert(err.message || 'Error triggering retry');
    } finally {
      setActionInProgress(false);
    }
  };

  const handleProcessDocument = async (docId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      setProcessingDocId(docId);
      setProcessingMsg('Starting AI extraction pipeline...');
      await api.processDocument(docId);
      setProcessingMsg('Processing... extracting clinical entities');

      // Poll status every 2 seconds until complete or failed
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = setInterval(async () => {
        try {
          const status = await api.getDocumentStatus(docId);
          if (status.processing_status === 'COMPLETED') {
            clearInterval(pollIntervalRef.current!);
            setProcessingDocId(null);
            setProcessingMsg(null);
            if (onRefresh) await onRefresh();
          } else if (status.processing_status === 'FAILED' || status.processing_status === 'REVIEW_REQUIRED') {
            clearInterval(pollIntervalRef.current!);
            setProcessingMsg(`Extraction ${status.processing_status.toLowerCase()}. Check document details.`);
            setTimeout(() => { setProcessingDocId(null); setProcessingMsg(null); }, 4000);
            if (onRefresh) await onRefresh();
          } else {
            setProcessingMsg(`Processing (${status.current_step || status.processing_status})...`);
          }
        } catch {
          clearInterval(pollIntervalRef.current!);
          setProcessingDocId(null);
          setProcessingMsg(null);
        }
      }, 2000);
    } catch (err: any) {
      setProcessingDocId(null);
      setProcessingMsg(null);
      alert(err.message || 'Error starting AI extraction');
    }
  };

  // Cleanup polling on unmount
  useEffect(() => {
    return () => { if (pollIntervalRef.current) clearInterval(pollIntervalRef.current); };
  }, []);

  const handleDelete = async (docId: string, filename: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm(`Are you sure you want to delete '${filename}'? This will permanently remove the stored physical file and record.`)) {
      return;
    }
    try {
      setActionInProgress(true);
      await api.deleteDocument(docId);
      if (selectedDoc?.id === docId) {
        setSelectedDoc(null);
      }
      if (onRefresh) await onRefresh();
    } catch (err: any) {
      alert(err.message || 'Error deleting document');
    } finally {
      setActionInProgress(false);
    }
  };

  const filteredDocs = documents.filter((doc) => {
    const matchesStatus = statusFilter === 'ALL' || doc.processing_status === statusFilter;
    const term = searchFilter.toLowerCase().trim();
    const matchesSearch =
      !term ||
      doc.original_filename.toLowerCase().includes(term) ||
      doc.sha256_checksum.toLowerCase().includes(term) ||
      (doc.facility && doc.facility.toLowerCase().includes(term));

    return matchesStatus && matchesSearch;
  });

  return (
    <div className="space-y-6 animate-fadeIn pb-12">
      {/* Page Header & Action Button */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-wide flex items-center gap-2.5">
            <FileText className="w-6 h-6 text-teal-400" />
            <span>Medical Reports & Ingestion</span>
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Secure, immutable document storage with SHA-256 verification, safe filename handling, and asynchronous state tracking.
          </p>
        </div>

        <button
          onClick={() => {
            setUploadError(null);
            setUploadSuccessMsg(null);
            setSelectedFile(null);
            if (patients.length > 0 && !targetPatientId) {
              setTargetPatientId(patients[0].id);
            }
            setShowUploadModal(true);
          }}
          className="px-4 py-2.5 rounded-xl bg-teal-600 hover:bg-teal-500 text-white text-xs font-semibold tracking-wider flex items-center gap-2 shadow-[0_0_15px_rgba(20,184,166,0.3)] transition-all self-start sm:self-auto"
        >
          <UploadCloud className="w-4 h-4" />
          <span>Upload Medical Report</span>
        </button>
      </div>

      {/* Filter & Search Bar */}
      <div className="bg-[#0e1424] border border-slate-800 rounded-2xl p-4 shadow-lg flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="relative w-full md:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchFilter}
            onChange={(e) => setSearchFilter(e.target.value)}
            placeholder="Search by filename, checksum, or facility..."
            className="w-full pl-10 pr-4 py-2 bg-slate-900 border border-slate-700/80 rounded-xl text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-teal-500 transition-colors"
          />
        </div>

        <div className="flex items-center gap-3 w-full md:w-auto flex-wrap">
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <Filter className="w-3.5 h-3.5 text-teal-400" />
            <span>State:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-2.5 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500"
            >
              <option value="ALL">All States</option>
              <option value="QUEUED">Queued</option>
              <option value="PROCESSING">Processing</option>
              <option value="COMPLETED">Completed</option>
              <option value="REVIEW_REQUIRED">Review Required</option>
              <option value="FAILED">Failed</option>
            </select>
          </div>
          <span className="text-xs text-slate-500 font-mono">
            {filteredDocs.length} of {documents.length} records
          </span>
        </div>
      </div>

      {/* Main Reports Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* Document Cards List */}
        <div className="lg:col-span-7 space-y-3">
          {filteredDocs.map((doc) => {
            const isSelected = selectedDoc?.id === doc.id;
            return (
              <div
                key={doc.id}
                onClick={() => setSelectedDoc(doc)}
                className={`p-5 rounded-2xl border transition-all cursor-pointer ${
                  isSelected
                    ? 'border-teal-500 bg-[#0f1a2c] shadow-[0_0_20px_rgba(20,184,166,0.15)]'
                    : 'border-slate-800 bg-[#0e1424] hover:border-slate-700'
                }`}
              >
                <div className="flex items-start justify-between gap-3 mb-2">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-bold text-white truncate max-w-xs sm:max-w-md">
                        {doc.original_filename}
                      </h3>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                        {doc.document_type}
                      </span>
                    </div>

                    <div className="flex items-center gap-3 text-[11px] text-slate-400 flex-wrap">
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3 h-3 text-slate-500" />
                        <span>{doc.report_date || new Date(doc.created_at).toLocaleDateString()}</span>
                      </span>
                      <span>•</span>
                      <span className="flex items-center gap-1">
                        <Building2 className="w-3 h-3 text-slate-500" />
                        <span>{doc.facility || 'Clinical Laboratory'}</span>
                      </span>
                    </div>
                  </div>

                  {/* Processing Status Badge */}
                  <span
                    className={`px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold uppercase tracking-wider flex-shrink-0 ${
                      doc.processing_status === 'COMPLETED'
                        ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                        : doc.processing_status === 'REVIEW_REQUIRED'
                        ? 'bg-amber-500/15 text-amber-300 border border-amber-500/30'
                        : doc.processing_status === 'FAILED'
                        ? 'bg-rose-500/15 text-rose-300 border border-rose-500/30'
                        : doc.processing_status === 'PROCESSING'
                        ? 'bg-sky-500/15 text-sky-300 border border-sky-500/30 animate-pulse'
                        : 'bg-amber-500/10 text-amber-300 border border-amber-500/20'
                    }`}
                  >
                    {doc.processing_status}
                  </span>
                </div>

                {/* Footer bar */}
                <div className="flex items-center justify-between text-[10px] font-mono text-slate-500 pt-3 border-t border-slate-800/80">
                  <span className="flex items-center gap-1 truncate max-w-[280px]" title={doc.sha256_checksum}>
                    <Hash className="w-3 h-3 text-teal-400/80" /> SHA-256: {doc.sha256_checksum.slice(0, 16)}...
                  </span>

                  <div className="flex items-center gap-3">
                    <span>{(doc.file_size_bytes / 1024).toFixed(1)} KB</span>

                    {/* Retry button for failed or review required items */}
                    {(doc.processing_status === 'FAILED' || doc.processing_status === 'REVIEW_REQUIRED') && (
                      <button
                        onClick={(e) => handleRetry(doc.id, e)}
                        disabled={actionInProgress}
                        className="px-2 py-0.5 rounded bg-teal-500/10 hover:bg-teal-500/20 text-teal-300 border border-teal-500/30 text-[10px] flex items-center gap-1"
                        title="Retry processing job"
                      >
                        <RotateCw className="w-2.5 h-2.5" /> Retry
                      </button>
                    )}

                    {/* Delete button */}
                    <button
                      onClick={(e) => handleDelete(doc.id, doc.original_filename, e)}
                      disabled={actionInProgress}
                      className="text-slate-500 hover:text-rose-400 p-1"
                      title="Delete document"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}

          {filteredDocs.length === 0 && (
            <div className="p-12 text-center rounded-2xl bg-[#0e1424] border border-slate-800 text-slate-500 text-xs space-y-2">
              <FileText className="w-8 h-8 text-slate-600 mx-auto" />
              <p className="font-semibold text-slate-400">No Medical Documents Found</p>
              <p className="text-[11px] text-slate-500">
                Click "Upload Medical Report" to ingest PDF, PNG, JPG, or TXT laboratory results.
              </p>
            </div>
          )}
        </div>

        {/* Document Inspection & Metadata Inspector */}
        <div className="lg:col-span-5">
          {selectedDoc ? (
            <div className="p-6 rounded-2xl bg-[#0e1424] border border-slate-800 space-y-5 sticky top-20 shadow-xl">
              <div className="border-b border-slate-800 pb-3">
                <span className="text-[10px] font-mono uppercase text-teal-400 font-bold tracking-wider">
                  Document Metadata Inspector
                </span>
                <h3 className="text-base font-bold text-white mt-1 truncate">
                  {selectedDoc.original_filename}
                </h3>
                <span className="text-xs text-slate-400 font-mono">
                  Document ID: {selectedDoc.id}
                </span>
              </div>

              {/* Metadata Key-Value List */}
              <div className="space-y-2 text-xs">
                <div className="flex justify-between py-1 border-b border-slate-800/60">
                  <span className="text-slate-400">Document Type:</span>
                  <span className="text-white font-mono font-medium">{selectedDoc.document_type}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-800/60">
                  <span className="text-slate-400">Patient ID:</span>
                  <span className="text-teal-300 font-mono">{selectedDoc.patient_id}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-800/60">
                  <span className="text-slate-400">MIME Content-Type:</span>
                  <span className="text-slate-300 font-mono">{selectedDoc.file_type}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-800/60">
                  <span className="text-slate-400">File Size:</span>
                  <span className="text-slate-300 font-mono">
                    {(selectedDoc.file_size_bytes / 1024).toFixed(1)} KB ({selectedDoc.file_size_bytes.toLocaleString()} bytes)
                  </span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-800/60">
                  <span className="text-slate-400">Origin / Facility:</span>
                  <span className="text-slate-300">{selectedDoc.facility || 'Clinical Center'}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-800/60">
                  <span className="text-slate-400">Upload Timestamp:</span>
                  <span className="text-slate-300 font-mono">
                    {new Date(selectedDoc.created_at).toLocaleString()}
                  </span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-800/60">
                  <span className="text-slate-400">Processing State:</span>
                  <span className="text-amber-400 font-mono font-bold">{selectedDoc.processing_status}</span>
                </div>
              </div>

              {/* Cryptographic Verification Box */}
              <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1 text-xs">
                <span className="text-[10px] font-mono text-teal-400 uppercase font-bold tracking-wider flex items-center gap-1.5">
                  <Hash className="w-3.5 h-3.5" /> Cryptographic SHA-256 Checksum
                </span>
                <p className="font-mono text-[11px] text-slate-300 break-all bg-slate-950/60 p-2 rounded border border-slate-800/60">
                  {selectedDoc.sha256_checksum}
                </p>
                <span className="text-[10px] text-slate-500 italic block pt-0.5">
                  Verified against original stored bytes. Guaranteed immutable.
                </span>
              </div>

              {/* Error Box if FAILED */}
              {selectedDoc.processing_error && (
                <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300 space-y-1">
                  <span className="font-bold flex items-center gap-1.5 text-rose-400">
                    <AlertCircle className="w-4 h-4" /> Processing Exception
                  </span>
                  <p>{selectedDoc.processing_error}</p>
                </div>
              )}

              {/* Live processing indicator */}
              {processingDocId === selectedDoc.id && processingMsg && (
                <div className="p-3 rounded-xl bg-violet-500/10 border border-violet-500/30 flex items-center gap-2.5 text-xs text-violet-300">
                  <Loader2 className="w-4 h-4 text-violet-400 animate-spin flex-shrink-0" />
                  <span>{processingMsg}</span>
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex flex-wrap items-center gap-2 pt-2">
                <a
                  href={`http://127.0.0.1:8000/api/documents/${selectedDoc.id}/download`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex-1 px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold flex items-center justify-center gap-2 border border-slate-700 transition-colors"
                >
                  <Download className="w-3.5 h-3.5 text-teal-400" />
                  <span>Download Original</span>
                </a>

                {/* Process (AI Extract) button — for QUEUED/FAILED/REVIEW_REQUIRED */}
                {['QUEUED', 'FAILED', 'REVIEW_REQUIRED'].includes(selectedDoc.processing_status) && (
                  <button
                    onClick={(e) => handleProcessDocument(selectedDoc.id, e)}
                    disabled={processingDocId === selectedDoc.id || actionInProgress}
                    className="flex-1 px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white text-xs font-semibold flex items-center justify-center gap-1.5 shadow-lg shadow-violet-600/30 transition-all"
                  >
                    {processingDocId === selectedDoc.id
                      ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      : <Zap className="w-3.5 h-3.5" />
                    }
                    <span>{processingDocId === selectedDoc.id ? 'Extracting...' : 'AI Extract'}</span>
                  </button>
                )}

                {/* Retry button — only for FAILED/REVIEW_REQUIRED */}
                {(selectedDoc.processing_status === 'FAILED' || selectedDoc.processing_status === 'REVIEW_REQUIRED') && (
                  <button
                    onClick={(e) => handleRetry(selectedDoc.id, e)}
                    disabled={actionInProgress || processingDocId === selectedDoc.id}
                    className="px-4 py-2 rounded-xl bg-slate-700 hover:bg-slate-600 text-slate-200 text-xs font-semibold flex items-center gap-1.5 border border-slate-600 transition-all"
                  >
                    <RotateCw className="w-3.5 h-3.5" />
                    <span>Re-queue</span>
                  </button>
                )}
              </div>
            </div>
          ) : (
            <div className="p-12 text-center rounded-2xl bg-[#0e1424] border border-slate-800 text-slate-500 text-xs space-y-2 sticky top-20">
              <Eye className="w-8 h-8 text-slate-600 mx-auto" />
              <p className="font-semibold text-slate-400">No Document Selected</p>
              <p className="text-[11px] text-slate-500">
                Select a document from the list to inspect its SHA-256 cryptographic metadata and processing pipeline state.
              </p>
            </div>
          )}
        </div>

      </div>

      {/* ========================================================= */}
      {/* Upload Document Modal */}
      {/* ========================================================= */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 overflow-y-auto">
          <div className="bg-[#0e1424] border border-slate-700/80 rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden my-8 animate-fadeIn">
            
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-[#090d16]/70">
              <div>
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <UploadCloud className="w-5 h-5 text-teal-400" />
                  <span>Upload Medical Report</span>
                </h2>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Original documents are hashed, validated, and safely stored in isolated storage.
                </p>
              </div>
              <button
                onClick={() => setShowUploadModal(false)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {uploadError && (
              <div className="mx-6 mt-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-center gap-2.5 text-xs text-rose-300">
                <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
                <span>{uploadError}</span>
              </div>
            )}

            {uploadSuccessMsg && (
              <div className="mx-6 mt-4 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center gap-2.5 text-xs text-emerald-300">
                <CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                <span>{uploadSuccessMsg}</span>
              </div>
            )}

            <form onSubmit={handleUploadSubmit} className="p-6 space-y-4">
              
              {/* Patient Selector */}
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Target Patient <span className="text-rose-400">*</span>
                </label>
                <select
                  value={targetPatientId}
                  onChange={(e) => setTargetPatientId(e.target.value)}
                  required
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-teal-500 font-medium"
                >
                  {patients.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.first_name} {p.last_name} ({p.mrn}) - {p.age} y/o {p.sex}
                    </option>
                  ))}
                </select>
              </div>

              {/* Document Type */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Report Type</label>
                  <select
                    value={docType}
                    onChange={(e) => setDocType(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-teal-500"
                  >
                    <option value="LABORATORY_REPORT">Laboratory Report</option>
                    <option value="DISCHARGE_SUMMARY">Discharge Summary</option>
                    <option value="RADIOLOGY_REPORT">Radiology Report</option>
                    <option value="CLINICAL_NOTE">Clinical Note</option>
                    <option value="CONSULTATION">Consultation</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Report Date</label>
                  <input
                    type="date"
                    value={reportDate}
                    onChange={(e) => setReportDate(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-teal-500"
                  />
                </div>
              </div>

              {/* Facility & Source */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Origin Facility</label>
                  <input
                    type="text"
                    value={facilityName}
                    onChange={(e) => setFacilityName(e.target.value)}
                    placeholder="e.g. St. Jude Labs"
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-teal-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Clinical Source</label>
                  <input
                    type="text"
                    value={sourceName}
                    onChange={(e) => setSourceName(e.target.value)}
                    placeholder="e.g. Inpatient EHR"
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-teal-500"
                  />
                </div>
              </div>

              {/* Drag & Drop / File Input Box */}
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Document File (PDF, PNG, JPG, TIFF, WEBP, TXT) <span className="text-rose-400">*</span>
                </label>
                <div className="border-2 border-dashed border-slate-700 hover:border-teal-500 rounded-2xl p-6 text-center bg-slate-900/60 transition-colors">
                  <input
                    type="file"
                    id="doc-upload-input"
                    onChange={handleFileChange}
                    accept=".pdf,.png,.jpg,.jpeg,.tiff,.webp,.txt"
                    className="hidden"
                  />
                  <label
                    htmlFor="doc-upload-input"
                    className="cursor-pointer flex flex-col items-center space-y-2"
                  >
                    <UploadCloud className="w-8 h-8 text-teal-400 animate-bounce" />
                    <span className="text-xs font-semibold text-slate-200">
                      {selectedFile ? selectedFile.name : 'Click to select or drag & drop file'}
                    </span>
                    <span className="text-[10px] text-slate-500">
                      Maximum allowed size: 25MB • Strict magic-bytes integrity validation
                    </span>
                  </label>
                </div>
              </div>

              {/* Real-time Progress Bar */}
              {uploading && (
                <div className="space-y-1.5 pt-2">
                  <div className="flex justify-between text-[11px] font-mono text-teal-300">
                    <span>Uploading and hashing payload...</span>
                    <span>{uploadProgress}%</span>
                  </div>
                  <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                    <div
                      className="bg-teal-500 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${uploadProgress}%` }}
                    ></div>
                  </div>
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowUploadModal(false)}
                  disabled={uploading}
                  className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={uploading || !selectedFile}
                  className="px-5 py-2 rounded-xl bg-teal-600 hover:bg-teal-500 text-white text-xs font-semibold tracking-wide flex items-center gap-2 shadow-[0_0_12px_rgba(20,184,166,0.3)] transition-all disabled:opacity-50"
                >
                  <UploadCloud className="w-4 h-4" />
                  <span>{uploading ? 'Ingesting...' : 'Ingest Document'}</span>
                </button>
              </div>

            </form>
          </div>
        </div>
      )}

    </div>
  );
};
