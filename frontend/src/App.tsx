import React, { useState, useEffect } from 'react';
import { Sidebar } from './components/layout/Sidebar';
import { Topbar } from './components/layout/Topbar';
import { DashboardPage } from './components/pages/DashboardPage';
import { PatientsPage } from './components/pages/PatientsPage';
import { PatientOverviewPage } from './components/pages/PatientOverviewPage';
import { ReportsPage } from './components/pages/ReportsPage';
import { ReviewQueuePage } from './components/pages/ReviewQueuePage';
import { ConflictsPage } from './components/pages/ConflictsPage';
import { TimelinePage } from './components/pages/TimelinePage';
import { SettingsPage } from './components/pages/SettingsPage';
import { api } from './services/api';
import { Patient, DocumentItem, ConflictItem, ReviewItem, OperationalStats, AuditLogEntry } from './types';
import { ShieldAlert, Info } from 'lucide-react';

export function App() {
  const [currentTab, setCurrentTab] = useState('dashboard');
  const [searchQuery, setSearchQuery] = useState('');
  const [stats, setStats] = useState<OperationalStats | null>(null);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [selectedPatient, setSelectedPatient] = useState<Patient | null>(null);
  const [overviewPatientId, setOverviewPatientId] = useState<string | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [conflicts, setConflicts] = useState<ConflictItem[]>([]);
  const [reviewItems, setReviewItems] = useState<ReviewItem[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    try {
      setLoading(true);
      const [statsData, patientsData, docsData, conflictsData, reviewData, auditData] = await Promise.all([
        api.getStats().catch(() => null),
        api.getPatients({ include_archived: true }).catch(() => []),
        api.getDocuments().catch(() => []),
        api.getConflicts().catch(() => []),
        api.getReviewQueue().catch(() => []),
        api.getAuditLogs().catch(() => [])
      ]);

      setStats(statsData);
      setPatients(patientsData);
      if (patientsData.length > 0 && !selectedPatient) {
        setSelectedPatient(patientsData[0]); // Default to Alex Morgan
      }
      setDocuments(docsData);
      setConflicts(conflictsData);
      setReviewItems(reviewData);
      setAuditLogs(auditData);
    } catch (e) {
      console.error("Error loading MedLens data:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCreatePatient = async (payload: any) => {
    const created = await api.createPatient(payload);
    await loadData();
    setSelectedPatient(created);
    setOverviewPatientId(created.id);
    setCurrentTab('patient-overview');
  };

  const handleResolveConflict = async (id: string, notes: string, newStatus: string = 'RESOLVED') => {
    await api.resolveConflict(id, notes, newStatus);
    await loadData();
  };

  const handleReviewAction = async (id: string, action: string, correctedValue?: string, reason?: string) => {
    await api.takeReviewAction(id, action, correctedValue, reason);
    await loadData();
  };

  const pendingReviewCount = reviewItems.filter(r => r.status === 'PENDING').length;
  const unresolvedConflictCount = conflicts.filter(c => c.status === 'UNRESOLVED' || c.status === 'OPEN').length;

  return (
    <div className="flex h-screen bg-[#090d16] text-slate-100 font-sans overflow-hidden">
      
      {/* Sidebar Navigation */}
      <Sidebar
        currentTab={currentTab}
        setCurrentTab={setCurrentTab}
        pendingReviewCount={pendingReviewCount}
        conflictCount={unresolvedConflictCount}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        
        {/* Topbar */}
        <Topbar
          searchQuery={searchQuery}
          setSearchQuery={setSearchQuery}
          onSelectSearchResult={(item) => {
            if (item.patient_id) {
              const matched = patients.find(p => p.id === item.patient_id);
              if (matched) setSelectedPatient(matched);
              setOverviewPatientId(item.patient_id);
            }
            setCurrentTab(item.link_tab || 'patient-overview');
          }}
        />

        {/* Dynamic Page Router Body */}
        <main className="flex-1 overflow-y-auto p-6 md:p-8">
          <div className="max-w-7xl mx-auto space-y-6">
            
            {currentTab === 'dashboard' && (
              <DashboardPage
                stats={stats}
                patients={patients}
                onSelectPatient={(p) => {
                  setSelectedPatient(p);
                  setOverviewPatientId(p.id);
                  setCurrentTab('patient-overview');
                }}
                onNavigate={setCurrentTab}
              />
            )}

            {currentTab === 'patients' && (
              <PatientsPage
                patients={patients}
                onSelectPatient={(p) => {
                  setSelectedPatient(p);
                  setOverviewPatientId(p.id);
                  setCurrentTab('patient-overview');
                }}
                onCreatePatient={handleCreatePatient}
                onRefreshData={loadData}
              />
            )}

            {currentTab === 'patient-overview' && overviewPatientId && (
              <PatientOverviewPage
                patientId={overviewPatientId}
                onBack={() => setCurrentTab('patients')}
                onPatientDeleted={async () => {
                  await loadData();
                  setCurrentTab('patients');
                }}
              />
            )}

            {currentTab === 'reports' && (
              <ReportsPage
                documents={documents}
                patients={patients}
                onRefresh={loadData}
              />
            )}

            {currentTab === 'review' && (
              <ReviewQueuePage
                items={reviewItems}
                onAction={handleReviewAction}
              />
            )}

            {currentTab === 'conflicts' && (
              <ConflictsPage
                conflicts={conflicts}
                onResolveConflict={handleResolveConflict}
              />
            )}

            {currentTab === 'timeline' && (
              <TimelinePage
                patient={selectedPatient}
                patients={patients}
                onSelectPatient={(p) => setSelectedPatient(p)}
                documents={documents}
                conflicts={conflicts}
              />
            )}

            {currentTab === 'settings' && (
              <SettingsPage auditLogs={auditLogs} />
            )}

          </div>
        </main>

        {/* Persistent Non-Diagnostic Clinical Disclaimer */}
        <footer className="bg-[#0c121e] border-t border-slate-800 px-6 py-2.5 flex items-center justify-between text-[11px] text-slate-400">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />
            <span>
              <strong>Clinical Notice:</strong> MedLens is an information organization and understanding tool. It does not provide medical diagnosis or treatment recommendations.
            </span>
          </div>
          <span className="hidden sm:inline text-slate-500 font-mono">
            Always consult a licensed medical professional for clinical decisions.
          </span>
        </footer>

      </div>

    </div>
  );
}

export default App;
