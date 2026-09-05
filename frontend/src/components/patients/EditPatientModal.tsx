import React, { useState } from 'react';
import { X, Save, AlertCircle, Plus, Trash2 } from 'lucide-react';
import { Patient, Condition, Allergy, Medication, Symptom } from '../../types';
import { ProvenanceBadge } from '../common/Badges';

interface EditPatientModalProps {
  patient: Patient;
  onClose: () => void;
  onSave: (updatedData: any) => Promise<void>;
}

export const EditPatientModal: React.FC<EditPatientModalProps> = ({
  patient,
  onClose,
  onSave,
}) => {
  const [firstName, setFirstName] = useState(patient.first_name);
  const [lastName, setLastName] = useState(patient.last_name);
  const [dob, setDob] = useState(patient.date_of_birth);
  const [age, setAge] = useState(patient.age);
  const [sex, setSex] = useState(patient.sex);
  const [phone, setPhone] = useState(patient.contact_phone || '');
  const [email, setEmail] = useState(patient.contact_email || '');
  const [relevantHistory, setRelevantHistory] = useState(patient.relevant_history || '');
  const [notes, setNotes] = useState(patient.notes || '');
  const [isArchived, setIsArchived] = useState(patient.is_archived || false);

  // Lists
  const [conditions, setConditions] = useState<Condition[]>([...(patient.conditions || [])]);
  const [allergies, setAllergies] = useState<Allergy[]>([...(patient.allergies || [])]);
  const [medications, setMedications] = useState<Medication[]>([...(patient.medications || [])]);
  const [symptoms, setSymptoms] = useState<Symptom[]>([...(patient.symptoms || [])]);

  // Temp inputs for adding items
  const [newCond, setNewCond] = useState('');
  const [newAllergen, setNewAllergen] = useState('');
  const [newAllergyReaction, setNewAllergyReaction] = useState('');
  const [newAllergySeverity, setNewAllergySeverity] = useState('MODERATE');
  const [newMedName, setNewMedName] = useState('');
  const [newMedDose, setNewMedDose] = useState('');
  const [newMedFreq, setNewMedFreq] = useState('');
  const [newSymptom, setNewSymptom] = useState('');
  const [newSymptomDuration, setNewSymptomDuration] = useState('');

  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const calculateAge = (dobString: string) => {
    const birthDate = new Date(dobString);
    if (isNaN(birthDate.getTime())) return;
    const today = new Date();
    let calculatedAge = today.getFullYear() - birthDate.getFullYear();
    const m = today.getMonth() - birthDate.getMonth();
    if (m < 0 || (m === 0 && today.getDate() < birthDate.getDate())) {
      calculatedAge--;
    }
    if (calculatedAge >= 0 && calculatedAge <= 130) {
      setAge(calculatedAge);
    }
  };

  const handleDobChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setDob(val);
    calculateAge(val);
  };

  const handleAddCondition = () => {
    if (!newCond.trim()) return;
    setConditions([
      ...conditions,
      {
        id: `temp-${Date.now()}`,
        condition_name: newCond.trim(),
        status: 'ACTIVE',
        provenance: 'USER_PROVIDED',
      },
    ]);
    setNewCond('');
  };

  const handleAddAllergy = () => {
    if (!newAllergen.trim()) return;
    setAllergies([
      ...allergies,
      {
        id: `temp-${Date.now()}`,
        allergen: newAllergen.trim(),
        reaction: newAllergyReaction.trim() || undefined,
        severity: newAllergySeverity,
        provenance: 'USER_PROVIDED',
      },
    ]);
    setNewAllergen('');
    setNewAllergyReaction('');
  };

  const handleAddMedication = () => {
    if (!newMedName.trim()) return;
    setMedications([
      ...medications,
      {
        id: `temp-${Date.now()}`,
        medication_name: newMedName.trim(),
        dosage: newMedDose.trim() || undefined,
        frequency: newMedFreq.trim() || undefined,
        route: 'ORAL',
        provenance: 'USER_PROVIDED',
      },
    ]);
    setNewMedName('');
    setNewMedDose('');
    setNewMedFreq('');
  };

  const handleAddSymptom = () => {
    if (!newSymptom.trim()) return;
    setSymptoms([
      ...symptoms,
      {
        id: `temp-${Date.now()}`,
        symptom: newSymptom.trim(),
        duration: newSymptomDuration.trim() || undefined,
        severity: 'MODERATE',
        provenance: 'USER_PROVIDED',
      },
    ]);
    setNewSymptom('');
    setNewSymptomDuration('');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!firstName.trim() || !lastName.trim()) {
      setError('First and last name are required.');
      return;
    }

    if (!/^\d{4}-\d{2}-\d{2}$/.test(dob)) {
      setError('Date of birth must follow YYYY-MM-DD format.');
      return;
    }

    const birthDate = new Date(dob);
    if (birthDate > new Date()) {
      setError('Date of birth cannot be in the future.');
      return;
    }

    if (age < 0 || age > 130) {
      setError('Age must be between 0 and 130.');
      return;
    }

    try {
      setSaving(true);
      const payload = {
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        date_of_birth: dob,
        age: Number(age),
        sex,
        contact_phone: phone.trim() || null,
        contact_email: email.trim() || null,
        relevant_history: relevantHistory.trim() || null,
        notes: notes.trim() || null,
        is_archived: isArchived,
        conditions: conditions.map((c) => ({
          condition_name: c.condition_name,
          status: c.status || 'ACTIVE',
          diagnosed_date: c.diagnosed_date || null,
          notes: c.notes || null,
          provenance: 'USER_PROVIDED',
        })),
        allergies: allergies.map((a) => ({
          allergen: a.allergen,
          reaction: a.reaction || null,
          severity: a.severity || 'MODERATE',
          provenance: 'USER_PROVIDED',
        })),
        medications: medications.map((m) => ({
          medication_name: m.medication_name,
          dosage: m.dosage || null,
          frequency: m.frequency || null,
          route: m.route || 'ORAL',
          provenance: 'USER_PROVIDED',
        })),
        symptoms: symptoms.map((s) => ({
          symptom: s.symptom,
          duration: s.duration || null,
          severity: s.severity || 'MODERATE',
          provenance: 'USER_PROVIDED',
        })),
      };

      await onSave(payload);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to update patient record.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="bg-[#0e1424] border border-slate-700/80 rounded-2xl w-full max-w-3xl shadow-2xl overflow-hidden my-8 animate-fadeIn">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-[#090d16]/70">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-white">Edit Patient Record</h2>
              <span className="font-mono text-xs px-2 py-0.5 rounded bg-teal-500/10 text-teal-400 border border-teal-500/20">
                MRN: {patient.mrn}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Update demographics, notes, and clinical items. All modifications tracked with <code className="text-teal-300">USER_PROVIDED</code> provenance.
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Error notification */}
        {error && (
          <div className="mx-6 mt-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-center gap-2.5 text-xs text-rose-300">
            <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-6 max-h-[75vh] overflow-y-auto">
          {/* Section: Demographics */}
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-teal-400 mb-3 flex items-center justify-between">
              <span>Patient Demographics</span>
              <ProvenanceBadge provenance="USER_PROVIDED" />
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  First Name <span className="text-rose-400">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
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
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
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
                  value={dob}
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
                    value={age}
                    onChange={(e) => setAge(parseInt(e.target.value, 10) || 0)}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-teal-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Sex</label>
                  <select
                    value={sex}
                    onChange={(e) => setSex(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-teal-500"
                  >
                    <option value="MALE">Male</option>
                    <option value="FEMALE">Female</option>
                    <option value="OTHER">Other</option>
                    <option value="UNKNOWN">Unknown</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Contact Phone</label>
                <input
                  type="text"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="555-0100"
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-teal-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Contact Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="patient@example.org"
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-teal-500"
                />
              </div>
            </div>
          </div>

          {/* Section: Clinical History & Notes */}
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-teal-400 mb-3 flex items-center justify-between">
              <span>Clinical History & Impressions</span>
              <ProvenanceBadge provenance="USER_PROVIDED" />
            </h3>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Relevant History (Family, Surgical, Social)
                </label>
                <textarea
                  rows={2}
                  value={relevantHistory}
                  onChange={(e) => setRelevantHistory(e.target.value)}
                  placeholder="e.g. Prior laparoscopic cholecystectomy, maternal T2D, non-smoker..."
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-teal-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Clinical Intake Notes</label>
                <textarea
                  rows={2}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="General clinician observations, care goals, referral context..."
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-teal-500"
                />
              </div>
            </div>
          </div>

          {/* Section: Symptoms */}
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-teal-400 mb-2 flex items-center justify-between">
              <span>Reported Symptoms</span>
              <ProvenanceBadge provenance="USER_PROVIDED" />
            </h3>

            <div className="flex flex-wrap gap-2 mb-2">
              {symptoms.map((s, idx) => (
                <span
                  key={idx}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs"
                >
                  <span>{s.symptom} {s.duration && `(${s.duration})`}</span>
                  <button
                    type="button"
                    onClick={() => setSymptoms(symptoms.filter((_, i) => i !== idx))}
                    className="hover:text-rose-400"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </span>
              ))}
              {symptoms.length === 0 && (
                <span className="text-xs text-slate-500 italic">No symptoms recorded.</span>
              )}
            </div>

            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Add symptom (e.g. Shortness of breath)"
                value={newSymptom}
                onChange={(e) => setNewSymptom(e.target.value)}
                className="flex-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-teal-500"
              />
              <input
                type="text"
                placeholder="Duration (e.g. 2 weeks)"
                value={newSymptomDuration}
                onChange={(e) => setNewSymptomDuration(e.target.value)}
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

          {/* Section: Existing Conditions */}
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-teal-400 mb-2 flex items-center justify-between">
              <span>Existing Conditions</span>
              <ProvenanceBadge provenance="USER_PROVIDED" />
            </h3>

            <div className="flex flex-wrap gap-2 mb-2">
              {conditions.map((c, idx) => (
                <span
                  key={idx}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-blue-500/10 border border-blue-500/30 text-blue-300 text-xs"
                >
                  <span>{c.condition_name} ({c.status})</span>
                  <button
                    type="button"
                    onClick={() => setConditions(conditions.filter((_, i) => i !== idx))}
                    className="hover:text-rose-400"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </span>
              ))}
              {conditions.length === 0 && (
                <span className="text-xs text-slate-500 italic">No conditions recorded.</span>
              )}
            </div>

            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Add condition (e.g. Essential Hypertension)"
                value={newCond}
                onChange={(e) => setNewCond(e.target.value)}
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

          {/* Section: Allergies */}
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-teal-400 mb-2 flex items-center justify-between">
              <span>Allergies</span>
              <ProvenanceBadge provenance="USER_PROVIDED" />
            </h3>

            <div className="flex flex-wrap gap-2 mb-2">
              {allergies.map((a, idx) => (
                <span
                  key={idx}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs"
                >
                  <span>{a.allergen} {a.reaction && `(${a.reaction})`} - {a.severity}</span>
                  <button
                    type="button"
                    onClick={() => setAllergies(allergies.filter((_, i) => i !== idx))}
                    className="hover:text-rose-400"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </span>
              ))}
              {allergies.length === 0 && (
                <span className="text-xs text-slate-500 italic">No known allergies.</span>
              )}
            </div>

            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Allergen (e.g. Penicillin)"
                value={newAllergen}
                onChange={(e) => setNewAllergen(e.target.value)}
                className="flex-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-teal-500"
              />
              <input
                type="text"
                placeholder="Reaction (e.g. Anaphylaxis)"
                value={newAllergyReaction}
                onChange={(e) => setNewAllergyReaction(e.target.value)}
                className="w-40 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-teal-500"
              />
              <select
                value={newAllergySeverity}
                onChange={(e) => setNewAllergySeverity(e.target.value)}
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

          {/* Section: Medications */}
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-teal-400 mb-2 flex items-center justify-between">
              <span>Medications</span>
              <ProvenanceBadge provenance="USER_PROVIDED" />
            </h3>

            <div className="flex flex-wrap gap-2 mb-2">
              {medications.map((m, idx) => (
                <span
                  key={idx}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs"
                >
                  <span>{m.medication_name} {m.dosage && `${m.dosage}`} {m.frequency && `(${m.frequency})`}</span>
                  <button
                    type="button"
                    onClick={() => setMedications(medications.filter((_, i) => i !== idx))}
                    className="hover:text-rose-400"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </span>
              ))}
              {medications.length === 0 && (
                <span className="text-xs text-slate-500 italic">No medications recorded.</span>
              )}
            </div>

            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Medication name (e.g. Lisinopril)"
                value={newMedName}
                onChange={(e) => setNewMedName(e.target.value)}
                className="flex-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-teal-500"
              />
              <input
                type="text"
                placeholder="Dose (e.g. 10 mg)"
                value={newMedDose}
                onChange={(e) => setNewMedDose(e.target.value)}
                className="w-28 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-teal-500"
              />
              <input
                type="text"
                placeholder="Freq (e.g. Once daily)"
                value={newMedFreq}
                onChange={(e) => setNewMedFreq(e.target.value)}
                className="w-32 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-teal-500"
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

          {/* Archive Status Toggle */}
          <div className="pt-2 border-t border-slate-800 flex items-center justify-between">
            <div>
              <span className="text-xs font-semibold text-slate-300">Archive Patient Record</span>
              <p className="text-[11px] text-slate-500">
                Archiving hides this patient from default searches without deleting historical clinical records.
              </p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={isArchived}
                onChange={(e) => setIsArchived(e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-amber-600"></div>
            </label>
          </div>

          {/* Action buttons */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition-colors"
            >
              Cancel
            </button>

            <button
              type="submit"
              disabled={saving}
              className="px-5 py-2 rounded-xl bg-teal-600 hover:bg-teal-500 text-white text-xs font-semibold tracking-wide flex items-center gap-2 shadow-[0_0_12px_rgba(20,184,166,0.3)] transition-all disabled:opacity-50"
            >
              <Save className="w-4 h-4" />
              <span>{saving ? 'Saving...' : 'Save Patient Changes'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
