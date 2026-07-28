import asyncio
import io
import json
import re
import uuid
from pathlib import Path
from typing import Literal, TypedDict

from fastapi import HTTPException, status
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph
from pypdf import PdfReader
from sqlalchemy import select
from supabase import create_client

from backend.config import Config
from backend.database import async_session_local
from backend.complain_management.models import Complaint, RiskAssessment
from .schemas import (
    ComplaintCreate,
    ComplaintDraft,
    ComplaintExtractionResponse,
    RiskAssessmentCreate,
    RiskAssessmentRead,
)


class ComplaintInputState(TypedDict):
    raw_text: str | None
    file_bytes: bytes | None
    file_name: str | None
    extracted_text: str
    storage_path: str | None
    complaint: dict
    current_complaint: dict | None
    intent: str | None


def get_llm() -> ChatGroq:
    return ChatGroq(
        model=Config.GROQ_MODEL,
        api_key=Config.GROQ_API_KEY,
        temperature=0,
    )

def normalize_text(value: str | None) -> str:
    if not value:
        return ""

    return re.sub(r"\s+", " ", value.strip().lower())


def is_similar_text(a: str | None, b: str | None) -> bool:
    a_norm = normalize_text(a)
    b_norm = normalize_text(b)

    if not a_norm or not b_norm:
        return False

    return a_norm in b_norm or b_norm in a_norm


def choose_input(state: ComplaintInputState) -> Literal["pdf", "text"]:
    if state["file_bytes"] is not None:
        return "pdf"

    return "text"


def choose_intent(state: ComplaintInputState) -> Literal["extract", "update"]:
    current_complaint = state.get("current_complaint") or {}
    has_existing_complaint = any(
        (value not in (None, ""))
        for value in current_complaint.values()
    )

    if (
        has_existing_complaint
        and state.get("file_bytes") is None
        and (state.get("raw_text") or "").strip()
    ):
        return "update"

    return "extract"


def extract_pdf_text(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))

    text = "\n".join(
        page.extract_text() or ""
        for page in reader.pages
    ).strip()

    if not text:
        raise ValueError(
            "No text could be extracted from this PDF. "
            "It may be a scanned image PDF and need OCR."
        )

    return text


def upload_pdf_to_supabase(file_bytes: bytes, file_name: str) -> str:
    supabase = create_client(
        Config.SUPABASE_URL,
        Config.SUPABASE_SERVICE_ROLE_KEY,
    )

    safe_file_name = Path(file_name).name
    storage_path = f"complaints/{uuid.uuid4()}-{safe_file_name}"

    supabase.storage.from_(Config.SUPABASE_BUCKET).upload(
        path=storage_path,
        file=file_bytes,
        file_options={
            "content-type": "application/pdf",
            "upsert": "false",
        },
    )

    return storage_path


async def is_duplicate_complaint(complaint_data: ComplaintCreate) -> bool:
    async with async_session_local() as session:
        statement = select(Complaint)

        if complaint_data.batch_number:
            statement = statement.where(Complaint.batch_number == complaint_data.batch_number)
        else:
            # no batch number to anchor on — fall back to product name only
            statement = statement.where(Complaint.product_name == complaint_data.product_name)

        result = await session.execute(statement)
        existing_complaints = result.scalars().all()

        for existing in existing_complaints:
            same_customer = is_similar_text(complaint_data.customer_name, existing.customer_name)
            same_product = is_similar_text(complaint_data.product_name, existing.product_name)

            if not (same_customer and same_product):
                continue

            if complaint_data.batch_number and existing.batch_number == complaint_data.batch_number:
                return True

            if complaint_data.complaint_description and is_similar_text(
                complaint_data.complaint_description,
                existing.complaint_description,
            ):
                return True

        return False


async def create_complaint(complaint_data: ComplaintCreate) -> Complaint:
    is_duplicate = await is_duplicate_complaint(complaint_data)

    if is_duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate complaint detected.",
        )

    complaint = Complaint(**complaint_data.model_dump())

    async with async_session_local() as session:
        session.add(complaint)
        await session.commit()
        await session.refresh(complaint)

    return complaint


