import uuid
from datetime import date, datetime

from pydantic import ConfigDict, Field
from sqlmodel import SQLModel

from .models import ComplaintSource, ComplaintType, Priority, Severity
import uuid


class ComplaintCreate(SQLModel):
    complaint_source: ComplaintSource
    customer_name: str
    product_name: str
    product_strength: str | None = None
    batch_number: str | None = None
    manufacturing_date: date | None = None
    expiry_date: date | None = None
    quantity_affected: str | None = None
    complaint_type: ComplaintType
    complaint_date: date | None = None
    complaint_description: str | None = None
    initial_severity: Severity
    priority: Priority


class ComplaintRead(ComplaintCreate):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
    
class ComplaintTextRequest(SQLModel):
    raw_text: str = Field(min_length=10)
    complaint_source: ComplaintSource = ComplaintSource.EMAIL
    
class ComplaintDraft(SQLModel):
    complaint_source: ComplaintSource | None = None
    customer_name: str | None = None
    product_name: str | None = None
    product_strength: str | None = None
    batch_number: str | None = None
    manufacturing_date: date | None = None
    expiry_date: date | None = None
    quantity_affected: str | None = None
    complaint_type: ComplaintType | None = None
    complaint_date: date | None = None
    complaint_description: str | None = None
    initial_severity: Severity | None = None
    priority: Priority | None = None
    
class ComplaintExtractionResponse(ComplaintDraft):
    storage_path: str | None = None
    risk_assessment: dict | None = None


class RiskAssessmentCreate(SQLModel):
    complaint_id: uuid.UUID | None = None
    complaint_summary: str | None = None
    severity_suggested: str | None = None
    suggested_next_action: str | None = None
    initial_risk_assessment: str | None = None


class RiskAssessmentRead(RiskAssessmentCreate):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
    
class ComplaintSaveRequest(ComplaintCreate):
    risk_assessment: RiskAssessmentCreate | None = None