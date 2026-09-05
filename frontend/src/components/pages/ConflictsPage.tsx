import React, { useState } from 'react';
import {
  AlertTriangle,
  CheckCircle,
  ShieldAlert,
  Check,
  Filter,
  Info,
  Clock,
  UserCheck,
  XCircle,
  Eye,
  FileText
} from 'lucide-react';
import { ConflictItem } from '../../types';
import { SeverityBadge } from '../common/Badges';

interface ConflictsPageProps {
  conflicts: ConflictItem[];
  onResolveConflict: (id: string, notes: string, newStatus?: string) => Promise<void>;
}

export const ConflictsPage: React.FC<ConflictsPageProps> = ({ conflicts, onResolveConflict }) => {
  const [selectedConflict, setSelectedConflict] = useState<ConflictItem | null>(null);
  const [modalAction, setModalAction] = useState<'RESOLVED' | 'REVIEWED' | 'DISMISSED'>('RESOLVED');
  const [resolutionNotes, setResolutionNotes] = useState('Verified against clinical sources and patient record.');
  const [resolving, setResolving] = useState(false);
  
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'ACTIVE' | 'RESOLVED' | 'DISMISSED'>('ACTIVE');
  const [severityFilter, setSeverityFilter] = useState<string>('ALL');

  // Metrics
  const totalCount = conflicts.length;
  const highCount = conflicts.filter(c => c.severity?.toUpperCase() === 'HIGH').length;
  const mediumCount = conflicts.filter(c => ['MEDIUM', 'WARNING'].includes(c.severity?.toUpperCase())).length;
  const lowCount = conflicts.filter(c => ['LOW', 'INFO'].includes(c.severity?.toUpperCase())).length;

  const handleActionClick = (conflict: ConflictItem, action: 'RESOLVED' | 'REVIEWED' | 'DISMISSED') => {
    setSelectedConflict(conflict);
    setModalAction(action);
    if (action === 'REVIEWED') {
      setResolutionNotes('Discrepancy reviewed by clinician. Monitoring alongside active record.');
    } else if (action === 'DISMISSED') {
      setResolutionNotes('Discrepancy dismissed as non-actionable or clinically reconciled.');
    } else {
      setResolutionNotes('Reconciled against original source document. Document discrepancy noted in chart.');
    }
  };

  const handleConfirmAction = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedConflict) return;
    setResolving(true);
    try {
      await onResolveConflict(selectedConflict.id, resolutionNotes, modalAction);
      setSelectedConflict(null);
    } catch (err: any) {
      alert(err.message || 'Error updating conflict record');
    } finally {
      setResolving(false);
    }
  };

  const filteredConflicts = conflicts.filter(c => {
    const isAct = c.status === 'OPEN' || c.status === 'UNRESOLVED';
    if (statusFilter === 'ACTIVE' && !isAct) return false;
    if (statusFilter === 'RESOLVED' && c.status !== 'RESOLVED' && c.status !== 'REVIEWED') return false;
    if (statusFilter === 'DISMISSED' && c.status !== 'DISMISSED') return false;

    if (severityFilter !== 'ALL') {
      const s = c.severity?.toUpperCase();
      if (severityFilter === 'HIGH' && s !== 'HIGH') return false;
      if (severityFilter === 'MEDIUM' && s !== 'MEDIUM' && s !== 'WARNING') return false;
      if (severityFilter === 'LOW' && s !== 'LOW' && s !== 'INFO') return false;
    }
    return true;
  });

  return (
    <div className="space-y-6 animate-fadeIn">
      
      {/* Header & Clinical Decision-Support Notice */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-wide flex items-center gap-2.5">
            <ShieldAlert className="w-6 h-6 text-amber-400" />
            <span>Clinical Inconsistencies & Contradiction Detection</span>
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Automated cross-document verification flags drug-allergy risks, divergent dosages, conflicting lab panels, and demographic mismatches.
          </p>
        </div>

        {/* Safety Disclaimer Callout */}
        <div className="p-3 bg-amber-950/40 border border-amber-500/30 rounded-xl text-[11px] text-amber-300/90 max-w-md">
          <span className="font-bold block text-amber-200 mb-0.5">Clinical Safety Notice</span>
          All flagged inconsistencies represent automated findings for clinical decision-support and require human clinical verification before taking medical action.
        </div>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-[#0e1424] border border-slate-800">
          <span className="text-[11px] font-mono text-slate-400 uppercase block">Total Conflicts</span>
          <span className="text-2xl font-bold text-white font-mono mt-1 block">{totalCount}</span>
        </div>
        <div className="p-4 rounded-xl bg-rose-950/20 border border-rose-500/30">
          <span className="text-[11px] font-mono text-rose-300 uppercase block">High Severity</span>
          <span className="text-2xl font-bold text-rose-400 font-mono mt-1 block">{highCount}</span>
        </div>
        <div className="p-4 rounded-xl bg-amber-950/20 border border-amber-500/30">
          <span className="text-[11px] font-mono text-amber-300 uppercase block">Medium Severity</span>
          <span className="text-2xl font-bold text-amber-400 font-mono mt-1 block">{mediumCount}</span>
        </div>
        <div className="p-4 rounded-xl bg-blue-950/20 border border-blue-500/30">
          <span className="text-[11px] font-mono text-blue-300 uppercase block">Low / Info</span>
          <span className="text-2xl font-bold text-blue-400 font-mono mt-1 block">{lowCount}</span>
        </div>
      </div>

      {/* Filter Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 rounded-xl bg-[#0e1424] border border-slate-800 text-xs">
        <div className="flex items-center gap-2">
          <Filter className="w-3.5 h-3.5 text-slate-400" />
          <span className="text-slate-400 font-medium">Status Filter:</span>
          <div className="flex gap-1">
            {(['ACTIVE', 'RESOLVED', 'DISMISSED', 'ALL'] as const).map(tab => (
              <button
                key={tab}
                onClick={() => setStatusFilter(tab)}
                className={`px-3 py-1 rounded-lg font-medium transition-all ${
                  statusFilter === tab
                    ? 'bg-teal-500/20 text-teal-300 border border-teal-500/30'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800'
                }`}
              >
                {tab}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-slate-400 font-medium">Severity:</span>
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="px-2.5 py-1 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:border-teal-500"
          >
            <option value="ALL">All Severities</option>
            <option value="HIGH">High Severity Only</option>
            <option value="MEDIUM">Medium Severity Only</option>
            <option value="LOW">Low Severity Only</option>
          </select>
        </div>
      </div>

      {/* Conflicts List */}
      <div className="space-y-4">
        {filteredConflicts.map((conflict) => {
          const isActive = conflict.status === 'OPEN' || conflict.status === 'UNRESOLVED';
          const isReviewed = conflict.status === 'REVIEWED';
          const isResolved = conflict.status === 'RESOLVED';
          const isDismissed = conflict.status === 'DISMISSED';

          return (
            <div
              key={conflict.id}
              className={`p-6 rounded-2xl border transition-all ${
                isActive
                  ? conflict.severity?.toUpperCase() === 'HIGH'
                    ? 'border-rose-500/40 bg-[#140e16]'
                    : 'border-amber-500/30 bg-[#120e1a]'
                  : 'border-slate-800 bg-[#0e1424] opacity-80'
              }`}
            >
              {/* Top Meta Bar */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
                <div className="flex items-center gap-3">
                  <SeverityBadge severity={conflict.severity} />
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-semibold uppercase">
                    {conflict.conflict_type.replace(/_/g, ' ')}
                  </span>
                  <h3 className="text-sm font-bold text-white tracking-wide">{conflict.title}</h3>
                </div>

                <div className="flex items-center gap-2">
                  <span className={`text-[10px] font-mono px-2.5 py-1 rounded-full font-bold uppercase ${
                    isActive
                      ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                      : isReviewed
                      ? 'bg-blue-500/20 text-blue-300 border border-blue-500/40'
                      : isResolved
                      ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                      : 'bg-slate-700/50 text-slate-400 border border-slate-600'
                  }`}>
                    {conflict.status}
                  </span>
                </div>
              </div>

              {/* Conflict Narrative Explanation */}
              <p className="text-xs sm:text-sm text-slate-200 mb-4 leading-relaxed">
                {conflict.description}
              </p>

              {/* Two Conflicting Sources Display */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 text-xs font-mono mb-4">
                <div className="p-3 rounded-xl bg-black/40 border border-slate-800/80 space-y-1">
                  <span className="text-[10px] uppercase text-slate-400 block font-semibold">Source Evidence 1</span>
                  <span className="text-amber-300 block font-medium">{conflict.source_a || 'Patient Profile'}</span>
                </div>
                <div className="p-3 rounded-xl bg-black/40 border border-slate-800/80 space-y-1">
                  <span className="text-[10px] uppercase text-slate-400 block font-semibold">Source Evidence 2</span>
                  <span className="text-rose-300 block font-medium">{conflict.source_b || 'Clinical Record'}</span>
                </div>
              </div>

              {/* Conflicting Values Payload (if cleanly structured) */}
              {conflict.conflicting_values && (
                <div className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800 text-[11px] font-mono text-slate-400 mb-4 overflow-x-auto">
                  <span className="text-[10px] uppercase text-slate-400 block font-bold mb-1">Normalized Conflict Payload:</span>
                  <code>{conflict.conflicting_values}</code>
                </div>
              )}

              {/* Clinician Review Notes if present */}
              {conflict.resolution_notes && (
                <div className="text-xs text-slate-400 italic mb-3 p-3 rounded-xl bg-slate-900/60 border border-slate-800 flex items-start gap-2">
                  <UserCheck className="w-4 h-4 text-teal-400 flex-shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold text-slate-300 not-italic">Clinician Reviewer Note: </span>
                    "{conflict.resolution_notes}"
                    {conflict.resolved_by && (
                      <span className="block text-[11px] text-slate-400 not-italic mt-0.5">
                        Recorded by {conflict.resolved_by} on {conflict.resolved_at ? new Date(conflict.resolved_at).toLocaleDateString() : 'recent review'}
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* Review & Resolution Actions */}
              <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-800/80 text-xs">
                <span className="text-[11px] text-slate-400 font-mono">
                  Identified: {new Date(conflict.created_at).toLocaleString()}
                </span>

                <div className="flex items-center gap-2">
                  {isActive && (
                    <>
                      <button
                        onClick={() => handleActionClick(conflict, 'REVIEWED')}
                        className="px-3 py-1.5 rounded-lg bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 border border-blue-500/40 flex items-center gap-1.5 transition-all"
                        title="Acknowledge inconsistency and mark as reviewed without altering source records"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        <span>Mark Reviewed</span>
                      </button>

                      <button
                        onClick={() => handleActionClick(conflict, 'RESOLVED')}
                        className="px-3.5 py-1.5 rounded-lg bg-teal-600 hover:bg-teal-500 text-white font-semibold flex items-center gap-1.5 shadow-sm transition-all"
                        title="Reconcile and mark as resolved with rationale note"
                      >
                        <CheckCircle className="w-3.5 h-3.5" />
                        <span>Resolve</span>
                      </button>

                      <button
                        onClick={() => handleActionClick(conflict, 'DISMISSED')}
                        className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 border border-slate-700 flex items-center gap-1.5 transition-all"
                        title="Dismiss non-actionable discrepancy"
                      >
                        <XCircle className="w-3.5 h-3.5" />
                        <span>Dismiss</span>
                      </button>
                    </>
                  )}

                  {!isActive && (
                    <button
                      onClick={() => handleActionClick(conflict, 'RESOLVED')}
                      className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 flex items-center gap-1.5 transition-all text-[11px]"
                    >
                      <span>Update Review Notes</span>
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}

        {filteredConflicts.length === 0 && (
          <div className="p-12 text-center rounded-2xl bg-[#0e1424] border border-slate-800 space-y-2">
            <CheckCircle className="w-8 h-8 text-teal-400 mx-auto opacity-60" />
            <div className="text-sm font-bold text-white">No Inconsistencies Matching Filter</div>
            <p className="text-xs text-slate-400">
              No cross-document or clinical discrepancies detected under selected filter criteria.
            </p>
          </div>
        )}
      </div>

      {/* Clinician Action Modal */}
      {selectedConflict && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0c121e] border border-slate-700 max-w-lg w-full rounded-2xl p-6 shadow-2xl space-y-4 animate-scaleUp">
            <div>
              <span className="text-[10px] font-mono uppercase text-teal-400 font-bold tracking-wider">
                Clinical Conflict Action: {modalAction}
              </span>
              <h3 className="text-base font-bold text-white mt-1">
                {selectedConflict.title}
              </h3>
              <p className="text-xs text-slate-400 mt-1">
                Underlying original clinical records will remain immutable. Action and rationales are logged to the permanent audit trail.
              </p>
            </div>

            <form onSubmit={handleConfirmAction} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-300 font-medium mb-1">
                  Clinician Reviewer Note / Rationale *
                </label>
                <textarea
                  rows={3}
                  required
                  value={resolutionNotes}
                  onChange={(e) => setResolutionNotes(e.target.value)}
                  className="w-full p-3 bg-slate-900 border border-slate-700 rounded-xl text-white font-sans text-xs focus:outline-none focus:border-teal-500"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setSelectedConflict(null)}
                  className="px-4 py-2 rounded-lg border border-slate-700 text-slate-300 hover:bg-slate-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={resolving}
                  className="px-5 py-2 rounded-lg bg-teal-600 hover:bg-teal-500 text-white font-semibold disabled:opacity-50"
                >
                  {resolving ? 'Submitting...' : `Confirm ${modalAction}`}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
};
