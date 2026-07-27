# backend/complain_management/router.py

import json

from fastapi import APIRouter, status, Form, HTTPException, UploadFile, File

from .schemas import (
    ComplaintCreate,
    ComplaintRead,
    ComplaintDraft,
    ComplaintSaveRequest,
    ComplaintTextRequest,
    ComplaintExtractionResponse,
    RiskAssessmentRead,
    RiskAssessmentCreate
)
from .services import (
    create_complaint,
    extract_complaint_from_input,
    summarize_and_create_risk_assessment,
    create_risk_assessment,
)

from typing import Annotated


router = APIRouter(
    prefix="/complaints",
    tags=["Complaints"],
)


MAX_PDF_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/extract", response_model=ComplaintExtractionResponse)
async def extract_complaint(raw_text: Annotated[str | None, Form()] = None, file: Annotated[UploadFile | None, File()] = None, current_complaint: Annotated[str | None, Form()] = None):
    current_complaint_data = None

    if current_complaint:
        try:
            current_complaint_data = json.loads(current_complaint)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid current complaint payload.",
            ) from exc

    if not raw_text and not file:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide pasted text or a PDF file.",
        )

    if raw_text and file:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide either pasted text or one PDF, not both.",
        )

    if file:
        file_name = file.filename or "complaint.pdf"

        if (
            file.content_type != "application/pdf"
            and not file_name.lower().endswith(".pdf")
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Only PDF files are accepted.",
            )

        file_bytes = await file.read()

        return await extract_complaint_from_input(
            raw_text=None,
            file_bytes=file_bytes,
            file_name=file_name,
            current_complaint=current_complaint_data,
        )

    return await extract_complaint_from_input(
        raw_text=raw_text,
        current_complaint=current_complaint_data,
    )
    
@router.post("/save", response_model=ComplaintRead, status_code=status.HTTP_201_CREATED)
async def add_complaint(complaint_data: ComplaintSaveRequest):
    complaint_payload = ComplaintCreate.model_validate(
        complaint_data.model_dump(exclude={"risk_assessment_id"})
    )

    complaint = await create_complaint(complaint_payload)

    if complaint_data.risk_assessment_id:
        await create_risk_assessment(
            RiskAssessmentCreate(complaint_id=complaint.id),
            complaint_id=complaint.id,
            risk_assessment_id=complaint_data.risk_assessment_id,
        )

    return complaint


@router.post("/assess", response_model=RiskAssessmentRead)
async def assess_complaint(complaint: ComplaintDraft):
    # Accept the extracted complaint draft and ask the LLM to summarize and assess risk
    return await summarize_and_create_risk_assessment(complaint.model_dump())