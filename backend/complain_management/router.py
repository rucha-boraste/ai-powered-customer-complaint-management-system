# backend/complain_management/router.py

from fastapi import APIRouter, status, Form, HTTPException, UploadFile, File

from .schemas import ComplaintCreate, ComplaintRead, ComplaintDraft, ComplaintTextRequest, ComplaintExtractionResponse
from .services import create_complaint, extract_complaint_from_input

from typing import Annotated


router = APIRouter(
    prefix="/complaints",
    tags=["Complaints"],
)


MAX_PDF_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/extract", response_model=ComplaintExtractionResponse)
async def extract_complaint(raw_text: Annotated[str | None, Form()] = None,file: Annotated[UploadFile | None, File()] = None,):
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
        )

    return await extract_complaint_from_input(
        raw_text=raw_text,
    )
    
@router.post("/", response_model=ComplaintRead, status_code=status.HTTP_201_CREATED)
async def add_complaint(complaint_data: ComplaintCreate):
    return await create_complaint(complaint_data)