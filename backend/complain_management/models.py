import uuid
from datetime import date, datetime
from enum import Enum

import sqlalchemy.dialects.postgresql as pg
from sqlalchemy import Column, Date, Enum as SQLEnum, String, Text
from sqlalchemy.sql import func
from sqlmodel import Field, SQLModel


class ComplaintSource(str, Enum):
    EMAIL = "Email"
    PHONE = "Phone"
    WEB_PORTAL = "Web Portal"
    DIRECT_MAIL = "Direct Mail"


class ComplaintType(str, Enum):
    PACKAGING_DEFECT = "Packaging Defect"
    PRODUCT_QUALITY = "Product Quality"
    ADVERSE_EVENT = "Adverse Event"
    LABELING_ISSUE = "Labeling Issue"
    LOGISTICS = "Logistics"


class Severity(str, Enum):
    CRITICAL = "Critical"
    MAJOR = "Major"
    MINOR = "Minor"


class Priority(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class Complaint(SQLModel, table=True):
    __tablename__ = "complaints"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(
            pg.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
    )

    complaint_source: ComplaintSource = Field(
        sa_column=Column(
            SQLEnum(ComplaintSource, name="complaint_source_enum"),
            nullable=False,
        )
    )

    customer_name: str = Field(
        sa_column=Column(
            String(255),
            nullable=False,
            index=True,
        )
    )

    product_name: str = Field(
        sa_column=Column(
            String(255),
            nullable=False,
            index=True,
        )
    )

    product_strength: str | None = Field(
        default=None,
        sa_column=Column(
            String(100),
        ),
    )

    batch_number: str | None = Field(
        default=None,
        sa_column=Column(
            String(100),
            index=True,
        ),
    )

    manufacturing_date: date | None = Field(
        default=None,
        sa_column=Column(Date),
    )

    expiry_date: date | None = Field(
        default=None,
        sa_column=Column(Date),
    )

    quantity_affected: str | None = Field(
        default=None,
        sa_column=Column(
            String(50),
        ),
    )

    complaint_type: ComplaintType = Field(
        sa_column=Column(
            SQLEnum(ComplaintType, name="complaint_type_enum"),
            nullable=False,
        )
    )

    complaint_date: date | None = Field(
        default=None,
        sa_column=Column(
            Date,
            index=True,
        ),
    )

    complaint_description: str | None = Field(
        default=None,
        sa_column=Column(
            Text,
        ),
    )

    initial_severity: Severity = Field(
        sa_column=Column(
            SQLEnum(Severity, name="severity_enum"),
            nullable=False,
        )
    )

    priority: Priority = Field(
        sa_column=Column(
            SQLEnum(Priority, name="priority_enum"),
            nullable=False,
        )
    )

    created_at: datetime = Field(
        sa_column=Column(
            pg.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=func.now(),
        )
    )

    updated_at: datetime = Field(
        sa_column=Column(
            pg.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        )
    )

    def __repr__(self):
        return (
            f"<Complaint(id={self.id}, "
            f"customer='{self.customer_name}', "
            f"product='{self.product_name}')>"
        )