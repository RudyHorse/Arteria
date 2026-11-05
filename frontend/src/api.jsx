import axios from "axios";

const API = axios.create({ baseURL: "http://localhost:8000/api" });

export const uploadPdf = (file, parser) => {
  const form = new FormData();
  form.append("file", file);
  if (parser) form.append("parser", parser);
  return API.post("/upload", form);
};

export const listParsers = () => API.get("/parsers");

export const listPatients = () => API.get("/patients");

export const createPatient = (name) => API.post("/patients", { name });

export const deletePatient = (id) => API.delete(`/patients/${id}`);

export const getPatient = (id) => API.get(`/patients/${id}`);

export const listAnalyses = (patientId) =>
  API.get("/analyses", { params: patientId ? { patient_id: patientId } : {} });

export const getAnalysis = (id) => API.get(`/analyses/${id}`);

export const assignAnalysisToPatient = (id, patientId) =>
  API.put(`/analyses/${id}/patient`, { patient_id: patientId });

export const assignAnalysesToPatient = (ids, patientId) =>
  API.put("/analyses/patient", { ids, patient_id: patientId });

export const deleteAnalysis = (id) => API.delete(`/analyses/${id}`);
