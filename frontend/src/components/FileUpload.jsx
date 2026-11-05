import React, { useState, useEffect } from "react";
import { uploadPdf, listParsers } from "../api";

function FileUpload({ onAnalysisLoaded, onBatchLoaded }) {
  const [files, setFiles] = useState([]);
  const [statuses, setStatuses] = useState([]);
  const [loading, setLoading] = useState(false);
  const [parsers, setParsers] = useState([]);
  const [parser, setParser] = useState("local");

  useEffect(() => {
    listParsers()
      .then((r) => {
        setParsers(r.data.parsers || ["local"]);
        if (r.data.default) setParser(r.data.default);
      })
      .catch(() => setParsers(["local"]));
  }, []);

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!files.length) return;
    setLoading(true);

    const list = files.map((f) => ({ name: f.name, status: "pending", error: "" }));
    setStatuses(list);

    let lastLoaded = null;
    const savedIds = [];
    for (let i = 0; i < files.length; i++) {
      list[i].status = "uploading";
      setStatuses([...list]);
      try {
        const res = await uploadPdf(files[i], parser);
        list[i].status = "ok";
        list[i].saved = `${res.data.patient_name || "Unknown"} · ${res.data.analysis_date} · #${res.data.id}`;
        savedIds.push(res.data.id);
        lastLoaded = res.data;
      } catch (err) {
        list[i].status = "error";
        list[i].error = err.response?.data?.detail || "Upload failed";
      }
      setStatuses([...list]);
    }

    setLoading(false);
    setFiles([]);
    if (lastLoaded && onAnalysisLoaded) onAnalysisLoaded(lastLoaded);
    if (onBatchLoaded) onBatchLoaded(savedIds);
  };

  const badge = (s) => {
    if (s.status === "ok") return <span className="badge bg-success">saved</span>;
    if (s.status === "error") return <span className="badge bg-danger">failed</span>;
    if (s.status === "uploading") return <span className="badge bg-primary">processing…</span>;
    return <span className="badge bg-secondary">queued</span>;
  };

  return (
    <div className="card">
      <div className="card-header">Upload Blood Analysis PDFs</div>
      <div className="card-body">
        <form onSubmit={handleUpload}>
          <div className="mb-3">
            <label className="form-label small text-muted mb-1">Parser</label>
            <select className="form-select form-select-sm mb-2" value={parser}
              onChange={(e) => setParser(e.target.value)}>
              {parsers.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
            <input className="form-control" type="file" accept=".pdf" multiple
              onChange={(e) => setFiles(Array.from(e.target.files || []))} />
            <div className="form-text">
              Select one or more PDFs — each is analyzed and saved as a separate result.
            </div>
          </div>
          {statuses.length > 0 && (
            <ul className="list-group mb-3">
              {statuses.map((s, i) => (
                <li key={i} className="list-group-item d-flex justify-content-between align-items-center py-1">
                  <span className="text-truncate me-2" title={s.name}>
                    {s.name}
                    {s.saved && <span className="d-block small text-muted">saved: {s.saved}</span>}
                  </span>
                  <span className="d-flex align-items-center gap-2">
                    {s.error && <span className="small text-danger">{s.error}</span>}
                    {badge(s)}
                  </span>
                </li>
              ))}
            </ul>
          )}
          <button className="btn btn-primary" type="submit" disabled={!files.length || loading}>
            {loading
              ? "Processing…"
              : files.length > 1
                ? `Upload & Analyze ${files.length} files`
                : "Upload & Analyze"}
          </button>
        </form>
      </div>
    </div>
  );
}

export default FileUpload;
