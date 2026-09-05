import React from 'react';
import {
  ShieldCheck,
  UserCheck,
  Cpu,
  FileText,
  Calculator,
  AlertTriangle,
  Info,
  AlertCircle,
  ArrowDown,
  ArrowUp,
  CheckCircle,
  HelpCircle
} from 'lucide-react';

export const ProvenanceBadge: React.FC<{ provenance: string }> = ({ provenance }) => {
  const norm = provenance.toUpperCase();
  
  if (norm.includes('USER')) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold uppercase tracking-wider bg-amber-500/10 text-amber-300 border border-amber-500/30">
        <UserCheck className="w-3 h-3" />
        <span>USER PROVIDED</span>
      </span>
    );
  }
  if (norm.includes('CORRECTED')) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold uppercase tracking-wider bg-violet-500/15 text-violet-300 border border-violet-500/40">
        <UserCheck className="w-3 h-3 text-violet-400" />
        <span>HUMAN CORRECTED</span>
      </span>
    );
  }
  if (norm.includes('REJECTED')) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold uppercase tracking-wider bg-rose-500/15 text-rose-300 border border-rose-500/40">
        <AlertCircle className="w-3 h-3 text-rose-400" />
        <span>HUMAN REJECTED</span>
      </span>
    );
  }
  if (norm.includes('VERIFIED') || norm.includes('HUMAN')) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold uppercase tracking-wider bg-teal-500/10 text-teal-300 border border-teal-500/30">
        <ShieldCheck className="w-3 h-3 text-teal-400" />
        <span>HUMAN VERIFIED</span>
      </span>
    );
  }
  if (norm.includes('AI') || norm.includes('GENERATED') || norm.includes('EXTRACTED')) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold uppercase tracking-wider bg-indigo-500/15 text-indigo-300 border border-indigo-500/30">
        <Cpu className="w-3 h-3 text-indigo-400" />
        <span>AI EXTRACTED</span>
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold uppercase tracking-wider bg-slate-800 text-slate-300 border border-slate-700">
      <Calculator className="w-3 h-3" />
      <span>SYSTEM CALCULATED</span>
    </span>
  );
};

export const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const norm = status.toUpperCase();

  switch (norm) {
    case 'LOW':
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase bg-sky-500/15 text-sky-300 border border-sky-500/30">
          <ArrowDown className="w-3 h-3" />
          <span>LOW</span>
        </span>
      );
    case 'NORMAL':
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
          <CheckCircle className="w-3 h-3" />
          <span>NORMAL</span>
        </span>
      );
    case 'HIGH':
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase bg-rose-500/15 text-rose-300 border border-rose-500/30">
          <ArrowUp className="w-3 h-3" />
          <span>HIGH</span>
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase bg-slate-800 text-slate-300 border border-slate-700" title="Reference range not provided or not assessable in source report">
          <HelpCircle className="w-3 h-3" />
          <span>UNKNOWN</span>
        </span>
      );
  }
};

export const SeverityBadge: React.FC<{ severity: string }> = ({ severity }) => {
  const norm = severity.toUpperCase();

  switch (norm) {
    case 'HIGH':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase bg-rose-950/80 text-rose-300 border border-rose-500/40">
          <AlertCircle className="w-3 h-3 text-rose-400" />
          <span>HIGH SEVERITY</span>
        </span>
      );
    case 'MEDIUM':
    case 'WARNING':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase bg-amber-950/80 text-amber-300 border border-amber-500/40">
          <AlertTriangle className="w-3 h-3 text-amber-400" />
          <span>MEDIUM SEVERITY</span>
        </span>
      );
    case 'LOW':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase bg-blue-950/80 text-blue-300 border border-blue-500/40">
          <Info className="w-3 h-3 text-blue-400" />
          <span>LOW SEVERITY</span>
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase bg-slate-900 text-slate-300 border border-slate-700">
          <Info className="w-3 h-3 text-slate-400" />
          <span>INFO</span>
        </span>
      );
  }
};

export const LabStatusBadge = StatusBadge;
export const ConflictSeverityBadge = SeverityBadge;
