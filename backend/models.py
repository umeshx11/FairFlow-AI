import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    organization = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    audits = relationship("Audit", back_populates="user", cascade="all, delete-orphan")


class Audit(Base):
    __tablename__ = "audits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    dataset_name = Column(String(255), nullable=False)
    total_candidates = Column(Integer, nullable=False)
    disparate_impact = Column(Float, nullable=False)
    stat_parity_diff = Column(Float, nullable=False)
    equal_opp_diff = Column(Float, nullable=False)
    avg_odds_diff = Column(Float, nullable=False)
    bias_detected = Column(Boolean, nullable=False, default=False)
    mitigation_applied = Column(Boolean, nullable=False, default=False)
    mitigation_results = Column(JSON, nullable=True)

    user = relationship("User", back_populates="audits")
    candidates = relationship("Candidate", back_populates="audit", cascade="all, delete-orphan")
    memories = relationship("AuditMemory", back_populates="audit", cascade="all, delete-orphan")
    certificates = relationship("AuditCertificate", back_populates="audit", cascade="all, delete-orphan")


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audit_id = Column(UUID(as_uuid=True), ForeignKey("audits.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    gender = Column(String(64), nullable=False, index=True)
    ethnicity = Column(String(128), nullable=False, index=True)
    age = Column(Integer, nullable=False)
    years_experience = Column(Float, nullable=False)
    education_level = Column(String(128), nullable=False)
    original_decision = Column(Boolean, nullable=False)
    mitigated_decision = Column(Boolean, nullable=True)
    bias_flagged = Column(Boolean, nullable=False, default=False, index=True)
    shap_values = Column(JSON, nullable=True)
    counterfactual_result = Column(JSON, nullable=True)
    feature_payload = Column(JSON, nullable=False, default=dict)
    skills = Column(Text, nullable=True)
    previous_companies = Column(Text, nullable=True)

    audit = relationship("Audit", back_populates="candidates")


class AuditMemory(Base):
    __tablename__ = "audit_memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    audit_id = Column(UUID(as_uuid=True), ForeignKey("audits.id"), nullable=True, index=True)
    stage = Column(String(64), nullable=False, index=True)
    memory_text = Column(Text, nullable=False)
    vector = Column(JSON, nullable=False, default=list)
    memory_metadata = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    audit = relationship("Audit", back_populates="memories")


class AuditCertificate(Base):
    __tablename__ = "audit_certificates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audit_id = Column(UUID(as_uuid=True), ForeignKey("audits.id"), nullable=False, index=True)
    hash_algorithm = Column(String(32), nullable=False, default="sha256")
    report_hash = Column(String(128), nullable=False, index=True)
    epsilon = Column(Float, nullable=False, default=1.0)
    payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    audit = relationship("Audit", back_populates="certificates")
