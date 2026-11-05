import os
import uuid
import shutil
from datetime import date
from typing import List

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import engine, get_db, Base
from models import Patient, Analysis, Result
from schemas import OCRResult, AnalysisCreate, AnalysisResponse, PatientResponse, PatientListItem, PatientCreate, AnalysisAssign, AnalysesAssign
from ocr_processor import extract_text_from_pdf, parse_blood_analysis
from parsers import available_parsers, extract_payload

Base.metadata.create_all(bind=engine)


def _migrate():
    from sqlalchemy import text as sql_text
    with engine.connect() as conn:
        cols = [row[1] for row in conn.execute(sql_text("PRAGMA table_info(analyses)"))]
        if "parser" not in cols:
            conn.execute(sql_text("ALTER TABLE analyses ADD COLUMN parser VARCHAR(50)"))
            conn.commit()


_migrate()

app = FastAPI(title="Arteria API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.get("/api/parsers")
def list_parsers():
    parsers = available_parsers()
    return {"parsers": parsers, "default": "local"}


@app.post("/api/upload", response_model=AnalysisResponse)
async def upload_pdf(file: UploadFile = File(...), parser: str = Form("local"), db: Session = Depends(get_db)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files allowed")
    if parser not in available_parsers():
        raise HTTPException(400, f"Parser '{parser}' is not available")

    filename = f"{uuid.uuid4()}_{file.filename}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        text = extract_payload(filepath, parser)
        print(f"[{parser}] Extracted {len(text)} chars of JSON")
        ocr_data: OCRResult = parse_blood_analysis(text)
        print(f"[{parser}] Parsed {len(ocr_data.results)} results")
    except Exception as e:
        raise HTTPException(500, f"Processing failed: {str(e)}")

    analysis_date = date.today()
    try:
        parts = ocr_data.analysis_date.split("-")
        analysis_date = date(int(parts[0]), int(parts[1]), int(parts[2]))
    except Exception:
        pass

    patient = db.query(Patient).filter(Patient.name == ocr_data.patient_name).first()
    if not patient:
        patient = Patient(name=ocr_data.patient_name, created_at=date.today())
        db.add(patient)
        db.flush()

    analysis = Analysis(
        patient_id=patient.id,
        analysis_date=analysis_date,
        study_type=ocr_data.study_type,
        conclusion=ocr_data.conclusion,
        pdf_filename=filename,
        parser=parser,
    )
    db.add(analysis)
    db.flush()

    for r in ocr_data.results:
        result = Result(
            analysis_id=analysis.id,
            test_name=r.test_name,
            result_value=r.result_value,
            result_text=r.result_text,
            reference_min=r.reference_min,
            reference_max=r.reference_max,
            reference_text=r.reference_text,
            unit=r.unit,
            is_abnormal=1 if r.is_abnormal else 0,
        )
        db.add(result)

    db.commit()
    db.refresh(analysis)
    analysis.patient_name = patient.name
    return analysis


@app.post("/api/analyses", response_model=AnalysisResponse)
def create_analysis(data: AnalysisCreate, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.name == data.patient_name).first()
    if not patient:
        patient = Patient(name=data.patient_name, created_at=date.today())
        db.add(patient)
        db.flush()

    analysis = Analysis(
        patient_id=patient.id,
        analysis_date=data.analysis_date,
        study_type=data.study_type,
        conclusion=data.conclusion,
    )
    db.add(analysis)
    db.flush()

    for r in data.results:
        result = Result(
            analysis_id=analysis.id,
            test_name=r.test_name,
            result_value=r.result_value,
            result_text=r.result_text,
            reference_min=r.reference_min,
            reference_max=r.reference_max,
            reference_text=r.reference_text,
            unit=r.unit,
            is_abnormal=1 if r.is_abnormal else 0,
        )
        db.add(result)

    db.commit()
    db.refresh(analysis)
    analysis.patient_name = patient.name
    return analysis


@app.get("/api/patients", response_model=List[PatientListItem])
def list_patients(db: Session = Depends(get_db)):
    return db.query(Patient).all()


@app.post("/api/patients", response_model=PatientListItem)
def create_patient(data: PatientCreate, db: Session = Depends(get_db)):
    name = (data.name or "").strip()
    if not name:
        raise HTTPException(400, "Patient name required")
    existing = db.query(Patient).filter(Patient.name == name).first()
    if existing:
        return existing
    patient = Patient(name=name, created_at=date.today())
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


@app.delete("/api/patients/{patient_id}")
def delete_patient(patient_id: int, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(404, "Patient not found")
    db.delete(patient)
    db.commit()
    return {"ok": True}


@app.get("/api/patients/{patient_id}", response_model=PatientResponse)
def get_patient(patient_id: int, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(404, "Patient not found")
    return patient


def enrich_analysis(analysis: Analysis) -> Analysis:
    analysis.patient_name = analysis.patient.name if analysis.patient else None
    return analysis


@app.get("/api/analyses/{analysis_id}", response_model=AnalysisResponse)
def get_analysis(analysis_id: int, db: Session = Depends(get_db)):
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(404, "Analysis not found")
    return enrich_analysis(analysis)


@app.delete("/api/analyses/{analysis_id}")
def delete_analysis(analysis_id: int, db: Session = Depends(get_db)):
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(404, "Analysis not found")
    patient_id = analysis.patient_id
    db.delete(analysis)
    db.commit()
    _delete_patient_if_empty(patient_id, db)
    return {"ok": True}


@app.put("/api/analyses/patient")
def assign_analyses_patient(data: AnalysesAssign, db: Session = Depends(get_db)):
    if not data.ids:
        raise HTTPException(400, "No analyses specified")
    patient = db.query(Patient).filter(Patient.id == data.patient_id).first()
    if not patient:
        raise HTTPException(404, "Patient not found")

    analyses = db.query(Analysis).filter(Analysis.id.in_(data.ids)).all()
    if len(analyses) != len(set(data.ids)):
        raise HTTPException(404, "Some analyses not found")

    old_patient_ids = set()
    for a in analyses:
        old_patient_ids.add(a.patient_id)
        a.patient_id = patient.id
    db.commit()
    for pid in old_patient_ids - {patient.id}:
        _delete_patient_if_empty(pid, db)

    return {"ok": True, "assigned": len(analyses)}


@app.put("/api/analyses/{analysis_id}/patient", response_model=AnalysisResponse)
def assign_analysis_patient(analysis_id: int, data: AnalysisAssign, db: Session = Depends(get_db)):
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(404, "Analysis not found")
    patient = db.query(Patient).filter(Patient.id == data.patient_id).first()
    if not patient:
        raise HTTPException(404, "Patient not found")

    old_patient_id = analysis.patient_id
    analysis.patient_id = patient.id
    db.commit()
    if old_patient_id != patient.id:
        _delete_patient_if_empty(old_patient_id, db)

    db.refresh(analysis)
    return enrich_analysis(analysis)


def _delete_patient_if_empty(patient_id: int, db: Session):
    remaining = db.query(Analysis).filter(Analysis.patient_id == patient_id).count()
    if remaining == 0:
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if patient:
            db.delete(patient)
            db.commit()


@app.get("/api/analyses", response_model=List[AnalysisResponse])
def list_analyses(patient_id: int = None, db: Session = Depends(get_db)):
    q = db.query(Analysis)
    if patient_id:
        q = q.filter(Analysis.patient_id == patient_id)
    analyses = q.all()
    for a in analyses:
        enrich_analysis(a)
    return analyses


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
