# backend/complain_management/services.py

from backend.database import async_session_local
from .models import Complaint
from .schemas import ComplaintCreate


async def create_complaint(complaint_data: ComplaintCreate) -> Complaint:
    complaint = Complaint(**complaint_data.model_dump())

    async with async_session_local() as session:
        session.add(complaint)
        await session.commit()
        await session.refresh(complaint)

    return complaint