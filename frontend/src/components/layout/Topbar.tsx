import React, { useState, useEffect, useRef } from 'react';
import { Search, Bell, Shield, User, Lock, Activity, FileText, AlertTriangle, Pill, Stethoscope, ChevronRight, X } from 'lucide-react';
import { api } from '../../services/api';
import { GlobalSearchResultItem } from '../../types';

interface TopbarProps {
  searchQuery: string;
  setSearchQuery: (q: string) => void;
  onSelectSearchResult?: (item: GlobalSearchResultItem) => void;
}

export const Topbar: React.FC<TopbarProps> = ({ searchQuery, setSearchQuery, onSelectSearchResult }) => {
  const [results, setResults] = useState<GlobalSearchResultItem[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!searchQuery.trim()) {
      setResults([]);
      setIsOpen(false);
      return;
    }

    const timer = setTimeout(async () => {
      try {
        setIsSearching(true);
        const data = await api.globalSearch(searchQuery.trim());
        setResults(data.results || []);
        setIsOpen(true);
      } catch (err) {
        console.error("Global search error:", err);
      } finally {
        setIsSearching(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'PATIENT': return <User className="w-3.5 h-3.5 text-sky-400" />;
      case 'DOCUMENT': return <FileText className="w-3.5 h-3.5 text-teal-400" />;
      case 'DIAGNOSIS': return <Activity className="w-3.5 h-3.5 text-emerald-400" />;
      case 'MEDICATION': return <Pill className="w-3.5 h-3.5 text-purple-400" />;
      case 'LABORATORY': return <Stethoscope className="w-3.5 h-3.5 text-amber-400" />;
      case 'CONFLICT': return <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />;
      default: return <Search className="w-3.5 h-3.5 text-slate-400" />;
    }
  };

  return (
    <header className="h-16 bg-[#0c121e]/90 backdrop-blur-md border-b border-slate-800 px-6 flex items-center justify-between sticky top-0 z-40">
      
      {/* Global Search Input with Popover */}
      <div className="relative w-full max-w-lg" ref={dropdownRef}>
        <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onFocus={() => { if (results.length > 0) setIsOpen(true); }}
          placeholder="Global Search (Patient Name, MRN, Test, Med, Diagnosis, Conflict)..."
          className="w-full pl-10 pr-9 py-2 bg-slate-900/90 border border-slate-700/80 rounded-xl text-xs text-slate-200 placeholder-slate-400 focus:outline-none focus:border-teal-500 transition-colors shadow-inner"
        />
        {searchQuery && (
          <button
            onClick={() => { setSearchQuery(''); setIsOpen(false); }}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}

        {/* Global Search Results Dropdown */}
        {isOpen && (
          <div className="absolute top-full left-0 right-0 mt-2 bg-[#0d1424] border border-slate-700/80 rounded-xl shadow-2xl overflow-hidden z-50 max-h-96 overflow-y-auto">
            <div className="p-2.5 bg-slate-900/60 border-b border-slate-800 flex items-center justify-between text-[11px] text-slate-400">
              <span className="font-semibold uppercase tracking-wider text-slate-300">
                {isSearching ? 'Searching...' : `Found ${results.length} Matches`}
              </span>
              <span className="font-mono text-[10px] text-teal-400">Phase 10 Global Index</span>
            </div>

            {results.length === 0 && !isSearching ? (
              <div className="p-5 text-center text-xs text-slate-400 font-sans">
                No matching patients, documents, diagnoses, or lab results found.
              </div>
            ) : (
              <div className="divide-y divide-slate-800/60">
                {results.map((item, idx) => (
                  <div
                    key={idx}
                    onClick={() => {
                      setIsOpen(false);
                      if (onSelectSearchResult) onSelectSearchResult(item);
                    }}
                    className="p-3 hover:bg-slate-800/60 transition-colors cursor-pointer flex items-center justify-between group"
                  >
                    <div className="flex items-start gap-3 min-w-0">
                      <div className="p-1.5 rounded-lg bg-slate-800 border border-slate-700/50 mt-0.5">
                        {getCategoryIcon(item.category)}
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-semibold text-slate-100 truncate group-hover:text-teal-300 transition-colors">
                            {item.title}
                          </span>
                          <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700/60 uppercase">
                            {item.category}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-400 truncate mt-0.5">
                          {item.subtitle}
                        </p>
                      </div>
                    </div>
                    <ChevronRight className="w-4 h-4 text-slate-500 group-hover:text-teal-400 group-hover:translate-x-0.5 transition-all flex-shrink-0 ml-2" />
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-4">
        
        {/* Security / Privacy Indicator */}
        <div className="hidden sm:flex items-center gap-2 px-3 py-1 rounded-full bg-slate-900 border border-slate-700 text-[11px] font-mono text-slate-300">
          <Lock className="w-3 h-3 text-teal-400" />
          <span>Demo Mode • Synthetic Data</span>
        </div>

        {/* Notifications */}
        <button
          className="relative p-2 text-slate-400 hover:text-slate-200 rounded-lg hover:bg-slate-800 transition-colors"
          title="Notifications"
          aria-label="Notifications"
        >
          <Bell className="w-4 h-4" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-teal-400 animate-pulse"></span>
        </button>

        {/* Current Clinician User Profile */}
        <div className="flex items-center gap-2.5 pl-3 border-l border-slate-800">
          <div className="w-8 h-8 rounded-full bg-teal-900/60 border border-teal-500/40 flex items-center justify-center text-teal-300 font-bold text-xs">
            SL
          </div>
          <div className="hidden md:flex flex-col text-left">
            <span className="text-xs font-semibold text-white">Dr. Sarah Lin</span>
            <span className="text-[10px] text-slate-400 font-mono">Attending Physician</span>
          </div>
        </div>

      </div>

    </header>
  );
};

