from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import Base, engine
from backend.routers import exports, imports, projects, records, validation


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="CodeFlow Review API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)


@app.get("/api/health")
def health(): return {"status": "ok", "product": "CodeFlow Review"}


app.include_router(projects.router, prefix="/api")
app.include_router(imports.router, prefix="/api")
app.include_router(records.router, prefix="/api")
app.include_router(validation.router, prefix="/api")
app.include_router(exports.router, prefix="/api")

