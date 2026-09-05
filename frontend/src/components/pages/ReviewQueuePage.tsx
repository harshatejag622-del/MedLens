import React, { useState } from 'react';
import {
  CheckSquare,
  Check,
  X,
  Edit3,
  AlertCircle,
  ShieldAlert,
  Clock,
  Filter,
  Eye,
  FileText,
  HelpCircle,
  CornerDownRight,
  ShieldCheck,
  UserCheck,
  RotateCcw
} from 'lucide-react';
import { ReviewItem } from '../../types';
import { api } from '../../services/api';

interface ReviewQueueProps {
  items: ReviewItem[];
  onAction: (id: string, action: string, correctedValue?: string, reason?: string) => Promise<void>;
}

export const ReviewQueuePage: React.FC<ReviewQueueProps> = ({ items, onAction }) => {
  const [actingId, setActingId] = useState<string | null>(null);
  
  // Filters
  const [statusFilter, setStatusFilter] = useState<'PENDING' | 'ACCEPTED' | 'EDITED' | 'REJECTED' | 'DEFERRED' | 'ALL'>('PENDING');
  const [priorityFilter, setPriorityFilter] = useState<string>('ALL');
  const [typeFilter, setTypeFilter] = useState<string>('ALL');

  // Side-by-side inspection drawer / modal
  const [selectedReview, setSelectedReview] = useState<any | null>(null);
  const [loadingDetails, setLoadingDetails] = useState(false);

  // Edit / Action modal state
  const [actionModalItem, setActionModalItem] = useState<ReviewItem | null>(null);
  const [actionModalType, setActionModalType] = useState<'ACCEPT' | 'CORRECT' | 'REJECT' | 'DEFER'>('ACCEPT');
  const [correctedVal, setCorrectedVal] = useState('');
  const [actionReason, setActionReason] = useState('');

  // Open detailed side-by-side view
  const handleOpenDetails = async (item: ReviewItem) => {
    try {
      setLoadingDetails(true);
      const data = await api.getReviewItemDetails(item.id);
      setSelectedReview(data);
    } catch (e: any) {
      alert(e.message || 'Error fetching review item details');
    } finally {
      setLoadingDetails(false);
    }
  };

  const handleOpenActionModal = (item: ReviewItem, action: 'ACCEPT' | 'CORRECT' | 'REJECT' | 'DEFER') => {
    setActionModalItem(item);
    setActionModalType(action);
    setCorrectedVal(item.current_value || '');
    if (action === 'ACCEPT') {
      setActionReason('Verified against source report. Extraction confirmed accurate.');
    } else if (action === 'REJECT') {
      setActionReason('Extraction rejected. Value does not match source document evidence.');
    } else if (action === 'DEFER') {
      setActionReason('Deferred for senior clinician review or lab consultation.');
    } else {
      setActionReason('Corrected by clinician to align with source report document.');
    }
  };

  const handleConfirmAction = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!actionModalItem) return;
    setActingId(actionModalItem.id);
    try {
      await onAction(
        actionModalItem.id,
        actionModalType,
        actionModalType === 'CORRECT' ? correctedVal : undefined,
        actionReason
      );
      setActionModalItem(null);
      setSelectedReview(null);
    } catch (e: any) {
      alert(e.message || 'Action failed');
    } finally {
      setActingId(null);
    }
  };

  // Filter items
  const filteredItems = items.filter((item) => {
    if (statusFilter !== 'ALL' && item.status?.toUpperCase() !== statusFilter) return false;
    if (priorityFilter !== 'ALL' && item.priority?.toUpperCase() !== priorityFilter) return false;
    if (typeFilter !== 'ALL' && item.target_type?.toUpperCase() !== typeFilter) return false;
    return true;
  });

  // KPI calculations
  const totalPending = items.filter(i => i.status === 'PENDING').length;
  const highPriorityPending = items.filter(i => i.status === 'PENDING' && i.priority === 'HIGH').length;
  const totalAccepted = items.filter(i => i.status === 'ACCEPTED').length;
  const totalEdited = items.filter(i => i.status === 'EDITED').length;
  const totalRejected = items.filter(i => i.status === 'REJECTED').length;

  return (
    <div className="space-y-6 animate-fadeIn">
      
      {/* Header & Clinical Safety Notice */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-wide flex items-center gap-2.5">
            <CheckSquare className="w-6 h-6 text-amber-400" />
            <span>Clinical Review Queue & Human Verification</span>
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Human-in-the-loop verification layer. Accept, correct, reject, or defer AI-extracted clinical items with immutable audit logging.
          </p>
        </div>

        {/* Safety Callout */}
        <div className="p-3 bg-amber-950/40 border border-amber-500/30 rounded-xl text-[11px] text-amber-300/90 max-w-md">
          <span className="font-bold block text-amber-200 mb-0.5">Verification Safety Policy</span>
          AI-extracted items require human clinician review before being treated as clinically verified. Underlying source data is preserved permanently.
        </div>
      </div>

      {/* KPI Metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3.5">
        <div className="p-3.5 rounded-xl bg-[#0e1424] border border-slate-800">
          <span className="text-[11px] font-mono text-slate-400 uppercase block">Pending Reviews</span>
          <span className="text-2xl font-bold text-white font-mono mt-0.5 block">{totalPending}</span>
        </div>
        <div className="p-3.5 rounded-xl bg-rose-950/20 border border-rose-500/30">
          <span className="text-[11px] font-mono text-rose-300 uppercase block">High Priority</span>
          <span className="text-2xl font-bold text-rose-400 font-mono mt-0.5 block">{highPriorityPending}</span>
        </div>
        <div className="p-3.5 rounded-xl bg-teal-950/20 border border-teal-500/30">
          <span className="text-[11px] font-mono text-teal-300 uppercase block">Verified (Accepted)</span>
          <span className="text-2xl font-bold text-teal-400 font-mono mt-0.5 block">{totalAccepted}</span>
        </div>
        <div className="p-3.5 rounded-xl bg-violet-950/20 border border-violet-500/30">
          <span className="text-[11px] font-mono text-violet-300 uppercase block">Corrected</span>
          <span className="text-2xl font-bold text-violet-400 font-mono mt-0.5 block">{totalEdited}</span>
        </div>
        <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-700">
          <span className="text-[11px] font-mono text-slate-400 uppercase block">Rejected</span>
          <span className="text-2xl font-bold text-slate-300 font-mono mt-0.5 block">{totalRejected}</span>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 rounded-xl bg-[#0e1424] border border-slate-800 text-xs">
        <div className="flex items-center gap-2">
          <Filter className="w-3.5 h-3.5 text-slate-400" />
          <span className="text-slate-400 font-medium">Status:</span>
          <div className="flex gap-1">
            {(['PENDING', 'ACCEPTED', 'EDITED', 'REJECTED', 'DEFERRED', 'ALL'] as const).map(tab => (
              <button
                key={tab}
                onClick={() => setStatusFilter(tab)}
                className={`px-3 py-1 rounded-lg font-medium transition-all ${
                  statusFilter === tab
                    ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800'
                }`}
              >
                {tab}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className="text-slate-400 font-medium">Priority:</span>
            <select
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value)}
              className="px-2.5 py-1 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:border-teal-500"
            >
              <option value="ALL">All Priorities</option>
              <option value="HIGH">High Only</option>
              <option value="MEDIUM">Medium Only</option>
              <option value="LOW">Low Only</option>
            </select>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="text-slate-400 font-medium">Type:</span>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="px-2.5 py-1 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:border-teal-500"
            >
              <option value="ALL">All Data Types</option>
              <option value="LAB_RESULT">Laboratory Result</option>
              <option value="MEDICATION">Medication</option>
              <option value="ALLERGY">Allergy</option>
              <option value="CONDITION">Condition</option>
            </select>
          </div>
        </div>
      </div>

      {/* Review Items List */}
      <div className="space-y-4">
        {filteredItems.map((item) => {
          const isPending = item.status === 'PENDING';
          const isAccepted = item.status === 'ACCEPTED';
          const isEdited = item.status === 'EDITED';
          const isRejected = item.status === 'REJECTED';
          const isDeferred = item.status === 'DEFERRED';

          return (
            <div
              key={item.id}
              className={`p-6 rounded-2xl border transition-all ${
                isPending
                  ? item.priority === 'HIGH'
                    ? 'border-rose-500/40 bg-[#140e16]'
                    : 'border-amber-500/30 bg-[#0e1424]'
                  : 'border-slate-800 bg-[#0e1424] opacity-85'
              }`}
            >
              <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
                <div className="space-y-2.5 flex-1">
                  {/* Top Tags */}
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`px-2.5 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider ${
                      item.priority === 'HIGH'
                        ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                        : item.priority === 'MEDIUM'
                        ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                        : 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                    }`}>
                      {item.priority} PRIORITY
                    </span>

                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                      TYPE: {item.target_type}
                    </span>

                    <span className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold uppercase ${
                      isPending
                        ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                        : isAccepted
                        ? 'bg-teal-500/20 text-teal-300 border border-teal-500/40'
                        : isEdited
                        ? 'bg-violet-500/20 text-violet-300 border border-violet-500/40'
                        : isRejected
                        ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                        : 'bg-slate-700 text-slate-400'
                    }`}>
                      {item.status}
                    </span>

                    {item.confidence !== undefined && item.confidence !== null && (
                      <span className="text-[10px] font-mono text-slate-400 bg-slate-900 px-2 py-0.5 rounded border border-slate-800" title="Extraction confidence on source document">
                        {Math.round(item.confidence * 100)}% Confidence
                      </span>
                    )}
                  </div>

                  {/* Field & Values */}
                  <div className="text-base font-bold text-white flex flex-wrap items-center gap-2">
                    <span>Field:</span>
                    <span className="text-amber-300 font-mono">{item.field_name}</span>
                    
                    <div className="text-sm font-normal text-slate-300 flex items-center gap-2 ml-1">
                      {/* Original value */}
                      <span>(Extracted: <span className="font-mono text-white font-semibold">{item.original_value || item.current_value}</span>)</span>
                      
                      {/* Corrected diff if edited */}
                      {isEdited && item.corrected_value && (
                        <span className="text-violet-300 font-mono font-semibold flex items-center gap-1">
                          <CornerDownRight className="w-3 h-3 text-violet-400" />
                          <span>Corrected to: {item.corrected_value}</span>
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Review Rationale */}
                  <p className="text-xs text-slate-300 leading-relaxed">
                    <strong className="text-slate-400 font-semibold">Review Rationale: </strong>
                    {item.reason}
                  </p>

                  {/* Reviewer Note if available */}
                  {item.reviewer_note && (
                    <div className="text-xs text-slate-400 italic p-2.5 rounded-lg bg-slate-900/60 border border-slate-800">
                      <strong className="text-slate-300 not-italic">Clinician Review Note: </strong>
                      "{item.reviewer_note}"
                      {item.reviewed_by && (
                        <span className="block text-[10px] text-slate-400 not-italic mt-0.5">
                          — {item.reviewed_by} on {item.reviewed_at ? new Date(item.reviewed_at).toLocaleDateString() : 'recent'}
                        </span>
                      )}
                    </div>
                  )}
                </div>

                {/* Right Actions */}
                <div className="flex flex-col sm:flex-row md:flex-col gap-2 flex-shrink-0">
                  <button
                    onClick={() => handleOpenDetails(item)}
                    className="px-3.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold flex items-center justify-center gap-1.5 border border-slate-700 transition-all"
                    title="Inspect side-by-side source document context and linked clinical conflicts"
                  >
                    <Eye className="w-3.5 h-3.5 text-teal-400" />
                    <span>Inspect Evidence</span>
                  </button>

                  {isPending && (
                    <div className="flex flex-wrap items-center gap-1.5">
                      <button
                        disabled={actingId === item.id}
                        onClick={() => handleOpenActionModal(item, 'ACCEPT')}
                        className="px-3 py-1.5 rounded-xl bg-teal-600 hover:bg-teal-500 text-white text-xs font-semibold flex items-center gap-1 shadow-sm transition-all disabled:opacity-40"
                        title="Accept AI extraction as clinically verified"
                      >
                        <Check className="w-3 h-3" />
                        <span>Accept</span>
                      </button>

                      <button
                        disabled={actingId === item.id}
                        onClick={() => handleOpenActionModal(item, 'CORRECT')}
                        className="px-3 py-1.5 rounded-xl bg-violet-600/20 hover:bg-violet-600/30 text-violet-300 border border-violet-500/40 text-xs font-semibold flex items-center gap-1 transition-all disabled:opacity-40"
                        title="Edit extracted value and record human correction"
                      >
                        <Edit3 className="w-3 h-3" />
                        <span>Correct</span>
                      </button>

                      <button
                        disabled={actingId === item.id}
                        onClick={() => handleOpenActionModal(item, 'REJECT')}
                        className="px-3 py-1.5 rounded-xl bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/40 text-xs font-semibold flex items-center gap-1 transition-all disabled:opacity-40"
                        title="Reject inaccurate extraction"
                      >
                        <X className="w-3 h-3" />
                        <span>Reject</span>
                      </button>

                      <button
                        disabled={actingId === item.id}
                        onClick={() => handleOpenActionModal(item, 'DEFER')}
                        className="px-2.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-400 text-xs font-semibold flex items-center gap-1 transition-all disabled:opacity-40"
                        title="Defer item to review later"
                      >
                        <Clock className="w-3 h-3" />
                        <span>Defer</span>
                      </button>
                    </div>
                  )}

                  {!isPending && (
                    <button
                      onClick={() => handleOpenActionModal(item, 'CORRECT')}
                      className="px-3 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white text-[11px] font-medium border border-slate-700 transition-all"
                    >
                      Re-review / Amend
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}

        {filteredItems.length === 0 && (
          <div className="p-12 text-center rounded-2xl bg-[#0e1424] border border-slate-800 space-y-2">
            <CheckSquare className="w-8 h-8 text-teal-400 mx-auto opacity-60" />
            <div className="text-sm font-bold text-white">No Review Items Matching Criteria</div>
            <p className="text-xs text-slate-400">
              There are no pending clinical items requiring human verification under the selected filters.
            </p>
          </div>
        )}
      </div>

      {/* ========================================================= */}
      {/* Side-by-Side Review & Evidence Inspection Modal (Req 4) */}
      {/* ========================================================= */}
      {selectedReview && (
        <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-[#0c121e] border border-slate-700 max-w-4xl w-full rounded-2xl p-6 shadow-2xl space-y-5 animate-scaleUp my-8">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <span className="text-[10px] font-mono uppercase text-teal-400 font-bold tracking-wider">
                  Side-by-Side Human Clinical Verification
                </span>
                <h3 className="text-base font-bold text-white mt-0.5">
                  Inspect Field: {selectedReview.review_item.field_name}
                </h3>
              </div>
              <button
                onClick={() => setSelectedReview(null)}
                className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Side-by-Side Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              
              {/* LEFT: Source Document Context */}
              <div className="p-4 rounded-xl bg-black/50 border border-slate-800 space-y-3">
                <div className="flex items-center gap-2 text-slate-300 font-bold text-xs">
                  <FileText className="w-4 h-4 text-amber-400" />
                  <span>LEFT: Original Source Report Evidence</span>
                </div>
                <div className="text-[11px] text-slate-400 space-y-1">
                  <div>Document: <span className="text-slate-200 font-mono">{selectedReview.review_item.document_name}</span></div>
                  <div>Patient: <span className="text-slate-200 font-mono">{selectedReview.review_item.patient_name} (MRN: {selectedReview.review_item.patient_mrn})</span></div>
                </div>

                <div className="p-3 bg-slate-900 border border-slate-800 rounded-lg text-xs font-mono text-slate-200 whitespace-pre-wrap leading-relaxed max-h-56 overflow-y-auto">
                  {selectedReview.review_item.source_text || "Source excerpt unavailable or extracted from binary structure."}
                </div>

                {/* Related Phase 7 Conflicts */}
                {selectedReview.related_conflicts && selectedReview.related_conflicts.length > 0 && (
                  <div className="p-3 rounded-lg bg-rose-950/30 border border-rose-500/40 space-y-1.5">
                    <span className="text-[10px] font-bold text-rose-300 flex items-center gap-1 uppercase">
                      <ShieldAlert className="w-3 h-3 text-rose-400" />
                      Associated Clinical Conflict:
                    </span>
                    {selectedReview.related_conflicts.map((rc: any) => (
                      <p key={rc.id} className="text-[11px] text-rose-200 leading-snug">
                        <strong>{rc.title}:</strong> {rc.description}
                      </p>
                    ))}
                  </div>
                )}
              </div>

              {/* RIGHT: AI-Extracted Structured Representation */}
              <div className="p-4 rounded-xl bg-[#0e1424] border border-slate-800 space-y-3">
                <div className="flex items-center gap-2 text-slate-300 font-bold text-xs">
                  <UserCheck className="w-4 h-4 text-teal-400" />
                  <span>RIGHT: AI-Extracted Structured Record</span>
                </div>

                <div className="p-3 bg-slate-900 border border-slate-800 rounded-lg space-y-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Target Type:</span>
                    <span className="text-slate-200 font-mono font-bold">{selectedReview.review_item.target_type}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Original AI Value:</span>
                    <span className="text-amber-300 font-mono font-bold">{selectedReview.review_item.original_value}</span>
                  </div>
                  {selectedReview.review_item.corrected_value && (
                    <div className="flex justify-between">
                      <span className="text-slate-400">Corrected Value:</span>
                      <span className="text-violet-300 font-mono font-bold">{selectedReview.review_item.corrected_value}</span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span className="text-slate-400">Extraction Confidence:</span>
                    <span className="text-slate-200 font-mono font-bold">{selectedReview.review_item.confidence_percent}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Verification Status:</span>
                    <span className="text-teal-300 font-mono font-bold">{selectedReview.review_item.status}</span>
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-[11px] text-amber-200/90 leading-relaxed">
                  <strong className="block text-amber-300 mb-0.5">Verification Instruction:</strong>
                  Inspect the source document excerpt on the left. If the extracted value matches the original report, click <strong>Accept</strong>. If the extraction contains a typo or omission, click <strong>Correct</strong> to provide the accurate clinical value.
                </div>
              </div>

            </div>

            {/* Quick Action Footer in Inspection Modal */}
            <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-800">
              <span className="text-[11px] text-slate-400">
                Audit: Verified modifications are permanently logged with clinician credentials.
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => {
                    const item = items.find(i => i.id === selectedReview.review_item.id);
                    if (item) handleOpenActionModal(item, 'CORRECT');
                  }}
                  className="px-4 py-2 rounded-xl bg-violet-600/20 hover:bg-violet-600/30 text-violet-300 border border-violet-500/40 text-xs font-semibold"
                >
                  Edit / Correct Value
                </button>
                <button
                  onClick={() => {
                    const item = items.find(i => i.id === selectedReview.review_item.id);
                    if (item) handleOpenActionModal(item, 'ACCEPT');
                  }}
                  className="px-4 py-2 rounded-xl bg-teal-600 hover:bg-teal-500 text-white text-xs font-semibold flex items-center gap-1.5"
                >
                  <Check className="w-3.5 h-3.5" />
                  <span>Verify & Accept</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* Action Execution Modal (Accept / Correct / Reject / Defer) */}
      {/* ========================================================= */}
      {actionModalItem && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0c121e] border border-slate-700 max-w-lg w-full rounded-2xl p-6 shadow-2xl space-y-4 animate-scaleUp">
            <div>
              <span className="text-[10px] font-mono uppercase text-teal-400 font-bold tracking-wider">
                Human Verification Action: {actionModalType}
              </span>
              <h3 className="text-base font-bold text-white mt-1">
                {actionModalItem.field_name} (Current: {actionModalItem.current_value})
              </h3>
              <p className="text-xs text-slate-400 mt-1">
                Original AI extraction will remain intact. Action is recorded in the immutable audit trail.
              </p>
            </div>

            <form onSubmit={handleConfirmAction} className="space-y-4 text-xs">
              {/* Corrected Value Input if action is CORRECT */}
              {actionModalType === 'CORRECT' && (
                <div>
                  <label className="block text-slate-300 font-medium mb-1">
                    Corrected Clinical Value *
                  </label>
                  <input
                    type="text"
                    required
                    value={correctedVal}
                    onChange={(e) => setCorrectedVal(e.target.value)}
                    placeholder="Enter accurate value (e.g. 11.2 g/dL)"
                    className="w-full p-3 bg-slate-900 border border-slate-700 rounded-xl text-white font-mono text-xs focus:outline-none focus:border-teal-500"
                  />
                  <span className="text-[10px] text-slate-400 mt-1 block">
                    Original AI extraction: <code className="text-amber-300">{actionModalItem.original_value || actionModalItem.current_value}</code>
                  </span>
                </div>
              )}

              <div>
                <label className="block text-slate-300 font-medium mb-1">
                  Clinician Reviewer Rationale / Note *
                </label>
                <textarea
                  rows={3}
                  required
                  value={actionReason}
                  onChange={(e) => setActionReason(e.target.value)}
                  placeholder="Clinical verification reason or discrepancy explanation"
                  className="w-full p-3 bg-slate-900 border border-slate-700 rounded-xl text-white font-sans text-xs focus:outline-none focus:border-teal-500"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setActionModalItem(null)}
                  className="px-4 py-2 rounded-lg border border-slate-700 text-slate-300 hover:bg-slate-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actingId === actionModalItem.id}
                  className="px-5 py-2 rounded-lg bg-teal-600 hover:bg-teal-500 text-white font-semibold disabled:opacity-50"
                >
                  {actingId === actionModalItem.id ? 'Processing...' : `Confirm ${actionModalType}`}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
};
