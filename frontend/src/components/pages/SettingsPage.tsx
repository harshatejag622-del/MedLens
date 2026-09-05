import React from 'react';
import { Settings, ShieldCheck, Database, Cpu, Lock, FileText, CheckCircle2 } from 'lucide-react';
import { AuditLogEntry } from '../../types';

interface SettingsPageProps {
  auditLogs: AuditLogEntry[];
}

export const SettingsPage: React.FC<SettingsPageProps> = ({ auditLogs }) => {
  return (
    <div className="space-y-8 animate-fadeIn">
      
      <div>
        <h1 className="text-2xl font-bold text-white tracking-wide flex items-center gap-2.5">
          <Settings className="w-6 h-6 text-teal-400" />
          <span>System Architecture & Governance</span>
        </h1>
        <p className="text-xs sm:text-sm text-slate-400 mt-1">
          Active system configuration, modular AI provider status, and tamper-evident append-only audit trails.
        </p>
      </div>

      {/* Configuration Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        
        <div className="p-5 rounded-2xl bg-[#0e1424] border border-slate-800 space-y-3">
          <div className="flex items-center gap-2.5 text-teal-400 font-semibold text-xs uppercase tracking-wider">
            <Cpu className="w-4 h-4" />
            <span>AI Provider Architecture</span>
          </div>
          <div className="text-lg font-bold text-white font-mono">
            Deterministic Local NLP
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            Pluggable provider interface active. Running offline rule-based deterministic clinical extractor. Vertex AI / Gemini integration ready via configuration.
          </p>
          <div className="pt-2 text-[10px] font-mono text-slate-500">
            PROVIDER: BaseAIProvider (local)
          </div>
        </div>

        <div className="p-5 rounded-2xl bg-[#0e1424] border border-slate-800 space-y-3">
          <div className="flex items-center gap-2.5 text-sky-400 font-semibold text-xs uppercase tracking-wider">
            <Database className="w-4 h-4" />
            <span>Database Storage</span>
          </div>
          <div className="text-lg font-bold text-white font-mono">
            SQLite (Cloud SQL Ready)
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            Normalized relational schema with foreign key constraints, indexes, and transactional integrity across patients, documents, and lab records.
          </p>
          <div className="pt-2 text-[10px] font-mono text-slate-500">
            CONNECTION: sqlite:///./medlens.db
          </div>
        </div>

        <div className="p-5 rounded-2xl bg-[#0e1424] border border-slate-800 space-y-3">
          <div className="flex items-center gap-2.5 text-emerald-400 font-semibold text-xs uppercase tracking-wider">
            <ShieldCheck className="w-4 h-4" />
            <span>Compliance & Privacy</span>
          </div>
          <div className="text-lg font-bold text-white font-mono">
            Synthetic Demo Mode
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            Designed with healthcare security and privacy considerations. Zero real PHI in demo records. Strict source provenance preservation enforced.
          </p>
          <div className="pt-2 text-[10px] font-mono text-slate-500">
            STATUS: DEMO_MODE=TRUE
          </div>
        </div>

      </div>

      {/* Append-Only Audit Log Viewer */}
      <div className="rounded-2xl border border-slate-800 bg-[#0e1424] p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div>
            <h3 className="text-base font-bold text-white tracking-wide">
              Append-Only Audit Log
            </h3>
            <span className="text-xs text-slate-400">
              Immutable provenance tracking of all clinician interactions, document extractions, and verification events.
            </span>
          </div>
          <span className="text-xs font-mono text-teal-400 bg-teal-500/10 px-3 py-1 rounded-full border border-teal-500/20">
            {auditLogs.length} Events Logged
          </span>
        </div>

        <div className="overflow-x-auto max-h-96 overflow-y-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-slate-900/90 text-slate-400 text-[10px] uppercase sticky top-0">
              <tr>
                <th className="py-2.5 px-4">Timestamp (UTC)</th>
                <th className="py-2.5 px-4">Action</th>
                <th className="py-2.5 px-4">Entity</th>
                <th className="py-2.5 px-4">Entity ID</th>
                <th className="py-2.5 px-4">User</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300">
              {auditLogs.map((log) => (
                <tr key={log.id} className="hover:bg-slate-800/30">
                  <td className="py-2.5 px-4 text-slate-400">{log.timestamp}</td>
                  <td className="py-2.5 px-4 text-teal-400 font-bold">{log.action}</td>
                  <td className="py-2.5 px-4 text-slate-300">{log.entity_type}</td>
                  <td className="py-2.5 px-4 text-slate-400 truncate max-w-[140px]" title={log.entity_id}>
                    {log.entity_id}
                  </td>
                  <td className="py-2.5 px-4 text-slate-300">{log.user_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  );
};
