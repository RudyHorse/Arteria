from pydantic import BaseModel
from typing import List, Optional
from datetime import date


class ResultBase(BaseModel):
    test_name: str
    result_value: Optional[float] = None
    result_text: Optional[str] = None
    reference_min: Optional[float] = None
    reference_max: Optional[float] = None
    reference_text: Optional[str] = None
    unit: Optional[str] = None
    is_abnormal: bool = False


class ResultResponse(ResultBase):
    id: int
    analysis_id: int

    class Config:
        from_attributes = True


class AnalysisBase(BaseModel):
    analysis_date: date
    study_type: str
    conclusion: Optional[str] = None


class AnalysisCreate(AnalysisBase):
    patient_name: str
    results: List[ResultBase]


class AnalysisResponse(AnalysisBase):
    id: int
    patient_id: int
    patient_name: Optional[str] = None
    pdf_filename: Optional[str] = None
    parser: Optional[str] = None
    results: List[ResultResponse]

    class Config:
        from_attributes = True


class PatientResponse(BaseModel):
    id: int
    name: str
    created_at: date
    analyses: List[AnalysisResponse]

    class Config:
        from_attributes = True


class PatientListItem(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class PatientCreate(BaseModel):
    name: str


class AnalysisAssign(BaseModel):
    patient_id: int


class AnalysesAssign(BaseModel):
    ids: List[int]
    patient_id: int


class OCRResult(BaseModel):
    patient_name: str
    analysis_date: str
    study_type: str
    conclusion: Optional[str] = None
    results: List[ResultBase]
