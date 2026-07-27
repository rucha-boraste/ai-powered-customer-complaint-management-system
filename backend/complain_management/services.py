from backend.database import async_session_local
from .models import Complaint
from .schemas import ComplaintCreate, ComplaintDraft, ComplaintTextRequest, ComplaintExtractionResponse

import asyncio
import io
import uuid
from pathlib import Path

from typing import TypedDict, Literal

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph

from pypdf import PdfReader
from supabase import create_client

from backend.config import Config
from backend.complain_management.models import ComplaintSource


class ComplaintInputState(TypedDict):
    raw_text: str | None
    file_bytes: bytes | None
    file_name: str | None
    extracted_text: str
    storage_path: str | None
    complaint: dict
    
def get_llm() -> ChatGroq:
    return ChatGroq(
        model=Config.GROQ_MODEL,
        api_key=Config.GROQ_API_KEY,
        temperature=0,
    )


def choose_input(state: ComplaintInputState) -> Literal["pdf", "text"]:
    if state["file_bytes"] is not None:
        return "pdf"
    
    return "text"


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


async def extract_pdf_text_node(state: ComplaintInputState):
    extracted_text = await asyncio.to_thread(
        extract_pdf_text,
        state["file_bytes"],
    )
    
    return {"extracted_text": extracted_text}

def upload_pdf_to_supabase(file_bytes: bytes, file_name: str) -> str:
    supabase = create_client(
        Config.SUPABASE_URL,
        Config.SUPABASE_SERVICE_ROLE_KEY,
    )
    
    safe_file_name = Path(file_name).name

    storage_path = (
        f"complaints/{uuid.uuid4()}-{safe_file_name}"
    )

    supabase.storage.from_(Config.SUPABASE_BUCKET).upload(
        path=storage_path,
        file=file_bytes,
        file_options={
            "content-type": "application/pdf",
            "upsert": "false",
        },
    )

    return storage_path

async def store_pdf_node(state: ComplaintInputState):
    storage_path = await asyncio.to_thread(
        upload_pdf_to_supabase,
        state["file_bytes"],
        state["file_name"] or "complaint.pdf",
    )

    return {"storage_path": storage_path}

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
                "{extracted_text}"
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


def prepare_text_node(state: ComplaintInputState):
    return {
        "extracted_text": state["raw_text"] or "",
        "storage_path": None,
    }
    
builder = StateGraph(ComplaintInputState)

builder.add_node("choose_input", lambda state: {})
builder.add_node("prepare_text", prepare_text_node)
builder.add_node("extract_pdf_text", extract_pdf_text_node)
builder.add_node("store_pdf", store_pdf_node)
builder.add_node("extract_complaint", extract_complaint_node)

builder.add_edge(START, "choose_input")

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
builder.add_edge("extract_complaint", END)

complaint_graph = builder.compile()


async def extract_complaint_from_input(raw_text: str | None, file_bytes: bytes | None = None, file_name: str | None = None,) -> ComplaintExtractionResponse:
    result = await complaint_graph.ainvoke(
        {
            "raw_text": raw_text,
            "file_bytes": file_bytes,
            "file_name": file_name,
        }
    )

    draft = ComplaintDraft.model_validate(result["complaint"])

    return ComplaintExtractionResponse(
        **draft.model_dump(),
        storage_path=result.get("storage_path"),
    )



async def create_complaint(complaint_data: ComplaintCreate) -> Complaint:
    complaint = Complaint(**complaint_data.model_dump())

    async with async_session_local() as session:
        session.add(complaint)
        await session.commit()
        await session.refresh(complaint)

    return complaint