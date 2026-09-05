import React from 'react';
import { LayoutDashboard, Users, FileText, CheckSquare, AlertTriangle, Clock, Settings, ShieldCheck, Activity } from 'lucide-react';

interface SidebarProps {
  currentTab: string;
  setCurrentTab: (tab: string) => void;
  pendingReviewCount?: number;
  conflictCount?: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  setCurrentTab,
  pendingReviewCount = 0,
  conflictCount = 0
}) => {
  const menuItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'patients', label: 'Patients', icon: Users },
    { id: 'reports', label: 'Reports', icon: FileText },
    { id: 'review', label: 'Review Queue', icon: CheckSquare, badge: pendingReviewCount },
    { id: 'conflicts', label: 'Conflicts', icon: AlertTriangle, badge: conflictCount, badgeVariant: 'rose' },
    { id: 'timeline', label: 'Timeline', icon: Clock },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  return (
    <aside className="w-64 bg-[#0c121e] border-r border-slate-800 flex flex-col justify-between flex-shrink-0 select-none">
      <div>
        {/* Brand Header */}
        <div className="h-16 flex items-center px-6 border-b border-slate-800 gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-teal-700 to-teal-500 flex items-center justify-center text-white font-black shadow-[0_0_15px_rgba(20,184,166,0.3)]">
            <Activity className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="font-bold text-base tracking-wide text-white flex items-center gap-1.5">
              <span>MEDLENS</span>
              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-teal-500/20 text-teal-300 border border-teal-500/30">v1.0</span>
            </div>
            <div className="text-[10px] text-slate-400 font-mono tracking-wider uppercase">
              Clinical Intelligence
            </div>
          </div>
        </div>

        {/* Navigation List */}
        <nav className="p-4 space-y-1.5">
          {menuItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setCurrentTab(item.id)}
                className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-teal-500/15 text-teal-300 border border-teal-500/30 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                }`}
              >
                <div className="flex items-center gap-3">
                  <Icon className={`w-4 h-4 ${isActive ? 'text-teal-400' : 'text-slate-400'}`} />
                  <span>{item.label}</span>
                </div>
                {item.badge !== undefined && item.badge > 0 && (
                  <span className={`px-2 py-0.5 rounded-full text-xs font-mono font-bold ${
                    item.badgeVariant === 'rose'
                      ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                      : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                  }`}>
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Safety Compliance Footer Badge */}
      <div className="p-4 m-3 rounded-xl bg-slate-900/90 border border-slate-800 text-[11px] text-slate-400 space-y-2">
        <div className="flex items-center gap-1.5 text-teal-400 font-semibold text-xs">
          <ShieldCheck className="w-4 h-4" />
          <span>Non-Diagnostic System</span>
        </div>
        <p className="text-[10px] text-slate-400 leading-tight">
          MedLens organizes and traces clinical evidence. Professional human review required for medical decisions.
        </p>
      </div>
    </aside>
  );
};