async def create_risk_assessment(
    risk_data: RiskAssessmentCreate,
    complaint_id: uuid.UUID | None = None,
    risk_assessment_id: uuid.UUID | None = None,
) -> RiskAssessment:
    if complaint_id is not None:
        risk_data = risk_data.model_copy(update={"complaint_id": complaint_id})

    async with async_session_local() as session:
        if complaint_id is not None:
            existing_statement = select(RiskAssessment).where(
                RiskAssessment.complaint_id == complaint_id
            )
            existing_result = await session.execute(existing_statement)
            existing_ra = existing_result.scalar_one_or_none()

            if existing_ra is not None:
                for key, value in risk_data.model_dump().items():
                    setattr(existing_ra, key, value)

                session.add(existing_ra)
                await session.commit()
                await session.refresh(existing_ra)
                return existing_ra

        if risk_assessment_id is not None:
            statement = select(RiskAssessment).where(RiskAssessment.id == risk_assessment_id)
            result = await session.execute(statement)
            ra = result.scalar_one_or_none()

            if ra is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Risk assessment not found.",
                )

            for key, value in risk_data.model_dump().items():
                setattr(ra, key, value)

            session.add(ra)
            await session.commit()
            await session.refresh(ra)
            return ra

        ra = RiskAssessment(**risk_data.model_dump())
        session.add(ra)
        await session.commit()
        await session.refresh(ra)
        return ra


#Graph Nodes
async def extract_pdf_text_node(state: ComplaintInputState):
    extracted_text = await asyncio.to_thread(
        extract_pdf_text,
        state["file_bytes"],
    )

    return {"extracted_text": extracted_text}


async def store_pdf_node(state: ComplaintInputState):
    storage_path = await asyncio.to_thread(
        upload_pdf_to_supabase,
        state["file_bytes"],
        state["file_name"] or "complaint.pdf",
    )

    return {"storage_path": storage_path}


def prepare_text_node(state: ComplaintInputState):
    return {
        "extracted_text": state["raw_text"] or "",
        "storage_path": None,
    }


