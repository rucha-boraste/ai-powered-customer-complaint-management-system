from fastapi import FastAPI
from .database import initdb
from contextlib import asynccontextmanager
from .complain_management.router import router
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Server is Starting")
    await initdb()
    yield
    print("Server is stopping")

app = FastAPI(
    lifespan=lifespan
)

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_VERSION = "/api/v1"

app.include_router(router, prefix=API_VERSION)

@app.get("/")
async def root():
    return{
        "message" :"Backend is working fine!"
    }