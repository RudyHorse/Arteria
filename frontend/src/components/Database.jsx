import React, { useState, useEffect } from "react";
import { listAnalyses, getAnalysis, deleteAnalysis } from "../api";
import CandleChart from "./CandleChart";

function Database({ analysis, patientId, onAnalysisSelected, onAnalysisDeleted }) {
  const [analyses, setAnalyses] = useState([]);
  const [showHistory, setShowHistory] = useState(true);
  const [showChart, setShowChart] = useState(true);
  const [showAbnormal, setShowAbnormal] = useState(true);
  const [err, setErr] = useState("");

  const loadAll = () => {
    if (!patientId) {
      setAnalyses([]);
      return;
    }
    listAnalyses(patientId)
      .then((r) => setAnalyses(r.data))
      .catch(() => setAnalyses([]));
  };

  useEffect(() => {
    loadAll();
  }, [patientId]);

  const selectAnalysis = async (id) => {
    if (analysis && id === analysis.id) return;
    try {
      const res = await getAnalysis(id);
      if (onAnalysisSelected) onAnalysisSelected(res.data);
    } catch {
      setErr("Failed to load analysis");
    }
  };

  const handleDeleteAnalysis = async (id, e) => {
    e.stopPropagation();
    if (!window.confirm("Delete this analysis?")) return;
    try {
      await deleteAnalysis(id);
      loadAll();
      if (analysis && analysis.id === id) {
        if (onAnalysisDeleted) onAnalysisDeleted();
      }
    } catch {
      setErr("Failed to delete analysis");
    }
  };

  const barData = (analysis?.results || [])
    .filter((r) => r.result_value != null)
    .map((r) => ({
      name: r.test_name.length > 12 ? r.test_name.slice(0, 12) + "..." : r.test_name,
      result: r.result_value,
      refMin: r.reference_min,
      refMax: r.reference_max,
      unit: r.unit,
      abnormal: r.is_abnormal,
    }))
    .filter((d) => d.refMin != null || d.refMax != null);

  if (!patientId) {
    return (
      <div className="card">
        <div className="card-body text-muted">
          Select a patient from the left panel to view their saved results.
        </div>
      </div>
    );
  }

  return (
    <div>
      {err && <div className="alert alert-danger py-1 px-2 small">{err}</div>}

      <div className="card mb-3">
        <div className="card-header d-flex justify-content-between align-items-center"
          style={{ cursor: "pointer" }}
          onClick={() => setShowHistory((v) => !v)}>
          <span>Analysis History</span>
          <span>
            <span className="badge bg-primary me-2">{analyses.length} analyses</span>
            <span>{showHistory ? "▾" : "▸"}</span>
          </span>
        </div>
        {showHistory && analyses.length > 0 && (
          <div className="list-group list-group-flush" style={{ maxHeight: 320, overflowY: "auto" }}>
            {analyses.map((a) => (
              <div key={a.id}
                className={`list-group-item list-group-item-action d-flex justify-content-between align-items-center ${analysis?.id === a.id ? "active" : ""}`}
                onClick={() => selectAnalysis(a.id)} style={{ cursor: "pointer" }}>
                <span className="text-truncate me-2">
                  {a.analysis_date} — {a.study_type}
                </span>
                <div className="d-flex align-items-center">
                  <span className="badge bg-secondary rounded-pill me-2">{a.results?.length || 0} tests</span>
                  <button className="btn btn-sm btn-outline-danger" title="Delete"
                    onClick={(e) => handleDeleteAnalysis(a.id, e)}>&times;</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {analysis && barData.length > 0 && (
        <div className="card mb-3">
          <div className="card-header d-flex justify-content-between align-items-center"
            style={{ cursor: "pointer" }}
            onClick={() => setShowChart((v) => !v)}>
            <span>Results</span>
            <span>{showChart ? "▾" : "▸"}</span>
          </div>
          {showChart && (
            <div className="card-body">
              <CandleChart data={barData} />
              <div className="mt-2 small text-muted d-flex flex-wrap gap-3">
                <span className="d-inline-flex align-items-center gap-1">
                  <span style={{ display: "inline-block", width: 14, height: 6, background: "#9db2c8", borderRadius: 2 }} />
                  Reference range
                </span>
                <span className="d-inline-flex align-items-center gap-1">
                  <span style={{ color: "#198754" }}>◆</span> In range
                </span>
                <span className="d-inline-flex align-items-center gap-1">
                  <span style={{ color: "#dc3545" }}>◆</span> Out of range
                </span>
              </div>
            </div>
          )}
        </div>
      )}

      {analysis && (
        <div className="card mb-3">
          <div className="card-header d-flex justify-content-between align-items-center"
            style={{ cursor: "pointer" }}
            onClick={() => setShowAbnormal((v) => !v)}>
            <span>Abnormal Results</span>
            <span>{showAbnormal ? "▾" : "▸"}</span>
          </div>
          {showAbnormal && (
            <div className="card-body">
              {analysis.results?.filter((r) => r.is_abnormal).length > 0 ? (
                <table className="table table-sm table-danger mb-0">
                  <thead>
                    <tr>
                      <th>Test</th>
                      <th>Result</th>
                      <th>Reference</th>
                      <th>Unit</th>
                    </tr>
                  </thead>
                  <tbody>
                    {analysis.results.filter((r) => r.is_abnormal).map((r, i) => (
                      <tr key={i}>
                        <td>{r.test_name}</td>
                        <td>{r.result_text ?? r.result_value}</td>
                        <td>{r.reference_text}</td>
                        <td>{r.unit}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="text-muted mb-0">All results are within normal range</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default Database;
