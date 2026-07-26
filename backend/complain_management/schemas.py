# backend/complain_management/schemas.py

import uuid
from datetime import date, datetime

from pydantic import ConfigDict
from sqlmodel import SQLModel

from .models import ComplaintSource, ComplaintType, Priority, Severity


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