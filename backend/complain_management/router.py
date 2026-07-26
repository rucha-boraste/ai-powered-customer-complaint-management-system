# backend/complain_management/router.py

from fastapi import APIRouter, status

from .schemas import ComplaintCreate, ComplaintRead
from .services import create_complaint

router = APIRouter(
    prefix="/complaints",
    tags=["Complaints"],
)


@router.post("/", response_model=ComplaintRead, status_code=status.HTTP_201_CREATED)
async def add_complaint(complaint_data: ComplaintCreate):
    return await create_complaint(complaint_data)