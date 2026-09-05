import React, { useState } from 'react';
import {
  Users,
  UserPlus,
  Search,
  X,
  Plus,
  Trash2,
  Edit,
  Archive,
  ArchiveRestore,
  ExternalLink,
  Filter,
  AlertCircle,
  Calendar,
  Phone,
  Mail,
  Shield,
  FileText
} from 'lucide-react';
import { Patient, Condition, Allergy, Medication, Symptom } from '../../types';
import { ProvenanceBadge } from '../common/Badges';
import { EditPatientModal } from '../patients/EditPatientModal';
import { api } from '../../services/api';

interface PatientsPageProps {
  patients: Patient[];
  onSelectPatient: (patient: Patient) => void;
  onCreatePatient: (payload: any) => Promise<void>;
  onRefreshData?: () => Promise<void>;
}

export const PatientsPage: React.FC<PatientsPageProps> = ({
  patients,
  onSelectPatient,
  onCreatePatient,
  onRefreshData
}) => {
  // Modal states
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingPatient, setEditingPatient] = useState<Patient | null>(null);
  const [patientToDelete, setPatientToDelete] = useState<Patient | null>(null);
  const [deleting, setDeleting] = useState(false);

  // Search and filter states
  const [searchTerm, setSearchTerm] = useState('');
  const [sexFilter, setSexFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL'); // ALL, ACTIVE, ARCHIVED

  // Intake Form State
  const [formMrn, setFormMrn] = useState(`SYN-${Math.floor(1000 + Math.random() * 9000)}`);
  const [formFirstName, setFormFirstName] = useState('');
  const [formLastName, setFormLastName] = useState('');
  const [formDob, setFormDob] = useState('1985-06-15');
  const [formAge, setFormAge] = useState(41);
  const [formSex, setFormSex] = useState('FEMALE');
  const [formPhone, setFormPhone] = useState('555-0199');
  const [formEmail, setFormEmail] = useState('');
  const [formRelevantHistory, setFormRelevantHistory] = useState('No prior hospitalizations or major surgical interventions.');
  const [formNotes, setFormNotes] = useState('Routine clinical evaluation intake.');

  // Form lists
  const [formConditions, setFormConditions] = useState<{ name: string; status: string }[]>([]);
  const [formAllergies, setFormAllergies] = useState<{ allergen: string; reaction: string; severity: string }[]>([]);
  const [formMedications, setFormMedications] = useState<{ name: string; dose: string; freq: string }[]>([]);
  const [formSymptoms, setFormSymptoms] = useState<{ symptom: string; duration: string }[]>([]);

  // Item inputs
  const [tempCond, setTempCond] = useState('');
  const [tempAllergen, setTempAllergen] = useState('');
  const [tempReaction, setTempReaction] = useState('');
  const [tempSeverity, setTempSeverity] = useState('MODERATE');
  const [tempMed, setTempMed] = useState('');
  const [tempDose, setTempDose] = useState('');
  const [tempFreq, setTempFreq] = useState('');
  const [tempSymptom, setTempSymptom] = useState('');
  const [tempDuration, setTempDuration] = useState('');

  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Auto calculate age from DoB
  const handleDobChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setFormDob(val);
    const birthDate = new Date(val);
    if (!isNaN(birthDate.getTime())) {
      const today = new Date();
      let calculatedAge = today.getFullYear() - birthDate.getFullYear();
      const m = today.getMonth() - birthDate.getMonth();
      if (m < 0 || (m === 0 && today.getDate() < birthDate.getDate())) {
        calculatedAge--;
      }
      if (calculatedAge >= 0 && calculatedAge <= 130) {
        setFormAge(calculatedAge);
      }
    }
  };

  const handleAddCondition = () => {
    if (!tempCond.trim()) return;
    setFormConditions([...formConditions, { name: tempCond.trim(), status: 'ACTIVE' }]);
    setTempCond('');
  };

  const handleAddAllergy = () => {
    if (!tempAllergen.trim()) return;
    setFormAllergies([
      ...formAllergies,
      {
        allergen: tempAllergen.trim(),
        reaction: tempReaction.trim() || 'Unspecified reaction',
        severity: tempSeverity
      }
    ]);
    setTempAllergen('');
    setTempReaction('');
  };

  const handleAddMedication = () => {
    if (!tempMed.trim()) return;
    setFormMedications([
      ...formMedications,
      {
        name: tempMed.trim(),
        dose: tempDose.trim() || 'Unspecified dose',
        freq: tempFreq.trim() || 'Daily'
      }
    ]);
    setTempMed('');
    setTempDose('');
    setTempFreq('');
  };

  const handleAddSymptom = () => {
    if (!tempSymptom.trim()) return;
    setFormSymptoms([
      ...formSymptoms,
      {
        symptom: tempSymptom.trim(),
        duration: tempDuration.trim() || 'Recent'
      }
    ]);
    setTempSymptom('');
    setTempDuration('');
  };

  const resetForm = () => {
    setFormMrn(`SYN-${Math.floor(1000 + Math.random() * 9000)}`);
    setFormFirstName('');
    setFormLastName('');
    setFormDob('1985-06-15');
    setFormAge(41);
    setFormSex('FEMALE');
    setFormPhone('555-0199');
    setFormEmail('');
    setFormRelevantHistory('No prior hospitalizations or major surgical interventions.');
    setFormNotes('Routine clinical evaluation intake.');
    setFormConditions([]);
    setFormAllergies([]);
    setFormMedications([]);
    setFormSymptoms([]);
    setFormError(null);
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!formFirstName.trim() || !formLastName.trim()) {
      setFormError('Patient first name and last name are required.');
      return;
    }

    if (!formMrn.trim()) {
      setFormError('Medical Record Number (MRN) is required.');
      return;
    }

    if (!/^\d{4}-\d{2}-\d{2}$/.test(formDob)) {
      setFormError('Date of birth must follow YYYY-MM-DD format.');
      return;
    }

    const birthDate = new Date(formDob);
    if (birthDate > new Date()) {
      setFormError('Date of birth cannot be in the future.');
      return;
    }

    try {
      setSubmitting(true);
      const payload = {
        mrn: formMrn.trim().toUpperCase(),
        first_name: formFirstName.trim(),
        last_name: formLastName.trim(),
        date_of_birth: formDob,
        age: Number(formAge),
        sex: formSex,
        contact_phone: formPhone.trim() || null,
        contact_email: formEmail.trim() || null,
        relevant_history: formRelevantHistory.trim() || null,
        notes: formNotes.trim() || null,
        is_synthetic_demo: true,
        is_archived: false,
        conditions: formConditions.map((c) => ({
          condition_name: c.name,
          status: c.status,
          provenance: 'USER_PROVIDED'
        })),
        allergies: formAllergies.map((a) => ({
          allergen: a.allergen,
          reaction: a.reaction,
          severity: a.severity,
          provenance: 'USER_PROVIDED'
        })),
        medications: formMedications.map((m) => ({
          medication_name: m.name,
          dosage: m.dose,
          frequency: m.freq,
          route: 'ORAL',
          provenance: 'USER_PROVIDED'
        })),
        symptoms: formSymptoms.map((s) => ({
          symptom: s.symptom,
          duration: s.duration,
          severity: 'MODERATE',
          provenance: 'USER_PROVIDED'
        }))
      };

      await onCreatePatient(payload);
      setShowCreateModal(false);
      resetForm();
    } catch (err: any) {
      setFormError(err.message || 'Error creating patient intake record.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleArchiveToggle = async (patient: Patient, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      if (patient.is_archived) {
        await api.unarchivePatient(patient.id);
      } else {
        await api.archivePatient(patient.id);
      }
      if (onRefreshData) await onRefreshData();
    } catch (err: any) {
      alert(err.message || 'Error modifying archive state');
    }
  };

  const confirmDeletePatient = async () => {
    if (!patientToDelete) return;
    try {
      setDeleting(true);
      await api.deletePatient(patientToDelete.id);
      setPatientToDelete(null);
      if (onRefreshData) await onRefreshData();
    } catch (err: any) {
      alert(err.message || 'Error deleting patient');
    } finally {
      setDeleting(false);
    }
  };

  const handleSaveEdit = async (updatedData: any) => {
    if (!editingPatient) return;
    await api.updatePatient(editingPatient.id, updatedData);
    setEditingPatient(null);
    if (onRefreshData) await onRefreshData();
  };

  // Client filtering
  const filteredPatients = patients.filter((p) => {
    const term = searchTerm.toLowerCase().trim();
    const matchesSearch =
      !term ||
      `${p.first_name} ${p.last_name}`.toLowerCase().includes(term) ||
      p.mrn.toLowerCase().includes(term) ||
      (p.notes && p.notes.toLowerCase().includes(term)) ||
      (p.relevant_history && p.relevant_history.toLowerCase().includes(term)) ||
      p.conditions?.some((c) => c.condition_name.toLowerCase().includes(term)) ||
      p.allergies?.some((a) => a.allergen.toLowerCase().includes(term));

    const matchesSex = sexFilter === 'ALL' || p.sex === sexFilter;

    const matchesStatus =
      statusFilter === 'ALL' ||
      (statusFilter === 'ARCHIVED' && p.is_archived) ||
      (statusFilter === 'ACTIVE' && !p.is_archived);

    return matchesSearch && matchesSex && matchesStatus;
  });

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Top Action Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-wide flex items-center gap-2.5">
            <Users className="w-6 h-6 text-teal-400" />
            <span>Patient Management</span>
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Master patient directory, clinical profile intake, and traceable provenance records.
          </p>
        </div>

        <button
          onClick={() => {
            resetForm();
            setShowCreateModal(true);
          }}
          className="px-4 py-2.5 rounded-xl bg-teal-600 hover:bg-teal-500 text-white text-xs font-semibold tracking-wider flex items-center gap-2 shadow-[0_0_15px_rgba(20,184,166,0.3)] transition-all self-start sm:self-auto"
        >
          <UserPlus className="w-4 h-4" />
          <span>New Patient Intake</span>
        </button>
      </div>

      {/* Filter & Search Toolbar */}
      <div className="bg-[#0e1424] border border-slate-800 rounded-2xl p-4 shadow-lg flex flex-col md:flex-row items-center justify-between gap-4">
        {/* Search input */}
        <div className="relative w-full md:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search by name, MRN, condition, or notes..."
            className="w-full pl-10 pr-4 py-2 bg-slate-900 border border-slate-700/80 rounded-xl text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-teal-500 transition-colors"
          />
          {searchTerm && (
            <button
              onClick={() => setSearchTerm('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* Filter controls */}
        <div className="flex items-center gap-3 w-full md:w-auto flex-wrap sm:flex-nowrap">
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <Filter className="w-3.5 h-3.5 text-teal-400" />
            <span>Sex:</span>
            <select
              value={sexFilter}
              onChange={(e) => setSexFilter(e.target.value)}
              className="px-2.5 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500"
            >
              <option value="ALL">All</option>
              <option value="FEMALE">Female</option>
              <option value="MALE">Male</option>
              <option value="OTHER">Other</option>
            </select>
          </div>

          <div className="flex items-center gap-2 text-xs text-slate-400">
            <span>Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-2.5 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500"
            >
              <option value="ALL">All Statuses</option>
              <option value="ACTIVE">Active Records</option>
              <option value="ARCHIVED">Archived Only</option>
            </select>
          </div>

          <span className="text-xs text-slate-500 font-mono hidden lg:inline">
            Showing {filteredPatients.length} of {patients.length} patients
          </span>
        </div>
      </div>

      {/* Patients Table */}
      <div className="bg-[#0e1424] border border-slate-800 rounded-2xl shadow-xl overflow-hidden">
        {filteredPatients.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-800 bg-[#090d16]/70 text-slate-400 font-mono text-[11px]">
                  <th className="py-3 px-4 font-medium">Patient / MRN</th>
                  <th className="py-3 px-4 font-medium">Demographics</th>
                  <th className="py-3 px-4 font-medium">Conditions & Allergies</th>
                  <th className="py-3 px-4 font-medium">Relevant History</th>
                  <th className="py-3 px-4 font-medium">Record Status</th>
                  <th className="py-3 px-4 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {filteredPatients.map((patient) => (
                  <tr
                    key={patient.id}
                    onClick={() => onSelectPatient(patient)}
                    className="hover:bg-slate-900/60 cursor-pointer transition-colors group"
                  >
                    {/* Patient Name & MRN */}
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-xl bg-teal-500/10 border border-teal-500/25 flex items-center justify-center text-teal-400 font-bold text-xs flex-shrink-0">
                          {patient.first_name[0]}{patient.last_name[0]}
                        </div>
                        <div>
                          <span className="font-semibold text-white group-hover:text-teal-300 transition-colors block">
                            {patient.first_name} {patient.last_name}
                          </span>
                          <span className="font-mono text-[11px] text-teal-400/90 block">
                            {patient.mrn}
                          </span>
                        </div>
                      </div>
                    </td>

                    {/* Demographics */}
                    <td className="py-3 px-4 text-slate-300">
                      <span>{patient.age} y/o {patient.sex}</span>
                      <span className="block text-[11px] text-slate-500 font-mono">
                        DoB: {patient.date_of_birth}
                      </span>
                    </td>

                    {/* Conditions & Allergies */}
                    <td className="py-3 px-4">
                      <div className="space-y-1 max-w-xs">
                        {patient.conditions && patient.conditions.length > 0 ? (
                          <div className="flex flex-wrap gap-1">
                            {patient.conditions.slice(0, 2).map((c, i) => (
                              <span
                                key={i}
                                className="px-2 py-0.5 rounded bg-blue-500/10 border border-blue-500/20 text-blue-300 text-[10px]"
                              >
                                {c.condition_name}
                              </span>
                            ))}
                            {patient.conditions.length > 2 && (
                              <span className="text-[10px] text-slate-500">
                                +{patient.conditions.length - 2} more
                              </span>
                            )}
                          </div>
                        ) : (
                          <span className="text-slate-500 text-[11px] italic">No conditions</span>
                        )}

                        {patient.allergies && patient.allergies.length > 0 && (
                          <div className="flex flex-wrap gap-1 pt-0.5">
                            {patient.allergies.slice(0, 2).map((a, i) => (
                              <span
                                key={i}
                                className="px-2 py-0.5 rounded bg-rose-500/10 border border-rose-500/20 text-rose-300 text-[10px]"
                              >
                                {a.allergen}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </td>

                    {/* Relevant History */}
                    <td className="py-3 px-4 text-slate-300 max-w-xs">
                      <p className="line-clamp-2 text-[11px] text-slate-400">
                        {patient.relevant_history || patient.notes || 'Intake registered.'}
                      </p>
                    </td>

                    {/* Status badges */}
                    <td className="py-3 px-4">
                      <div className="flex flex-col gap-1 items-start">
                        {patient.is_archived ? (
                          <span className="px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/30 text-[10px] font-semibold">
                            ARCHIVED
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 text-[10px] font-medium">
                            ACTIVE
                          </span>
                        )}
                        {patient.is_synthetic_demo && (
                          <span className="text-[9px] font-mono text-slate-500">
                            DEMO PHI
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Row Actions */}
                    <td className="py-3 px-4 text-right" onClick={(e) => e.stopPropagation()}>
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => onSelectPatient(patient)}
                          className="px-2.5 py-1 rounded-lg bg-teal-600/20 hover:bg-teal-600/30 border border-teal-500/30 text-teal-300 hover:text-white transition-colors text-[11px] flex items-center gap-1"
                          title="Open Clinical Overview"
                        >
                          <ExternalLink className="w-3 h-3" />
                          <span>View</span>
                        </button>

                        <button
                          onClick={() => setEditingPatient(patient)}
                          className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
                          title="Edit Patient"
                        >
                          <Edit className="w-3.5 h-3.5" />
                        </button>

                        <button
                          onClick={(e) => handleArchiveToggle(patient, e)}
                          className={`p-1.5 rounded-lg transition-colors ${
                            patient.is_archived
                              ? 'bg-amber-500/10 hover:bg-amber-500/20 text-amber-300'
                              : 'bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-amber-400'
                          }`}
                          title={patient.is_archived ? 'Restore Patient' : 'Archive Patient'}
                        >
                          {patient.is_archived ? (
                            <ArchiveRestore className="w-3.5 h-3.5" />
                          ) : (
                            <Archive className="w-3.5 h-3.5" />
                          )}
                        </button>

                        <button
                          onClick={() => setPatientToDelete(patient)}
                          className="p-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 hover:text-rose-300 transition-colors"
                          title="Delete Patient"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-12 text-center space-y-3">
            <Users className="w-10 h-10 text-slate-600 mx-auto" />
            <h3 className="text-sm font-semibold text-slate-300">No Patient Records Found</h3>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              {searchTerm || sexFilter !== 'ALL' || statusFilter !== 'ALL'
                ? 'No patients match your current search or filter criteria. Try resetting filters.'
                : 'No patients registered in the system yet. Click New Patient Intake to create one.'}
            </p>
            {(searchTerm || sexFilter !== 'ALL' || statusFilter !== 'ALL') && (
              <button
                onClick={() => {
                  setSearchTerm('');
                  setSexFilter('ALL');
                  setStatusFilter('ALL');
                }}
                className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-teal-400 text-xs font-medium"
              >
                Clear All Filters
              </button>
            )}
          </div>
        )}
      </div>

      {/* ========================================================= */}
      {/* Create New Patient Intake Modal */}
      {/* ========================================================= */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 overflow-y-auto">
          <div className="bg-[#0e1424] border border-slate-700/80 rounded-2xl w-full max-w-3xl shadow-2xl overflow-hidden my-8 animate-fadeIn">
            
            {/* Modal Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-[#090d16]/70">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-lg font-bold text-white">New Patient Intake Registration</h2>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-teal-500/10 text-teal-300 border border-teal-500/20 font-semibold">
                    SYNTHETIC DEMO
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  Complete demographic intake and baseline medical profile. All clinical fields receive <code className="text-teal-300">USER_PROVIDED</code> provenance.
                </p>
              </div>
              <button
                onClick={() => setShowCreateModal(false)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Error Notification */}
            {formError && (
              <div className="mx-6 mt-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-center gap-2.5 text-xs text-rose-300">
                <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
                <span>{formError}</span>
              </div>
            )}

            {/* Form Body */}
            <form onSubmit={handleCreateSubmit} className="p-6 space-y-6 max-h-[75vh] overflow-y-auto">
              
              {/* Demographics */}
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-teal-400 mb-3 flex items-center justify-between">
                  <span>Patient Demographics</span>
                  <ProvenanceBadge provenance="USER_PROVIDED" />
                </h3>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1">
                      MRN <span className="text-rose-400">*</span>
                    </label>
                    <input
                      type="text"
                      required
                      value={formMrn}
                      onChange={(e) => setFormMrn(e.target.value)}
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs font-mono text-slate-100 focus:outline-none focus:border-teal-500"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1">
                      First Name <span className="text-rose-400">*</span>
                    </label>
                    <input
                      type="text"
                      required
                      placeholder="Jane"
                      value={formFirstName}
                      onChange={(e) => setFormFirstName(e.target.value)}
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-teal-500"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1">
                      Last Name <span className="text-rose-400">*</span>
                    </label>
                    <input
                      type="text"
                      required
                      placeholder="Doe"
                      value={formLastName}
                      onChange={(e) => setFormLastName(e.target.value)}
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-teal-500"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1">
                      Date of Birth <span className="text-rose-400">*</span>
                    </label>
                    <input
                      type="date"
                      required
                      value={formDob}
                      onChange={handleDobChange}
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-teal-500"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-xs font-medium text-slate-300 mb-1">Age</label>
                      <input
                        type="number"
                        min={0}
                        max={130}
                        value={formAge}
                        onChange={(e) => setFormAge(parseInt(e.target.value, 10) || 0)}
                        className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-teal-500"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-300 mb-1">Sex</label>
                      <select
                        value={formSex}
                        onChange={(e) => setFormSex(e.target.value)}
                        className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-teal-500"
                      >
                        <option value="FEMALE">Female</option>
                        <option value="MALE">Male</option>
                        <option value="OTHER">Other</option>
                        <option value="UNKNOWN">Unknown</option>
                      </select>
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1">Contact Phone</label>
                    <input
                      type="text"
                      placeholder="555-0199"
                      value={formPhone}
                      onChange={(e) => setFormPhone(e.target.value)}
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-teal-500"
                    />
                  </div>
                </div>
              </div>

              {/* History & Notes */}
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-teal-400 mb-3 flex items-center justify-between">
                  <span>Medical History & Intake Notes</span>
                  <ProvenanceBadge provenance="USER_PROVIDED" />
                </h3>

                <div className="space-y-3">
                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1">
                      Relevant Medical / Surgical / Family History
                    </label>
                    <textarea
                      rows={2}
                      value={formRelevantHistory}
                      onChange={(e) => setFormRelevantHistory(e.target.value)}
                      placeholder="e.g. Prior appendectomy (1998), paternal history of hypertension, non-smoker..."
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-teal-500"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1">Clinical Intake Notes</label>
                    <textarea
                      rows={2}
                      value={formNotes}
                      onChange={(e) => setFormNotes(e.target.value)}
                      placeholder="Clinical presentation impressions, preliminary triage notes..."
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-teal-500"
                    />
                  </div>
                </div>
              </div>

              {/* Symptoms Input */}
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-teal-400 mb-2 flex items-center justify-between">
                  <span>Reported Symptoms</span>
                  <ProvenanceBadge provenance="USER_PROVIDED" />
                </h3>

                <div className="flex flex-wrap gap-2 mb-2">
                  {formSymptoms.map((s, idx) => (
                    <span
                      key={idx}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs"
                    >
                      <span>{s.symptom} ({s.duration})</span>
                      <button
                        type="button"
                        onClick={() => setFormSymptoms(formSymptoms.filter((_, i) => i !== idx))}
                        className="hover:text-rose-400"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </span>
                  ))}
                  {formSymptoms.length === 0 && (
                    <span className="text-xs text-slate-500 italic">No symptoms added.</span>
                  )}
                </div>

                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="Symptom (e.g. Chronic cough)"
                    value={tempSymptom}
                    onChange={(e) => setTempSymptom(e.target.value)}
                    className="flex-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-teal-500"
                  />
                  <input
                    type="text"
                    placeholder="Duration (e.g. 2 weeks)"
                    value={tempDuration}
                    onChange={(e) => setTempDuration(e.target.value)}
                    className="w-36 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-teal-500"
                  />
                  <button
                    type="button"
                    onClick={handleAddSymptom}
                    className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs flex items-center gap-1 border border-slate-700"
                  >
                    <Plus className="w-3.5 h-3.5" /> Add
                  </button>
                </div>
              </div>

              {/* Conditions Input */}
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-teal-400 mb-2 flex items-center justify-between">
                  <span>Existing Conditions</span>
                  <ProvenanceBadge provenance="USER_PROVIDED" />
                </h3>

                <div className="flex flex-wrap gap-2 mb-2">
                  {formConditions.map((c, idx) => (
                    <span
                      key={idx}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-blue-500/10 border border-blue-500/30 text-blue-300 text-xs"
                    >
                      <span>{c.name} ({c.status})</span>
                      <button
                        type="button"
                        onClick={() => setFormConditions(formConditions.filter((_, i) => i !== idx))}
                        className="hover:text-rose-400"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </span>
                  ))}
                  {formConditions.length === 0 && (
                    <span className="text-xs text-slate-500 italic">No conditions added.</span>
                  )}
                </div>

                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="Condition name (e.g. Asthma)"
                    value={tempCond}
                    onChange={(e) => setTempCond(e.target.value)}
                    className="flex-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-teal-500"
                  />
                  <button
                    type="button"
                    onClick={handleAddCondition}
                    className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs flex items-center gap-1 border border-slate-700"
                  >
                    <Plus className="w-3.5 h-3.5" /> Add
                  </button>
                </div>
              </div>

              {/* Allergies Input */}
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-teal-400 mb-2 flex items-center justify-between">
                  <span>Known Allergies</span>
                  <ProvenanceBadge provenance="USER_PROVIDED" />
                </h3>

                <div className="flex flex-wrap gap-2 mb-2">
                  {formAllergies.map((a, idx) => (
                    <span
                      key={idx}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs"
                    >
                      <span>{a.allergen} ({a.reaction}) - {a.severity}</span>
                      <button
                        type="button"
                        onClick={() => setFormAllergies(formAllergies.filter((_, i) => i !== idx))}
                        className="hover:text-rose-400"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </span>
                  ))}
                  {formAllergies.length === 0 && (
                    <span className="text-xs text-slate-500 italic">No allergies recorded.</span>
                  )}
                </div>

                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="Allergen (e.g. Penicillin)"
                    value={tempAllergen}
                    onChange={(e) => setTempAllergen(e.target.value)}
                    className="flex-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-teal-500"
                  />
                  <input
                    type="text"
                    placeholder="Reaction (e.g. Hives)"
                    value={tempReaction}
                    onChange={(e) => setTempReaction(e.target.value)}
                    className="w-36 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-teal-500"
                  />
                  <select
                    value={tempSeverity}
                    onChange={(e) => setTempSeverity(e.target.value)}
                    className="px-2 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-teal-500"
                  >
                    <option value="MILD">Mild</option>
                    <option value="MODERATE">Moderate</option>
                    <option value="SEVERE">Severe</option>
                    <option value="LIFE_THREATENING">Life-Threatening</option>
                  </select>
                  <button
                    type="button"
                    onClick={handleAddAllergy}
                    className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs flex items-center gap-1 border border-slate-700"
                  >
                    <Plus className="w-3.5 h-3.5" /> Add
                  </button>
                </div>
              </div>

              {/* Medications Input */}
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-teal-400 mb-2 flex items-center justify-between">
                  <span>Current Medications</span>
                  <ProvenanceBadge provenance="USER_PROVIDED" />
                </h3>

                <div className="flex flex-wrap gap-2 mb-2">
                  {formMedications.map((m, idx) => (
                    <span
                      key={idx}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs"
                    >
                      <span>{m.name} {m.dose} ({m.freq})</span>
                      <button
                        type="button"
                        onClick={() => setFormMedications(formMedications.filter((_, i) => i !== idx))}
                        className="hover:text-rose-400"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </span>
                  ))}
                  {formMedications.length === 0 && (
                    <span className="text-xs text-slate-500 italic">No medications recorded.</span>
                  )}
                </div>

                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="Medication name (e.g. Lisinopril)"
                    value={tempMed}
                    onChange={(e) => setTempMed(e.target.value)}
                    className="flex-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-teal-500"
                  />
                  <input
                    type="text"
                    placeholder="Dose (e.g. 10 mg)"
                    value={tempDose}
                    onChange={(e) => setTempDose(e.target.value)}
                    className="w-28 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-teal-500"
                  />
                  <input
                    type="text"
                    placeholder="Freq (e.g. Daily)"
                    value={tempFreq}
                    onChange={(e) => setTempFreq(e.target.value)}
                    className="w-28 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-teal-500"
                  />
                  <button
                    type="button"
                    onClick={handleAddMedication}
                    className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs flex items-center gap-1 border border-slate-700"
                  >
                    <Plus className="w-3.5 h-3.5" /> Add
                  </button>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition-colors"
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 rounded-xl bg-teal-600 hover:bg-teal-500 text-white text-xs font-semibold tracking-wide flex items-center gap-2 shadow-[0_0_12px_rgba(20,184,166,0.3)] transition-all disabled:opacity-50"
                >
                  <UserPlus className="w-4 h-4" />
                  <span>{submitting ? 'Registering...' : 'Register Patient Intake'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Patient Modal */}
      {editingPatient && (
        <EditPatientModal
          patient={editingPatient}
          onClose={() => setEditingPatient(null)}
          onSave={handleSaveEdit}
        />
      )}

      {/* Delete Confirmation Modal */}
      {patientToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
          <div className="bg-[#0e1424] border border-rose-500/30 rounded-2xl w-full max-w-md p-6 space-y-4 animate-fadeIn">
            <div className="w-12 h-12 rounded-full bg-rose-500/10 text-rose-400 flex items-center justify-center mx-auto">
              <Trash2 className="w-6 h-6" />
            </div>

            <div className="text-center space-y-1.5">
              <h3 className="text-base font-bold text-white">Delete Patient Record?</h3>
              <p className="text-xs text-slate-400">
                Are you sure you want to delete patient <strong>{patientToDelete.first_name} {patientToDelete.last_name}</strong> (MRN: {patientToDelete.mrn})?
              </p>
              <p className="text-[11px] text-rose-400/90 pt-1">
                This will cascade delete all associated conditions, allergies, medications, and document references.
              </p>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setPatientToDelete(null)}
                disabled={deleting}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium"
              >
                Cancel
              </button>
              <button
                onClick={confirmDeletePatient}
                disabled={deleting}
                className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold shadow-lg shadow-rose-600/30 flex items-center gap-1.5"
              >
                <Trash2 className="w-4 h-4" />
                <span>{deleting ? 'Deleting...' : 'Confirm Delete'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
