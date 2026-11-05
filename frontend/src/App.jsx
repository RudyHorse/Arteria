import React, { useState, useEffect } from "react";
import { listPatients, deletePatient } from "./api";
import FileUpload from "./components/FileUpload";
import ResultsTable from "./components/ResultsTable";
import Database from "./components/Database";
import Dashboard from "./components/Dashboard";

function App() {
  const [patients, setPatients] = useState([]);
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [view, setView] = useState("upload");
  const [trendTests, setTrendTests] = useState([]);
  const [batchIds, setBatchIds] = useState([]);

  const loadPatients = () => {
    listPatients().then((r) => setPatients(r.data)).catch(() => {});
  };

  useEffect(loadPatients, []);

  const onAnalysisLoaded = (data) => {
    setAnalysis(data);
    setSelectedPatient(data.patient_id);
    setView("table");
    loadPatients();
  };

  const onPatientDeleted = (deletedId) => {
    if (analysis && analysis.patient_id === deletedId) {
      setAnalysis(null);
      setView("upload");
    }
    if (selectedPatient === deletedId) setSelectedPatient(null);
    loadPatients();
  };

  const handleDeletePatient = async (p, e) => {
    e.stopPropagation();
    if (!window.confirm(`Delete patient "${p.name}" and all their analyses?`)) return;
    try {
      await deletePatient(p.id);
      onPatientDeleted(p.id);
    } catch (err) {
      alert(err.response?.data?.detail || "Failed to delete patient");
    }
  };

  return (
    <div className="container py-4">
      <h1 className="mb-4">Arteria</h1>

      <ul className="nav nav-tabs mb-4">
        <li className="nav-item">
          <button className={`nav-link ${view === "upload" ? "active" : ""}`}
            onClick={() => setView("upload")}>Upload PDF</button>
        </li>
        <li className="nav-item">
          <button className={`nav-link ${view === "table" ? "active" : ""}`}
            onClick={() => setView("table")}>Results</button>
        </li>
        <li className="nav-item">
          <button className={`nav-link ${view === "database" ? "active" : ""}`}
            onClick={() => setView("database")}>Database</button>
        </li>
        <li className="nav-item">
          <button className={`nav-link ${view === "dashboard" ? "active" : ""}`}
            onClick={() => setView("dashboard")}>Dashboard</button>
        </li>
      </ul>

      <div className="row">
        <div className="col-md-3">
          <div className="card">
            <div className="card-header">Patients</div>
            <ul className="list-group list-group-flush">
              {patients.map((p) => (
                <li key={p.id}
                  className={`list-group-item list-group-item-action d-flex justify-content-between align-items-center ${selectedPatient === p.id ? "active" : ""}`}
                  style={{ cursor: "pointer" }}
                  onClick={() => { setSelectedPatient(p.id); setAnalysis(null); setView("dashboard"); }}>
                  <span>{p.name}</span>
                  <button className="btn btn-sm btn-outline-danger py-0 px-1" title="Delete patient"
                    onClick={(e) => handleDeletePatient(p, e)}>&times;</button>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="col-md-9">
          {view === "upload" && (
            <FileUpload onAnalysisLoaded={onAnalysisLoaded} onBatchLoaded={setBatchIds} />
          )}
          {view === "table" && (
            <ResultsTable
              analysis={analysis}
              patients={patients}
              batchIds={batchIds}
              onAnalysisUpdated={(data) => {
                setAnalysis(data);
                setSelectedPatient(data.patient_id);
              }}
              onPatientsChanged={loadPatients}
              onPatientDeleted={onPatientDeleted}
            />
          )}
          {view === "database" && (
            <Database
              analysis={analysis}
              patientId={selectedPatient}
              onAnalysisSelected={(data) => {
                setAnalysis(data);
                setSelectedPatient(data.patient_id);
              }}
              onAnalysisDeleted={() => setAnalysis(null)}
            />
          )}
          {view === "dashboard" && (
            <Dashboard
              patientId={selectedPatient}
              trendTests={trendTests}
              setTrendTests={setTrendTests}
            />
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
