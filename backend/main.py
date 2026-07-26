from fastapi import FastAPI
from .database import initdb
from contextlib import asynccontextmanager
from .complain_management.router import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Server is Starting")
    await initdb()
    yield
    print("Server is stopping")

app = FastAPI(
    lifespan=lifespan
)

API_VERSION = "/api/v1"

app.include_router(router, prefix=API_VERSION)

@app.get("/")
async def root():
    return{
        "message" :"Backend is working fine!"
    }