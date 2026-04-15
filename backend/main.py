from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import Base, engine
from routers.audit import router as audit_router
from routers.auth import router as auth_router
from routers.candidates import router as candidates_router
from routers.governance import router as governance_router
from routers.inspection import router as inspection_router
from routers.mitigation import router as mitigation_router


app = FastAPI(title="FairLens AI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


@app.get("/")
def health_check():
    return {"status": "FairLens AI running"}


app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(audit_router, prefix="/audit", tags=["audit"])
app.include_router(candidates_router, tags=["candidates"])
app.include_router(mitigation_router, tags=["mitigation"])
app.include_router(inspection_router, tags=["inspection"])
app.include_router(governance_router, tags=["governance"])
