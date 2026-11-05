import React, { useState, useEffect } from "react";
import {
  XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine,
  ResponsiveContainer, LineChart, Line,
} from "recharts";
import { getPatient } from "../api";

function Dashboard({ patientId, trendTests, setTrendTests }) {
  const [patient, setPatient] = useState(null);
  const [addingTrend, setAddingTrend] = useState(false);

  useEffect(() => {
    setAddingTrend(false);
    if (!patientId) {
      setPatient(null);
      return;
    }
    getPatient(patientId).then((r) => setPatient(r.data)).catch(() => {});
  }, [patientId]);

  if (!patient) {
    return <div className="text-muted">Select a patient from the left panel</div>;
  }

  const sortedAnalyses = [...(patient.analyses || [])].sort(
    (a, b) => String(a.analysis_date).localeCompare(String(b.analysis_date))
  );

  const allTestNames = [];
  const seen = new Set();
  sortedAnalyses.forEach((a) => {
    (a.results || []).forEach((r) => {
      if (!seen.has(r.test_name)) {
        seen.add(r.test_name);
        allTestNames.push(r.test_name);
      }
    });
  });
  allTestNames.sort();
  const availableTests = allTestNames.filter((n) => !trendTests.includes(n));

  const trendInfoFor = (testName) => {
    const points = [];
    let refMin = null;
    let refMax = null;
    sortedAnalyses.forEach((a) => {
      const rec = a.results?.find((r) => r.test_name === testName);
      if (!rec) return;
      if (rec.result_value != null) {
        points.push({ date: a.analysis_date, value: rec.result_value });
      }
      if (rec.reference_min != null) refMin = rec.reference_min;
      if (rec.reference_max != null) refMax = rec.reference_max;
    });
    return { points, refMin, refMax };
  };

  return (
    <div>
      <div className="card">
        <div className="card-header d-flex justify-content-between align-items-center">
          <span>Trends Over Time</span>
          <div className="d-flex align-items-center gap-2">
            {addingTrend ? (
              <select className="form-select form-select-sm" style={{ width: 220 }}
                defaultValue=""
                onChange={(e) => {
                  const v = e.target.value;
                  if (v) setTrendTests((t) => [...t, v]);
                  setAddingTrend(false);
                }}>
                <option value="" disabled>Select parameter…</option>
                {availableTests.map((n) => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            ) : (
              <button className="btn btn-sm btn-outline-primary py-0 px-2" title="Add trend graph"
                onClick={() => setAddingTrend(true)}
                disabled={availableTests.length === 0}>+</button>
            )}
          </div>
        </div>

        {trendTests.length > 0 && (
          <div className="card-body">
            <div className="row g-3">
              {trendTests.map((tn) => {
                const { points, refMin, refMax } = trendInfoFor(tn);
                const vals = points.map((p) => p.value);
                const lo = Math.min(...vals, ...(refMin != null ? [refMin] : []));
                const hi = Math.max(...vals, ...(refMax != null ? [refMax] : []));
                const pad = (hi - lo) * 0.1 || 1;
                const yDomain = [lo - pad, hi + pad];
                return (
                  <div className="col-md-4" key={tn}>
                    <div className="card h-100">
                      <div className="card-header d-flex justify-content-between align-items-center py-1">
                        <span className="small text-truncate" title={tn}>{tn}</span>
                        <button className="btn btn-sm btn-outline-danger py-0 px-1" title="Remove"
                          onClick={() => setTrendTests((t) => t.filter((x) => x !== tn))}>&times;</button>
                      </div>
                      <div className="card-body p-2">
                        {points.length > 0 ? (
                          <ResponsiveContainer width="100%" height={160}>
                            <LineChart data={points} margin={{ top: 5, right: 8, left: -18, bottom: 0 }}>
                              <CartesianGrid strokeDasharray="3 3" />
                              <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                              <YAxis tick={{ fontSize: 10 }} domain={yDomain} />
                              <Tooltip />
                              {refMin != null && (
                                <ReferenceLine y={refMin} stroke="#fd7e14" strokeDasharray="4 3"
                                  label={{ value: `min ${refMin}`, position: "insideBottomRight", fill: "#fd7e14", fontSize: 9 }} />
                              )}
                              {refMax != null && (
                                <ReferenceLine y={refMax} stroke="#fd7e14" strokeDasharray="4 3"
                                  label={{ value: `max ${refMax}`, position: "insideTopRight", fill: "#fd7e14", fontSize: 9 }} />
                              )}
                              <Line type="monotone" dataKey="value" stroke="#0d6efd"
                                dot={{ r: 2 }} connectNulls />
                            </LineChart>
                          </ResponsiveContainer>
                        ) : (
                          <p className="text-muted small mb-0 p-2">No data</p>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="small text-muted mt-2">Dashed lines — reference min/max</div>
          </div>
        )}
      </div>
    </div>
  );
}

export default Dashboard;
