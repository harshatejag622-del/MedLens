import React from 'react';
import { Users, FileText, CheckSquare, AlertTriangle, ArrowRight, ShieldCheck, Activity, Clock } from 'lucide-react';
import { OperationalStats, Patient } from '../../types';

interface DashboardProps {
  stats: OperationalStats | null;
  patients: Patient[];
  onSelectPatient: (patient: Patient) => void;
  onNavigate: (tab: string) => void;
}

export const DashboardPage: React.FC<DashboardProps> = ({
  stats,
  patients,
  onSelectPatient,
  onNavigate
}) => {
  const cards = [
    {
      label: 'Total Patients',
      value: stats?.total_patients ?? 0,
      icon: Users,
      color: 'text-sky-400',
      bg: 'bg-sky-500/10',
      border: 'border-sky-500/30',
      action: () => onNavigate('patients')
    },
    {
      label: 'Reports Processed',
      value: stats?.reports_processed ?? 0,
      icon: FileText,
      color: 'text-teal-400',
      bg: 'bg-teal-500/10',
      border: 'border-teal-500/30',
      action: () => onNavigate('reports')
    },
    {
      label: 'Pending Reviews',
      value: stats?.pending_reviews ?? 0,
      icon: CheckSquare,
      color: 'text-amber-400',
      bg: 'bg-amber-500/10',
      border: 'border-amber-500/30',
      action: () => onNavigate('review')
    },
    {
      label: 'Detected Conflicts',
      value: stats?.unresolved_conflicts ?? 0,
      icon: AlertTriangle,
      color: 'text-rose-400',
      bg: 'bg-rose-500/10',
      border: 'border-rose-500/30',
      action: () => onNavigate('conflicts')
    }
  ];

  return (
    <div className="space-y-8 animate-fadeIn">
      
      {/* Top Banner / Mission Statement */}
      <div className="p-7 rounded-2xl bg-gradient-to-r from-[#0f172a]/95 via-[#0f2334]/85 to-[#042f2e]/60 border border-teal-500/20 shadow-2xl backdrop-blur-md flex flex-col md:flex-row items-start md:items-center justify-between gap-6 relative overflow-hidden">
        <div className="absolute -right-20 -top-20 w-72 h-72 bg-teal-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="relative z-10">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-[11px] font-mono uppercase tracking-widest text-teal-400 font-bold px-2.5 py-0.5 rounded-full bg-teal-500/10 border border-teal-500/25">
              Clinical Information Intelligence Platform
            </span>
            <span className="text-[10px] font-mono text-slate-400 bg-slate-800/80 px-2 py-0.5 rounded-full border border-slate-700">
              v1.0 Production
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
            Clinical Operations Dashboard
          </h1>
          <p className="text-xs sm:text-sm text-slate-300/90 max-w-2xl mt-1.5 leading-relaxed font-sans">
            MedLens standardizes fragmented medical reports into traceable, verified clinical records with strict provenance and reference range preservation.
          </p>
        </div>

        <div className="flex items-center gap-3 relative z-10 flex-shrink-0">
          <button
            onClick={() => onNavigate('patients')}
            className="px-5 py-3 rounded-xl bg-gradient-to-r from-teal-600 to-teal-500 hover:from-teal-500 hover:to-teal-400 text-white text-xs font-bold tracking-wider transition-all shadow-[0_0_25px_rgba(20,184,166,0.35)] flex items-center gap-2.5 active:scale-95"
          >
            <span>Patient Intake</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* 4 Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {cards.map((card) => {
          const Icon = card.icon;
          return (
            <div
              key={card.label}
              onClick={card.action}
              className={`p-5 rounded-2xl glass-panel glass-panel-hover cursor-pointer flex items-center justify-between group`}
            >
              <div>
                <span className="text-xs text-slate-400 font-medium block mb-1 tracking-wide">{card.label}</span>
                <span className="text-3xl font-extrabold font-mono text-white tracking-tight">{card.value}</span>
              </div>
              <div className={`p-3.5 rounded-xl ${card.bg} ${card.color} group-hover:scale-110 transition-transform shadow-inner`}>
                <Icon className="w-6 h-6" />
              </div>
            </div>
          );
        })}
      </div>

      {/* Phase 10 Clinical Intelligence Metrics Breakdown (A, B, C, D, E) */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Safety & Clinical Conflict Status */}
        <div className="p-5 rounded-2xl glass-panel space-y-3.5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-100 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-400" />
              Conflict Safety Breakdown
            </span>
            <button onClick={() => onNavigate('conflicts')} className="text-[11px] text-teal-400 hover:text-teal-300 font-medium hover:underline">
              Resolve →
            </button>
          </div>
          <div className="grid grid-cols-3 gap-2 text-center text-xs">
            <div className="p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/25">
              <span className="text-[9px] text-rose-300 block font-mono font-semibold">HIGH</span>
              <span className="text-lg font-bold text-rose-400 font-mono">{stats?.high_conflicts ?? 0}</span>
            </div>
            <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/25">
              <span className="text-[9px] text-amber-300 block font-mono font-semibold">MEDIUM</span>
              <span className="text-lg font-bold text-amber-400 font-mono">{stats?.medium_conflicts ?? 0}</span>
            </div>
            <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/25">
              <span className="text-[9px] text-emerald-300 block font-mono font-semibold">RESOLVED</span>
              <span className="text-lg font-bold text-emerald-400 font-mono">{stats?.resolved_conflicts ?? 0}</span>
            </div>
          </div>
          <p className="text-[11px] text-slate-400 font-mono">
            Patients with high conflicts: <strong className="text-rose-400">{stats?.patients_with_high_conflicts ?? 0}</strong>
          </p>
        </div>

        {/* Verification & Human-in-the-Loop Status */}
        <div className="p-5 rounded-2xl glass-panel space-y-3.5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-100 flex items-center gap-2">
              <CheckSquare className="w-4 h-4 text-teal-400" />
              Verification Queue Status
            </span>
            <button onClick={() => onNavigate('review')} className="text-[11px] text-teal-400 hover:text-teal-300 font-medium hover:underline">
              Queue →
            </button>
          </div>
          <div className="grid grid-cols-3 gap-2 text-center text-xs">
            <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/25">
              <span className="text-[9px] text-amber-300 block font-mono font-semibold">PENDING</span>
              <span className="text-lg font-bold text-amber-400 font-mono">{stats?.pending_reviews ?? 0}</span>
            </div>
            <div className="p-2.5 rounded-xl bg-teal-500/10 border border-teal-500/25">
              <span className="text-[9px] text-teal-300 block font-mono font-semibold">VERIFIED</span>
              <span className="text-lg font-bold text-teal-400 font-mono">{stats?.verified_reviews ?? 0}</span>
            </div>
            <div className="p-2.5 rounded-xl bg-violet-500/10 border border-violet-500/25">
              <span className="text-[9px] text-violet-300 block font-mono font-semibold">CORRECTED</span>
              <span className="text-lg font-bold text-violet-400 font-mono">{stats?.corrected_reviews ?? 0}</span>
            </div>
          </div>
          <p className="text-[11px] text-slate-400 font-mono">
            High priority items: <strong className="text-amber-400">{stats?.high_priority_reviews ?? 0}</strong>
          </p>
        </div>

        {/* Clinical Data Provenance Breakdown */}
        <div className="p-5 rounded-2xl glass-panel space-y-3.5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-100 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-sky-400" />
              Clinical Provenance
            </span>
            <span className="text-[10px] font-mono text-slate-400 bg-slate-800/80 px-2 py-0.5 rounded border border-slate-700">Strict Audit</span>
          </div>
          <div className="grid grid-cols-3 gap-2 text-center text-xs">
            <div className="p-2.5 rounded-xl bg-sky-500/10 border border-sky-500/25">
              <span className="text-[9px] text-sky-300 block font-mono font-semibold">AI EXTRACT</span>
              <span className="text-lg font-bold text-sky-400 font-mono">{stats?.ai_extracted_items ?? 0}</span>
            </div>
            <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/25">
              <span className="text-[9px] text-emerald-300 block font-mono font-semibold">VERIFIED</span>
              <span className="text-lg font-bold text-emerald-400 font-mono">{stats?.human_verified_items ?? 0}</span>
            </div>
            <div className="p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/25">
              <span className="text-[9px] text-rose-300 block font-mono font-semibold">REJECTED</span>
              <span className="text-lg font-bold text-rose-400 font-mono">{stats?.human_rejected_items ?? 0}</span>
            </div>
          </div>
          <p className="text-[11px] text-slate-400 font-mono">
            Total Clinical Items: <strong className="text-sky-300">{stats?.total_clinical_items ?? 0}</strong>
          </p>
        </div>
      </div>

      {/* Main Two-Column Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        
        {/* Left: Synthetic Demo Patient Quick Switcher */}
        <div className="lg:col-span-7 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-white tracking-wide flex items-center gap-2">
              <Users className="w-4 h-4 text-teal-400" />
              <span>Synthetic Demo Patients</span>
            </h2>
            <button
              onClick={() => onNavigate('patients')}
              className="text-xs text-teal-400 hover:text-teal-300 font-medium"
            >
              View All Patients →
            </button>
          </div>

          <div className="space-y-3">
            {patients.map((pat) => (
              <div
                key={pat.id}
                onClick={() => onSelectPatient(pat)}
                className="p-5 rounded-2xl glass-panel glass-panel-hover cursor-pointer flex items-center justify-between group"
              >
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2.5">
                    <span className="font-bold text-sm text-white group-hover:text-teal-300 transition-colors">
                      {pat.first_name} {pat.last_name}
                    </span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800/90 text-slate-300 border border-slate-700/80">
                      MRN: {pat.mrn}
                    </span>
                    {pat.is_synthetic_demo && (
                      <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-teal-500/15 text-teal-300 border border-teal-500/35 font-semibold">
                        SYNTHETIC
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-slate-400 font-sans">
                    Age {pat.age} • {pat.sex} • DoB: {pat.date_of_birth}
                  </div>
                  <div className="flex items-center gap-2 pt-0.5 text-[11px] text-slate-300">
                    <span className="text-slate-400">Allergies:</span>
                    {pat.allergies.length > 0 ? (
                      <span className="text-rose-400 font-medium">{pat.allergies.map(a => a.allergen).join(', ')}</span>
                    ) : (
                      <span className="text-slate-500">None Recorded</span>
                    )}
                  </div>
                </div>

                <div className="p-2.5 rounded-xl bg-slate-800/50 text-slate-400 group-hover:text-teal-300 group-hover:bg-teal-500/20 group-hover:translate-x-1 transition-all">
                  <ArrowRight className="w-4 h-4" />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Operational Activity Feed */}
        <div className="lg:col-span-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-white tracking-wide flex items-center gap-2">
              <Clock className="w-4 h-4 text-teal-400" />
              <span>Recent Audit Events</span>
            </h2>
            <button
              onClick={() => onNavigate('settings')}
              className="text-xs text-teal-400 hover:text-teal-300 font-medium"
            >
              Full Audit Log →
            </button>
          </div>

          <div className="p-5 rounded-2xl bg-[#0e1424] border border-slate-800 space-y-4">
            {stats?.recent_activity && stats.recent_activity.length > 0 ? (
              <div className="space-y-3">
                {stats.recent_activity.slice(0, 6).map((log) => (
                  <div key={log.id} className="text-xs pb-3 border-b border-slate-800/80 last:border-0 last:pb-0">
                    <div className="flex items-center justify-between text-slate-400 mb-1">
                      <span className="font-mono text-teal-400 font-semibold">{log.action}</span>
                      <span className="text-[10px] text-slate-500">
                        {new Date(log.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                    <div className="text-slate-300 font-mono text-[11px]">
                      Entity: {log.entity_type} ({log.entity_id.slice(0, 8)}...)
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-6 text-slate-500 text-xs">
                No recent activity recorded.
              </div>
            )}
          </div>
        </div>

      </div>

    </div>
  );
};
