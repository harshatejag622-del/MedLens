import React, { useState, useEffect } from 'react';
import {
  Clock,
  Calendar,
  FileText,
  CheckCircle,
  AlertTriangle,
  UserCheck,
  Activity,
  Filter,
  Search,
  ArrowUpDown,
  TrendingUp,
  Pill,
  Stethoscope,
  FileSpreadsheet,
  Cpu,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Zap,
  Info,
  ExternalLink,
  ShieldCheck,
  ShieldAlert
} from 'lucide-react';
import { Patient, DocumentItem, ConflictItem } from '../../types';
import { api } from '../../services/api';
import { ProvenanceBadge, LabStatusBadge, ConflictSeverityBadge } from '../common/Badges';

interface TimelinePageProps {
  patient: Patient | null;
  patients?: Patient[];
  onSelectPatient?: (p: Patient) => void;
  documents: DocumentItem[];
  conflicts: ConflictItem[];
}

export const TimelinePage: React.FC<TimelinePageProps> = ({
  patient,
  patients = [],
  onSelectPatient,
  documents,
  conflicts
}) => {
  // Navigation Tabs within Longitudinal View (Req 16)
  const [activeSubTab, setActiveSubTab] = useState<'timeline' | 'summary' | 'trends' | 'medications' | 'diagnoses'>('timeline');

  // Timeline State
  const [timelineEvents, setTimelineEvents] = useState<any[]>([]);
  const [totalEvents, setTotalEvents] = useState(0);
  const [loadingTimeline, setLoadingTimeline] = useState(false);
  const [sortOrder, setSortOrder] = useState<'desc' | 'asc'>('desc');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedEventType, setSelectedEventType] = useState<string>('ALL');
  const [selectedVerification, setSelectedVerification] = useState<string>('ALL');
  const [expandedEventId, setExpandedEventId] = useState<string | null>(null);

  // Clinical Summary State
  const [summaryData, setSummaryData] = useState<any | null>(null);
  const [generatingSummary, setGeneratingSummary] = useState(false);

  // Lab Trends State
  const [trendsData, setTrendsData] = useState<Record<string, any>>({});
  const [loadingTrends, setLoadingTrends] = useState(false);
  const [selectedTrendTest, setSelectedTrendTest] = useState<string | null>(null);

  // Medication & Diagnosis History State
  const [medHistory, setMedHistory] = useState<any[]>([]);
  const [diagHistory, setDiagHistory] = useState<any[]>([]);
  const [loadingHistories, setLoadingHistories] = useState(false);

  // Fetch Timeline Events
  const fetchTimeline = async () => {
    if (!patient) return;
    try {
      setLoadingTimeline(true);
      const params: any = {
        sort_order: sortOrder,
        search_query: searchQuery.trim() || undefined
      };
      if (selectedEventType !== 'ALL') {
        params.event_type = [selectedEventType];
      }
      if (selectedVerification !== 'ALL') {
        params.verification_status = selectedVerification;
      }
      const res = await api.getTimeline(patient.id, params);
      setTimelineEvents(res.events || []);
      setTotalEvents(res.total || 0);
    } catch (e: any) {
      console.error('Failed to load timeline events:', e);
    } finally {
      setLoadingTimeline(false);
    }
  };

  // Fetch Longitudinal Trends
  const fetchTrends = async () => {
    if (!patient) return;
    try {
      setLoadingTrends(true);
      const res = await api.getLabTrends(patient.id);
      const trends = res.trends || {};
      setTrendsData(trends);
      const keys = Object.keys(trends);
      if (keys.length > 0 && !selectedTrendTest) {
        setSelectedTrendTest(keys[0]);
      }
    } catch (e: any) {
      console.error('Failed to load lab trends:', e);
    } finally {
      setLoadingTrends(false);
    }
  };

  // Fetch Histories
  const fetchHistories = async () => {
    if (!patient) return;
    try {
      setLoadingHistories(true);
      const [mRes, dRes] = await Promise.all([
        api.getMedicationHistory(patient.id),
        api.getDiagnosisHistory(patient.id)
      ]);
      setMedHistory(mRes.medications || []);
      setDiagHistory(dRes.diagnoses || []);
    } catch (e: any) {
      console.error('Failed to load histories:', e);
    } finally {
      setLoadingHistories(false);
    }
  };

  // Generate / Load Clinical Summary
  const handleGenerateSummary = async () => {
    if (!patient) return;
    try {
      setGeneratingSummary(true);
      const res = await api.generateClinicalSummary(patient.id);
      setSummaryData(res);
    } catch (e: any) {
      alert(e.message || 'Error synthesizing clinical summary');
    } finally {
      setGeneratingSummary(false);
    }
  };

  // Reset Filters
  const handleClearFilters = () => {
    setSearchQuery('');
    setSelectedEventType('ALL');
    setSelectedVerification('ALL');
    setSortOrder('desc');
  };

  useEffect(() => {
    if (patient) {
      fetchTimeline();
      fetchTrends();
      fetchHistories();
    }
  }, [patient?.id, sortOrder, selectedEventType, selectedVerification]);

  if (!patient) {
    return (
      <div className="p-12 text-center rounded-2xl bg-[#0e1424] border border-slate-800 space-y-4">
        <Clock className="w-10 h-10 text-teal-400 mx-auto opacity-70" />
        <div className="space-y-1">
          <h2 className="text-base font-bold text-white">Select a Patient for Longitudinal Analysis</h2>
          <p className="text-xs text-slate-400 max-w-md mx-auto">
            Choose a patient to visualize their chronological timeline, laboratory trends, medication regimens, and evidence-grounded clinical summaries.
          </p>
        </div>
        {patients.length > 0 && (
          <div className="flex flex-wrap items-center justify-center gap-2 pt-2">
            {patients.map(p => (
              <button
                key={p.id}
                onClick={() => onSelectPatient && onSelectPatient(p)}
                className="px-3.5 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700 text-xs text-slate-200 font-medium transition-all"
              >
                {p.first_name} {p.last_name} ({p.mrn})
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fadeIn">
      
      {/* Header & Patient Context Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-bold text-white tracking-wide flex items-center gap-2.5">
              <Clock className="w-6 h-6 text-teal-400" />
              <span>Longitudinal Clinical Intelligence</span>
            </h1>
            <span className="text-xs font-mono px-2.5 py-0.5 rounded-full bg-teal-500/10 text-teal-300 border border-teal-500/30 font-semibold">
              {patient.first_name} {patient.last_name} (MRN: {patient.mrn})
            </span>
          </div>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Chronological clinical events, discrete laboratory trajectories, longitudinal medication histories, and evidence-grounded narrative summarization.
          </p>
        </div>

        {/* Patient Switcher if multiple available */}
        {patients.length > 1 && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400 font-medium">Switch Patient:</span>
            <select
              value={patient.id}
              onChange={(e) => {
                const found = patients.find(p => p.id === e.target.value);
                if (found && onSelectPatient) onSelectPatient(found);
              }}
              className="px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-teal-500"
            >
              {patients.map(p => (
                <option key={p.id} value={p.id}>
                  {p.first_name} {p.last_name} ({p.mrn})
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Navigation Sub-Tabs */}
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-800 pb-3 text-xs">
        <button
          onClick={() => setActiveSubTab('timeline')}
          className={`px-4 py-2 rounded-xl font-semibold flex items-center gap-2 transition-all ${
            activeSubTab === 'timeline'
              ? 'bg-teal-600 text-white shadow-sm'
              : 'text-slate-400 hover:text-white hover:bg-slate-800'
          }`}
        >
          <Clock className="w-4 h-4" />
          <span>Patient Timeline ({totalEvents})</span>
        </button>

        <button
          onClick={() => {
            setActiveSubTab('summary');
            if (!summaryData) handleGenerateSummary();
          }}
          className={`px-4 py-2 rounded-xl font-semibold flex items-center gap-2 transition-all ${
            activeSubTab === 'summary'
              ? 'bg-teal-600 text-white shadow-sm'
              : 'text-slate-400 hover:text-white hover:bg-slate-800'
          }`}
        >
          <Cpu className="w-4 h-4" />
          <span>Clinical Summary</span>
        </button>

        <button
          onClick={() => setActiveSubTab('trends')}
          className={`px-4 py-2 rounded-xl font-semibold flex items-center gap-2 transition-all ${
            activeSubTab === 'trends'
              ? 'bg-teal-600 text-white shadow-sm'
              : 'text-slate-400 hover:text-white hover:bg-slate-800'
          }`}
        >
          <TrendingUp className="w-4 h-4" />
          <span>Laboratory Trends ({Object.keys(trendsData).length})</span>
        </button>

        <button
          onClick={() => setActiveSubTab('medications')}
          className={`px-4 py-2 rounded-xl font-semibold flex items-center gap-2 transition-all ${
            activeSubTab === 'medications'
              ? 'bg-teal-600 text-white shadow-sm'
              : 'text-slate-400 hover:text-white hover:bg-slate-800'
          }`}
        >
          <Pill className="w-4 h-4" />
          <span>Medication History ({medHistory.length})</span>
        </button>

        <button
          onClick={() => setActiveSubTab('diagnoses')}
          className={`px-4 py-2 rounded-xl font-semibold flex items-center gap-2 transition-all ${
            activeSubTab === 'diagnoses'
              ? 'bg-teal-600 text-white shadow-sm'
              : 'text-slate-400 hover:text-white hover:bg-slate-800'
          }`}
        >
          <Stethoscope className="w-4 h-4" />
          <span>Diagnosis History ({diagHistory.length})</span>
        </button>
      </div>

      {/* ========================================================= */}
      {/* SUB-TAB 1: CHRONOLOGICAL TIMELINE (Req 1, 2, 3) */}
      {/* ========================================================= */}
      {activeSubTab === 'timeline' && (
        <div className="space-y-4">
          
          {/* Timeline Filter Controls */}
          <div className="p-4 rounded-2xl bg-[#0e1424] border border-slate-800 space-y-3 text-xs">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
              {/* Search Bar */}
              <div className="relative flex-1 max-w-md">
                <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && fetchTimeline()}
                  placeholder="Search timeline events, diagnoses, labs, sources..."
                  className="w-full pl-9 pr-4 py-2 bg-slate-900 border border-slate-700 rounded-xl text-white font-sans text-xs focus:outline-none focus:border-teal-500"
                />
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setSortOrder(prev => prev === 'desc' ? 'asc' : 'desc')}
                  className="px-3 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 font-medium flex items-center gap-1.5 transition-all"
                  title="Toggle sorting direction"
                >
                  <ArrowUpDown className="w-3.5 h-3.5 text-teal-400" />
                  <span>{sortOrder === 'desc' ? 'Newest First' : 'Oldest First'}</span>
                </button>

                <button
                  onClick={fetchTimeline}
                  className="px-3 py-2 rounded-xl bg-teal-600 hover:bg-teal-500 text-white font-semibold flex items-center gap-1.5 transition-all shadow-sm"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${loadingTimeline ? 'animate-spin' : ''}`} />
                  <span>Refresh</span>
                </button>

                <button
                  onClick={handleClearFilters}
                  className="px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 transition-all font-medium"
                >
                  Clear Filters
                </button>
              </div>
            </div>

            {/* Filter Dropdowns */}
            <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-slate-800/80">
              <div className="flex items-center gap-1.5">
                <span className="text-slate-400 font-medium">Event Type:</span>
                <select
                  value={selectedEventType}
                  onChange={(e) => setSelectedEventType(e.target.value)}
                  className="px-2.5 py-1 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:border-teal-500"
                >
                  <option value="ALL">All Event Types</option>
                  <option value="INTAKE">Patient Intake</option>
                  <option value="CONDITION">Condition / Diagnosis</option>
                  <option value="MEDICATION">Medication</option>
                  <option value="LABORATORY">Laboratory Result</option>
                  <option value="DOCUMENT">Report Ingestion</option>
                  <option value="CONFLICT">Clinical Discrepancy</option>
                  <option value="VERIFICATION">Human Verification</option>
                </select>
              </div>

              <div className="flex items-center gap-1.5">
                <span className="text-slate-400 font-medium">Verification Provenance:</span>
                <select
                  value={selectedVerification}
                  onChange={(e) => setSelectedVerification(e.target.value)}
                  className="px-2.5 py-1 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:border-teal-500"
                >
                  <option value="ALL">All Provenance</option>
                  <option value="HUMAN_VERIFIED">Human Verified</option>
                  <option value="HUMAN_CORRECTED">Human Corrected</option>
                  <option value="AI_EXTRACTED">AI Extracted</option>
                  <option value="USER_PROVIDED">User Provided</option>
                  <option value="SYSTEM_CALCULATED">System Calculated</option>
                </select>
              </div>
            </div>
          </div>

          {/* Timeline Tree Visualization */}
          <div className="p-8 rounded-2xl bg-[#0e1424] border border-slate-800 relative space-y-6">
            <div className="absolute left-10 top-8 bottom-8 w-0.5 bg-slate-800"></div>

            {timelineEvents.map((evt) => {
              const isExpanded = expandedEventId === evt.id;
              const isConflict = evt.event_type === 'CONFLICT';
              const isLab = evt.event_type === 'LABORATORY';
              const isHighSev = evt.severity === 'HIGH';

              return (
                <div
                  key={evt.id}
                  className={`relative pl-10 transition-all ${
                    isConflict && isHighSev ? 'opacity-100' : ''
                  }`}
                >
                  {/* Timeline Dot */}
                  <div className={`absolute left-0 top-1.5 w-4 h-4 rounded-full border-2 border-[#0e1424] transition-all ${
                    isConflict
                      ? isHighSev ? 'bg-rose-500 shadow-[0_0_10px_#f43f5e]' : 'bg-amber-400 shadow-[0_0_10px_#f59e0b]'
                      : isLab
                      ? 'bg-sky-400 shadow-[0_0_8px_#38bdf8]'
                      : evt.event_type === 'VERIFICATION'
                      ? 'bg-teal-400 shadow-[0_0_8px_#14b8a6]'
                      : 'bg-indigo-400 shadow-[0_0_8px_#818cf8]'
                  }`}></div>

                  <div className={`p-4 rounded-xl border transition-all ${
                    isConflict && isHighSev
                      ? 'bg-rose-950/20 border-rose-500/40'
                      : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
                  }`}>
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-1.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-xs font-bold text-teal-300">
                          {evt.event_date}
                        </span>
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-semibold uppercase">
                          {evt.event_type}
                        </span>
                        <ProvenanceBadge provenance={evt.verification_status} />
                        {evt.severity && evt.severity !== 'NORMAL' && (
                          <ConflictSeverityBadge severity={evt.severity} />
                        )}
                      </div>

                      <button
                        onClick={() => setExpandedEventId(isExpanded ? null : evt.id)}
                        className="text-slate-400 hover:text-white flex items-center gap-1 text-[11px] font-medium"
                      >
                        <span>{isExpanded ? 'Less' : 'Details'}</span>
                        {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                      </button>
                    </div>

                    <h3 className="text-sm font-bold text-white tracking-wide">
                      {evt.title}
                    </h3>
                    <p className="text-xs text-slate-300 mt-1 leading-relaxed">
                      {evt.description}
                    </p>

                    {/* Expanded Traceability Panel (Req 13) */}
                    {isExpanded && (
                      <div className="mt-3 pt-3 border-t border-slate-800 grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs font-mono text-slate-400 animate-fadeIn">
                        <div className="p-2.5 rounded-lg bg-black/40 border border-slate-800/80">
                          <span className="text-[10px] uppercase text-slate-500 block mb-0.5">Source Document</span>
                          <span className="text-amber-300 font-medium">{evt.source_document || 'Direct Clinical Profile'}</span>
                        </div>
                        <div className="p-2.5 rounded-lg bg-black/40 border border-slate-800/80">
                          <span className="text-[10px] uppercase text-slate-500 block mb-0.5">Location / Context</span>
                          <span className="text-slate-200">{evt.source_location || 'Ingestion Pipeline'}</span>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {timelineEvents.length === 0 && (
              <div className="p-8 text-center text-xs text-slate-400">
                No timeline events found matching the specified filters.
              </div>
            )}
          </div>

        </div>
      )}

      {/* ========================================================= */}
      {/* SUB-TAB 2: EVIDENCE-GROUNDED CLINICAL SUMMARY (Req 7, 8, 9) */}
      {/* ========================================================= */}
      {activeSubTab === 'summary' && (
        <div className="space-y-6">
          <div className="p-6 rounded-2xl bg-[#0e1424] border border-slate-800 space-y-4 shadow-xl">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
              <div>
                <span className="text-[10px] font-mono uppercase tracking-wider text-teal-400 font-bold block">
                  AI-Assisted Clinical Narrative
                </span>
                <h2 className="text-lg font-bold text-white mt-0.5">
                  Longitudinal Clinical Summary for {patient.first_name} {patient.last_name}
                </h2>
              </div>
              <button
                disabled={generatingSummary}
                onClick={handleGenerateSummary}
                className="px-4 py-2 rounded-xl bg-teal-600 hover:bg-teal-500 text-white text-xs font-semibold flex items-center gap-2 shadow-sm transition-all disabled:opacity-50"
              >
                <Zap className={`w-3.5 h-3.5 ${generatingSummary ? 'animate-spin' : ''}`} />
                <span>{generatingSummary ? 'Synthesizing...' : 'Regenerate Summary'}</span>
              </button>
            </div>

            {/* Clinical Safety Disclaimer Callout */}
            <div className="p-3 bg-slate-900 border border-amber-500/30 rounded-xl text-xs text-amber-200/90 flex items-start gap-2">
              <Info className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
              <div>
                <strong className="block text-amber-300 font-bold mb-0.5">Decision-Support Notice:</strong>
                {summaryData?.disclaimer || "MedLens longitudinal summaries are grounded strictly in stored records and do not constitute independent medical diagnoses or treatment recommendations."}
              </div>
            </div>

            {/* Structured Summary Narrative Sections */}
            {summaryData?.sections ? (
              <div className="space-y-4 text-xs sm:text-sm text-slate-200 leading-relaxed font-sans">
                <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-teal-400 font-mono">Patient Overview</h3>
                  <p>{summaryData.sections.patient_overview}</p>
                </div>

                <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-teal-400 font-mono">Clinical History & Diagnoses</h3>
                  <p>{summaryData.sections.diagnoses}</p>
                </div>

                <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-teal-400 font-mono">Medications & Allergies</h3>
                  <p>{summaryData.sections.medications}</p>
                  <p className="pt-1">{summaryData.sections.allergies}</p>
                </div>

                <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-teal-400 font-mono">Laboratory Trends & Out-of-Range Analytes</h3>
                  <p>{summaryData.sections.laboratories}</p>
                </div>

                <div className="p-4 rounded-xl bg-amber-950/20 border border-amber-500/30 space-y-1">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-amber-400 font-mono">Unresolved Clinical Conflicts</h3>
                  <p>{summaryData.sections.unresolved_conflicts}</p>
                </div>

                <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-teal-400 font-mono">Human Verification Audit</h3>
                  <p>{summaryData.sections.verification_status}</p>
                </div>
              </div>
            ) : (
              <div className="p-8 text-center text-xs text-slate-400">
                Click "Regenerate Summary" to synthesize a grounded clinical narrative for this patient.
              </div>
            )}

            {/* Evidence References Table (Req 8) */}
            {summaryData?.evidence_references && summaryData.evidence_references.length > 0 && (
              <div className="pt-4 border-t border-slate-800 space-y-2">
                <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider font-mono">
                  Traceable Supporting Evidence ({summaryData.evidence_references.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs font-mono">
                    <thead>
                      <tr className="border-b border-slate-800 text-slate-500 text-[10px]">
                        <th className="pb-2">Clinical Item</th>
                        <th className="pb-2">Category</th>
                        <th className="pb-2">Source Reference</th>
                        <th className="pb-2">Provenance</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 text-slate-300">
                      {summaryData.evidence_references.map((ev: any, idx: number) => (
                        <tr key={idx} className="hover:bg-slate-900/40">
                          <td className="py-2 font-bold text-white">{ev.item}</td>
                          <td className="py-2 text-slate-400">{ev.category}</td>
                          <td className="py-2 text-amber-300">{ev.source}</td>
                          <td className="py-2">
                            <ProvenanceBadge provenance={ev.provenance} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* SUB-TAB 3: LONGITUDINAL LAB TRENDS (Req 4) */}
      {/* ========================================================= */}
      {activeSubTab === 'trends' && (
        <div className="space-y-6">
          <div className="p-6 rounded-2xl bg-[#0e1424] border border-slate-800 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <TrendingUp className="w-5 h-5 text-teal-400" />
                  <span>Longitudinal Laboratory Trajectories</span>
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  Chronological analyte trendlines with reference range boundaries and abnormal flags.
                </p>
              </div>

              {/* Select Analyte */}
              {Object.keys(trendsData).length > 0 && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-400 font-medium">Analyte:</span>
                  <select
                    value={selectedTrendTest || ''}
                    onChange={(e) => setSelectedTrendTest(e.target.value)}
                    className="px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-teal-500 font-mono"
                  >
                    {Object.keys(trendsData).map(k => (
                      <option key={k} value={k}>{k} ({trendsData[k].points_count} points)</option>
                    ))}
                  </select>
                </div>
              )}
            </div>

            {selectedTrendTest && trendsData[selectedTrendTest] ? (
              <div className="space-y-4 pt-2">
                {/* Trend Summary Info */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
                  <div className="p-3 rounded-xl bg-slate-900 border border-slate-800">
                    <span className="text-[10px] text-slate-500 uppercase block">Analyte Name</span>
                    <span className="text-sm font-bold text-white">{trendsData[selectedTrendTest].test_name}</span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-900 border border-slate-800">
                    <span className="text-[10px] text-slate-500 uppercase block">Primary Unit</span>
                    <span className="text-sm font-bold text-teal-400">{trendsData[selectedTrendTest].primary_unit || 'N/A'}</span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-900 border border-slate-800">
                    <span className="text-[10px] text-slate-500 uppercase block">Total Data Points</span>
                    <span className="text-sm font-bold text-white">{trendsData[selectedTrendTest].points_count}</span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-900 border border-slate-800">
                    <span className="text-[10px] text-slate-500 uppercase block">Unit Consistency</span>
                    <span className={`text-sm font-bold ${trendsData[selectedTrendTest].multiple_units ? 'text-amber-400' : 'text-emerald-400'}`}>
                      {trendsData[selectedTrendTest].multiple_units ? 'Varying Units' : 'Consistent'}
                    </span>
                  </div>
                </div>

                {/* Chronological Points Table & Trajectory Plot */}
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-slate-800 text-slate-400 font-mono text-[11px]">
                        <th className="pb-3">Collection Date</th>
                        <th className="pb-3">Value</th>
                        <th className="pb-3">Reference Range</th>
                        <th className="pb-3">Abnormal Flag</th>
                        <th className="pb-3">Verification</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 font-mono">
                      {trendsData[selectedTrendTest].data_points.map((pt: any) => (
                        <tr key={pt.id} className="hover:bg-slate-900/40">
                          <td className="py-3 text-slate-300 font-bold">{pt.date}</td>
                          <td className="py-3 font-bold text-white">
                            {pt.value} {pt.unit}
                            {pt.original_ai_value && pt.original_ai_value !== String(pt.value) && (
                              <span className="block text-[10px] text-slate-500 font-normal">
                                Original: {pt.original_ai_value}
                              </span>
                            )}
                          </td>
                          <td className="py-3 text-slate-400">
                            {pt.reference_low !== undefined && pt.reference_high !== undefined && pt.reference_low !== null
                              ? `${pt.reference_low} - ${pt.reference_high} ${pt.unit}`
                              : (pt.reference_text || 'See source lab report')}
                          </td>
                          <td className="py-3">
                            <LabStatusBadge status={pt.status} />
                          </td>
                          <td className="py-3">
                            <ProvenanceBadge provenance={pt.provenance || (pt.is_verified ? "HUMAN_VERIFIED" : "AI_EXTRACTED")} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <div className="p-8 text-center text-xs text-slate-400">
                No longitudinal laboratory values recorded for this patient.
              </div>
            )}
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* SUB-TAB 4: LONGITUDINAL MEDICATION HISTORY (Req 5) */}
      {/* ========================================================= */}
      {activeSubTab === 'medications' && (
        <div className="space-y-6">
          <div className="p-6 rounded-2xl bg-[#0e1424] border border-slate-800 space-y-4">
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <Pill className="w-5 h-5 text-teal-400" />
              <span>Longitudinal Medication Regimen & History</span>
            </h2>

            {medHistory.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-slate-800 text-slate-400 font-mono text-[11px]">
                      <th className="pb-3">Medication</th>
                      <th className="pb-3">Dose & Frequency</th>
                      <th className="pb-3">Route</th>
                      <th className="pb-3">Start Date</th>
                      <th className="pb-3">Status</th>
                      <th className="pb-3">Source & Verification</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {medHistory.map((m) => (
                      <tr key={m.id} className="hover:bg-slate-900/40">
                        <td className="py-3 font-bold text-white font-mono">{m.medication_name}</td>
                        <td className="py-3 text-slate-200">{m.dose} ({m.frequency})</td>
                        <td className="py-3 text-slate-400 font-mono text-[11px]">{m.route}</td>
                        <td className="py-3 font-mono text-slate-300">{m.start_date}</td>
                        <td className="py-3">
                          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase bg-teal-500/10 text-teal-300 border border-teal-500/30">
                            {m.current_status}
                          </span>
                        </td>
                        <td className="py-3 space-y-1">
                          <div className="text-[11px] text-slate-400">{m.source}</div>
                          <ProvenanceBadge provenance={m.verification_status} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-8 text-center text-xs text-slate-400">
                No medication records found in the current patient chart.
              </div>
            )}
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* SUB-TAB 5: LONGITUDINAL DIAGNOSIS HISTORY (Req 6) */}
      {/* ========================================================= */}
      {activeSubTab === 'diagnoses' && (
        <div className="space-y-6">
          <div className="p-6 rounded-2xl bg-[#0e1424] border border-slate-800 space-y-4">
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <Stethoscope className="w-5 h-5 text-teal-400" />
              <span>Longitudinal Diagnosis Progression</span>
            </h2>

            {diagHistory.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-slate-800 text-slate-400 font-mono text-[11px]">
                      <th className="pb-3">Diagnosis</th>
                      <th className="pb-3">First Recorded</th>
                      <th className="pb-3">Most Recent</th>
                      <th className="pb-3">Current Status</th>
                      <th className="pb-3">Supporting Documents</th>
                      <th className="pb-3">Verification</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {diagHistory.map((d, idx) => (
                      <tr key={idx} className="hover:bg-slate-900/40">
                        <td className="py-3 font-bold text-white text-sm">{d.diagnosis}</td>
                        <td className="py-3 font-mono text-teal-300">{d.first_recorded_date}</td>
                        <td className="py-3 font-mono text-slate-300">{d.most_recent_date}</td>
                        <td className="py-3">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase ${
                            d.current_status === 'ACTIVE'
                              ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                              : 'bg-slate-800 text-slate-400'
                          }`}>
                            {d.current_status}
                          </span>
                        </td>
                        <td className="py-3 text-slate-400 font-mono text-[11px]">
                          {d.supporting_sources?.join(', ') || 'Patient Profile'}
                        </td>
                        <td className="py-3">
                          <ProvenanceBadge provenance={d.verification_status} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-8 text-center text-xs text-slate-400">
                No diagnosis progression records documented.
              </div>
            )}
          </div>
        </div>
      )}

    </div>
  );
};
