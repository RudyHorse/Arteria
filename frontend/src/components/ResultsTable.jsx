import React, { useState } from "react";
import {
  createPatient, assignAnalysisToPatient, assignAnalysesToPatient,
  deletePatient, getAnalysis,
} from "../api";

function ResultsTable({ analysis, patients, batchIds, onAnalysisUpdated, onPatientsChanged, onPatientDeleted }) {
  const [selectedId, setSelectedId] = useState("");
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  if (!analysis) {
    return (
      <div className="card">
        <div className="card-body text-muted">
          No analysis loaded. Upload a PDF to check results and assign them to a patient.
        </div>
      </div>
    );
  }

  const handleCreate = async () => {
    const name = newName.trim();
    if (!name) return;
    setCreating(true);
    setErr("");
    setMsg("");
    try {
      const res = await createPatient(name);
      if (onPatientsChanged) onPatientsChanged();
      setSelectedId(res.data.id);
      setNewName("");
      setMsg(`Patient "${res.data.name}" created`);
    } catch (e) {
      setErr(e.response?.data?.detail || "Failed to create patient");
    } finally {
      setCreating(false);
    }
  };

  const handleAssign = async () => {
    if (!selectedId || selectedId === "__new__") return;
    setSaving(true);
    setErr("");
    setMsg("");
    try {
      const patient = patients.find((x) => x.id === Number(selectedId));
      const isBatch = batchIds && batchIds.length > 1;
      if (isBatch) {
        const res = await assignAnalysesToPatient(batchIds, selectedId);
        const resGet = await getAnalysis(analysis.id);
        if (onAnalysisUpdated) onAnalysisUpdated(resGet.data);
        setMsg(`${res.data.assigned} analyses saved to patient "${patient?.name || selectedId}"`);
      } else {
        const res = await assignAnalysisToPatient(analysis.id, selectedId);
        if (onAnalysisUpdated) onAnalysisUpdated(res.data);
        setMsg(`Saved to patient "${res.data.patient_name}"`);
      }
      if (onPatientsChanged) onPatientsChanged();
    } catch (e) {
      setErr(e.response?.data?.detail || "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const handleDeletePatient = async () => {
    const p = patients.find((x) => x.id === Number(selectedId));
    if (!p) return;
    if (!window.confirm(`Delete patient "${p.name}" and all their analyses?`)) return;
    setErr("");
    setMsg("");
    try {
      await deletePatient(p.id);
      setSelectedId("");
      if (onPatientDeleted) onPatientDeleted(p.id);
      setMsg(`Patient "${p.name}" deleted`);
    } catch (e) {
      setErr(e.response?.data?.detail || "Failed to delete patient");
    }
  };

  return (
    <div>
      <div className="card mb-3">
        <div className="card-body">
          <h5>{analysis.study_type}</h5>
          <p className="mb-1"><strong>Patient:</strong> {analysis.patient_name || `ID ${analysis.patient_id}`}</p>
          <p className="mb-1"><strong>Date:</strong> {analysis.analysis_date}</p>
          {analysis.conclusion && (
            <p className="mb-0"><strong>Conclusion:</strong> {analysis.conclusion}</p>
          )}

          <div className="row g-2 align-items-end mt-3">
            <div className="col-auto">
              <label className="form-label small mb-1 text-muted">Patient</label>
              <select className="form-select form-select-sm" value={selectedId}
                onChange={(e) => setSelectedId(e.target.value)}>
                <option value="">— select patient —</option>
                {patients.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
                <option value="__new__">＋ New patient…</option>
              </select>
            </div>
            {selectedId === "__new__" && (
              <div className="col-auto d-flex gap-2">
                <input className="form-control form-control-sm" placeholder="Patient name"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleCreate()} />
                <button className="btn btn-sm btn-outline-primary" onClick={handleCreate}
                  disabled={creating || !newName.trim()}>
                  {creating ? "Creating…" : "Create"}
                </button>
              </div>
            )}
            <div className="col-auto">
              <button className="btn btn-sm btn-success" onClick={handleAssign}
                disabled={!selectedId || selectedId === "__new__" || saving}>
                {saving
                  ? "Saving…"
                  : batchIds && batchIds.length > 1
                    ? `Save All (${batchIds.length}) to Patient`
                    : "Save to Patient"}
              </button>
            </div>
            <div className="col-auto">
              <button className="btn btn-sm btn-outline-danger" onClick={handleDeletePatient}
                disabled={!selectedId || selectedId === "__new__"}>
                Delete Patient
              </button>
            </div>
          </div>

          {msg && <div className="alert alert-success py-1 px-2 mt-2 mb-0 small">{msg}</div>}
          {err && <div className="alert alert-danger py-1 px-2 mt-2 mb-0 small">{err}</div>}
        </div>
      </div>

      <div className="card">
        <div className="card-header">Results Table</div>
        <div className="table-responsive">
          <table className="table table-striped mb-0">
            <thead>
              <tr>
                <th>Test</th>
                <th>Result</th>
                <th>Reference Range</th>
                <th>Unit</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {analysis.results?.map((r, i) => (
                <tr key={i} className={r.is_abnormal ? "table-danger" : ""}>
                  <td>{r.test_name}</td>
                  <td>{r.result_text ?? r.result_value ?? "-"}</td>
                  <td>{r.reference_text ?? "-"}</td>
                  <td>{r.unit || "-"}</td>
                  <td>
                    {r.is_abnormal ? (
                      <span className="badge bg-danger">Abnormal</span>
                    ) : (
                      <span className="badge bg-success">Normal</span>
                    )}
                  </td>
                </tr>
              ))}
              {(!analysis.results || analysis.results.length === 0) && (
                <tr><td colSpan="5" className="text-muted">No results parsed</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default ResultsTable;
