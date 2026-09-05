import React, { useState, useEffect } from 'react';
import {
  User,
  FileText,
  Activity,
  AlertTriangle,
  Clock,
  Edit,
  Archive,
  ArchiveRestore,
  Trash2,
  ArrowLeft,
  Calendar,
  Phone,
  Mail,
  Shield,
  FileCheck,
  CheckCircle,
  AlertCircle,
  RefreshCw,
  Eye,
  Info,
  ExternalLink,
  ShieldAlert,
  Zap
} from 'lucide-react';
import { PatientOverview, Patient } from '../../types';
import { api } from '../../services/api';
import { ProvenanceBadge, LabStatusBadge, ConflictSeverityBadge } from '../common/Badges';
import { EditPatientModal } from '../patients/EditPatientModal';

interface PatientOverviewPageProps {
  patientId: string;
  onBack: () => void;
  onPatientDeleted?: () => void;
}

export const PatientOverviewPage: React.FC<PatientOverviewPageProps> = ({
  patientId,
  onBack,
  onPatientDeleted
}) => {
  const [overview, setOverview] = useState<PatientOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'all' | 'clinical' | 'labs' | 'documents' | 'timeline' | 'conflicts'>('all');
  
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [actionInProgress, setActionInProgress] = useState(false);
  const [selectedDocText, setSelectedDocText] = useState<{ name: string; text?: string } | null>(null);

  const fetchOverview = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getPatientOverview(patientId);
      setOverview(data);
    } catch (err: any) {
      console.error('Error loading patient overview:', err);
      setError(err.message || 'Failed to load patient clinical intelligence overview.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOverview();
  }, [patientId]);

  const handleArchiveToggle = async () => {
    if (!overview) return;
    try {
      setActionInProgress(true);
      if (overview.is_archived) {
        await api.unarchivePatient(overview.id);
      } else {
        await api.archivePatient(overview.id);
      }
      await fetchOverview();
    } catch (err: any) {
      alert(err.message || 'Error modifying archive status');
    } finally {
      setActionInProgress(false);
    }
  };

  const handleDelete = async () => {
    if (!overview) return;
    try {
      setActionInProgress(true);
      await api.deletePatient(overview.id);
      setShowDeleteConfirm(false);
      if (onPatientDeleted) {
        onPatientDeleted();
      } else {
        onBack();
      }
    } catch (err: any) {
      alert(err.message || 'Error deleting patient record');
      setActionInProgress(false);
    }
  };

  const handleSaveEdit = async (updatedData: any) => {
    if (!overview) return;
    await api.updatePatient(overview.id, updatedData);
    await fetchOverview();
  };

  const [scanningConflicts, setScanningConflicts] = useState(false);
  const handleScanConflicts = async () => {
    if (!overview) return;
    try {
      setScanningConflicts(true);
      await api.detectConflicts(overview.id);
      await fetchOverview();
    } catch (err: any) {
      alert(err.message || 'Error running conflict detection scan');
    } finally {
      setScanningConflicts(false);
    }
  };

  // -------------------------------------------------------------
  // Render: Loading State
  // -------------------------------------------------------------
  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-slate-800 rounded-xl"></div>
          <div className="h-6 w-48 bg-slate-800 rounded-lg"></div>
        </div>
        <div className="bg-[#0e1424] border border-slate-800 rounded-2xl p-6 h-40"></div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-[#0e1424] border border-slate-800 rounded-2xl p-6 h-64"></div>
          <div className="bg-[#0e1424] border border-slate-800 rounded-2xl p-6 h-64"></div>
        </div>
      </div>
    );
  }

  // -------------------------------------------------------------
  // Render: Error State
  // -------------------------------------------------------------
  if (error || !overview) {
    return (
      <div className="bg-[#0e1424] border border-rose-500/30 rounded-2xl p-8 text-center space-y-4 max-w-lg mx-auto my-12">
        <div className="w-12 h-12 rounded-full bg-rose-500/10 text-rose-400 flex items-center justify-center mx-auto">
          <AlertCircle className="w-6 h-6" />
        </div>
        <h2 className="text-lg font-bold text-white">Unable to Load Patient Overview</h2>
        <p className="text-xs text-slate-400">{error || 'The requested patient record could not be found.'}</p>
        <div className="flex justify-center gap-3 pt-2">
          <button
            onClick={onBack}
            className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition-colors"
          >
            Back to Patients
          </button>
          <button
            onClick={fetchOverview}
            className="px-4 py-2 rounded-xl bg-teal-600 hover:bg-teal-500 text-white text-xs font-medium flex items-center gap-2 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Retry</span>
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fadeIn pb-12">
      {/* Top Back Navigation & Action Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <button
          onClick={onBack}
          className="inline-flex items-center gap-2 text-xs font-medium text-slate-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Patient Directory</span>
        </button>

        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            onClick={() => setShowEditModal(true)}
            className="px-3.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium flex items-center gap-1.5 border border-slate-700 transition-colors"
          >
            <Edit className="w-3.5 h-3.5 text-teal-400" />
            <span>Edit Profile</span>
          </button>

          <button
            onClick={handleArchiveToggle}
            disabled={actionInProgress}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-medium flex items-center gap-1.5 border transition-colors ${
              overview.is_archived
                ? 'bg-amber-500/10 border-amber-500/30 text-amber-300 hover:bg-amber-500/20'
                : 'bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700'
            }`}
          >
            {overview.is_archived ? (
              <>
                <ArchiveRestore className="w-3.5 h-3.5" />
                <span>Restore Patient</span>
              </>
            ) : (
              <>
                <Archive className="w-3.5 h-3.5 text-amber-400" />
                <span>Archive Patient</span>
              </>
            )}
          </button>

          <button
            onClick={() => setShowDeleteConfirm(true)}
            className="px-3.5 py-1.5 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 text-rose-300 text-xs font-medium flex items-center gap-1.5 transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5 text-rose-400" />
            <span>Delete</span>
          </button>
        </div>
      </div>

      {/* Patient Master Header Card */}
      <div className="bg-[#0e1424] border border-slate-800/90 rounded-2xl p-6 shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-80 h-80 bg-teal-500/5 rounded-full blur-3xl pointer-events-none"></div>

        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 relative z-10">
          <div className="flex items-start sm:items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-teal-500/20 to-teal-800/30 border border-teal-500/30 flex items-center justify-center text-teal-400 font-bold text-xl flex-shrink-0">
              {overview.first_name[0]}{overview.last_name[0]}
            </div>

            <div>
              <div className="flex items-center gap-3 flex-wrap">
                <h1 className="text-xl sm:text-2xl font-bold text-white tracking-wide">
                  {overview.first_name} {overview.last_name}
                </h1>
                <span className="font-mono text-xs px-2.5 py-1 rounded-md bg-teal-500/10 text-teal-300 border border-teal-500/25 font-semibold">
                  MRN: {overview.mrn}
                </span>
                {overview.is_synthetic_demo && (
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/10 border border-blue-500/20 text-blue-400 font-medium">
                    SYNTHETIC DEMO DATA
                  </span>
                )}
                {overview.is_archived && (
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/30 text-amber-300 font-semibold">
                    ARCHIVED RECORD
                  </span>
                )}
              </div>

              {/* Patient quick meta info */}
              <div className="flex items-center gap-4 text-xs text-slate-400 mt-2 flex-wrap">
                <span className="flex items-center gap-1.5">
                  <User className="w-3.5 h-3.5 text-slate-500" />
                  <span>{overview.age} y/o {overview.sex}</span>
                </span>
                <span className="text-slate-600">•</span>
                <span className="flex items-center gap-1.5">
                  <Calendar className="w-3.5 h-3.5 text-slate-500" />
                  <span>DoB: {overview.date_of_birth}</span>
                </span>
                {overview.contact_phone && (
                  <>
                    <span className="text-slate-600">•</span>
                    <span className="flex items-center gap-1.5">
                      <Phone className="w-3.5 h-3.5 text-slate-500" />
                      <span>{overview.contact_phone}</span>
                    </span>
                  </>
                )}
                {overview.contact_email && (
                  <>
                    <span className="text-slate-600">•</span>
                    <span className="flex items-center gap-1.5">
                      <Mail className="w-3.5 h-3.5 text-slate-500" />
                      <span>{overview.contact_email}</span>
                    </span>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Quick Metrics Pills */}
          <div className="flex items-center gap-3 flex-wrap sm:flex-nowrap border-t md:border-t-0 pt-3 md:pt-0 border-slate-800">
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl px-3.5 py-2 text-center min-w-[72px]">
              <span className="text-[10px] font-medium text-slate-400 uppercase tracking-wider block">Conditions</span>
              <span className="text-sm font-bold text-white">{overview.conditions?.length || 0}</span>
            </div>
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl px-3.5 py-2 text-center min-w-[72px]">
              <span className="text-[10px] font-medium text-slate-400 uppercase tracking-wider block">Allergies</span>
              <span className="text-sm font-bold text-rose-300">{overview.allergies?.length || 0}</span>
            </div>
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl px-3.5 py-2 text-center min-w-[72px]">
              <span className="text-[10px] font-medium text-slate-400 uppercase tracking-wider block">Labs</span>
              <span className="text-sm font-bold text-teal-300">{overview.lab_results?.length || 0}</span>
            </div>
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl px-3.5 py-2 text-center min-w-[72px]">
              <span className="text-[10px] font-medium text-slate-400 uppercase tracking-wider block">Conflicts</span>
              <span className={`text-sm font-bold ${overview.conflicts?.length ? 'text-amber-400' : 'text-slate-400'}`}>
                {overview.conflicts?.length || 0}
              </span>
            </div>
          </div>
        </div>

        {/* Clinical Tabs Bar */}
        <div className="flex items-center gap-2 mt-6 pt-4 border-t border-slate-800/80 overflow-x-auto pb-1 text-xs">
          {[
            { id: 'all', label: 'Overview & Summary' },
            { id: 'clinical', label: `Clinical Profile (${(overview.conditions?.length || 0) + (overview.allergies?.length || 0) + (overview.medications?.length || 0)})` },
            { id: 'labs', label: `Laboratory Results (${overview.lab_results?.length || 0})` },
            { id: 'documents', label: `Reports (${overview.documents?.length || 0})` },
            { id: 'timeline', label: `Longitudinal Timeline (${overview.timeline?.length || 0})` },
            { id: 'conflicts', label: `Conflicts (${overview.conflicts?.length || 0})` }
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`px-3.5 py-1.5 rounded-lg font-medium whitespace-nowrap transition-all ${
                activeTab === tab.id
                  ? 'bg-teal-600 text-white shadow-[0_0_12px_rgba(20,184,166,0.3)]'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/70'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* ========================================================= */}
      {/* SECTION: Overview & Clinical Summary (Tabs: 'all') */}
      {/* ========================================================= */}
      {(activeTab === 'all' || activeTab === 'clinical') && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Column 1 & 2: Clinical Summary & Medical History */}
          <div className="lg:col-span-2 space-y-6">
            
            {/* Narrative Synthesis / Summary */}
            <div className="bg-[#0e1424] border border-slate-800 rounded-2xl p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-teal-400 flex items-center gap-2">
                  <FileText className="w-4 h-4 text-teal-400" />
                  <span>Clinical Narrative & Synthesis</span>
                </h3>
                {overview.summaries?.length > 0 && (
                  <ProvenanceBadge provenance={overview.summaries[0].provenance} />
                )}
              </div>

              {overview.summaries && overview.summaries.length > 0 ? (
                <div className="space-y-3">
                  {overview.summaries.map((s) => (
                    <div key={s.id} className="bg-slate-900/70 rounded-xl p-4 border border-slate-800/80 text-xs text-slate-300 leading-relaxed">
                      <p>{s.content}</p>
                      <div className="mt-2.5 pt-2 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-500 font-mono">
                        <span>Synthesis Engine: {s.summary_type}</span>
                        <span>Generated: {new Date(s.generated_at).toLocaleString()}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-6 rounded-xl bg-slate-900/40 border border-slate-800/50 text-center text-xs text-slate-500">
                  <p>No synthesized clinical summary available for this patient record.</p>
                </div>
              )}
            </div>

            {/* Reported Symptoms */}
            <div className="bg-[#0e1424] border border-slate-800 rounded-2xl p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-teal-400 flex items-center gap-2">
                  <Activity className="w-4 h-4 text-teal-400" />
                  <span>Reported Symptoms ({overview.symptoms?.length || 0})</span>
                </h3>
                <ProvenanceBadge provenance="USER_PROVIDED" />
              </div>

              {overview.symptoms && overview.symptoms.length > 0 ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {overview.symptoms.map((sym) => (
                    <div
                      key={sym.id}
                      className="p-3 rounded-xl bg-slate-900/60 border border-slate-800/80 flex items-start justify-between gap-2"
                    >
                      <div>
                        <span className="text-xs font-semibold text-white block">{sym.symptom}</span>
                        {sym.duration && (
                          <span className="text-[11px] text-slate-400 mt-0.5 block">Duration: {sym.duration}</span>
                        )}
                      </div>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20">
                        {sym.severity}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/50 text-center text-xs text-slate-500 italic">
                  No active symptoms recorded.
                </div>
              )}
            </div>

            {/* Existing Conditions */}
            <div className="bg-[#0e1424] border border-slate-800 rounded-2xl p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-teal-400 flex items-center gap-2">
                  <Shield className="w-4 h-4 text-teal-400" />
                  <span>Documented Conditions ({overview.conditions?.length || 0})</span>
                </h3>
                <ProvenanceBadge provenance="USER_PROVIDED" />
              </div>

              {overview.conditions && overview.conditions.length > 0 ? (
                <div className="space-y-2.5">
                  {overview.conditions.map((c) => (
                    <div
                      key={c.id}
                      className="p-3 rounded-xl bg-slate-900/60 border border-slate-800/80 flex items-center justify-between gap-3"
                    >
                      <div>
                        <span className="text-xs font-semibold text-white block">{c.condition_name}</span>
                        <div className="flex items-center gap-2 text-[11px] text-slate-400 mt-0.5">
                          {c.diagnosed_date && <span>Diagnosed: {c.diagnosed_date}</span>}
                          {c.notes && (
                            <>
                              <span>•</span>
                              <span className="text-slate-400 italic">{c.notes}</span>
                            </>
                          )}
                        </div>
                      </div>
                      <span className="text-[10px] font-mono px-2.5 py-0.5 rounded bg-blue-500/10 text-blue-300 border border-blue-500/20 font-medium">
                        {c.status}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/50 text-center text-xs text-slate-500 italic">
                  No chronic conditions documented.
                </div>
              )}
            </div>

          </div>

          {/* Column 3: Allergies, Medications & Demographics Sidebar */}
          <div className="space-y-6">
            
            {/* Allergies Card */}
            <div className="bg-[#0e1424] border border-slate-800 rounded-2xl p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-rose-400 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-rose-400" />
                  <span>Allergies ({overview.allergies?.length || 0})</span>
                </h3>
                <ProvenanceBadge provenance="USER_PROVIDED" />
              </div>

              {overview.allergies && overview.allergies.length > 0 ? (
                <div className="space-y-2.5">
                  {overview.allergies.map((a) => (
                    <div
                      key={a.id}
                      className="p-3 rounded-xl bg-rose-500/5 border border-rose-500/20 flex items-start justify-between gap-2"
                    >
                      <div>
                        <span className="text-xs font-bold text-rose-200 block">{a.allergen}</span>
                        {a.reaction && (
                          <span className="text-[11px] text-rose-300/80 mt-0.5 block">
                            Reaction: {a.reaction}
                          </span>
                        )}
                      </div>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30 font-semibold">
                        {a.severity}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/50 text-center text-xs text-slate-500 italic">
                  No known medical allergies.
                </div>
              )}
            </div>

            {/* Medications Card */}
            <div className="bg-[#0e1424] border border-slate-800 rounded-2xl p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-emerald-400 flex items-center gap-2">
                  <FileCheck className="w-4 h-4 text-emerald-400" />
                  <span>Active Medications ({overview.medications?.length || 0})</span>
                </h3>
                <ProvenanceBadge provenance="USER_PROVIDED" />
              </div>

              {overview.medications && overview.medications.length > 0 ? (
                <div className="space-y-2.5">
                  {overview.medications.map((m) => (
                    <div
                      key={m.id}
                      className="p-3 rounded-xl bg-emerald-500/5 border border-emerald-500/20 flex items-start justify-between gap-2"
                    >
                      <div>
                        <span className="text-xs font-bold text-emerald-200 block">{m.medication_name}</span>
                        <div className="text-[11px] text-slate-400 mt-0.5">
                          {m.dosage && <span>{m.dosage}</span>}
                          {m.frequency && <span> • {m.frequency}</span>}
                          {m.route && <span> ({m.route})</span>}
                        </div>
                      </div>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-medium">
                        ACTIVE
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/50 text-center text-xs text-slate-500 italic">
                  No active medications reported.
                </div>
              )}
            </div>

            {/* Relevant History & Background Details */}
            <div className="bg-[#0e1424] border border-slate-800 rounded-2xl p-5 space-y-4">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-teal-400">
                Medical Background & History
              </h3>

              <div className="space-y-3 text-xs">
                <div>
                  <span className="text-slate-400 block font-medium mb-1">Relevant Medical / Surgical History:</span>
                  <p className="text-slate-200 bg-slate-900/70 p-3 rounded-xl border border-slate-800 leading-relaxed">
                    {overview.relevant_history || 'No prior surgical or family history recorded.'}
                  </p>
                </div>

                <div>
                  <span className="text-slate-400 block font-medium mb-1">Clinical Notes & Impressions:</span>
                  <p className="text-slate-200 bg-slate-900/70 p-3 rounded-xl border border-slate-800 leading-relaxed">
                    {overview.notes || 'No notes added.'}
                  </p>
                </div>
              </div>
            </div>

          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* SECTION: Laboratory Results (Tabs: 'all', 'labs') */}
      {/* ========================================================= */}
      {(activeTab === 'all' || activeTab === 'labs') && (
        <div className="bg-[#0e1424] border border-slate-800 rounded-2xl p-6 shadow-xl">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Activity className="w-4 h-4 text-teal-400" />
                <span>Structured Laboratory Results ({overview.lab_results?.length || 0})</span>
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Discrete analyte values normalized with standardized reference range boundaries and abnormal flags.
              </p>
            </div>
            <ProvenanceBadge provenance="DOCUMENT_EXTRACTED" />
          </div>

          {overview.lab_results && overview.lab_results.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 font-mono text-[11px]">
                    <th className="pb-3 font-medium">Test / Analyte</th>
                    <th className="pb-3 font-medium">Result Value</th>
                    <th className="pb-3 font-medium">Reference Range</th>
                    <th className="pb-3 font-medium">Status Flag</th>
                    <th className="pb-3 font-medium">Provenance & Verification</th>
                    <th className="pb-3 font-medium">Collection Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {overview.lab_results.map((lab) => (
                    <tr key={lab.id} className="hover:bg-slate-900/40 transition-colors">
                      <td className="py-3 font-medium text-slate-100">
                        <span>{lab.test_name}</span>
                        <span className="block text-[11px] text-slate-500 font-mono">{lab.category}</span>
                      </td>
                      <td className="py-3 font-mono font-bold text-slate-200">
                        {lab.numerical_value !== undefined && lab.numerical_value !== null ? (
                          <span>{lab.numerical_value} {lab.unit}</span>
                        ) : (
                          <span>{lab.text_value || 'N/A'}</span>
                        )}
                        {/* Human corrected diff indicator */}
                        {lab.original_ai_value && lab.original_ai_value !== lab.text_value && (
                          <span className="block text-[10px] font-normal text-slate-400 mt-0.5" title="Original AI extraction before human clinician correction">
                            AI extracted: <del className="text-rose-400/80">{lab.original_ai_value}</del> → <span className="text-teal-300 font-semibold">{lab.text_value}</span>
                          </span>
                        )}
                      </td>
                      <td className="py-3 font-mono text-slate-400">
                        {lab.reference_low !== undefined && lab.reference_high !== undefined && lab.reference_low !== null ? (
                          <span>{lab.reference_low} - {lab.reference_high} {lab.unit}</span>
                        ) : (
                          <span>{lab.reference_text || 'See lab-specific range'}</span>
                        )}
                      </td>
                      <td className="py-3">
                        <LabStatusBadge status={lab.flag} />
                      </td>
                      <td className="py-3">
                        <div className="flex flex-col gap-1 items-start">
                          <ProvenanceBadge provenance={lab.provenance || (lab.is_verified ? "HUMAN_VERIFIED" : "AI_EXTRACTED")} />
                          {lab.confidence !== undefined && lab.confidence !== null && (
                            <span className="text-[10px] font-mono text-slate-400" title="Extraction confidence indicates model certainty on source document, not medical certainty">
                              {Math.round(lab.confidence * 100)}% conf
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-3 text-slate-400 font-mono text-[11px]">
                        {lab.collection_date ? new Date(lab.collection_date).toLocaleDateString() : 'N/A'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="p-8 text-center bg-slate-900/40 rounded-xl border border-slate-800/50 space-y-2">
              <Activity className="w-8 h-8 text-slate-600 mx-auto" />
              <p className="text-xs text-slate-400 font-medium">No laboratory panels on file for this patient.</p>
              <p className="text-[11px] text-slate-500">Upload a CBC or Chemistry report to populate discrete laboratory analytics.</p>
            </div>
          )}
        </div>
      )}

      {/* ========================================================= */}
      {/* SECTION: Reports & Documents (Tabs: 'all', 'documents') */}
      {/* ========================================================= */}
      {(activeTab === 'all' || activeTab === 'documents') && (
        <div className="bg-[#0e1424] border border-slate-800 rounded-2xl p-6 shadow-xl">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <FileText className="w-4 h-4 text-teal-400" />
                <span>Associated Medical Reports ({overview.documents?.length || 0})</span>
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Ingested PDF and OCR records with cryptographically verified SHA-256 signatures.
              </p>
            </div>
            <ProvenanceBadge provenance="DOCUMENT_EXTRACTED" />
          </div>

          {overview.documents && overview.documents.length > 0 ? (
            <div className="space-y-3">
              {overview.documents.map((doc) => (
                <div
                  key={doc.id}
                  className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                >
                  <div className="flex items-start gap-3">
                    <div className="p-2.5 rounded-xl bg-teal-500/10 text-teal-400 border border-teal-500/20">
                      <FileText className="w-5 h-5" />
                    </div>
                    <div>
                      <span className="text-xs font-bold text-slate-100 block">{doc.filename}</span>
                      <div className="flex items-center gap-3 text-[11px] text-slate-400 mt-1 font-mono flex-wrap">
                        <span>Facility: {doc.facility_name || 'Medical Center'}</span>
                        <span>•</span>
                        <span>Size: {(doc.file_size_bytes / 1024).toFixed(1)} KB</span>
                        <span>•</span>
                        <span title={doc.sha256_checksum}>
                          SHA-256: {doc.sha256_checksum.substring(0, 14)}...
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 self-end sm:self-center">
                    <span className="text-[10px] font-mono px-2.5 py-1 rounded bg-teal-500/10 text-teal-300 border border-teal-500/30">
                      {doc.processing_status}
                    </span>
                    <button
                      onClick={() =>
                        setSelectedDocText({
                          name: doc.filename,
                          text: `Document ${doc.filename} verified with SHA-256 checksum: ${doc.sha256_checksum}. Ingested from ${doc.facility_name || 'Regional Lab'}.`
                        })
                      }
                      className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
                      title="Inspect Report Info"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-8 text-center bg-slate-900/40 rounded-xl border border-slate-800/50 space-y-2">
              <FileText className="w-8 h-8 text-slate-600 mx-auto" />
              <p className="text-xs text-slate-400 font-medium">No medical documents attached to this patient.</p>
              <p className="text-[11px] text-slate-500">Go to the Reports page to upload a clinical laboratory document or discharge summary.</p>
            </div>
          )}
        </div>
      )}

      {/* ========================================================= */}
      {/* SECTION: Longitudinal Clinical Timeline (Tabs: 'all', 'timeline') */}
      {/* ========================================================= */}
      {(activeTab === 'all' || activeTab === 'timeline') && (
        <div className="bg-[#0e1424] border border-slate-800 rounded-2xl p-6 shadow-xl">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Clock className="w-4 h-4 text-teal-400" />
                <span>Longitudinal Clinical Timeline ({overview.timeline?.length || 0})</span>
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Multi-source chronological record merging intake history, lab dates, medications, and encounters.
              </p>
            </div>
          </div>

          {overview.timeline && overview.timeline.length > 0 ? (
            <div className="relative pl-6 space-y-6 before:content-[''] before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-800">
              {overview.timeline.map((evt) => (
                <div key={evt.id} className="relative group">
                  {/* Timeline bullet */}
                  <div className="absolute -left-[19px] top-1 w-3.5 h-3.5 rounded-full bg-[#0e1424] border-2 border-teal-500 group-hover:border-teal-400 transition-colors"></div>

                  <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 hover:border-slate-700 transition-all">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 sm:gap-4 mb-1.5">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-white">{evt.title}</span>
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400">
                          {evt.event_type}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 font-mono text-[11px] text-slate-400">
                        <Calendar className="w-3 h-3 text-slate-500" />
                        <span>{evt.date}</span>
                        <ProvenanceBadge provenance={evt.source_provenance} />
                      </div>
                    </div>
                    <p className="text-xs text-slate-300">{evt.description}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-8 text-center bg-slate-900/40 rounded-xl border border-slate-800/50 space-y-2">
              <Clock className="w-8 h-8 text-slate-600 mx-auto" />
              <p className="text-xs text-slate-400">No longitudinal events recorded.</p>
            </div>
          )}
        </div>
      )}

      {/* ========================================================= */}
      {/* SECTION: Discrepancies & Conflicts (Tabs: 'all', 'conflicts') */}
      {/* ========================================================= */}
      {(activeTab === 'all' || activeTab === 'conflicts') && (
        <div className="bg-[#0e1424] border border-slate-800 rounded-2xl p-6 shadow-xl">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                <span>Safety & Cross-Document Conflicts ({overview.conflicts?.length || 0})</span>
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Automated detection of allergy-drug contraindications, duplicate entries, and timeline contradictions.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleScanConflicts}
                disabled={scanningConflicts}
                className="px-3 py-1.5 rounded-xl bg-amber-600/20 hover:bg-amber-600/30 text-amber-300 border border-amber-500/40 text-xs font-semibold flex items-center gap-1.5 transition-all disabled:opacity-50"
                title="Trigger automated conflict, allergy-drug contraindication, and discrepancy check"
              >
                <Zap className={`w-3.5 h-3.5 ${scanningConflicts ? 'animate-spin' : 'text-amber-400'}`} />
                <span>{scanningConflicts ? 'Analyzing...' : 'Scan Inconsistencies'}</span>
              </button>
              <ProvenanceBadge provenance="SYSTEM_CALCULATED" />
            </div>
          </div>

          {overview.conflicts && overview.conflicts.length > 0 ? (
            <div className="space-y-4">
              {overview.conflicts.map((conf) => (
                <div
                  key={conf.id}
                  className="p-4 rounded-xl bg-amber-500/5 border border-amber-500/20 space-y-3"
                >
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 text-amber-400" />
                      <span className="text-xs font-bold text-amber-300">{conf.conflict_type}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <ConflictSeverityBadge severity={conf.severity as any} />
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                        {conf.status}
                      </span>
                    </div>
                  </div>

                  <p className="text-xs text-slate-200">{conf.description}</p>

                  {(conf.source_one || conf.source_two) && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 text-[11px] font-mono">
                      {conf.source_one && (
                        <div className="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800">
                          <span className="text-slate-500 block mb-1">Source Evidence A:</span>
                          <span className="text-slate-300">{conf.source_one}</span>
                        </div>
                      )}
                      {conf.source_two && (
                        <div className="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800">
                          <span className="text-slate-500 block mb-1">Source Evidence B:</span>
                          <span className="text-slate-300">{conf.source_two}</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="p-8 text-center bg-slate-900/40 rounded-xl border border-slate-800/50 space-y-2">
              <CheckCircle className="w-8 h-8 text-emerald-500 mx-auto" />
              <p className="text-xs text-slate-300 font-medium">No cross-document conflicts or contraindications detected.</p>
              <p className="text-[11px] text-slate-500">Prescription records, allergies, and lab results are aligned.</p>
            </div>
          )}
        </div>
      )}

      {/* Document Raw Info Modal */}
      {selectedDocText && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
          <div className="bg-[#0e1424] border border-slate-800 rounded-2xl w-full max-w-lg p-6 space-y-4">
            <h3 className="text-sm font-bold text-white">{selectedDocText.name}</h3>
            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 text-xs font-mono text-slate-300 whitespace-pre-wrap">
              {selectedDocText.text}
            </div>
            <div className="flex justify-end">
              <button
                onClick={() => setSelectedDocText(null)}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs text-white"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Patient Modal */}
      {showEditModal && overview && (
        <EditPatientModal
          patient={overview}
          onClose={() => setShowEditModal(false)}
          onSave={handleSaveEdit}
        />
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
          <div className="bg-[#0e1424] border border-rose-500/30 rounded-2xl w-full max-w-md p-6 space-y-4 animate-fadeIn">
            <div className="w-12 h-12 rounded-full bg-rose-500/10 text-rose-400 flex items-center justify-center mx-auto">
              <Trash2 className="w-6 h-6" />
            </div>

            <div className="text-center space-y-1.5">
              <h3 className="text-base font-bold text-white">Delete Patient Record?</h3>
              <p className="text-xs text-slate-400">
                Are you sure you want to permanently delete patient <strong>{overview.first_name} {overview.last_name}</strong> (MRN: {overview.mrn})?
              </p>
              <p className="text-[11px] text-rose-400/90 pt-1">
                This action will cascade delete all associated conditions, allergies, medications, lab results, and documents.
              </p>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                disabled={actionInProgress}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={actionInProgress}
                className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold shadow-lg shadow-rose-600/30 flex items-center gap-1.5"
              >
                <Trash2 className="w-4 h-4" />
                <span>{actionInProgress ? 'Deleting...' : 'Confirm Delete'}</span>
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};