async def extract_complaint_node(state: ComplaintInputState):
    parser = JsonOutputParser(pydantic_object=ComplaintDraft)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
                You are an AI assistant that extracts structured complaint information for a Pharmaceutical Quality Management System (QMS).

                Your goal is to populate a complaint form from emails, letters, PDFs, scanned documents, phone call notes, web portal submissions, and free-form text.

                Return ONLY valid JSON matching the required schema.

                GENERAL RULES

                - Extract factual information from the document.
                - When appropriate, classify information based on context.
                - Never fabricate factual details.
                - If a field cannot reasonably be determined, return null.
                - Convert dates to YYYY-MM-DD whenever possible.
                - Ignore signatures, disclaimers, email footers and unrelated text.

                ----------------------------------------------------
                FIELD DEFINITIONS
                ----------------------------------------------------

                complaint_source

                Determine HOW the complaint was received.

                Allowed values:

                - Email
                - Phone
                - Web Portal
                - Direct Mail

                Determine this from context.

                Examples:

                Email
                - email headers (From:, To:, Subject:)
                - "emailed"
                - "received an email"
                - "customer emailed us"
                - email addresses in an email layout

                Phone
                - "called"
                - "phone call"
                - "telephonic complaint"
                - "customer contacted us by phone"

                Web Portal
                - "submitted through portal"
                - "portal complaint"
                - "ticket"
                - "case created online"

                Direct Mail
                - business letters
                - printed letters
                - company letterhead
                - "Dear Quality Team"
                - signed formal letter
                - PDFs that are clearly formal letters

                If none can be inferred, return null.

                ----------------------------------------------------

                customer_name

                The company or individual reporting the complaint.

                Rules:

                - Prefer the sender company.
                - If company and employee name both exist, choose the company.
                - Never choose the manufacturer receiving the complaint.

                Examples:

                ABC Pharma Pvt Ltd → customer_name

                Rahul Sharma
                ABC Pharma Pvt Ltd

                → customer_name = ABC Pharma Pvt Ltd

                ----------------------------------------------------

                product_name

                Commercial product name.

                ----------------------------------------------------

                product_strength

                Dosage or grade.

                Examples

                500 mg
                250 mg/5 mL
                USP Grade

                ----------------------------------------------------

                batch_number

                Manufacturing batch or lot number.

                ----------------------------------------------------

                manufacturing_date

                Manufacturing date.

                ----------------------------------------------------

                expiry_date

                Expiry date.

                ----------------------------------------------------

                quantity_affected

                Amount affected.

                Examples

                15 bottles

                4 cartons

                12 blister packs

                ----------------------------------------------------

                complaint_type

                Classify the complaint into ONE of:

                Packaging Defect
                Product Quality
                Adverse Event
                Labeling Issue
                Logistics

                Classification Guide

                Packaging Defect

                Examples

                broken blister
                seal failure
                damaged bottle
                container leak
                cap missing
                packaging torn
                foil peeled

                Product Quality

                Examples

                broken tablet
                discoloration
                foreign particles
                odor
                wrong hardness
                dissolution issue
                incorrect appearance
                powder clumping

                Adverse Event

                Examples

                patient experienced
                side effect
                hospitalization
                rash
                vomiting
                allergic reaction
                injury
                death

                Labeling Issue

                Examples

                wrong label
                incorrect expiry
                missing batch number
                incorrect leaflet
                printing error
                mislabelled strength

                Logistics

                Examples

                late delivery
                damaged during transport
                missing shipment
                temperature excursion
                wrong quantity delivered

                Return ONLY one enum.

                ----------------------------------------------------

                complaint_date

                Date complaint was made.

                If multiple dates exist, use the complaint submission date.

                ----------------------------------------------------

                complaint_description

                Summarize the reported complaint in 1–3 sentences while preserving the meaning.

                ----------------------------------------------------

                initial_severity

                Classify into:

                Critical
                Major
                Minor

                Guidelines

                Critical

                Patient safety risk

                Contamination

                Sterility failure

                Wrong medicine

                Wrong active ingredient

                Life-threatening adverse event

                Major

                Packaging defect

                Broken tablets

                Seal failure

                Incorrect labeling

                Missing tablets

                Quality issue affecting usability

                Minor

                Cosmetic defects

                Damaged outer carton

                Typographical issues

                Minor printing defects

                ----------------------------------------------------

                priority

                Classify into:

                High
                Medium
                Low

                Guidelines

                High

                Potential recall

                Patient impact

                Critical quality issue

                Urgent investigation required

                Medium

                Routine quality investigation

                No immediate patient impact

                Low

                Cosmetic issue

                Documentation issue

                Administrative issue

                ----------------------------------------------------

                IMPORTANT

                - Your output MUST strictly follow the JSON schema below.
                - Do not include markdown.
                - Do not include explanations.
                - Do not include extra keys.
                - Return only valid JSON.

                {format_instructions}
                """,
            ),
            (
                "user",
                "{extracted_text}",
            ),
        ]
    )

    chain = prompt | get_llm() | parser

    result = await chain.ainvoke(
        {
            "extracted_text": state["extracted_text"],
            "format_instructions": parser.get_format_instructions(),
        }
    )

    complaint = ComplaintDraft.model_validate(result)

    return {"complaint": complaint.model_dump()}


async def update_complaint_node(state: ComplaintInputState):
    parser = JsonOutputParser(pydantic_object=ComplaintDraft)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
                You are updating an existing complaint record for a Pharmaceutical Quality Management System (QMS).

                Treat the current complaint as the source of truth.
                Update ONLY the fields explicitly modified by the user.
                Preserve every other field exactly as it is.
                Never overwrite existing values with null unless the user explicitly asks to clear a field.
                Never invent information.
                If the user message is unrelated, return the complaint unchanged.

                Return ONLY valid JSON matching the required schema.
                """,
            ),
            (
                "user",
                "Current complaint:\n{current_complaint}\n\nUser message:\n{user_message}\n\nReturn the full complaint object with all fields.",
            ),
        ]
    )

    chain = prompt | get_llm() | parser

    result = await chain.ainvoke(
        {
            "current_complaint": json.dumps(state.get("current_complaint") or {}, default=str),
            "user_message": state["raw_text"] or "",
            "format_instructions": parser.get_format_instructions(),
        }
    )

    complaint = ComplaintDraft.model_validate(result)
    updated_complaint = complaint.model_dump()
    current_complaint = state.get("current_complaint") or {}

    for field in ComplaintExtractionResponse.model_fields.keys():
        if updated_complaint.get(field) in (None, ""):
            updated_complaint[field] = current_complaint.get(field)

    return {"complaint": updated_complaint}


