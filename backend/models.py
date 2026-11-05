from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(Date, nullable=False)

    analyses = relationship("Analysis", back_populates="patient", cascade="all, delete-orphan")


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    analysis_date = Column(Date, nullable=False)
    study_type = Column(String(255), nullable=False)
    conclusion = Column(Text, nullable=True)
    pdf_filename = Column(String(255), nullable=True)
    parser = Column(String(50), nullable=True)

    patient = relationship("Patient", back_populates="analyses")
    results = relationship("Result", back_populates="analysis", cascade="all, delete-orphan")


class Result(Base):
    __tablename__ = "results"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("analyses.id"), nullable=False)
    test_name = Column(String(255), nullable=False)
    result_value = Column(Float, nullable=True)
    result_text = Column(String(255), nullable=True)
    reference_min = Column(Float, nullable=True)
    reference_max = Column(Float, nullable=True)
    reference_text = Column(String(255), nullable=True)
    unit = Column(String(100), nullable=True)
    is_abnormal = Column(Integer, default=0)

    analysis = relationship("Analysis", back_populates="results")