async def summarize_risk_assessment(complaint: dict,) -> RiskAssessmentCreate:

    parser = JsonOutputParser(pydantic_object=RiskAssessmentCreate)

    prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
                    You are an AI assistant that summarizes a customer complaint and provides a brief initial risk assessment for a Pharmaceutical QMS.
    
                    Return ONLY valid JSON matching the schema below.
    
                    Fields:
                    - complaint_summary: A 1-3 sentence summary of the complaint.
                    - severity_suggested: One of Critical, Major, Minor (or null if unknown).
                    - suggested_next_action: Short recommended next action.
                    - initial_risk_assessment: One-paragraph initial risk assessment.
    
                    Do not invent facts. Base the summary on the provided complaint data.
                    """,
                ),
                (
                    "user",
                    "Complaint data:\n{complaint_json}\n\nReturn the JSON matching the schema. {format_instructions}",
                ),
            ]
        )
    
    chain = prompt | get_llm() | parser
    
    result = await chain.ainvoke(
        {
            "complaint_json": json.dumps(complaint, default=str),
            "format_instructions": parser.get_format_instructions(),
        }
    )

    return RiskAssessmentCreate.model_validate(result)

async def assess_risk_node(state: ComplaintInputState):
    complaint = state.get("complaint") or {}

    try:
        ra = await summarize_risk_assessment(complaint)
        return {"risk_assessment": ra.model_dump()}
    except Exception:
        return {"risk_assessment": None}


builder = StateGraph(ComplaintInputState)

builder.add_node("decide_intent", lambda state: {"intent": choose_intent(state)})
builder.add_node("choose_input", lambda state: {})
builder.add_node("prepare_text", prepare_text_node)
builder.add_node("extract_pdf_text", extract_pdf_text_node)
builder.add_node("store_pdf", store_pdf_node)
builder.add_node("extract_complaint", extract_complaint_node)
builder.add_node("update_complaint", update_complaint_node)
builder.add_node("assess_risk", assess_risk_node)

builder.add_edge(START, "decide_intent")

builder.add_conditional_edges(
    "decide_intent",
    choose_intent,
    {
        "extract": "choose_input",
        "update": "update_complaint",
    },
)

builder.add_conditional_edges(
    "choose_input",
    choose_input,
    {
        "pdf": "extract_pdf_text",
        "text": "prepare_text",
    },
)

builder.add_edge("prepare_text", "extract_complaint")
builder.add_edge("extract_pdf_text", "store_pdf")
builder.add_edge("store_pdf", "extract_complaint")
builder.add_edge("extract_complaint", "assess_risk")
builder.add_edge("update_complaint", "assess_risk")
builder.add_edge("assess_risk", END)

complaint_graph = builder.compile()


async def extract_complaint_from_input(raw_text: str | None, file_bytes: bytes | None = None, file_name: str | None = None, current_complaint: dict | None = None) -> ComplaintExtractionResponse:
    result = await complaint_graph.ainvoke(
        {
            "raw_text": raw_text,
            "file_bytes": file_bytes,
            "file_name": file_name,
            "current_complaint": current_complaint,
        }
    )

    draft = ComplaintDraft.model_validate(result["complaint"])

    storage_path = result.get("storage_path")
    if storage_path is None and current_complaint:
        storage_path = current_complaint.get("storage_path")

    risk_assessment = result.get("risk_assessment")

    return ComplaintExtractionResponse(
        **draft.model_dump(),
        storage_path=storage_path,
        risk_assessment=risk_assessment,
    )
